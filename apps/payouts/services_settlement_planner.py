"""
Payouts — Settlement Planner (Sprint 4 — Settlement Engine, Phase B, Step 2).

Deterministic, read-only eligibility layer that decides which invoices
(Layer 1 — Platform <-> Organization) and technician ledger balances
(Layer 2 — Organization <-> Provider) are candidates for a future
SettlementBatch, per the approved Phase A design:
  docs/13_Financial_Core/target_architecture/13_SETTLEMENT_NETTING_ENGINE.md

SCOPE (Step 2 only — strictly eligibility decisions, nothing else):
  - Reads Invoice, EscrowRecord, PaymentSplitSnapshot,
    TechnicianLedgerEntry, CompanyPlatformFeeEntry, AdjustmentDocument,
    FinancialBackfillTask, SettlementBatch, SettlementItem.
  - NEVER writes to the database. No .save(), .create(), .update(),
    .delete() call exists anywhere in this module.
  - Does NOT create SettlementBatch or SettlementItem rows (that is the
    future Batch Builder's job, a separate step per the approved Phase A
    roadmap).
  - Does NOT execute any settlement, bank transfer, or refund.
  - Does NOT modify Invoice, Payment, EscrowRecord, Ledger, or Settlement
    state in any way.
  - Delegates every amount calculation to SettlementCalculator
    (services_settlement_calculator.py, Step 1, unmodified) — this module
    never independently recomputes a commission, wage, or balance figure.

CONCURRENCY:
  No lock is acquired anywhere in this module, for the same reason
  documented in services_settlement_calculator.py: every method here is a
  pure read returning an immutable dataclass. There is no read-then-write
  sequence for a lock to protect against. Verified by a dedicated test
  (`test_no_database_writes_occur_during_planning`).

WHY "INVOICE MUST BE PAID" IS CHECKED BEFORE DELEGATING TO THE CALCULATOR:
  SettlementCalculator.calculate_layer1_for_invoice() does not itself
  check Invoice.status (it only cares about EscrowRecord.status, per its
  own docstring). The Planner adds this as an explicit, first-priority
  gate, because a non-PAID invoice can never legitimately be a settlement
  candidate regardless of what its EscrowRecord looks like (an
  EscrowRecord existing before the invoice is PAID is itself only
  possible in test-constructed or failure-recovery scenarios — see
  apps/invoices/services.py reserve_and_distribute_escrow_for_invoice(),
  which is only ever called AFTER Invoice.status is already saved as
  PAID). Blocking on invoice status first, before ever calling the
  Calculator, keeps the two checks orthogonal and keeps the blocked
  reason unambiguous.

WHY "ALREADY BATCHED" IS TWO SEPARATE CHECKS FOR LAYER 1:
  Per the approved eligibility rules, both of the following must be
  checked independently, because Sprint 4 Step 2 introduces no Batch
  Builder yet and therefore no code path guarantees they are always kept
  in sync with each other by construction:
    1. EscrowRecord.settlement_batch is already set to a non-FAILED
       batch (this FK is set by EscrowRecordService.mark_pending_settlement(),
       a Sprint 2 method with no caller yet).
    2. A SettlementItem already references this invoice via a non-FAILED
       batch (set by SettlementItemService.add_invoice_item(), also a
       Sprint 2 method with no caller yet).
  A future Batch Builder is expected to always set both together, but
  this Planner checks both defensively rather than assuming that
  invariant holds, since checking is cheap and the cost of a bug here
  (double-settlement) is high.

WHY LAYER 2's "ALREADY CLAIMED" CHECK BLOCKS THE WHOLE TECHNICIAN, NOT A
PARTIAL BALANCE:
  SettlementCalculator.calculate_layer2_for_technician() computes an
  all-time running balance (credits minus every debit), matching
  TechnicianLedgerService.get_balance() exactly. If some — but not all —
  of a technician's ledger entries are already referenced by a
  non-FAILED SettlementItem, computing "how much of the remaining
  balance is genuinely unclaimed" would require a different aggregation
  than the Calculator provides (summing only the unclaimed subset), which
  is explicitly a Batch Builder concern, not this Planner's. To avoid
  ever reporting an eligible amount that could result in double-settling
  part of a technician's balance, this Planner conservatively blocks the
  ENTIRE technician for this planning cycle if ANY of their ledger
  entries are already claimed, rather than attempting a partial-subset
  recomputation the approved eligibility rules did not specify a formula
  for. This is a deliberate, disclosed simplification, not an oversight.

WHY THE FinancialBackfillTask CHECK FOR LAYER 2 IS INDIRECT:
  FinancialBackfillTask has no direct `technician` foreign key — it only
  references `invoice` and `payment` (apps/payouts/models.py). To check
  whether a technician has an "unresolved FinancialBackfillTask", this
  module looks for TECHNICIAN_LEDGER-type unresolved tasks whose
  `invoice` matches an invoice that already has at least one
  TechnicianLedgerEntry for that technician. This is a best-effort,
  clearly-documented traversal, not a claim that FinancialBackfillTask
  was ever designed to be technician-scoped.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .services_settlement_calculator import (
    Layer1SettlementResult,
    Layer2SettlementResult,
    SettlementCalculator,
    SettlementPosition,
)

# AdjustmentDocument statuses that represent a correction still "in flight"
# — not yet finalized (APPLIED/REJECTED/CANCELLED are all terminal and no
# longer represent an outstanding risk to a settlement calculation).
_PENDING_ADJUSTMENT_STATUSES = frozenset({"draft", "pending_approval", "approved"})

# FinancialBackfillTask statuses that represent a financial write that has
# not yet successfully completed. RESOLVED is the only "safe" status;
# PENDING/PROCESSING/FAILED all represent an unresolved risk that the
# underlying ledger/escrow/fee state this Planner is reading from may not
# yet be complete or correct.
_UNRESOLVED_BACKFILL_STATUSES = frozenset({"pending", "processing", "failed"})


@dataclass(frozen=True)
class Layer1PlanningItem:
    """
    One Invoice's eligibility decision for a future Layer 1 SettlementBatch.

    `calculation` is populated whenever SettlementCalculator was actually
    invoked (i.e. whenever the invoice passed the PAID-status pre-check),
    even if the item is ultimately blocked for a Planner-level reason
    (already-batched, pending adjustment, unresolved backfill) — so a
    caller can always inspect the underlying amounts for a blocked item
    too, not only for eligible ones. It is None only when blocked before
    the Calculator was ever called (invoice not PAID).
    """

    invoice_id: int
    company_id: int
    payment_id: Optional[int]
    escrow_id: Optional[int]
    eligible: bool
    blocked_reason: Optional[str]
    calculation: Optional[Layer1SettlementResult]


@dataclass(frozen=True)
class Layer1PlanningReport:
    """Bucketed result of planning Layer 1 settlement across a company."""

    eligible_items: tuple[Layer1PlanningItem, ...]
    blocked_items: tuple[Layer1PlanningItem, ...]


@dataclass(frozen=True)
class Layer2PlanningItem:
    """
    One Technician's eligibility decision for a future Layer 2
    SettlementBatch. `calculation` is populated whenever the Calculator
    was invoked (i.e. always, unless a cross-company technician was
    passed, which raises ValueError instead of returning an item — see
    evaluate_layer2_for_technician()).
    """

    technician_id: int
    company_id: int
    eligible: bool
    blocked_reason: Optional[str]
    calculation: Optional[Layer2SettlementResult]


@dataclass(frozen=True)
class Layer2PlanningReport:
    """Bucketed result of planning Layer 2 settlement across a company."""

    eligible_items: tuple[Layer2PlanningItem, ...]
    blocked_items: tuple[Layer2PlanningItem, ...]


class SettlementPlanner:
    """
    Pure, read-only settlement eligibility service.

    Every method is a @staticmethod with no side effects. Calling any
    method any number of times with the same input always produces an
    identical result (verified by dedicated determinism tests) — there
    is no hidden mutable state, no caching, no randomness, no wall-clock
    dependency in any check below.
    """

    # ------------------------------------------------------------------
    # Layer 1 — Platform <-> Organization
    # ------------------------------------------------------------------

    @staticmethod
    def evaluate_layer1_for_invoice(invoice) -> Layer1PlanningItem:
        """
        Decide whether one Invoice is eligible for a future Layer 1
        SettlementBatch. Never raises for a normal business state — every
        outcome, eligible or blocked, is represented as a Layer1PlanningItem.
        """
        from apps.invoices.models import Invoice
        from .models import (
            AdjustmentDocument,
            EscrowRecord,
            FinancialBackfillTask,
            SettlementBatch,
            SettlementItem,
        )

        company = invoice.company

        if invoice.status != Invoice.Status.PAID:
            return Layer1PlanningItem(
                invoice_id=invoice.id,
                company_id=company.id,
                payment_id=None,
                escrow_id=None,
                eligible=False,
                blocked_reason=(
                    f"Invoice status is '{invoice.status}' — Layer 1 "
                    "settlement planning requires status PAID."
                ),
                calculation=None,
            )

        calculation = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        # Re-fetched independently of the Calculator's own internal lookup
        # (the Calculator does not expose the EscrowRecord object itself,
        # only figures derived from it) so this Planner can report
        # escrow_id / payment_id and inspect settlement_batch linkage.
        escrow = (
            EscrowRecord.objects.filter(company=company, invoice=invoice)
            .order_by("-held_at")
            .first()
        )
        escrow_id = escrow.pk if escrow is not None else None
        payment_id = escrow.payment_id if escrow is not None else None

        if calculation.position == SettlementPosition.BLOCKED:
            return Layer1PlanningItem(
                invoice_id=invoice.id,
                company_id=company.id,
                payment_id=payment_id,
                escrow_id=escrow_id,
                eligible=False,
                blocked_reason=calculation.blocked_reason,
                calculation=calculation,
            )

        # calculation was not BLOCKED, so escrow is guaranteed non-None here.
        if (
            escrow.settlement_batch_id is not None
            and escrow.settlement_batch.status != SettlementBatch.Status.FAILED
        ):
            return Layer1PlanningItem(
                invoice_id=invoice.id,
                company_id=company.id,
                payment_id=payment_id,
                escrow_id=escrow_id,
                eligible=False,
                blocked_reason=(
                    f"EscrowRecord #{escrow.pk} is already linked to "
                    f"SettlementBatch #{escrow.settlement_batch_id} "
                    f"(status='{escrow.settlement_batch.status}'), which is "
                    "not FAILED."
                ),
                calculation=calculation,
            )

        already_batched = (
            SettlementItem.objects.filter(company=company, invoice=invoice)
            .exclude(batch__status=SettlementBatch.Status.FAILED)
            .exists()
        )
        if already_batched:
            return Layer1PlanningItem(
                invoice_id=invoice.id,
                company_id=company.id,
                payment_id=payment_id,
                escrow_id=escrow_id,
                eligible=False,
                blocked_reason=(
                    "Invoice is already included in a non-FAILED "
                    "SettlementItem."
                ),
                calculation=calculation,
            )

        pending_adjustment = AdjustmentDocument.objects.filter(
            company=company,
            original_invoice=invoice,
            status__in=_PENDING_ADJUSTMENT_STATUSES,
        ).exists()
        if pending_adjustment:
            return Layer1PlanningItem(
                invoice_id=invoice.id,
                company_id=company.id,
                payment_id=payment_id,
                escrow_id=escrow_id,
                eligible=False,
                blocked_reason="Invoice has a pending AdjustmentDocument.",
                calculation=calculation,
            )

        unresolved_backfill = FinancialBackfillTask.objects.filter(
            company=company,
            invoice=invoice,
            status__in=_UNRESOLVED_BACKFILL_STATUSES,
        ).exists()
        if unresolved_backfill:
            return Layer1PlanningItem(
                invoice_id=invoice.id,
                company_id=company.id,
                payment_id=payment_id,
                escrow_id=escrow_id,
                eligible=False,
                blocked_reason=(
                    "Invoice has an unresolved FinancialBackfillTask."
                ),
                calculation=calculation,
            )

        return Layer1PlanningItem(
            invoice_id=invoice.id,
            company_id=company.id,
            payment_id=payment_id,
            escrow_id=escrow_id,
            eligible=True,
            blocked_reason=None,
            calculation=calculation,
        )

    @staticmethod
    def plan_layer1_for_company(company) -> Layer1PlanningReport:
        """
        Evaluate every Invoice belonging to `company` and bucket the
        results into eligible / blocked.

        Note on scale (disclosed, not fixed in Step 2): this evaluates
        every invoice for the company one at a time via
        evaluate_layer1_for_invoice(), which is the clearest, most
        directly testable design for this step. A future Batch Builder
        step may replace this with a single, more selective queryset
        (e.g. pre-filtering to invoices that already have a DISTRIBUTED
        EscrowRecord) for efficiency at scale — that is an optimization,
        not a change in eligibility semantics, and is deliberately
        deferred rather than attempted here.
        """
        from apps.invoices.models import Invoice

        eligible: list[Layer1PlanningItem] = []
        blocked: list[Layer1PlanningItem] = []
        for invoice in Invoice.objects.filter(company=company):
            item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)
            (eligible if item.eligible else blocked).append(item)

        return Layer1PlanningReport(
            eligible_items=tuple(eligible),
            blocked_items=tuple(blocked),
        )

    # ------------------------------------------------------------------
    # Layer 2 — Organization <-> Provider (Technician)
    # ------------------------------------------------------------------

    @staticmethod
    def evaluate_layer2_for_technician(company, technician) -> Layer2PlanningItem:
        """
        Decide whether one Technician's current ledger balance is
        eligible for a future Layer 2 SettlementBatch.

        Raises ValueError if `technician` does not belong to `company` —
        this propagates directly from
        SettlementCalculator.calculate_layer2_for_technician(), which
        already treats this as a caller/programming error, not a
        business state (see that method's own docstring).
        """
        from .models import (
            AdjustmentDocument,
            FinancialBackfillTask,
            SettlementBatch,
            SettlementItem,
            TechnicianLedgerEntry,
        )

        calculation = SettlementCalculator.calculate_layer2_for_technician(company, technician)

        already_claimed = (
            SettlementItem.objects.filter(
                company=company, ledger_entry__technician=technician,
            )
            .exclude(batch__status=SettlementBatch.Status.FAILED)
            .exists()
        )
        if already_claimed:
            return Layer2PlanningItem(
                technician_id=technician.id,
                company_id=company.id,
                eligible=False,
                blocked_reason=(
                    "Technician has ledger entries already included in a "
                    "non-FAILED SettlementItem."
                ),
                calculation=calculation,
            )

        pending_adjustment = AdjustmentDocument.objects.filter(
            company=company,
            status__in=_PENDING_ADJUSTMENT_STATUSES,
            technician_ledger_entry__technician=technician,
        ).exists()
        if pending_adjustment:
            return Layer2PlanningItem(
                technician_id=technician.id,
                company_id=company.id,
                eligible=False,
                blocked_reason=(
                    "Technician has a pending AdjustmentDocument linked to "
                    "a ledger entry."
                ),
                calculation=calculation,
            )

        technician_invoice_ids = TechnicianLedgerEntry.objects.filter(
            company=company, technician=technician,
        ).values_list("invoice_id", flat=True)
        unresolved_backfill = FinancialBackfillTask.objects.filter(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status__in=_UNRESOLVED_BACKFILL_STATUSES,
            invoice_id__in=technician_invoice_ids,
        ).exists()
        if unresolved_backfill:
            return Layer2PlanningItem(
                technician_id=technician.id,
                company_id=company.id,
                eligible=False,
                blocked_reason=(
                    "Technician has an unresolved FinancialBackfillTask on "
                    "a related invoice."
                ),
                calculation=calculation,
            )

        if calculation.position == SettlementPosition.PAYABLE:
            return Layer2PlanningItem(
                technician_id=technician.id,
                company_id=company.id,
                eligible=True,
                blocked_reason=None,
                calculation=calculation,
            )

        if calculation.position == SettlementPosition.ZERO:
            return Layer2PlanningItem(
                technician_id=technician.id,
                company_id=company.id,
                eligible=False,
                blocked_reason="Zero balance — nothing to settle.",
                calculation=calculation,
            )

        # RECEIVABLE: the technician owes the company, not the other way
        # around. Reported honestly as a blocked (non-payable) item, per
        # the explicit instruction that a negative balance must be
        # reported as receivable/debt, never silently treated as payable
        # or clamped to zero.
        return Layer2PlanningItem(
            technician_id=technician.id,
            company_id=company.id,
            eligible=False,
            blocked_reason=(
                "Technician owes the company (receivable/debt) — not a "
                "payable settlement in this direction."
            ),
            calculation=calculation,
        )

    @staticmethod
    def plan_layer2_for_company(company, technician=None) -> Layer2PlanningReport:
        """
        Evaluate technicians belonging to `company` and bucket the
        results into eligible / blocked.

        If `technician` is provided, only that technician is evaluated
        (still raising ValueError if it does not belong to `company`,
        via evaluate_layer2_for_technician's delegation to the
        Calculator). If omitted, every Technician belonging to the
        company is evaluated.
        """
        from apps.accounts.models import Technician

        if technician is not None:
            technicians = [technician]
        else:
            technicians = list(Technician.objects.filter(company=company))

        eligible: list[Layer2PlanningItem] = []
        blocked: list[Layer2PlanningItem] = []
        for tech in technicians:
            item = SettlementPlanner.evaluate_layer2_for_technician(company, tech)
            (eligible if item.eligible else blocked).append(item)

        return Layer2PlanningReport(
            eligible_items=tuple(eligible),
            blocked_items=tuple(blocked),
        )
