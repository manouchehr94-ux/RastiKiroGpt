"""
Payouts — Refund & Adjustment Execution Service (Sprint 5 — Phase B).

Executes an already-APPROVED AdjustmentDocument (Sprint 2, unmodified
lifecycle) by creating reversal ledger entries and, when applicable,
closing the linked EscrowRecord — then transitions the document to
APPLIED via the existing, unmodified AdjustmentDocumentService.mark_applied().

PRE-CODING AUDIT (per explicit instruction, performed before writing any
code in this module):

  TechnicianLedgerEntry.Source ALREADY includes REFUND ("بازگشت وجه") and
  ADJUSTMENT ("تعدیل"), and TechnicianLedgerService.create_debit() /
  create_credit() ALREADY accept an explicit `source` keyword argument
  directly (apps/payouts/services.py). This means a refund reversal can
  be written as:

      TechnicianLedgerService.create_debit(
          company=..., technician=..., source=Source.REFUND,
          amount_rial=..., idempotency_key=...,
      )

  with ZERO changes to TechnicianLedgerService. This module calls
  create_debit()/create_credit() directly — NOT
  record_manual_settlement() — specifically to avoid touching that
  method's `direction` parameter mapping at all. Its own docstring
  already flags `direction` as ambiguous ("TODO (P2): Replace `direction`
  with explicit entry_type once the business decides on canonical
  cash-flow terminology") — reusing create_debit()/create_credit()
  directly, which already supports exactly what is needed, is strictly
  safer than adding a new direction value to an already-flagged-ambiguous
  parameter. Conclusion: NO extension to TechnicianLedgerService is
  required or made.

  CompanyPlatformFeeEntry.Source ALREADY includes REFUND ("برگشت") and
  MANUAL_ADJUSTMENT ("تعدیل دستی"). However,
  PlatformFeeService.record_manual_credit() hardcodes
  source=Source.PLATFORM_FEE_SETTLEMENT with no parameter to select a
  different source. Unlike TechnicianLedgerService, there is no existing
  public method on PlatformFeeService that accepts an explicit `source`
  for a CREDIT write — record_invoice_fee() only ever writes a DEBIT, and
  record_manual_credit() is the only CREDIT-writing method, with its
  source hardcoded.

  WHY THIS SPECIFIC, MINIMAL EXTENSION IS REQUIRED (per the explicit
  "explain exactly why" instruction):
    - Why the existing API cannot support it as-is: record_manual_credit()
      has no `source` parameter at all; calling it today always produces
      source=PLATFORM_FEE_SETTLEMENT, which would mislabel a refund
      reversal as a routine fee settlement in the ledger — an auditor
      reading CompanyPlatformFeeEntry.source could not distinguish "the
      company paid its fee" from "the platform refunded a commission",
      which defeats the entire purpose of having a distinct REFUND source
      value that already exists in the model.
    - Why the new parameter is required: the model already reserves
      Source.REFUND specifically for this case; not using it would be a
      classification error, not a technical limitation being worked
      around — the fix is to let the existing method accept the source
      the model already defines, not to invent a new one.
    - Why it does not break previous behavior: the new `source` parameter
      is added as a keyword-only argument with a default of
      `CompanyPlatformFeeEntry.Source.PLATFORM_FEE_SETTLEMENT` — the exact
      value the method already hardcodes today. Every existing call site
      (tests/test_p7_verify.py, apps/payouts/services_settlement_execution.py)
      calls record_manual_credit() without a `source` argument at all, so
      every one of them continues to produce byte-for-byte identical
      behavior after this change. This is confirmed by grep: zero call
      sites pass `source=` today. The change is purely additive.

  EscrowRecordService.close() ALREADY accepts HELD/RESERVED/DISTRIBUTED/
  SETTLED as valid pre-states (Sprint 2, unmodified) — exactly the
  "refund before settlement" transition this module needs. NO change to
  EscrowRecordService is made.

  AdjustmentDocumentService.mark_applied() ALREADY exists and is reused
  UNMODIFIED — this module calls it after writing reversal entries,
  exactly mirroring how SettlementExecutionEngine (Sprint 4 Step 4) calls
  SettlementBatchService.mark_completed() after its own ledger writes.

  Conclusion of audit: the ONLY code change to an existing file in this
  entire sprint is the one additive, backward-compatible `source`
  keyword parameter on PlatformFeeService.record_manual_credit(). No
  other existing service, model, or migration is touched.

SAFE SCOPE (per approved Phase A + this sprint's explicit instructions):
  - FULL_REFUND only. PARTIAL_REFUND, CREDIT_NOTE, DEBIT_NOTE, and
    MANUAL_ADJUSTMENT are explicitly NOT executed by this module — see
    "BLOCKED SCENARIOS" below.
  - Refund BEFORE settlement only (EscrowRecord status HELD / RESERVED /
    DISTRIBUTED — never SETTLED or CLOSED). Refund AFTER settlement is
    explicitly BLOCKED — this module raises rather than inventing a
    reopening/reclaim mechanism.
  - Ledger-held technician wage only. If the invoice's payment was
    direct-split (PaymentSplitSnapshot.should_split_with_technician=True),
    this module raises rather than inventing a direct-split reversal
    formula ([OPEN-ISSUE: OI-04]/[OI-07], per the approved Phase A design).
  - No customer-facing balance of any kind is created, read, or modified
    ([OPEN-ISSUE: OI-05]/[OI-06] — no CustomerFinancialAccount exists or
    is invented here).

BLOCKED SCENARIOS (raise RefundExecutionBlockedError, never silently
skip or guess):
  - document.document_type != FULL_REFUND
    -> [OPEN-ISSUE: OI-07]: partial-refund proportionality and manual-
       adjustment direction/sign are not Product-Owner-decided.
  - EscrowRecord.status in (SETTLED, CLOSED) at execution time
    -> [OPEN-ISSUE: OI-07]: after-settlement refund tracking mechanism
       is not Product-Owner-decided. This module NEVER reopens a
       SETTLED or CLOSED EscrowRecord.
  - PaymentSplitSnapshot.should_split_with_technician == True for the
    original invoice's payment
    -> [OPEN-ISSUE: OI-04]/[OI-07]: direct-split reversal formula is not
       Product-Owner-decided.

TRANSACTION BOUNDARIES:
  execute(document) is one single @transaction.atomic block, matching
  the "everything inside transaction.atomic()" instruction. Within that
  block, the row lock, top-level idempotency check, and all blocking-
  scenario validation happen BEFORE any ledger write is attempted — so a
  blocked scenario never partially writes anything. The actual writes
  (platform fee CREDIT, technician DEBIT, escrow close(), mark_applied())
  happen inside a nested transaction.atomic() savepoint, exactly
  mirroring the two-phase pattern already used by
  SettlementExecutionEngine (Sprint 4 Step 4) and
  FinancialBackfillService._process_one() (Sprint 1) — if anything in
  that inner block raises, the savepoint rolls back every write made so
  far, leaving the document safely at APPROVED (no FAILED status exists
  for AdjustmentDocument, per its own state machine — a failed
  application simply leaves it retryable at APPROVED).

IDEMPOTENCY:
  - Top-level: execute() checks document.status == APPLIED FIRST, under
    the row lock, and returns immediately with a result describing the
    existing application — no ledger write, no escrow transition, no
    further state change is attempted. Mirrors
    SettlementExecutionEngine's COMPLETED short-circuit exactly.
  - Per-entry: every ledger write uses a deterministic idempotency_key
    derived from document.pk alone (f"adjustment:{document.pk}:platform_
    fee_reversal", f"adjustment:{document.pk}:technician_wage_reversal")
    — never a random/UUID key — so that even if the top-level check were
    somehow bypassed, the underlying services' own idempotency_key
    uniqueness constraint (unmodified, Sprint 1) would still prevent a
    duplicate row.

FINANCIAL BACKFILL:
  No new FinancialBackfillTask.TaskType is added (no migration risk).
  If a future retry mechanism is needed, the existing `invoice` FK on
  FinancialBackfillTask already provides sufficient linkage back to the
  AdjustmentDocument via AdjustmentDocument.original_invoice — consistent
  with the existing raw-string task_type precedent ("escrow_record").
  This module does NOT create a FinancialBackfillTask itself: unlike
  mark_paid()'s non-blocking side effects, a refund's ledger writes are
  the PRIMARY purpose of calling execute() (not a secondary, best-effort
  side effect of some other primary operation) — so a failure here must
  propagate to the caller as a raised exception (leaving the document
  retryable at APPROVED), not be silently swallowed into a background
  backfill queue. This matches the instruction "do not invent recovery
  workflows."
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from .exceptions import AdjustmentError, AdjustmentTransitionError
from .models import AdjustmentDocument
from .services import TechnicianLedgerService
from .services_adjustment import AdjustmentDocumentService
from .services_escrow import EscrowRecordService
from .services_platform_fee import PlatformFeeService


class RefundExecutionBlockedError(AdjustmentError):
    """
    Raised when execution has reached a scenario explicitly blocked by
    an unresolved Product Owner decision (OI-04, OI-05, OI-06, OI-07,
    OI-08). This module NEVER invents policy to work around this
    exception — the caller must resolve the underlying open issue.
    """


@dataclass(frozen=True)
class RefundExecutionResult:
    """
    Result of an execute(document) call.

    `status` is one of: "applied", "already_applied".
    `already_applied=True` (status == "already_applied") means this call
    was a pure idempotent no-op — nothing was written.
    """

    document: object  # AdjustmentDocument instance
    status: str
    platform_fee_entry_created: bool
    technician_ledger_entry_created: bool
    escrow_closed: bool


class RefundExecutionService:
    """
    Executes an APPROVED, FULL_REFUND AdjustmentDocument for an invoice
    whose EscrowRecord (if any) has not yet reached SETTLED/CLOSED, and
    whose technician wage (if any) was ledger-held, not direct-split.

    No UI, no API endpoint, no management command, no background job, no
    bank API call, no external transfer of any kind exists in this
    module.
    """

    @staticmethod
    @transaction.atomic
    def execute(document) -> RefundExecutionResult:
        locked = AdjustmentDocument.objects.select_for_update().get(pk=document.pk)

        # Idempotency: executing an already-APPLIED document is a safe
        # no-op. Checked BEFORE any validation or write is attempted.
        if locked.status == AdjustmentDocument.Status.APPLIED:
            return RefundExecutionResult(
                document=locked,
                status="already_applied",
                platform_fee_entry_created=False,
                technician_ledger_entry_created=False,
                escrow_closed=False,
            )

        # Reject execution from any non-APPROVED status (DRAFT,
        # PENDING_APPROVAL, REJECTED, CANCELLED) BEFORE any ledger write
        # is attempted. This reuses the existing, unmodified
        # AdjustmentTransitionError type (the same exception
        # AdjustmentDocumentService.mark_applied() itself raises for this
        # exact precondition) — this is not a new, parallel exception
        # type, it is the same guard restated early so that "no partial
        # write for a blocked status" holds even though mark_applied()
        # itself is only called at the very end of this method, after
        # the ledger writes. mark_applied()'s own guard remains the
        # authoritative check (it re-validates the same condition), this
        # is purely a fail-fast optimization using its exact exception
        # type and message format.
        if locked.status != AdjustmentDocument.Status.APPROVED:
            raise AdjustmentTransitionError(
                f"AdjustmentDocument #{locked.pk}: cannot execute from "
                f"status '{locked.status}'. Must be APPROVED."
            )

        RefundExecutionService._validate_safe_scope(locked)

        with transaction.atomic():
            invoice = locked.original_invoice
            company = locked.company

            platform_fee_created = RefundExecutionService._reverse_platform_fee(
                company, invoice, locked,
            )
            technician_entry_created = RefundExecutionService._reverse_technician_wage(
                company, invoice, locked,
            )
            escrow_closed = RefundExecutionService._close_escrow_if_applicable(
                company, invoice,
            )

            applied = AdjustmentDocumentService.mark_applied(locked)

        return RefundExecutionResult(
            document=applied,
            status="applied",
            platform_fee_entry_created=platform_fee_created,
            technician_ledger_entry_created=technician_entry_created,
            escrow_closed=escrow_closed,
        )

    # ------------------------------------------------------------------
    # Internal — scope validation (raises RefundExecutionBlockedError)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_safe_scope(document) -> None:
        from .models import EscrowRecord, PaymentSplitSnapshot

        if document.document_type != AdjustmentDocument.DocumentType.FULL_REFUND:
            raise RefundExecutionBlockedError(
                f"AdjustmentDocument #{document.pk}: document_type "
                f"'{document.document_type}' is not executable by this "
                "service. Only FULL_REFUND is implemented in this sprint "
                "— PARTIAL_REFUND, CREDIT_NOTE, DEBIT_NOTE, and "
                "MANUAL_ADJUSTMENT are blocked by [OPEN-ISSUE: OI-07] "
                "(proportionality / direction formulas not yet decided "
                "by the Product Owner)."
            )

        invoice = document.original_invoice
        escrow = (
            EscrowRecord.objects.filter(company=document.company, invoice=invoice)
            .order_by("-held_at")
            .first()
        )
        if escrow is not None and escrow.status in (
            EscrowRecord.Status.SETTLED, EscrowRecord.Status.CLOSED,
        ):
            raise RefundExecutionBlockedError(
                f"AdjustmentDocument #{document.pk}: invoice #{invoice.pk}'s "
                f"EscrowRecord #{escrow.pk} has already reached "
                f"'{escrow.status}'. Refund AFTER settlement is blocked by "
                "[OPEN-ISSUE: OI-07] (no approved tracking/shortfall "
                "mechanism exists). This service will never reopen a "
                "SETTLED or CLOSED EscrowRecord."
            )

        if escrow is not None:
            snapshot = PaymentSplitSnapshot.objects.filter(
                company=document.company, payment=escrow.payment,
            ).first()
            if snapshot is not None and snapshot.should_split_with_technician:
                raise RefundExecutionBlockedError(
                    f"AdjustmentDocument #{document.pk}: invoice #{invoice.pk}'s "
                    "technician wage was paid via direct gateway split, not "
                    "ledger-held. Direct-split reversal is blocked by "
                    "[OPEN-ISSUE: OI-04]/[OPEN-ISSUE: OI-07] (no approved "
                    "provider-debt formula exists for this case)."
                )

    # ------------------------------------------------------------------
    # Internal — reversal writes (each independently idempotent)
    # ------------------------------------------------------------------

    @staticmethod
    def _reverse_platform_fee(company, invoice, document) -> bool:
        from .models import CompanyPlatformFeeEntry

        original_debit = CompanyPlatformFeeEntry.objects.filter(
            company=company, invoice=invoice,
            entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
        ).first()
        if original_debit is None:
            # Nothing to reverse — this invoice never had a platform
            # commission recognized (cash/company-gateway payment, or
            # zero fee percent). Creating a CREDIT with no matching DEBIT
            # would introduce an unbalanced entry, so this is correctly a
            # no-op, not an error.
            return False

        amount = int(original_debit.amount_rial)
        entry = PlatformFeeService.record_manual_credit(
            company=company,
            amount_rial=amount,
            description=(
                f"Refund reversal — AdjustmentDocument #{document.pk}, "
                f"invoice #{invoice.pk}"
            ),
            idempotency_key=f"adjustment:{document.pk}:platform_fee_reversal",
            source=CompanyPlatformFeeEntry.Source.REFUND,
        )
        if entry is not None:
            document.platform_fee_reversal = amount
            document.platform_fee_entry = entry
            # PERSIST before mark_applied() runs. mark_applied() re-fetches
            # the document from the database
            # (AdjustmentDocument.objects.select_for_update().get(...)),
            # which would silently discard these attribute assignments if
            # they were left in-memory only — this was the exact root
            # cause of platform_fee_reversal being observed as None after
            # execution. update_fields is scoped to only these two fields;
            # no other column is touched.
            document.save(update_fields=["platform_fee_reversal", "platform_fee_entry"])
        return entry is not None

    @staticmethod
    def _reverse_technician_wage(company, invoice, document) -> bool:
        from .models import TechnicianLedgerEntry

        wage = int(invoice.settled_technician_wage or 0)
        if wage <= 0:
            # No technician wage was ever recognized for this invoice
            # (no technician assigned, or zero wage) — correctly a no-op.
            return False

        technician = getattr(getattr(invoice, "order", None), "technician", None)
        if technician is None:
            return False

        entry = TechnicianLedgerService.create_debit(
            company=company,
            technician=technician,
            source=TechnicianLedgerEntry.Source.REFUND,
            amount_rial=wage,
            idempotency_key=f"adjustment:{document.pk}:technician_wage_reversal",
            invoice=invoice,
            description=(
                f"Refund reversal — AdjustmentDocument #{document.pk}, "
                f"invoice #{invoice.pk}"
            ),
        )
        if entry is not None:
            document.technician_wage_reversal = wage
            document.technician_ledger_entry = entry
            # PERSIST before mark_applied() runs — same rationale as
            # _reverse_platform_fee() above: without this explicit save,
            # mark_applied()'s internal re-fetch discards the in-memory
            # assignment, leaving technician_wage_reversal as None on the
            # object ultimately returned to the caller. update_fields is
            # scoped to only these two fields.
            document.save(update_fields=["technician_wage_reversal", "technician_ledger_entry"])
        return entry is not None

    @staticmethod
    def _close_escrow_if_applicable(company, invoice) -> bool:
        from .models import EscrowRecord

        escrow = (
            EscrowRecord.objects.filter(company=company, invoice=invoice)
            .order_by("-held_at")
            .first()
        )
        if escrow is None:
            return False
        if escrow.status == EscrowRecord.Status.CLOSED:
            # Already closed (e.g. a retried, previously-successful
            # execution whose mark_applied() call failed afterward) —
            # safe no-op, never re-close.
            return False

        EscrowRecordService.close(escrow, reason="Full refund before settlement")
        return True
