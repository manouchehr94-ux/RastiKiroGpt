"""
Payouts — Financial Reconciliation Engine (Sprint 6, first safe layer).

Read-only cross-checking of already-persisted financial records. Detects
missing, duplicate, orphan, inconsistent, or blocked financial records and
reports them as structured, machine-readable issues.

HARD SCOPE, PER EXPLICIT INSTRUCTION:
  - Every function in this module is read-only. No .save(), .create(),
    .update(), .delete() call exists anywhere in this file.
  - Never auto-fixes anything. A discrepancy is reported, never corrected.
  - Never creates a new financial record of any kind (no ReconciliationRun
    or ReconciliationDiscrepancy model exists yet — this sprint's scope is
    strictly the detection functions themselves, returned as in-memory
    dataclasses, not persisted).
  - No UI, no API, no bank statement import, no accounting journal engine,
    no wallet — none of that exists in or is referenced by this file.

WHAT IS CHECKED (per explicit scope):
  1. Payment <-> Invoice: paid invoice with no matching PAID payment,
     duplicate PAID payments for one invoice, payment amount vs. invoice
     total mismatch.
  2. Invoice <-> EscrowRecord: a PAID invoice paid through a platform-owned
     gateway with no EscrowRecord at all (missing escrow).
  3. EscrowRecord <-> SettlementBatch/SettlementItem: a DISTRIBUTED escrow
     with no settlement linkage yet (informational — may simply be awaiting
     its next settlement cycle); a PENDING_SETTLEMENT/SETTLED escrow that is
     missing its batch link or its SettlementItem (a genuine inconsistency,
     since those statuses assert that linkage already happened).
  4. SettlementItem source integrity: a SettlementItem whose invoice,
     ledger_entry, AND platform_fee_entry FKs are all NULL — every one of
     those FKs uses on_delete=SET_NULL, so this is the "if possible"
     detectable analogue of "settlement item without valid invoice": the
     item has lost every trace of what it was created to represent.
  5. TechnicianLedgerEntry balance integrity: walks each technician's
     entries in chronological order and re-derives the running balance
     from scratch, comparing it against each entry's own stored
     balance_after — this directly targets the known, documented
     concurrency gap in ADR-008 §2/§3 (balance_after can drift under a
     race that get_balance() itself would never notice, since
     get_balance() only re-sums, it never checks the stored intermediate
     values against that sum).
  6. CompanyPlatformFeeEntry balance integrity: identical walk, per company
     (this ledger has no technician dimension).
  7. Orphan FinancialBackfillTask: a PENDING/PROCESSING task whose invoice
     AND payment FKs are both NULL — every existing retry handler in
     services_backfill.py dispatches by looking up task.invoice or
     task.payment, so a task with neither can never be processed by any
     existing recovery path.
  8. Blocked AdjustmentDocument detection: an APPROVED AdjustmentDocument
     that — if RefundExecutionService.execute() were called on it right
     now — would raise RefundExecutionBlockedError, per the exact three
     conditions that service already enforces (Sprint 5, unmodified):
     document_type != FULL_REFUND, EscrowRecord already SETTLED/CLOSED, or
     the technician wage was direct-split. This lets an operator see every
     "stuck, cannot proceed without a Product Owner decision" document
     without ever attempting execution — this is the BLOCKED severity's
     primary use in this module, and it is a pure read (it re-checks the
     same conditions RefundExecutionService._validate_safe_scope() already
     enforces, independently, never by calling that service).

SEVERITY LEVELS:
  OK       — checked, no issue found (only emitted by the aggregate report
             summary, never as an individual issue — there is nothing to
             report about an OK record).
  WARNING  — a state that may be entirely normal and resolve itself soon
             (e.g. a DISTRIBUTED escrow not yet claimed by a settlement
             batch), surfaced for visibility, not because it is wrong.
  ERROR    — a genuine data inconsistency that should not exist under any
             correct execution of the existing, already-merged services.
  BLOCKED  — a record whose correct next step is known but cannot be taken
             because it depends on an unresolved Product Owner decision
             (an Open Issue) — never invented policy, always reported.

DETERMINISM:
  Every check function returns a list built by iterating querysets with an
  explicit .order_by(), and the aggregate report sorts its combined issue
  list by (code, model, object_id) before returning — so two calls against
  unchanged data always produce byte-for-byte identical, identically
  ordered output.

TENANT ISOLATION:
  Every single query in this module is explicitly filtered by `company=`
  — even in places where a FK chain would already guarantee correct
  scoping — as a defensive, redundant guarantee, matching the same
  discipline already used throughout services_settlement_calculator.py
  and services_settlement_planner.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ReconciliationSeverity(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    BLOCKED = "blocked"


class IssueCode(str, Enum):
    """
    Stable, permanent, language-independent identifiers for every
    reconciliation issue this service can report.

    CONTRACT (must never be violated):
      - A code, once assigned, keeps its exact meaning forever. It must
        never be reassigned, renumbered, or reused for a different check,
        even if that check's logic or wording changes later.
      - A code never depends on language. The `message` on a
        ReconciliationIssue is free text and may be translated (e.g. into
        Persian) in the future without affecting `code` in any way.
      - New issue types always receive the next unused FIN-XXXX number;
        existing numbers are append-only and never rearranged.
      - `.name` (e.g. "INVOICE_PAID_WITHOUT_PAYMENT") is a human-readable
        mnemonic kept for debugging and log readability. It is informative
        only — the canonical, contractual identifier is `.value`
        (e.g. "FIN-0001").
    """

    INVOICE_PAID_WITHOUT_PAYMENT = "FIN-0001"
    DUPLICATE_PAID_PAYMENT = "FIN-0002"
    PAYMENT_INVOICE_AMOUNT_MISMATCH = "FIN-0003"
    INVOICE_PAID_WITHOUT_ESCROW = "FIN-0004"
    ESCROW_DISTRIBUTED_WITHOUT_SETTLEMENT_ITEM = "FIN-0005"
    ESCROW_SETTLEMENT_LINK_MISSING = "FIN-0006"
    ESCROW_SETTLEMENT_ITEM_MISSING = "FIN-0007"
    SETTLEMENT_ITEM_ORPHAN_SOURCE = "FIN-0008"
    TECHNICIAN_LEDGER_BALANCE_MISMATCH = "FIN-0009"
    PLATFORM_FEE_BALANCE_MISMATCH = "FIN-0010"
    ORPHAN_BACKFILL_TASK = "FIN-0011"
    ADJUSTMENT_BLOCKED_UNSUPPORTED_TYPE = "FIN-0012"
    ADJUSTMENT_BLOCKED_AFTER_SETTLEMENT = "FIN-0013"
    ADJUSTMENT_BLOCKED_DIRECT_SPLIT = "FIN-0014"


@dataclass(frozen=True)
class ReconciliationIssue:
    """
    One machine-readable finding. Never represents a write — detection only.

    `code` is the stable, permanent, language-independent identifier
    (e.g. "FIN-0001") — see IssueCode above. This is the field external
    consumers should key off of; it will never change meaning.

    `code_name` is the human-readable mnemonic (e.g.
    "INVOICE_PAID_WITHOUT_PAYMENT") kept purely for log/debug readability.

    `message` is a free-text explanation and may be translated in the
    future without affecting either code field.
    """

    severity: ReconciliationSeverity
    code: str
    code_name: str
    model: str
    object_id: Optional[int]
    company_id: int
    message: str


@dataclass(frozen=True)
class ReconciliationReport:
    """Aggregate, deterministically-ordered result of a full company reconciliation."""

    company_id: int
    issues: tuple[ReconciliationIssue, ...]

    @property
    def is_clean(self) -> bool:
        """True only if zero issues of any severity were found."""
        return len(self.issues) == 0

    @property
    def has_errors(self) -> bool:
        return any(i.severity == ReconciliationSeverity.ERROR for i in self.issues)

    @property
    def has_blocked(self) -> bool:
        return any(i.severity == ReconciliationSeverity.BLOCKED for i in self.issues)

    def by_severity(self, severity: ReconciliationSeverity) -> tuple[ReconciliationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == severity)


def _sort_key(issue: ReconciliationIssue):
    return (issue.code, issue.model, issue.object_id or 0)


class FinancialReconciliationService:
    """
    Read-only reconciliation checks. Every method is a @staticmethod with
    no side effects — see the module docstring's hard-scope statement.
    """

    # ------------------------------------------------------------------
    # 1. Payment <-> Invoice
    # ------------------------------------------------------------------

    @staticmethod
    def check_payment_invoice_consistency(company) -> list[ReconciliationIssue]:
        from apps.invoices.models import Invoice
        from apps.payments.models import Payment

        issues: list[ReconciliationIssue] = []

        paid_invoices = Invoice.objects.filter(
            company=company, status=Invoice.Status.PAID,
        ).order_by("id")
        for invoice in paid_invoices:
            paid_payments = list(
                Payment.objects.filter(
                    company=company, invoice=invoice, status=Payment.Status.PAID,
                ).order_by("id")
            )
            if not paid_payments:
                issues.append(ReconciliationIssue(
                    severity=ReconciliationSeverity.ERROR,
                    code=IssueCode.INVOICE_PAID_WITHOUT_PAYMENT.value,
                    code_name=IssueCode.INVOICE_PAID_WITHOUT_PAYMENT.name,
                    model="Invoice",
                    object_id=invoice.id,
                    company_id=company.id,
                    message=(
                        f"Invoice #{invoice.id} ({invoice.invoice_number}) has status "
                        "PAID but no Payment row with status PAID exists for it."
                    ),
                ))
                continue

            if len(paid_payments) > 1:
                issues.append(ReconciliationIssue(
                    severity=ReconciliationSeverity.ERROR,
                    code=IssueCode.DUPLICATE_PAID_PAYMENT.value,
                    code_name=IssueCode.DUPLICATE_PAID_PAYMENT.name,
                    model="Invoice",
                    object_id=invoice.id,
                    company_id=company.id,
                    message=(
                        f"Invoice #{invoice.id} ({invoice.invoice_number}) has "
                        f"{len(paid_payments)} Payment rows with status PAID; "
                        "expected exactly one."
                    ),
                ))

            for payment in paid_payments:
                if int(payment.amount) != int(invoice.total_amount):
                    issues.append(ReconciliationIssue(
                        severity=ReconciliationSeverity.ERROR,
                        code=IssueCode.PAYMENT_INVOICE_AMOUNT_MISMATCH.value,
                        code_name=IssueCode.PAYMENT_INVOICE_AMOUNT_MISMATCH.name,
                        model="Payment",
                        object_id=payment.id,
                        company_id=company.id,
                        message=(
                            f"Payment #{payment.id} amount ({int(payment.amount)}) does "
                            f"not equal Invoice #{invoice.id}'s total_amount "
                            f"({int(invoice.total_amount)})."
                        ),
                    ))

        return issues

    # ------------------------------------------------------------------
    # 2. Invoice <-> EscrowRecord
    # ------------------------------------------------------------------

    @staticmethod
    def check_invoice_escrow_consistency(company) -> list[ReconciliationIssue]:
        from apps.invoices.models import Invoice
        from apps.payments.models import Payment, PaymentGateway
        from .models import EscrowRecord

        issues: list[ReconciliationIssue] = []

        paid_invoices = Invoice.objects.filter(
            company=company, status=Invoice.Status.PAID,
        ).order_by("id")
        for invoice in paid_invoices:
            platform_payment = Payment.objects.filter(
                company=company, invoice=invoice, status=Payment.Status.PAID,
                gateway__owner_type=PaymentGateway.OwnerType.PLATFORM,
            ).order_by("id").first()
            if platform_payment is None:
                # Cash/manual/company-gateway invoice — no escrow was ever
                # expected for it (matches EscrowRecordService.is_eligible_
                # for_escrow()'s own gate). Correctly not an issue.
                continue

            escrow_exists = EscrowRecord.objects.filter(
                company=company, payment=platform_payment,
            ).exists()
            if not escrow_exists:
                issues.append(ReconciliationIssue(
                    severity=ReconciliationSeverity.ERROR,
                    code=IssueCode.INVOICE_PAID_WITHOUT_ESCROW.value,
                    code_name=IssueCode.INVOICE_PAID_WITHOUT_ESCROW.name,
                    model="Invoice",
                    object_id=invoice.id,
                    company_id=company.id,
                    message=(
                        f"Invoice #{invoice.id} ({invoice.invoice_number}) was paid via "
                        f"platform gateway Payment #{platform_payment.id}, but no "
                        "EscrowRecord exists for that payment."
                    ),
                ))

        return issues

    # ------------------------------------------------------------------
    # 3. EscrowRecord <-> SettlementBatch / SettlementItem
    # ------------------------------------------------------------------

    @staticmethod
    def check_escrow_settlement_consistency(company) -> list[ReconciliationIssue]:
        from .models import EscrowRecord, SettlementItem

        issues: list[ReconciliationIssue] = []

        relevant_statuses = [
            EscrowRecord.Status.DISTRIBUTED,
            EscrowRecord.Status.PENDING_SETTLEMENT,
            EscrowRecord.Status.SETTLED,
        ]
        escrows = EscrowRecord.objects.filter(
            company=company, status__in=relevant_statuses,
        ).order_by("id")

        for escrow in escrows:
            has_item = (
                escrow.invoice_id is not None
                and SettlementItem.objects.filter(
                    company=company, invoice_id=escrow.invoice_id,
                ).exists()
            )

            if escrow.status == EscrowRecord.Status.DISTRIBUTED:
                if not has_item and escrow.settlement_batch_id is None:
                    issues.append(ReconciliationIssue(
                        severity=ReconciliationSeverity.WARNING,
                        code=IssueCode.ESCROW_DISTRIBUTED_WITHOUT_SETTLEMENT_ITEM.value,
                        code_name=IssueCode.ESCROW_DISTRIBUTED_WITHOUT_SETTLEMENT_ITEM.name,
                        model="EscrowRecord",
                        object_id=escrow.id,
                        company_id=company.id,
                        message=(
                            f"EscrowRecord #{escrow.id} is DISTRIBUTED but has not yet "
                            "been claimed by any SettlementBatch/SettlementItem. This "
                            "may simply be awaiting its next settlement cycle."
                        ),
                    ))
                continue

            # PENDING_SETTLEMENT or SETTLED assert that linkage already
            # happened — missing linkage here is a genuine inconsistency,
            # not merely "not yet settled".
            if escrow.settlement_batch_id is None:
                issues.append(ReconciliationIssue(
                    severity=ReconciliationSeverity.ERROR,
                    code=IssueCode.ESCROW_SETTLEMENT_LINK_MISSING.value,
                    code_name=IssueCode.ESCROW_SETTLEMENT_LINK_MISSING.name,
                    model="EscrowRecord",
                    object_id=escrow.id,
                    company_id=company.id,
                    message=(
                        f"EscrowRecord #{escrow.id} has status '{escrow.status}' but "
                        "settlement_batch is not set."
                    ),
                ))
            elif not has_item:
                issues.append(ReconciliationIssue(
                    severity=ReconciliationSeverity.ERROR,
                    code=IssueCode.ESCROW_SETTLEMENT_ITEM_MISSING.value,
                    code_name=IssueCode.ESCROW_SETTLEMENT_ITEM_MISSING.name,
                    model="EscrowRecord",
                    object_id=escrow.id,
                    company_id=company.id,
                    message=(
                        f"EscrowRecord #{escrow.id} has status '{escrow.status}' and "
                        f"settlement_batch #{escrow.settlement_batch_id} set, but no "
                        "matching SettlementItem exists for its invoice."
                    ),
                ))

        return issues

    # ------------------------------------------------------------------
    # 4. SettlementItem source integrity
    # ------------------------------------------------------------------

    @staticmethod
    def check_settlement_item_integrity(company) -> list[ReconciliationIssue]:
        from .models import SettlementItem

        issues: list[ReconciliationIssue] = []

        orphans = SettlementItem.objects.filter(
            company=company,
            invoice__isnull=True,
            ledger_entry__isnull=True,
            platform_fee_entry__isnull=True,
        ).order_by("id")
        for item in orphans:
            issues.append(ReconciliationIssue(
                severity=ReconciliationSeverity.ERROR,
                code=IssueCode.SETTLEMENT_ITEM_ORPHAN_SOURCE.value,
                code_name=IssueCode.SETTLEMENT_ITEM_ORPHAN_SOURCE.name,
                model="SettlementItem",
                object_id=item.id,
                company_id=company.id,
                message=(
                    f"SettlementItem #{item.id} (batch #{item.batch_id}) has no "
                    "invoice, ledger_entry, or platform_fee_entry — every source "
                    "reference has been lost (each uses on_delete=SET_NULL), so "
                    "this item can no longer be traced to what it represents."
                ),
            ))

        return issues

    # ------------------------------------------------------------------
    # 5. TechnicianLedgerEntry balance integrity
    # ------------------------------------------------------------------

    @staticmethod
    def check_technician_ledger_balances(company) -> list[ReconciliationIssue]:
        from .models import TechnicianLedgerEntry

        issues: list[ReconciliationIssue] = []

        technician_ids = (
            TechnicianLedgerEntry.objects.filter(company=company)
            .order_by("technician_id")
            .values_list("technician_id", flat=True)
            .distinct()
        )

        for technician_id in technician_ids:
            entries = TechnicianLedgerEntry.objects.filter(
                company=company, technician_id=technician_id,
            ).order_by("created_at", "id")

            running_balance = 0
            for entry in entries:
                if entry.entry_type == TechnicianLedgerEntry.EntryType.CREDIT:
                    running_balance += int(entry.amount_rial)
                else:
                    running_balance -= int(entry.amount_rial)

                if running_balance != int(entry.balance_after):
                    issues.append(ReconciliationIssue(
                        severity=ReconciliationSeverity.ERROR,
                        code=IssueCode.TECHNICIAN_LEDGER_BALANCE_MISMATCH.value,
                        code_name=IssueCode.TECHNICIAN_LEDGER_BALANCE_MISMATCH.name,
                        model="TechnicianLedgerEntry",
                        object_id=entry.id,
                        company_id=company.id,
                        message=(
                            f"TechnicianLedgerEntry #{entry.id} (technician "
                            f"#{technician_id}): recomputed running balance "
                            f"({running_balance}) does not equal the entry's stored "
                            f"balance_after ({int(entry.balance_after)})."
                        ),
                    ))
                    # Do not break — a caller may want visibility into every
                    # entry from the first drift point onward, and each is
                    # independently useful for manual investigation.

        return issues

    # ------------------------------------------------------------------
    # 6. CompanyPlatformFeeEntry balance integrity
    # ------------------------------------------------------------------

    @staticmethod
    def check_platform_fee_balances(company) -> list[ReconciliationIssue]:
        from .models import CompanyPlatformFeeEntry

        issues: list[ReconciliationIssue] = []

        entries = CompanyPlatformFeeEntry.objects.filter(
            company=company,
        ).order_by("created_at", "id")

        running_balance = 0
        for entry in entries:
            if entry.entry_type == CompanyPlatformFeeEntry.EntryType.DEBIT:
                running_balance += int(entry.amount_rial)
            else:
                running_balance -= int(entry.amount_rial)

            if running_balance != int(entry.balance_after):
                issues.append(ReconciliationIssue(
                    severity=ReconciliationSeverity.ERROR,
                    code=IssueCode.PLATFORM_FEE_BALANCE_MISMATCH.value,
                    code_name=IssueCode.PLATFORM_FEE_BALANCE_MISMATCH.name,
                    model="CompanyPlatformFeeEntry",
                    object_id=entry.id,
                    company_id=company.id,
                    message=(
                        f"CompanyPlatformFeeEntry #{entry.id}: recomputed running "
                        f"balance ({running_balance}) does not equal the entry's "
                        f"stored balance_after ({int(entry.balance_after)})."
                    ),
                ))

        return issues

    # ------------------------------------------------------------------
    # 7. Orphan FinancialBackfillTask
    # ------------------------------------------------------------------

    @staticmethod
    def check_orphan_backfill_tasks(company) -> list[ReconciliationIssue]:
        from .models import FinancialBackfillTask

        issues: list[ReconciliationIssue] = []

        orphans = FinancialBackfillTask.objects.filter(
            company=company,
            status__in=[
                FinancialBackfillTask.Status.PENDING,
                FinancialBackfillTask.Status.PROCESSING,
            ],
            invoice__isnull=True,
            payment__isnull=True,
        ).order_by("id")
        for task in orphans:
            issues.append(ReconciliationIssue(
                severity=ReconciliationSeverity.WARNING,
                code=IssueCode.ORPHAN_BACKFILL_TASK.value,
                code_name=IssueCode.ORPHAN_BACKFILL_TASK.name,
                model="FinancialBackfillTask",
                object_id=task.id,
                company_id=company.id,
                message=(
                    f"FinancialBackfillTask #{task.id} (type={task.task_type}, "
                    f"status={task.status}) has neither an invoice nor a payment "
                    "reference — no existing retry handler can ever resolve it."
                ),
            ))

        return issues

    # ------------------------------------------------------------------
    # 8. Blocked AdjustmentDocument detection (read-only re-check of
    #    RefundExecutionService's own blocking conditions — never calls it)
    # ------------------------------------------------------------------

    @staticmethod
    def check_blocked_adjustment_documents(company) -> list[ReconciliationIssue]:
        from .models import AdjustmentDocument, EscrowRecord, PaymentSplitSnapshot

        issues: list[ReconciliationIssue] = []

        approved_documents = AdjustmentDocument.objects.filter(
            company=company, status=AdjustmentDocument.Status.APPROVED,
        ).order_by("id")

        for document in approved_documents:
            if document.document_type != AdjustmentDocument.DocumentType.FULL_REFUND:
                issues.append(ReconciliationIssue(
                    severity=ReconciliationSeverity.BLOCKED,
                    code=IssueCode.ADJUSTMENT_BLOCKED_UNSUPPORTED_TYPE.value,
                    code_name=IssueCode.ADJUSTMENT_BLOCKED_UNSUPPORTED_TYPE.name,
                    model="AdjustmentDocument",
                    object_id=document.id,
                    company_id=company.id,
                    message=(
                        f"AdjustmentDocument #{document.id} is APPROVED with "
                        f"document_type='{document.document_type}', which "
                        "RefundExecutionService does not execute "
                        "([OPEN-ISSUE: OI-07] — proportionality/direction not "
                        "yet decided by the Product Owner)."
                    ),
                ))
                continue

            invoice = document.original_invoice
            escrow = (
                EscrowRecord.objects.filter(company=company, invoice=invoice)
                .order_by("-held_at")
                .first()
            )
            if escrow is not None and escrow.status in (
                EscrowRecord.Status.SETTLED, EscrowRecord.Status.CLOSED,
            ):
                issues.append(ReconciliationIssue(
                    severity=ReconciliationSeverity.BLOCKED,
                    code=IssueCode.ADJUSTMENT_BLOCKED_AFTER_SETTLEMENT.value,
                    code_name=IssueCode.ADJUSTMENT_BLOCKED_AFTER_SETTLEMENT.name,
                    model="AdjustmentDocument",
                    object_id=document.id,
                    company_id=company.id,
                    message=(
                        f"AdjustmentDocument #{document.id} (invoice #{invoice.id}) "
                        f"cannot be executed: EscrowRecord #{escrow.id} has already "
                        f"reached '{escrow.status}' "
                        "([OPEN-ISSUE: OI-07] — no approved after-settlement refund "
                        "mechanism exists)."
                    ),
                ))
                continue

            if escrow is not None:
                snapshot = PaymentSplitSnapshot.objects.filter(
                    company=company, payment=escrow.payment,
                ).first()
                if snapshot is not None and snapshot.should_split_with_technician:
                    issues.append(ReconciliationIssue(
                        severity=ReconciliationSeverity.BLOCKED,
                        code=IssueCode.ADJUSTMENT_BLOCKED_DIRECT_SPLIT.value,
                        code_name=IssueCode.ADJUSTMENT_BLOCKED_DIRECT_SPLIT.name,
                        model="AdjustmentDocument",
                        object_id=document.id,
                        company_id=company.id,
                        message=(
                            f"AdjustmentDocument #{document.id} (invoice #{invoice.id}) "
                            "cannot be executed: the technician wage was paid via "
                            "direct gateway split "
                            "([OPEN-ISSUE: OI-04]/[OI-07] — no approved provider-debt "
                            "formula exists for this case)."
                        ),
                    ))

        return issues

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    @staticmethod
    def reconcile_company(company) -> ReconciliationReport:
        """
        Run every check for one company and return a single, deterministically
        ordered report. Never writes anything — purely composes the
        individual check methods above.
        """
        all_issues: list[ReconciliationIssue] = []
        all_issues.extend(FinancialReconciliationService.check_payment_invoice_consistency(company))
        all_issues.extend(FinancialReconciliationService.check_invoice_escrow_consistency(company))
        all_issues.extend(FinancialReconciliationService.check_escrow_settlement_consistency(company))
        all_issues.extend(FinancialReconciliationService.check_settlement_item_integrity(company))
        all_issues.extend(FinancialReconciliationService.check_technician_ledger_balances(company))
        all_issues.extend(FinancialReconciliationService.check_platform_fee_balances(company))
        all_issues.extend(FinancialReconciliationService.check_orphan_backfill_tasks(company))
        all_issues.extend(FinancialReconciliationService.check_blocked_adjustment_documents(company))

        all_issues.sort(key=_sort_key)

        return ReconciliationReport(
            company_id=company.id,
            issues=tuple(all_issues),
        )
