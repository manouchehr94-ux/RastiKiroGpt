"""
Payouts — Settlement Execution Engine (Sprint 4 — Settlement Engine, Phase
B, Step 4).

Executes an already-created READY SettlementBatch (Step 3, unmodified),
transitioning it READY -> EXECUTING -> COMPLETED (or -> FAILED on error),
and creates the accounting entries that represent settlement completion.

PRE-CODING AUDIT (per explicit instruction, performed before writing any
code in this module):

  TechnicianLedgerEntry.Source (apps/payouts/models.py) already includes
  MANUAL_SETTLEMENT ("تسویه دستی" / "Manual settlement") paired with
  EntryType.DEBIT — already wrapped by the existing, unmodified
  TechnicianLedgerService.record_manual_settlement(direction=
  "COMPANY_PAID_TECHNICIAN"), whose own docstring says: "Company
  wired/gave money to technician -> reduces positive balance." This is
  exactly Layer 2 settlement completion. NO new enum member, field, or
  migration is required.

  CompanyPlatformFeeEntry.Source already includes PLATFORM_FEE_SETTLEMENT
  ("تسویه کارمزد" / "Fee settlement") paired with EntryType.CREDIT —
  already wrapped by the existing, unmodified
  PlatformFeeService.record_manual_credit(), whose own docstring says:
  "Record a CREDIT (settlement) entry — company paid its platform fee."
  This is exactly the Layer 1 fee-reconciliation portion of settlement
  completion. NO new enum member, field, or migration is required.

  EscrowRecordService.mark_settled() (PENDING_SETTLEMENT -> SETTLED)
  already exists (Sprint 2) and was never called by any production code
  until now. The Batch Builder (Step 3) already advanced every Layer 1
  item's EscrowRecord to PENDING_SETTLEMENT and linked
  escrow.settlement_batch to the batch being built. Per the approved
  Money Ownership Lifecycle / Financial State Machine specification,
  SETTLED is the next, already-designed state after PENDING_SETTLEMENT —
  marking it here (as part of completing the very batch that record is
  linked to) is exactly the "existing approved design requires final
  settlement marking" case referenced in the Step 4 instructions, not an
  invented mutation. NO new escrow field or state is introduced.

  Conclusion of audit: every ledger/escrow write this module performs
  uses an EXISTING enum value, EXISTING model field, and EXISTING,
  previously-merged service method. Zero new choices, fields, or
  migrations were added or are needed.

WHY CompanyPlatformFeeEntry.CREDIT CARRIES ONLY THE COMMISSION PORTION,
NOT THE FULL ORGANIZATION SHARE:
  CompanyPlatformFeeEntry tracks a running FEE balance only (how much
  commission the company has been charged vs. how much of that has been
  reconciled/settled) — it is not a general "money the platform owes the
  company" ledger. For every online-gateway invoice, a matching DEBIT
  entry (source=ONLINE_GATEWAY, amount=platform_commission) was already
  created at invoice-paid time by the existing, unmodified
  PlatformFeeService.record_invoice_fee(). Crediting that exact same
  amount here, at batch-completion time, correctly reconciles that
  specific fee obligation as "now settled" — it does not (and must not)
  also carry the organization_share_rial portion, because no existing
  model tracks a running "platform owes organization" balance; that
  specific obligation is tracked per-payment by EscrowRecord itself, and
  its completion is represented by the EscrowRecord reaching SETTLED
  (see above), not by an additional ledger entry.

SCOPE (Step 4 only):
  - Executes an already-READY batch. Does NOT create, plan, or calculate
    batches/items — those are Steps 1-3 (unmodified).
  - Does NOT call any real bank API, external payment gateway, or
    external transfer service of any kind.
  - Does NOT add a view, API endpoint, management command, or background
    job.
  - Does NOT mutate Payment or Invoice in any way.
  - Does NOT mutate any existing (already-persisted) TechnicianLedgerEntry
    or CompanyPlatformFeeEntry row — both models already enforce this at
    the model layer (their own .save()/.delete() overrides raise
    PermissionError on any attempt to change amount_rial/balance_after or
    delete a row) — this module only ever creates new rows via the
    existing service methods, never edits or deletes existing ones.

TRANSACTION BOUNDARIES:
  execute_batch() is one single @transaction.atomic block, per the
  explicit instruction to prefer transaction.atomic() around both the
  state transition and the ledger writes together. Within that block, the
  ledger-write-and-complete step is wrapped in its OWN nested
  transaction.atomic() (a savepoint): if anything inside that inner block
  raises (a ledger write failing, an escrow transition failing,
  mark_completed's own guard failing), the savepoint rolls back — undoing
  every ledger entry and the mark_completed attempt together, atomically —
  and execution falls through to mark_failed(), which is a normal write
  in the still-open OUTER transaction and therefore persists correctly
  when the outer block commits. This is the same two-phase pattern
  already used by FinancialBackfillService._process_one() (Sprint 1,
  unmodified) — no new transactional pattern is introduced.

IDEMPOTENCY:
  - Executing an already-COMPLETED batch is a pure no-op: the very first
    thing execute_batch() does, under the row lock, is check for
    status == COMPLETED and return immediately with a result describing
    the existing completion — no ledger write, no escrow transition, no
    further state change is attempted.
  - Executing a FAILED batch is blocked: no explicit retry policy exists
    in this step (per instruction 5), so a FAILED batch is left to fall
    through to mark_executing()'s own existing guard, which raises
    SettlementBatchTransitionError for any status other than READY —
    including FAILED. No new exception type is introduced for this; the
    existing, already-tested guard is reused as-is.
  - Every ledger write created by this module uses a deterministic
    idempotency_key derived from (batch.pk, item.pk) or batch.pk alone —
    never a random/UUID key — so that even in a hypothetical scenario
    where this module's own top-level COMPLETED short-circuit were
    somehow bypassed, the underlying ledger services' own idempotency_key
    uniqueness constraint (unmodified, Sprint 1) would still prevent a
    duplicate row.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.db import transaction

from .exceptions import SettlementError
from .services import TechnicianLedgerService
from .services_escrow import EscrowRecordService
from .services_platform_fee import PlatformFeeService
from .services_settlement_batch import SettlementBatchService


class SettlementExecutionError(SettlementError):
    """
    Raised when this module detects a data-integrity problem it cannot
    safely proceed past (e.g. a SettlementItem referencing a ledger entry
    with no technician). Distinct from SettlementBatchTransitionError,
    which is raised by the existing, unmodified SettlementBatchService
    for an invalid state transition (e.g. executing a non-READY batch).
    """


@dataclass(frozen=True)
class ExecutionResult:
    """
    Result of an execute_batch() call.

    `status` is one of: "completed", "already_completed", "failed".
    `already_completed=True` (status == "already_completed") means this
    call was a pure idempotent no-op — nothing was written.
    """

    batch: object  # SettlementBatch instance
    status: str
    ledger_entries_created: int
    failure_reason: Optional[str]


class SettlementExecutionEngine:
    """
    Executes a READY SettlementBatch. No bank API, no external transfer,
    no UI, no API endpoint, no management command, no background job.
    """

    @staticmethod
    @transaction.atomic
    def execute_batch(batch, bank_reference=None) -> ExecutionResult:
        from .models import SettlementBatch

        locked = SettlementBatch.objects.select_for_update().get(pk=batch.pk)

        # Idempotency: executing an already-COMPLETED batch is a safe
        # no-op. Checked BEFORE calling mark_executing(), so no state
        # transition and no ledger write is even attempted.
        if locked.status == SettlementBatch.Status.COMPLETED:
            return ExecutionResult(
                batch=locked,
                status="already_completed",
                ledger_entries_created=0,
                failure_reason=None,
            )

        # For every other non-READY status (CALCULATING, EXECUTING, or
        # FAILED — FAILED batches are blocked because no retry policy
        # exists in this step, per instruction 5), let
        # SettlementBatchService.mark_executing()'s own existing guard
        # raise SettlementBatchTransitionError naturally. This module
        # does not duplicate that check with a second, parallel one.
        locked = SettlementBatchService.mark_executing(locked)

        try:
            with transaction.atomic():
                entries_created = SettlementExecutionEngine._complete_batch(locked)
                locked = SettlementBatchService.mark_completed(
                    locked, bank_reference=bank_reference,
                )
        except Exception as exc:
            # The inner `with transaction.atomic()` block above rolled
            # back its savepoint on this exception — every ledger entry
            # and the mark_completed attempt made inside it are already
            # undone. mark_failed() below is a normal write in the still
            # -open OUTER transaction (this method's own @transaction.atomic
            # decorator) and will persist when that outer transaction
            # commits, exactly matching the existing
            # FinancialBackfillService._process_one() two-phase pattern.
            locked = SettlementBatchService.mark_failed(locked, str(exc))
            return ExecutionResult(
                batch=locked,
                status="failed",
                ledger_entries_created=0,
                failure_reason=str(exc),
            )

        return ExecutionResult(
            batch=locked,
            status="completed",
            ledger_entries_created=entries_created,
            failure_reason=None,
        )

    # ------------------------------------------------------------------
    # Internal — dispatches by level, never called directly by callers
    # ------------------------------------------------------------------

    @staticmethod
    def _complete_batch(batch) -> int:
        from .models import SettlementBatch

        if batch.level == SettlementBatch.Level.PLATFORM_TO_ORG:
            return SettlementExecutionEngine._complete_layer1(batch)
        if batch.level == SettlementBatch.Level.ORG_TO_PROVIDER:
            return SettlementExecutionEngine._complete_layer2(batch)
        raise SettlementExecutionError(
            f"SettlementBatch #{batch.pk}: unknown level '{batch.level}' — "
            "cannot determine which completion logic to run."
        )

    @staticmethod
    def _complete_layer1(batch) -> int:
        """
        Layer 1 (Platform <-> Organization) completion:
          1. CREDIT the company's platform-fee ledger for the total
             commission amount already recorded (DEBIT) against these
             same invoices at invoice-paid time — reconciling that
             specific fee obligation as settled.
          2. Mark every linked EscrowRecord SETTLED (the already-designed
             next state after PENDING_SETTLEMENT, per the approved state
             machine).

        Both steps use only existing, unmodified service methods and
        existing enum values (see module docstring's pre-coding audit).
        """
        from .models import EscrowRecord

        escrows = list(
            EscrowRecord.objects.select_for_update().filter(
                company=batch.company, settlement_batch=batch,
            )
        )

        total_commission = sum(int(e.platform_commission_rial or 0) for e in escrows)
        entries_created = 0

        if total_commission > 0:
            entry = PlatformFeeService.record_manual_credit(
                company=batch.company,
                amount_rial=total_commission,
                description=(
                    f"Settlement completion — platform fee reconciliation "
                    f"for batch #{batch.pk}"
                ),
                idempotency_key=f"platform_fee_settlement:batch:{batch.pk}",
            )
            if entry is not None:
                entries_created += 1

        for escrow in escrows:
            EscrowRecordService.mark_settled(escrow, settlement_batch=batch)

        return entries_created

    @staticmethod
    def _complete_layer2(batch) -> int:
        """
        Layer 2 (Organization <-> Provider) completion: for every
        SettlementItem in this batch that references a technician ledger
        entry, create a DEBIT ("company paid technician") entry for the
        item's own net-payable amount (already computed and frozen by
        the Batch Builder, Step 3 — never re-derived here).

        Each write uses a deterministic idempotency_key derived from
        (batch.pk, item.pk), so re-attempting this method for an item
        that already has a corresponding entry is a safe no-op (the
        underlying TechnicianLedgerService._write_entry() idempotency
        check returns None rather than creating a duplicate). In normal
        operation this method is never actually re-invoked for the same
        batch, because execute_batch()'s top-level COMPLETED short-circuit
        prevents that — this per-item idempotency key is a second,
        independent safety layer, not the primary mechanism.
        """
        from .models import SettlementItem

        items = SettlementItem.objects.filter(
            company=batch.company, batch=batch, ledger_entry__isnull=False,
        ).select_related("ledger_entry", "ledger_entry__technician")

        entries_created = 0
        for item in items:
            technician = item.ledger_entry.technician
            entry = TechnicianLedgerService.record_manual_settlement(
                company=batch.company,
                technician=technician,
                amount_rial=item.amount_rial,
                direction="COMPANY_PAID_TECHNICIAN",
                reference=f"settlement_batch:{batch.pk}",
                description=(
                    f"Settlement completion — batch #{batch.pk}, "
                    f"item #{item.pk}"
                ),
                idempotency_key=f"settlement_batch:{batch.pk}:item:{item.pk}",
            )
            if entry is not None:
                entries_created += 1

        return entries_created
