"""
Payouts — Financial Closing Engine (Sprint 7, read-only control layer).

Evaluates whether a company's financial period can be safely closed.
Returns a structured result with blocking issues, warnings, and summaries
derived from already-persisted financial records.

HARD SCOPE, PER EXPLICIT INSTRUCTION:
  - Every function in this module is read-only. No .save(), .create(),
    .update(), .delete() call exists anywhere in this file.
  - Never mutates Invoice, Payment, EscrowRecord, SettlementBatch,
    SettlementItem, AdjustmentDocument, TechnicianLedgerEntry,
    CompanyPlatformFeeEntry, or FinancialBackfillTask.
  - No UI, no API, no management command, no dashboard, no docs.
  - Reuses Sprint 6 FinancialReconciliationService for reconciliation
    state — never duplicates reconciliation logic.
  - Durable period locking returns NOT_IMPLEMENTED because no
    FinancialPeriod or PeriodLock model exists in the codebase.

CALLABLE BY:
  Tests only (for now). Not wired into any production flow.

DETERMINISM:
  The evaluate() method produces identical output for identical data.
  All queries use explicit .order_by() and results are sorted.

TENANT ISOLATION:
  Every query is explicitly filtered by company=.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ClosingStatus(str, Enum):
    """Possible outcomes of a financial period closing evaluation."""

    CAN_CLOSE = "can_close"
    BLOCKED = "blocked"
    WARNING = "warning"
    ALREADY_CLOSED = "already_closed"
    NOT_IMPLEMENTED = "not_implemented"


class BlockingReason(str, Enum):
    """Machine-readable reasons why a period cannot be closed."""

    RECONCILIATION_ERROR = "reconciliation_error"
    RECONCILIATION_BLOCKED = "reconciliation_blocked"
    PENDING_BACKFILL_TASK = "pending_backfill_task"
    SETTLEMENT_BATCH_IN_PROGRESS = "settlement_batch_in_progress"
    PENDING_ADJUSTMENT_DOCUMENT = "pending_adjustment_document"
    OPEN_ESCROW_RECORD = "open_escrow_record"
    INVALID_INVOICE_FINANCIAL_STATE = "invalid_invoice_financial_state"


@dataclass(frozen=True)
class ClosingBlockingIssue:
    """One machine-readable blocking issue preventing period closure."""

    reason: BlockingReason
    model: str
    object_id: Optional[int]
    message: str


@dataclass(frozen=True)
class ClosingWarning:
    """One machine-readable warning (does not block, but noteworthy)."""

    reason: str
    model: str
    object_id: Optional[int]
    message: str


@dataclass(frozen=True)
class ReconciliationSummary:
    """Summary of reconciliation state for the evaluated period."""

    total_issues: int
    errors: int
    warnings: int
    blocked: int
    is_clean: bool


@dataclass(frozen=True)
class SettlementSummary:
    """Summary of settlement batch state within the period."""

    total_batches: int
    calculating: int
    ready: int
    executing: int
    completed: int
    failed: int


@dataclass(frozen=True)
class RefundAdjustmentSummary:
    """Summary of adjustment document state within the period."""

    total_documents: int
    draft: int
    pending_approval: int
    approved: int
    applied: int
    rejected: int
    cancelled: int


@dataclass(frozen=True)
class ClosingEvaluationResult:
    """
    Complete structured result of a financial period closing evaluation.

    This is the single return value from FinancialClosingEngine.evaluate().
    """

    company_id: int
    period_start: datetime
    period_end: datetime
    status: ClosingStatus
    blocking_issues: tuple[ClosingBlockingIssue, ...]
    warnings: tuple[ClosingWarning, ...]
    reconciliation_summary: ReconciliationSummary
    settlement_summary: SettlementSummary
    refund_adjustment_summary: RefundAdjustmentSummary
    durable_period_lock_status: ClosingStatus


def _blocking_sort_key(issue: ClosingBlockingIssue):
    return (issue.reason.value, issue.model, issue.object_id or 0)


def _warning_sort_key(warning: ClosingWarning):
    return (warning.reason, warning.model, warning.object_id or 0)


class FinancialClosingEngine:
    """
    Read-only financial period closing evaluation engine.

    Determines whether a company's financial period can be closed by
    checking all subsystems for unresolved/in-progress work. Never
    mutates any data.

    Usage:
        result = FinancialClosingEngine.evaluate(
            company=company,
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 31, 23, 59, 59),
        )
        if result.status == ClosingStatus.CAN_CLOSE:
            ...  # safe to close
    """

    @staticmethod
    def evaluate(
        company,
        period_start: datetime,
        period_end: datetime,
    ) -> ClosingEvaluationResult:
        """
        Evaluate whether the given financial period can be closed.

        This method is entirely read-only. It queries the database to
        gather state, delegates reconciliation to Sprint 6's
        FinancialReconciliationService, and returns a structured result.

        Args:
            company: The Company instance to evaluate.
            period_start: Start of the financial period (inclusive).
            period_end: End of the financial period (inclusive).

        Returns:
            ClosingEvaluationResult with status, blocking issues,
            warnings, and summaries.
        """
        blocking_issues: list[ClosingBlockingIssue] = []
        warnings: list[ClosingWarning] = []

        # --- 1. Reconciliation (delegate to Sprint 6) ---
        reconciliation_summary = FinancialClosingEngine._check_reconciliation(
            company, blocking_issues, warnings,
        )

        # --- 2. Pending FinancialBackfillTask ---
        FinancialClosingEngine._check_pending_backfill_tasks(
            company, period_start, period_end, blocking_issues,
        )

        # --- 3. In-progress SettlementBatch ---
        settlement_summary = FinancialClosingEngine._check_settlement_batches(
            company, period_start, period_end, blocking_issues,
        )

        # --- 4. Pending AdjustmentDocument ---
        refund_adjustment_summary = FinancialClosingEngine._check_adjustment_documents(
            company, period_start, period_end, blocking_issues,
        )

        # --- 5. Open EscrowRecord ---
        FinancialClosingEngine._check_open_escrow_records(
            company, period_start, period_end, blocking_issues,
        )

        # --- 6. Paid invoices with invalid financial state ---
        FinancialClosingEngine._check_invoice_financial_state(
            company, period_start, period_end, blocking_issues,
        )

        # --- 7. Durable period lock (NOT_IMPLEMENTED) ---
        durable_period_lock_status = ClosingStatus.NOT_IMPLEMENTED

        # --- Determine overall status ---
        blocking_issues.sort(key=_blocking_sort_key)
        warnings.sort(key=_warning_sort_key)

        if blocking_issues:
            status = ClosingStatus.BLOCKED
        elif warnings:
            status = ClosingStatus.WARNING
        else:
            status = ClosingStatus.CAN_CLOSE

        return ClosingEvaluationResult(
            company_id=company.id,
            period_start=period_start,
            period_end=period_end,
            status=status,
            blocking_issues=tuple(blocking_issues),
            warnings=tuple(warnings),
            reconciliation_summary=reconciliation_summary,
            settlement_summary=settlement_summary,
            refund_adjustment_summary=refund_adjustment_summary,
            durable_period_lock_status=durable_period_lock_status,
        )

    # ------------------------------------------------------------------
    # Internal check methods (all read-only, all static)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_reconciliation(
        company,
        blocking_issues: list[ClosingBlockingIssue],
        warnings: list[ClosingWarning],
    ) -> ReconciliationSummary:
        """
        Run Sprint 6 reconciliation and interpret its result.
        Adds blocking issues for ERROR and BLOCKED severities.
        """
        from apps.payouts.services_reconciliation import (
            FinancialReconciliationService,
            ReconciliationSeverity,
        )

        report = FinancialReconciliationService.reconcile_company(company)

        errors = len(report.by_severity(ReconciliationSeverity.ERROR))
        warns = len(report.by_severity(ReconciliationSeverity.WARNING))
        blocked = len(report.by_severity(ReconciliationSeverity.BLOCKED))

        # ERROR-severity reconciliation issues block closing
        for issue in report.by_severity(ReconciliationSeverity.ERROR):
            blocking_issues.append(ClosingBlockingIssue(
                reason=BlockingReason.RECONCILIATION_ERROR,
                model=issue.model,
                object_id=issue.object_id,
                message=f"Reconciliation {issue.code}: {issue.message}",
            ))

        # BLOCKED-severity reconciliation issues block closing
        for issue in report.by_severity(ReconciliationSeverity.BLOCKED):
            blocking_issues.append(ClosingBlockingIssue(
                reason=BlockingReason.RECONCILIATION_BLOCKED,
                model=issue.model,
                object_id=issue.object_id,
                message=f"Reconciliation {issue.code}: {issue.message}",
            ))

        # WARNING-severity reconciliation issues become warnings (non-blocking)
        for issue in report.by_severity(ReconciliationSeverity.WARNING):
            warnings.append(ClosingWarning(
                reason=f"reconciliation_warning:{issue.code}",
                model=issue.model,
                object_id=issue.object_id,
                message=f"Reconciliation {issue.code}: {issue.message}",
            ))

        return ReconciliationSummary(
            total_issues=len(report.issues),
            errors=errors,
            warnings=warns,
            blocked=blocked,
            is_clean=report.is_clean,
        )

    @staticmethod
    def _check_pending_backfill_tasks(
        company,
        period_start: datetime,
        period_end: datetime,
        blocking_issues: list[ClosingBlockingIssue],
    ) -> None:
        """
        Check for PENDING or PROCESSING FinancialBackfillTask within the period.
        Any such task blocks closing.
        """
        from apps.payouts.models import FinancialBackfillTask

        pending_tasks = FinancialBackfillTask.objects.filter(
            company=company,
            status__in=[
                FinancialBackfillTask.Status.PENDING,
                FinancialBackfillTask.Status.PROCESSING,
            ],
            created_at__gte=period_start,
            created_at__lte=period_end,
        ).order_by("id")

        for task in pending_tasks:
            blocking_issues.append(ClosingBlockingIssue(
                reason=BlockingReason.PENDING_BACKFILL_TASK,
                model="FinancialBackfillTask",
                object_id=task.id,
                message=(
                    f"FinancialBackfillTask #{task.id} (type={task.task_type}, "
                    f"status={task.status}) is unresolved within the period."
                ),
            ))

    @staticmethod
    def _check_settlement_batches(
        company,
        period_start: datetime,
        period_end: datetime,
        blocking_issues: list[ClosingBlockingIssue],
    ) -> SettlementSummary:
        """
        Check for SettlementBatch with status CALCULATING, READY, or
        EXECUTING within the period. These block closing.
        Also builds the settlement summary.
        """
        from apps.payouts.models import SettlementBatch

        batches_in_period = SettlementBatch.objects.filter(
            company=company,
            period_start__lte=period_end,
            period_end__gte=period_start,
        ).order_by("id")

        calculating = 0
        ready = 0
        executing = 0
        completed = 0
        failed = 0

        blocking_statuses = {
            SettlementBatch.Status.CALCULATING,
            SettlementBatch.Status.READY,
            SettlementBatch.Status.EXECUTING,
        }

        for batch in batches_in_period:
            if batch.status == SettlementBatch.Status.CALCULATING:
                calculating += 1
            elif batch.status == SettlementBatch.Status.READY:
                ready += 1
            elif batch.status == SettlementBatch.Status.EXECUTING:
                executing += 1
            elif batch.status == SettlementBatch.Status.COMPLETED:
                completed += 1
            elif batch.status == SettlementBatch.Status.FAILED:
                failed += 1

            if batch.status in blocking_statuses:
                blocking_issues.append(ClosingBlockingIssue(
                    reason=BlockingReason.SETTLEMENT_BATCH_IN_PROGRESS,
                    model="SettlementBatch",
                    object_id=batch.id,
                    message=(
                        f"SettlementBatch #{batch.id} has status '{batch.status}' "
                        f"and overlaps with the closing period."
                    ),
                ))

        total = calculating + ready + executing + completed + failed

        return SettlementSummary(
            total_batches=total,
            calculating=calculating,
            ready=ready,
            executing=executing,
            completed=completed,
            failed=failed,
        )

    @staticmethod
    def _check_adjustment_documents(
        company,
        period_start: datetime,
        period_end: datetime,
        blocking_issues: list[ClosingBlockingIssue],
    ) -> RefundAdjustmentSummary:
        """
        Check for AdjustmentDocument with status DRAFT, PENDING_APPROVAL,
        or APPROVED within the period. These block closing.
        Also builds the refund/adjustment summary.
        """
        from apps.payouts.models import AdjustmentDocument

        documents_in_period = AdjustmentDocument.objects.filter(
            company=company,
            created_at__gte=period_start,
            created_at__lte=period_end,
        ).order_by("id")

        draft = 0
        pending_approval = 0
        approved = 0
        applied = 0
        rejected = 0
        cancelled = 0

        blocking_statuses = {
            AdjustmentDocument.Status.DRAFT,
            AdjustmentDocument.Status.PENDING_APPROVAL,
            AdjustmentDocument.Status.APPROVED,
        }

        for doc in documents_in_period:
            if doc.status == AdjustmentDocument.Status.DRAFT:
                draft += 1
            elif doc.status == AdjustmentDocument.Status.PENDING_APPROVAL:
                pending_approval += 1
            elif doc.status == AdjustmentDocument.Status.APPROVED:
                approved += 1
            elif doc.status == AdjustmentDocument.Status.APPLIED:
                applied += 1
            elif doc.status == AdjustmentDocument.Status.REJECTED:
                rejected += 1
            elif doc.status == AdjustmentDocument.Status.CANCELLED:
                cancelled += 1

            if doc.status in blocking_statuses:
                blocking_issues.append(ClosingBlockingIssue(
                    reason=BlockingReason.PENDING_ADJUSTMENT_DOCUMENT,
                    model="AdjustmentDocument",
                    object_id=doc.id,
                    message=(
                        f"AdjustmentDocument #{doc.id} (type={doc.document_type}, "
                        f"status={doc.status}) is unresolved within the period."
                    ),
                ))

        total = draft + pending_approval + approved + applied + rejected + cancelled

        return RefundAdjustmentSummary(
            total_documents=total,
            draft=draft,
            pending_approval=pending_approval,
            approved=approved,
            applied=applied,
            rejected=rejected,
            cancelled=cancelled,
        )

    @staticmethod
    def _check_open_escrow_records(
        company,
        period_start: datetime,
        period_end: datetime,
        blocking_issues: list[ClosingBlockingIssue],
    ) -> None:
        """
        Check for EscrowRecord with open status (HELD, RESERVED,
        DISTRIBUTED, PENDING_SETTLEMENT) for invoices paid within the period.
        These block closing.
        """
        from apps.payouts.models import EscrowRecord

        open_statuses = [
            EscrowRecord.Status.HELD,
            EscrowRecord.Status.RESERVED,
            EscrowRecord.Status.DISTRIBUTED,
            EscrowRecord.Status.PENDING_SETTLEMENT,
        ]

        open_escrows = EscrowRecord.objects.filter(
            company=company,
            status__in=open_statuses,
            held_at__gte=period_start,
            held_at__lte=period_end,
        ).order_by("id")

        for escrow in open_escrows:
            blocking_issues.append(ClosingBlockingIssue(
                reason=BlockingReason.OPEN_ESCROW_RECORD,
                model="EscrowRecord",
                object_id=escrow.id,
                message=(
                    f"EscrowRecord #{escrow.id} has open status '{escrow.status}' "
                    f"within the closing period."
                ),
            ))

    @staticmethod
    def _check_invoice_financial_state(
        company,
        period_start: datetime,
        period_end: datetime,
        blocking_issues: list[ClosingBlockingIssue],
    ) -> None:
        """
        Check for paid invoices within the period that have invalid or
        incomplete financial state:
        - PAID invoice with no paid_at timestamp
        - PAID invoice with no PAID Payment and no recognized cash/manual settlement
        """
        from django.db.models import Q

        from apps.invoices.models import Invoice
        from apps.payments.models import Payment

        # Include PAID invoices where:
        # - paid_at falls within the period, OR
        # - paid_at is NULL but the invoice was created within the period
        #   (these are the broken ones we specifically want to catch)
        paid_invoices = Invoice.objects.filter(
            Q(paid_at__gte=period_start, paid_at__lte=period_end)
            | Q(paid_at__isnull=True, created_at__gte=period_start, created_at__lte=period_end),
            company=company,
            status=Invoice.Status.PAID,
        ).order_by("id")

        for invoice in paid_invoices:
            # Check: paid_at must be set
            if invoice.paid_at is None:
                blocking_issues.append(ClosingBlockingIssue(
                    reason=BlockingReason.INVALID_INVOICE_FINANCIAL_STATE,
                    model="Invoice",
                    object_id=invoice.id,
                    message=(
                        f"Invoice #{invoice.id} ({invoice.invoice_number}) is PAID "
                        "but has no paid_at timestamp."
                    ),
                ))
                continue

            # Check: at least one PAID payment must exist
            has_paid_payment = Payment.objects.filter(
                company=company,
                invoice=invoice,
                status=Payment.Status.PAID,
            ).exists()
            if not has_paid_payment:
                # Also check if it was settled via cash/manual (no payment row expected)
                if not invoice.settled_payment_method or invoice.settled_payment_method not in (
                    "cash", "manual", "cash_from_customer",
                ):
                    blocking_issues.append(ClosingBlockingIssue(
                        reason=BlockingReason.INVALID_INVOICE_FINANCIAL_STATE,
                        model="Invoice",
                        object_id=invoice.id,
                        message=(
                            f"Invoice #{invoice.id} ({invoice.invoice_number}) is PAID "
                            "but has no Payment with status PAID and is not a "
                            "cash/manual settlement."
                        ),
                    ))
