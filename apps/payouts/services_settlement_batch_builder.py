"""
Payouts — Settlement Batch Builder (Sprint 4 — Settlement Engine, Phase B,
Step 3).

Converts eligible SettlementPlanner results into real SettlementBatch and
SettlementItem records, per the approved Phase A design:
  docs/13_Financial_Core/target_architecture/13_SETTLEMENT_NETTING_ENGINE.md

and the approved Phase A Concurrency Strategy ADR (company-level
select_for_update() lock on CompanyFinancialPolicy, held for the entire
build transaction).

SCOPE (Step 3 only):
  - Creates SettlementBatch and SettlementItem rows (this is the first
    Sprint 4 step that writes to the database).
  - Advances EscrowRecord DISTRIBUTED -> PENDING_SETTLEMENT via the
    already-merged, unmodified EscrowRecordService.mark_pending_settlement()
    (Sprint 2, previously uncalled by any production code).
  - Marks the created batch READY via SettlementBatchService.mark_ready()
    (Sprint 2, unmodified).
  - Does NOT execute settlement: never calls mark_executing()/
    mark_completed()/mark_failed(). Never records a bank_reference.
    Never creates a TechnicianLedgerEntry or CompanyPlatformFeeEntry
    "settlement completion" entry.
  - Does NOT call any external API, bank transfer, refund execution, UI,
    API endpoint, management command, or background job.
  - Delegates every eligibility decision to SettlementPlanner (Step 2,
    unmodified) and every amount to SettlementCalculator (Step 1,
    unmodified) — this module never independently decides eligibility or
    recomputes an amount.

CONCURRENCY (per the approved ADR):
  select_for_update() is acquired on the company's CompanyFinancialPolicy
  row (a OneToOneField to Company that already exists before any
  settlement activity begins, per apps/tenants/models.py) and held for
  the ENTIRE build operation — from before the Planner is even invoked,
  through every SettlementItem creation, through mark_ready(). This is a
  single, company-wide lock covering BOTH Layer 1 and Layer 2 (per the
  approved ADR's explicit granularity decision: coarser than
  per-(company, level), because Sprint 4's actual write pattern does not
  require finer granularity, and the ADR explicitly confirms this
  internal choice can change later without touching this module's public
  API).

  If CompanyFinancialPolicy does not exist for the company yet, one is
  created with platform-default values as part of acquiring the lock —
  a company with no configured policy must still be lockable (e.g. a
  brand-new company with zero invoices). This get-or-create is the ONLY
  write in this module that is not itself part of building the batch —
  documented here explicitly rather than treated as an implicit side
  effect.

TRANSACTION BOUNDARIES:
  The entire build_layer1_batch() / build_layer2_batch() call is one
  @transaction.atomic block. If anything fails partway (e.g. an item
  creation raises), the whole operation rolls back: no batch, no items,
  no escrow transition persists. This matches the "correctness over
  throughput" instruction explicitly — a long-held lock for the full
  duration of one company's settlement build is an accepted cost.

IDEMPOTENCY / DUPLICATE PREVENTION:
  Running either build method twice in a row for the same company/period
  cannot duplicate active SettlementItems, because:
    1. The company-level lock serializes any two calls for the same
       company (the second call blocks until the first commits).
    2. SettlementPlanner's own eligibility queries (unmodified, Step 2)
       already exclude invoices/ledger entries claimed by a non-FAILED
       SettlementItem, or an invoice whose EscrowRecord.settlement_batch
       already links a non-FAILED batch. By the time a second call's
       Planner step runs, every item the first call claimed is no
       longer eligible, so the second call naturally builds a batch
       containing none of those items.
  This is "idempotency by natural exhaustion of eligible input" — the
  same mechanism SettlementPlanner itself documents and relies on; this
  module introduces no second, independent idempotency mechanism (e.g.
  a deterministic batch key), because the exclusion mechanism alone is
  sufficient given that all writes happen under the company lock.

  Layer 2 specifically: SettlementPlanner's "already claimed" check
  (`SettlementItem.objects.filter(ledger_entry__technician=technician)
  .exclude(batch__status=FAILED).exists()`) only requires ONE
  SettlementItem referencing ANY ONE of a technician's ledger entries in
  a non-FAILED batch to exclude that technician on future runs. This
  Builder therefore creates exactly ONE SettlementItem per eligible
  technician (referencing their most recent ledger entry, carrying the
  full net payable amount) rather than one item per ledger entry — this
  is the minimal write that satisfies the Planner's exclusion query
  while keeping Σ SettlementItem.amount_rial == batch.net_amount_rial
  exact. If this batch later fails, that one item's batch becomes
  FAILED, so the exclusion query above returns nothing for this
  technician and their entire ledger balance is correctly released back
  to eligibility on the next run — one item is sufficient for both the
  exclusion and the release behavior.

EMPTY-BATCH-DISCARD RULE:
  If SettlementPlanner reports zero eligible items for a company/period,
  no SettlementBatch row is created at all — matching the explicit
  instruction "If no eligible items exist, do not create an empty READY
  batch unless explicitly justified." No such justification exists in
  this step's scope, so the simplest, safest behavior (create nothing)
  is chosen.

DATA INTEGRITY:
  - Batch totals (net_amount_rial, total_credits, total_debits,
    items_count) are computed by summing the SettlementItem rows this
    module itself just created inside the same transaction, then
    re-verified against a fresh SUM() query before mark_ready() is ever
    called — never estimated, never trusted without a second check.
  - Every SettlementItem created by this module has `company` set to
    the batch's own company (enforced by SettlementItemService itself,
    which always uses `locked_batch.company` — never overridden here).
  - period_start < period_end is validated explicitly before any write.
  - A RECEIVABLE (Layer 1) or non-PAYABLE (Layer 2) planner result is
    never turned into a payable SettlementItem — SettlementPlanner
    already excludes these from eligible_items, and this module adds a
    second, defensive check before ever writing an item, rather than
    trusting the Planner's bucketing alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.db.models import Sum

from .exceptions import SettlementError
from .services_escrow import EscrowRecordService
from .services_settlement_batch import SettlementBatchService, SettlementItemService
from .services_settlement_calculator import SettlementPosition
from .services_settlement_planner import SettlementPlanner


class SettlementBatchBuilderError(SettlementError):
    """Raised for a data-integrity violation detected before/after writes."""


@dataclass(frozen=True)
class BatchBuildResult:
    """
    Result of a build_layer1_batch() / build_layer2_batch() call.

    `batch` is None when the empty-batch-discard rule applied (no
    eligible items were found) — this is a normal, non-error outcome,
    not a failure.
    """

    batch: Optional[object]  # SettlementBatch instance, or None
    items_created: int
    net_amount_rial: int
    total_credits: int
    total_debits: int


def _lock_company_financial_policy(company) -> None:
    """
    Acquire the company-level settlement lock, per the approved
    Concurrency Strategy ADR: select_for_update() on the company's
    CompanyFinancialPolicy row, get-or-create'd with platform defaults
    if it does not exist yet.

    The row itself is not read for any value by this module — only its
    lock matters here.
    """
    from apps.tenants.models import CompanyFinancialPolicy

    # get_or_create's own internal SELECT/INSERT is not itself protected
    # by select_for_update (Django cannot lock a row that may not exist
    # yet) — the subsequent select_for_update().get() immediately below
    # closes that window by re-fetching and locking the row under the
    # current transaction before any batch-building work begins. A
    # benign race here (two concurrent callers both attempting
    # get_or_create for a brand-new company) can only ever result in
    # exactly one row, per Django's documented get_or_create() behavior.
    CompanyFinancialPolicy.objects.get_or_create(company=company)
    CompanyFinancialPolicy.objects.select_for_update().get(company=company)


def _validate_period(period_start, period_end) -> None:
    if period_start >= period_end:
        raise SettlementBatchBuilderError(
            f"period_start ({period_start}) must be before period_end "
            f"({period_end})."
        )


def _assert_batch_totals_match_items(batch) -> None:
    from .models import SettlementItem

    total = SettlementItem.objects.filter(batch=batch).aggregate(
        total=Sum("amount_rial"),
    )["total"] or 0
    if total != batch.net_amount_rial:
        raise SettlementBatchBuilderError(
            f"SettlementBatch #{batch.pk}: sum of SettlementItem.amount_rial "
            f"({total}) does not equal batch.net_amount_rial "
            f"({batch.net_amount_rial})."
        )


class SettlementBatchBuilder:
    """
    Converts SettlementPlanner eligibility results into real
    SettlementBatch / SettlementItem records.

    Every public method is wrapped in @transaction.atomic and begins by
    acquiring the company-level lock, per the approved ADR. Neither
    method ever calls mark_executing(), mark_completed(), or
    mark_failed() — batches built here are left in READY status (or are
    never created at all, if nothing was eligible), awaiting a future,
    separate Execution step that this Sprint explicitly does not
    implement.
    """

    # ------------------------------------------------------------------
    # Layer 1 — Platform <-> Organization
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def build_layer1_batch(company, period_start, period_end, created_by=None) -> BatchBuildResult:
        from apps.invoices.models import Invoice
        from .models import EscrowRecord, SettlementBatch

        _validate_period(period_start, period_end)
        _lock_company_financial_policy(company)

        report = SettlementPlanner.plan_layer1_for_company(company)
        eligible = report.eligible_items

        if not eligible:
            return BatchBuildResult(
                batch=None, items_created=0, net_amount_rial=0,
                total_credits=0, total_debits=0,
            )

        batch = SettlementBatchService.create_batch(
            company=company,
            level=SettlementBatch.Level.PLATFORM_TO_ORG,
            period_start=period_start,
            period_end=period_end,
            created_by=created_by,
        )

        total_credits = 0
        total_debits = 0
        escrow_ids_to_advance: list[int] = []

        for item in eligible:
            calculation = item.calculation

            # Defensive re-checks (see module docstring's Data Integrity
            # section) — SettlementPlanner already guarantees both of
            # these hold for every eligible Layer 1 item, but this
            # module never trusts that guarantee silently.
            if calculation.position == SettlementPosition.RECEIVABLE:
                raise SettlementBatchBuilderError(
                    f"Invoice #{item.invoice_id}: Planner reported it as "
                    "eligible with a RECEIVABLE position — refusing to "
                    "create a payable SettlementItem for a negative amount."
                )
            if calculation.company_id != company.id:
                raise SettlementBatchBuilderError(
                    f"Invoice #{item.invoice_id}: calculation.company_id "
                    f"({calculation.company_id}) does not match the "
                    f"company being settled ({company.id})."
                )

            amount = calculation.net_position_rial
            if amount > 0:
                total_credits += amount
            elif amount < 0:
                total_debits += abs(amount)

            invoice = Invoice.objects.get(pk=item.invoice_id)
            SettlementItemService.add_invoice_item(
                batch,
                invoice,
                amount_rial=amount,
                description=(
                    f"Layer 1 settlement — invoice #{item.invoice_id}, "
                    f"escrow #{item.escrow_id}"
                ),
            )

            if item.escrow_id is not None:
                escrow_ids_to_advance.append(item.escrow_id)

        batch.net_amount_rial = total_credits - total_debits
        batch.total_credits = total_credits
        batch.total_debits = total_debits
        batch.items_count = len(eligible)
        batch.save(update_fields=[
            "net_amount_rial", "total_credits", "total_debits", "items_count", "updated_at",
        ])

        _assert_batch_totals_match_items(batch)

        batch = SettlementBatchService.mark_ready(batch)

        for escrow_id in escrow_ids_to_advance:
            escrow = EscrowRecord.objects.get(pk=escrow_id)
            EscrowRecordService.mark_pending_settlement(escrow, batch)

        return BatchBuildResult(
            batch=batch,
            items_created=len(eligible),
            net_amount_rial=batch.net_amount_rial,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    # ------------------------------------------------------------------
    # Layer 2 — Organization <-> Provider
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def build_layer2_batch(
        company, period_start, period_end, technician=None, created_by=None,
    ) -> BatchBuildResult:
        from .models import SettlementBatch, TechnicianLedgerEntry

        _validate_period(period_start, period_end)
        _lock_company_financial_policy(company)

        report = SettlementPlanner.plan_layer2_for_company(company, technician=technician)
        eligible = report.eligible_items

        if not eligible:
            return BatchBuildResult(
                batch=None, items_created=0, net_amount_rial=0,
                total_credits=0, total_debits=0,
            )

        batch = SettlementBatchService.create_batch(
            company=company,
            level=SettlementBatch.Level.ORG_TO_PROVIDER,
            period_start=period_start,
            period_end=period_end,
            created_by=created_by,
        )

        total_credits = 0
        total_debits = 0
        items_created = 0

        for item in eligible:
            calculation = item.calculation

            # Defensive re-checks — see module docstring's Data Integrity
            # section. SettlementPlanner already only buckets PAYABLE
            # technicians as eligible (ZERO -> "nothing to settle",
            # RECEIVABLE -> "owes the company" are both blocked_items).
            if calculation.position != SettlementPosition.PAYABLE:
                raise SettlementBatchBuilderError(
                    f"Technician #{item.technician_id}: Planner reported it "
                    f"as eligible with position '{calculation.position}' "
                    "(expected PAYABLE) — refusing to create a payable "
                    "SettlementItem."
                )
            if calculation.company_id != company.id:
                raise SettlementBatchBuilderError(
                    f"Technician #{item.technician_id}: calculation.company_id "
                    f"({calculation.company_id}) does not match the "
                    f"company being settled ({company.id})."
                )

            amount = calculation.net_position_rial  # always > 0, guaranteed above.
            total_credits += amount

            # One SettlementItem per technician, referencing their most
            # recent ledger entry, carrying the full net payable amount.
            # See the module docstring's Idempotency section for why one
            # item is sufficient (SettlementPlanner's exclusion query
            # only requires ANY ONE claimed entry to exclude the whole
            # technician on future runs).
            most_recent_entry = (
                TechnicianLedgerEntry.objects.filter(
                    company=company, technician_id=item.technician_id,
                )
                .order_by("-created_at", "-id")
                .first()
            )
            if most_recent_entry is None:
                # Cannot happen for a PAYABLE result (a positive balance
                # requires at least one CREDIT entry to exist), but
                # guarded explicitly rather than assumed.
                raise SettlementBatchBuilderError(
                    f"Technician #{item.technician_id}: reported PAYABLE "
                    "but has no TechnicianLedgerEntry rows at all."
                )

            SettlementItemService.add_ledger_item(
                batch,
                most_recent_entry,
                amount_rial=amount,
                description=(
                    f"Layer 2 settlement — technician #{item.technician_id} "
                    "net payable"
                ),
            )
            items_created += 1

        batch.net_amount_rial = total_credits - total_debits
        batch.total_credits = total_credits
        batch.total_debits = total_debits
        batch.items_count = items_created
        batch.save(update_fields=[
            "net_amount_rial", "total_credits", "total_debits", "items_count", "updated_at",
        ])

        _assert_batch_totals_match_items(batch)

        batch = SettlementBatchService.mark_ready(batch)

        return BatchBuildResult(
            batch=batch,
            items_created=items_created,
            net_amount_rial=batch.net_amount_rial,
            total_credits=total_credits,
            total_debits=total_debits,
        )
