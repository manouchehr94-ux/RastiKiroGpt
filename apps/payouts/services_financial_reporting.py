"""
Payouts — Financial Reporting Engine (Sprint 8, read-only reporting layer).

Provides structured, machine-readable financial reports for a company's
financial period. Designed for future dashboard/export/API layers to consume.

HARD SCOPE, PER EXPLICIT INSTRUCTION:
  - Every function in this module is read-only. No .save(), .create(),
    .update(), .delete() call exists anywhere in this file.
  - Never mutates Invoice, Payment, EscrowRecord, SettlementBatch,
    SettlementItem, AdjustmentDocument, TechnicianLedgerEntry,
    CompanyPlatformFeeEntry, or FinancialBackfillTask.
  - No UI, no API, no management command, no dashboard, no docs.
  - Reuses Sprint 6 FinancialReconciliationService for reconciliation.
  - Reuses Sprint 7 FinancialClosingEngine for closing readiness.
  - Does not create accounting records of any kind.

DETERMINISM:
  All queries use explicit .order_by() or aggregate functions.
  Repeated calls against unchanged data produce identical output.

TENANT ISOLATION:
  Every query is explicitly filtered by company=.

PERIOD ISOLATION:
  Every query respects period_start and period_end using stable date fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvoiceSummary:
    """Period invoice summary."""

    total_invoices: int
    paid_invoices: int
    unpaid_invoices: int
    cancelled_invoices: int
    draft_invoices: int
    gross_invoice_amount: Decimal
    paid_amount: Decimal
    unpaid_amount: Decimal


@dataclass(frozen=True)
class PaymentSummary:
    """Period payment summary."""

    total_payments: int
    paid_payments: int
    failed_payments: int
    cancelled_payments: int
    pending_payments: int
    needs_reconciliation_payments: int
    total_paid_amount: Decimal


@dataclass(frozen=True)
class EscrowSummary:
    """Period escrow summary."""

    total_escrows: int
    held_escrows: int
    reserved_escrows: int
    distributed_escrows: int
    pending_settlement_escrows: int
    settled_escrows: int
    closed_escrows: int
    total_held_amount: Decimal
    total_settled_amount: Decimal


@dataclass(frozen=True)
class SettlementReportSummary:
    """Period settlement batch summary."""

    total_batches: int
    calculating_batches: int
    ready_batches: int
    executing_batches: int
    completed_batches: int
    failed_batches: int
    completed_settlement_amount: Decimal
    pending_settlement_amount: Decimal


@dataclass(frozen=True)
class AdjustmentSummary:
    """Period adjustment/refund summary."""

    total_documents: int
    draft_count: int
    pending_approval_count: int
    approved_count: int
    applied_count: int
    rejected_count: int
    cancelled_count: int
    pending_amount: Decimal
    applied_amount: Decimal


@dataclass(frozen=True)
class ReconReportSummary:
    """Reconciliation summary from Sprint 6."""

    total_issues: int
    errors: int
    warnings: int
    blocked: int
    is_clean: bool


@dataclass(frozen=True)
class ClosingReadinessSummary:
    """Closing readiness from Sprint 7."""

    status: str
    blocking_issues_count: int
    warnings_count: int
    durable_lock_status: str


@dataclass(frozen=True)
class FinancialPeriodReport:
    """
    Complete structured financial report for a company period.

    This is the single return value from FinancialReportingService.generate_period_report().
    """

    company_id: int
    period_start: datetime
    period_end: datetime
    invoice_summary: InvoiceSummary
    payment_summary: PaymentSummary
    escrow_summary: EscrowSummary
    settlement_summary: SettlementReportSummary
    adjustment_summary: AdjustmentSummary
    reconciliation_summary: ReconReportSummary
    closing_readiness: ClosingReadinessSummary


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class FinancialReportingService:
    """
    Read-only financial reporting engine. Every method is a @staticmethod
    with no side effects.
    """

    @staticmethod
    def generate_period_report(
        company,
        period_start: datetime,
        period_end: datetime,
    ) -> FinancialPeriodReport:
        """
        Generate a complete financial report for the given company and period.

        This method is entirely read-only. It queries the database to
        gather aggregates, delegates to Sprint 6/7 services, and returns
        a structured result.

        Args:
            company: The Company instance to report on.
            period_start: Start of the reporting period (inclusive).
            period_end: End of the reporting period (inclusive).

        Returns:
            FinancialPeriodReport with all sub-summaries.
        """
        invoice_summary = FinancialReportingService._build_invoice_summary(
            company, period_start, period_end,
        )
        payment_summary = FinancialReportingService._build_payment_summary(
            company, period_start, period_end,
        )
        escrow_summary = FinancialReportingService._build_escrow_summary(
            company, period_start, period_end,
        )
        settlement_summary = FinancialReportingService._build_settlement_summary(
            company, period_start, period_end,
        )
        adjustment_summary = FinancialReportingService._build_adjustment_summary(
            company, period_start, period_end,
        )
        reconciliation_summary = FinancialReportingService._build_reconciliation_summary(
            company,
        )
        closing_readiness = FinancialReportingService._build_closing_readiness(
            company, period_start, period_end,
        )

        return FinancialPeriodReport(
            company_id=company.id,
            period_start=period_start,
            period_end=period_end,
            invoice_summary=invoice_summary,
            payment_summary=payment_summary,
            escrow_summary=escrow_summary,
            settlement_summary=settlement_summary,
            adjustment_summary=adjustment_summary,
            reconciliation_summary=reconciliation_summary,
            closing_readiness=closing_readiness,
        )

    # ------------------------------------------------------------------
    # Internal builders (all read-only, all static)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_invoice_summary(
        company, period_start: datetime, period_end: datetime,
    ) -> InvoiceSummary:
        """Build invoice summary for the period using created_at as period anchor."""
        from django.db.models import Q, Sum

        from apps.invoices.models import Invoice

        base_qs = Invoice.objects.filter(
            company=company,
            created_at__gte=period_start,
            created_at__lte=period_end,
        )

        total = base_qs.count()
        paid = base_qs.filter(status=Invoice.Status.PAID).count()
        cancelled = base_qs.filter(status=Invoice.Status.CANCELLED).count()
        draft = base_qs.filter(status=Invoice.Status.DRAFT).count()
        unpaid = base_qs.filter(
            status__in=[Invoice.Status.ISSUED, Invoice.Status.DRAFT],
        ).count()

        gross_amount = base_qs.aggregate(
            total=Sum("total_amount"),
        )["total"] or Decimal("0")

        paid_amount = base_qs.filter(
            status=Invoice.Status.PAID,
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

        unpaid_amount = base_qs.filter(
            status__in=[Invoice.Status.ISSUED, Invoice.Status.DRAFT],
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

        return InvoiceSummary(
            total_invoices=total,
            paid_invoices=paid,
            unpaid_invoices=unpaid,
            cancelled_invoices=cancelled,
            draft_invoices=draft,
            gross_invoice_amount=Decimal(str(gross_amount)),
            paid_amount=Decimal(str(paid_amount)),
            unpaid_amount=Decimal(str(unpaid_amount)),
        )

    @staticmethod
    def _build_payment_summary(
        company, period_start: datetime, period_end: datetime,
    ) -> PaymentSummary:
        """Build payment summary for the period using created_at as period anchor."""
        from django.db.models import Sum

        from apps.payments.models import Payment

        base_qs = Payment.objects.filter(
            company=company,
            created_at__gte=period_start,
            created_at__lte=period_end,
        )

        total = base_qs.count()
        paid = base_qs.filter(status=Payment.Status.PAID).count()
        failed = base_qs.filter(status=Payment.Status.FAILED).count()
        cancelled = base_qs.filter(status=Payment.Status.CANCELLED).count()
        pending = base_qs.filter(
            status__in=[Payment.Status.INITIATED, Payment.Status.PENDING],
        ).count()
        needs_recon = base_qs.filter(
            status=Payment.Status.NEEDS_RECONCILIATION,
        ).count()

        total_paid_amount = base_qs.filter(
            status=Payment.Status.PAID,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return PaymentSummary(
            total_payments=total,
            paid_payments=paid,
            failed_payments=failed,
            cancelled_payments=cancelled,
            pending_payments=pending,
            needs_reconciliation_payments=needs_recon,
            total_paid_amount=Decimal(str(total_paid_amount)),
        )

    @staticmethod
    def _build_escrow_summary(
        company, period_start: datetime, period_end: datetime,
    ) -> EscrowSummary:
        """Build escrow summary for the period using held_at as period anchor."""
        from django.db.models import Sum

        from apps.payouts.models import EscrowRecord

        base_qs = EscrowRecord.objects.filter(
            company=company,
            held_at__gte=period_start,
            held_at__lte=period_end,
        )

        total = base_qs.count()
        held = base_qs.filter(status=EscrowRecord.Status.HELD).count()
        reserved = base_qs.filter(status=EscrowRecord.Status.RESERVED).count()
        distributed = base_qs.filter(status=EscrowRecord.Status.DISTRIBUTED).count()
        pending_settlement = base_qs.filter(
            status=EscrowRecord.Status.PENDING_SETTLEMENT,
        ).count()
        settled = base_qs.filter(status=EscrowRecord.Status.SETTLED).count()
        closed = base_qs.filter(status=EscrowRecord.Status.CLOSED).count()

        # Open escrows: HELD, RESERVED, DISTRIBUTED, PENDING_SETTLEMENT
        open_statuses = [
            EscrowRecord.Status.HELD,
            EscrowRecord.Status.RESERVED,
            EscrowRecord.Status.DISTRIBUTED,
            EscrowRecord.Status.PENDING_SETTLEMENT,
        ]
        total_held_amount = base_qs.filter(
            status__in=open_statuses,
        ).aggregate(total=Sum("amount_rial"))["total"] or Decimal("0")

        # Settled/closed escrows
        settled_statuses = [
            EscrowRecord.Status.SETTLED,
            EscrowRecord.Status.CLOSED,
        ]
        total_settled_amount = base_qs.filter(
            status__in=settled_statuses,
        ).aggregate(total=Sum("amount_rial"))["total"] or Decimal("0")

        return EscrowSummary(
            total_escrows=total,
            held_escrows=held,
            reserved_escrows=reserved,
            distributed_escrows=distributed,
            pending_settlement_escrows=pending_settlement,
            settled_escrows=settled,
            closed_escrows=closed,
            total_held_amount=Decimal(str(total_held_amount)),
            total_settled_amount=Decimal(str(total_settled_amount)),
        )

    @staticmethod
    def _build_settlement_summary(
        company, period_start: datetime, period_end: datetime,
    ) -> SettlementReportSummary:
        """Build settlement batch summary using period overlap."""
        from django.db.models import Sum

        from apps.payouts.models import SettlementBatch

        # Batches that overlap with the reporting period
        base_qs = SettlementBatch.objects.filter(
            company=company,
            period_start__lte=period_end,
            period_end__gte=period_start,
        )

        total = base_qs.count()
        calculating = base_qs.filter(
            status=SettlementBatch.Status.CALCULATING,
        ).count()
        ready = base_qs.filter(status=SettlementBatch.Status.READY).count()
        executing = base_qs.filter(
            status=SettlementBatch.Status.EXECUTING,
        ).count()
        completed = base_qs.filter(
            status=SettlementBatch.Status.COMPLETED,
        ).count()
        failed = base_qs.filter(status=SettlementBatch.Status.FAILED).count()

        completed_amount = base_qs.filter(
            status=SettlementBatch.Status.COMPLETED,
        ).aggregate(total=Sum("net_amount_rial"))["total"] or Decimal("0")

        # Pending = CALCULATING + READY + EXECUTING
        pending_statuses = [
            SettlementBatch.Status.CALCULATING,
            SettlementBatch.Status.READY,
            SettlementBatch.Status.EXECUTING,
        ]
        pending_amount = base_qs.filter(
            status__in=pending_statuses,
        ).aggregate(total=Sum("net_amount_rial"))["total"] or Decimal("0")

        return SettlementReportSummary(
            total_batches=total,
            calculating_batches=calculating,
            ready_batches=ready,
            executing_batches=executing,
            completed_batches=completed,
            failed_batches=failed,
            completed_settlement_amount=Decimal(str(completed_amount)),
            pending_settlement_amount=Decimal(str(pending_amount)),
        )

    @staticmethod
    def _build_adjustment_summary(
        company, period_start: datetime, period_end: datetime,
    ) -> AdjustmentSummary:
        """Build adjustment/refund summary using created_at as period anchor."""
        from django.db.models import Sum

        from apps.payouts.models import AdjustmentDocument

        base_qs = AdjustmentDocument.objects.filter(
            company=company,
            created_at__gte=period_start,
            created_at__lte=period_end,
        )

        total = base_qs.count()
        draft = base_qs.filter(
            status=AdjustmentDocument.Status.DRAFT,
        ).count()
        pending_approval = base_qs.filter(
            status=AdjustmentDocument.Status.PENDING_APPROVAL,
        ).count()
        approved = base_qs.filter(
            status=AdjustmentDocument.Status.APPROVED,
        ).count()
        applied = base_qs.filter(
            status=AdjustmentDocument.Status.APPLIED,
        ).count()
        rejected = base_qs.filter(
            status=AdjustmentDocument.Status.REJECTED,
        ).count()
        cancelled = base_qs.filter(
            status=AdjustmentDocument.Status.CANCELLED,
        ).count()

        # Pending = DRAFT + PENDING_APPROVAL + APPROVED
        pending_statuses = [
            AdjustmentDocument.Status.DRAFT,
            AdjustmentDocument.Status.PENDING_APPROVAL,
            AdjustmentDocument.Status.APPROVED,
        ]
        pending_amount = base_qs.filter(
            status__in=pending_statuses,
        ).aggregate(total=Sum("amount_rial"))["total"] or Decimal("0")

        applied_amount = base_qs.filter(
            status=AdjustmentDocument.Status.APPLIED,
        ).aggregate(total=Sum("amount_rial"))["total"] or Decimal("0")

        return AdjustmentSummary(
            total_documents=total,
            draft_count=draft,
            pending_approval_count=pending_approval,
            approved_count=approved,
            applied_count=applied,
            rejected_count=rejected,
            cancelled_count=cancelled,
            pending_amount=Decimal(str(pending_amount)),
            applied_amount=Decimal(str(applied_amount)),
        )

    @staticmethod
    def _build_reconciliation_summary(company) -> ReconReportSummary:
        """
        Build reconciliation summary by delegating to Sprint 6
        FinancialReconciliationService.
        """
        from apps.payouts.services_reconciliation import (
            FinancialReconciliationService,
            ReconciliationSeverity,
        )

        report = FinancialReconciliationService.reconcile_company(company)

        errors = len(report.by_severity(ReconciliationSeverity.ERROR))
        warnings = len(report.by_severity(ReconciliationSeverity.WARNING))
        blocked = len(report.by_severity(ReconciliationSeverity.BLOCKED))

        return ReconReportSummary(
            total_issues=len(report.issues),
            errors=errors,
            warnings=warnings,
            blocked=blocked,
            is_clean=report.is_clean,
        )

    @staticmethod
    def _build_closing_readiness(
        company, period_start: datetime, period_end: datetime,
    ) -> ClosingReadinessSummary:
        """
        Build closing readiness summary by delegating to Sprint 7
        FinancialClosingEngine.
        """
        from apps.payouts.services_financial_closing import (
            FinancialClosingEngine,
        )

        result = FinancialClosingEngine.evaluate(
            company=company,
            period_start=period_start,
            period_end=period_end,
        )

        return ClosingReadinessSummary(
            status=result.status.value,
            blocking_issues_count=len(result.blocking_issues),
            warnings_count=len(result.warnings),
            durable_lock_status=result.durable_period_lock_status.value,
        )
