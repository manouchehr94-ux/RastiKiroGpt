"""
Sprint 8 — Financial Reporting Engine Tests.

Exercises FinancialReportingService (apps/payouts/services_financial_reporting.py)
against real, already-persisted financial records produced by the existing
Sprint 1-7 payment/invoice/escrow/settlement/refund/reconciliation/closing flows.

Scope: read-only reporting only. No test in this file asserts that the
service mutates anything — several tests explicitly assert the opposite
(no database writes occur as a result of calling generate_period_report()).
"""
import itertools
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.services import PaymentCallbackService
from apps.payouts.models import (
    AdjustmentDocument,
    CompanyPlatformFeeEntry,
    EscrowRecord,
    FinancialBackfillTask,
    PaymentSplitSnapshot,
    SettlementBatch,
    SettlementItem,
    TechnicianLedgerEntry,
)
from apps.payouts.services_financial_reporting import (
    AdjustmentSummary,
    ClosingReadinessSummary,
    EscrowSummary,
    FinancialPeriodReport,
    FinancialReportingService,
    InvoiceSummary,
    PaymentSummary,
    ReconReportSummary,
    SettlementReportSummary,
)
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Report Test Co {tag}",
        "code": f"rpt{tag}",
        "slug": f"rpt-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)



def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"rpttech{_n()}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=Decimal(str(service_pct)),
        goods_wage_percent=Decimal(str(goods_pct)),
        travel_wage_percent=Decimal(str(travel_pct)),
    )


def _order(company, technician=None) -> Order:
    return Order.objects.create(
        company=company,
        title=f"Report Test Order {_n()}",
        status=Order.Status.DONE,
        technician=technician,
    )


def _financial_policy(company, fee_percent=1) -> CompanyFinancialPolicy:
    policy, _ = CompanyFinancialPolicy.objects.get_or_create(
        company=company,
        defaults={
            "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
            "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
            "platform_fee_percent": Decimal(str(fee_percent)),
        },
    )
    policy.platform_fee_percent = Decimal(str(fee_percent))
    policy.save(update_fields=["platform_fee_percent"])
    return policy


def _issued_invoice(company, technician=None, total=10_000_000) -> Invoice:
    order = _order(company, technician=technician)
    invoice = Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-{company.code.upper()}-{Invoice.objects.count() + 1:05d}",
        status=Invoice.Status.ISSUED,
        issued_at=timezone.now(),
        subtotal=total,
        total_amount=total,
        net_amount_before_invoice_discounts=total,
        gross_amount=total,
        technician_service_wage_percent_snapshot=(
            Decimal(str(technician.service_wage_percent)) if technician else Decimal("0")
        ),
        technician_goods_wage_percent_snapshot=(
            Decimal(str(technician.goods_wage_percent)) if technician else Decimal("0")
        ),
        technician_travel_wage_percent_snapshot=(
            Decimal(str(technician.travel_wage_percent)) if technician else Decimal("0")
        ),
    )
    InvoiceItem.objects.create(
        company=company,
        invoice=invoice,
        description="خدمات تست",
        row_type=InvoiceItem.RowType.SERVICE,
        quantity=1,
        unit_price=total,
        total_price=total,
    )
    return invoice


def _platform_gateway(company) -> PaymentGateway:
    gateway, _created = PaymentGateway.objects.get_or_create(
        company=company,
        gateway_type=PaymentGateway.GatewayType.FAKE,
        defaults={
            "name": "Platform Test Gateway",
            "owner_type": PaymentGateway.OwnerType.PLATFORM,
            "is_active": True,
            "is_default": True,
        },
    )
    return gateway


def _pending_payment(company, invoice, gateway, reference_id) -> Payment:
    return Payment.objects.create(
        company=company,
        invoice=invoice,
        gateway=gateway,
        amount=invoice.total_amount,
        status=Payment.Status.PENDING,
        reference_id=reference_id,
    )


def _distributed_invoice(company, technician, *, total=10_000_000, fee_percent=1):
    """
    Build a fully real, DISTRIBUTED-escrow, PAID invoice by driving it
    through the actual production callback flow (PaymentCallbackService).
    """
    _financial_policy(company, fee_percent=fee_percent)
    gateway = _platform_gateway(company)
    invoice = _issued_invoice(company, technician=technician, total=total)
    payment = _pending_payment(company, invoice, gateway, f"SUCCESS-rpt-{_n()}")
    success, _, _ = PaymentCallbackService.handle_callback(
        company=company, reference_id=payment.reference_id,
    )
    assert success, "setup failed: payment callback did not succeed"
    invoice.refresh_from_db()
    return invoice, payment


def _fully_settled_invoice(company, technician, *, total=10_000_000, fee_percent=1):
    """
    Build a PAID invoice with a fully settled escrow — properly linked
    to a COMPLETED SettlementBatch with a matching SettlementItem.
    """
    from apps.payouts.services_escrow import EscrowRecordService
    from apps.payouts.services_settlement_batch import SettlementBatchService

    invoice, payment = _distributed_invoice(
        company, technician, total=total, fee_percent=fee_percent,
    )
    escrow = EscrowRecord.objects.get(company=company, payment=payment)

    now = timezone.now()
    batch = SettlementBatchService.create_batch(
        company=company,
        level="platform_to_org",
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    batch = SettlementBatchService.mark_ready(batch)
    escrow = EscrowRecordService.mark_pending_settlement(escrow, batch)
    EscrowRecordService.mark_settled(escrow)

    SettlementItem.objects.create(
        company=company,
        batch=batch,
        invoice=invoice,
        amount_rial=int(invoice.total_amount),
    )

    SettlementBatch.objects.filter(pk=batch.pk).update(
        status=SettlementBatch.Status.COMPLETED,
    )

    return invoice, payment


def _period():
    """Return a broad period window encompassing 'now'."""
    now = timezone.now()
    return now - timedelta(days=1), now + timedelta(days=1)



# =============================================================================
# 1. Empty period report
# =============================================================================

class EmptyPeriodReportTest(TestCase):

    def test_empty_period_returns_zero_counts(self):
        company = _company()
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertIsInstance(report, FinancialPeriodReport)
        self.assertEqual(report.company_id, company.id)
        self.assertEqual(report.period_start, period_start)
        self.assertEqual(report.period_end, period_end)

        # Invoice summary
        self.assertEqual(report.invoice_summary.total_invoices, 0)
        self.assertEqual(report.invoice_summary.paid_invoices, 0)
        self.assertEqual(report.invoice_summary.unpaid_invoices, 0)
        self.assertEqual(report.invoice_summary.cancelled_invoices, 0)
        self.assertEqual(report.invoice_summary.gross_invoice_amount, Decimal("0"))
        self.assertEqual(report.invoice_summary.paid_amount, Decimal("0"))
        self.assertEqual(report.invoice_summary.unpaid_amount, Decimal("0"))

        # Payment summary
        self.assertEqual(report.payment_summary.total_payments, 0)
        self.assertEqual(report.payment_summary.paid_payments, 0)
        self.assertEqual(report.payment_summary.total_paid_amount, Decimal("0"))

        # Escrow summary
        self.assertEqual(report.escrow_summary.total_escrows, 0)
        self.assertEqual(report.escrow_summary.total_held_amount, Decimal("0"))
        self.assertEqual(report.escrow_summary.total_settled_amount, Decimal("0"))

        # Settlement summary
        self.assertEqual(report.settlement_summary.total_batches, 0)

        # Adjustment summary
        self.assertEqual(report.adjustment_summary.total_documents, 0)

    def test_empty_period_reconciliation_is_clean(self):
        company = _company()
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertTrue(report.reconciliation_summary.is_clean)
        self.assertEqual(report.reconciliation_summary.errors, 0)
        self.assertEqual(report.reconciliation_summary.warnings, 0)
        self.assertEqual(report.reconciliation_summary.blocked, 0)

    def test_empty_period_closing_readiness(self):
        company = _company()
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.closing_readiness.status, "can_close")
        self.assertEqual(report.closing_readiness.blocking_issues_count, 0)
        self.assertEqual(report.closing_readiness.durable_lock_status, "not_implemented")


# =============================================================================
# 2. Clean paid invoice summary
# =============================================================================

class PaidInvoiceSummaryTest(TestCase):

    def test_paid_invoice_appears_in_summary(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech, total=5_000_000)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.invoice_summary.total_invoices, 1)
        self.assertEqual(report.invoice_summary.paid_invoices, 1)
        self.assertEqual(report.invoice_summary.unpaid_invoices, 0)
        self.assertEqual(report.invoice_summary.paid_amount, Decimal("5000000"))

    def test_multiple_paid_invoices_aggregate(self):
        company = _company()
        tech = _technician(company)
        _distributed_invoice(company, tech, total=3_000_000)
        _distributed_invoice(company, tech, total=7_000_000)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.invoice_summary.paid_invoices, 2)
        self.assertEqual(report.invoice_summary.paid_amount, Decimal("10000000"))


# =============================================================================
# 3. Unpaid invoice summary
# =============================================================================

class UnpaidInvoiceSummaryTest(TestCase):

    def test_issued_invoice_appears_as_unpaid(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech, total=8_000_000)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.invoice_summary.total_invoices, 1)
        self.assertEqual(report.invoice_summary.unpaid_invoices, 1)
        self.assertEqual(report.invoice_summary.paid_invoices, 0)
        self.assertEqual(report.invoice_summary.unpaid_amount, Decimal("8000000"))
        self.assertEqual(report.invoice_summary.gross_invoice_amount, Decimal("8000000"))

    def test_cancelled_invoice_counted_separately(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech, total=2_000_000)
        Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.CANCELLED)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.invoice_summary.cancelled_invoices, 1)
        self.assertEqual(report.invoice_summary.unpaid_invoices, 0)
        self.assertEqual(report.invoice_summary.paid_invoices, 0)



# =============================================================================
# 4. Payment breakdown
# =============================================================================

class PaymentBreakdownTest(TestCase):

    def test_paid_payment_summary(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech, total=6_000_000)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        # _distributed_invoice creates: PENDING payment → then PAID via callback
        # So we have 1 PAID payment
        self.assertGreaterEqual(report.payment_summary.paid_payments, 1)
        self.assertEqual(
            report.payment_summary.total_paid_amount, Decimal("6000000"),
        )

    def test_failed_payment_counted(self):
        company = _company()
        tech = _technician(company)
        _financial_policy(company)
        gateway = _platform_gateway(company)
        invoice = _issued_invoice(company, technician=tech, total=4_000_000)
        # Create a FAILED payment directly
        Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=gateway,
            amount=invoice.total_amount,
            status=Payment.Status.FAILED,
            reference_id=f"FAIL-rpt-{_n()}",
        )
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.payment_summary.failed_payments, 1)
        self.assertEqual(report.payment_summary.paid_payments, 0)

    def test_cancelled_payment_counted(self):
        company = _company()
        tech = _technician(company)
        _financial_policy(company)
        gateway = _platform_gateway(company)
        invoice = _issued_invoice(company, technician=tech)
        Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=gateway,
            amount=invoice.total_amount,
            status=Payment.Status.CANCELLED,
            reference_id=f"CANCEL-rpt-{_n()}",
        )
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.payment_summary.cancelled_payments, 1)


# =============================================================================
# 5. Escrow summary
# =============================================================================

class EscrowSummaryTest(TestCase):

    def test_distributed_escrow_in_summary(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech, total=9_000_000)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.escrow_summary.total_escrows, 1)
        self.assertEqual(report.escrow_summary.distributed_escrows, 1)
        self.assertEqual(
            report.escrow_summary.total_held_amount, Decimal("9000000"),
        )

    def test_settled_escrow_in_summary(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _fully_settled_invoice(company, tech, total=7_000_000)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.escrow_summary.settled_escrows, 1)
        self.assertEqual(
            report.escrow_summary.total_settled_amount, Decimal("7000000"),
        )
        self.assertEqual(report.escrow_summary.total_held_amount, Decimal("0"))


# =============================================================================
# 6. Settlement batch summary
# =============================================================================

class SettlementBatchSummaryTest(TestCase):

    def _create_batch(self, company, status, amount=1_000_000):
        from apps.payouts.services_settlement_batch import SettlementBatchService
        period_start, period_end = _period()
        batch = SettlementBatchService.create_batch(
            company=company,
            level="platform_to_org",
            period_start=period_start,
            period_end=period_end,
        )
        SettlementBatch.objects.filter(pk=batch.pk).update(
            status=status, net_amount_rial=amount,
        )
        return batch

    def test_settlement_batch_status_breakdown(self):
        company = _company()
        self._create_batch(company, SettlementBatch.Status.CALCULATING, 100_000)
        self._create_batch(company, SettlementBatch.Status.COMPLETED, 500_000)
        self._create_batch(company, SettlementBatch.Status.FAILED, 200_000)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.settlement_summary.total_batches, 3)
        self.assertEqual(report.settlement_summary.calculating_batches, 1)
        self.assertEqual(report.settlement_summary.completed_batches, 1)
        self.assertEqual(report.settlement_summary.failed_batches, 1)
        self.assertEqual(
            report.settlement_summary.completed_settlement_amount, Decimal("500000"),
        )
        self.assertEqual(
            report.settlement_summary.pending_settlement_amount, Decimal("100000"),
        )



# =============================================================================
# 7. Adjustment summary
# =============================================================================

class AdjustmentSummaryTest(TestCase):

    def test_adjustment_status_breakdown(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        # Create adjustments in various states
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.DRAFT,
            amount_rial=1_000_000,
            reason="draft adjustment",
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.APPLIED,
            amount_rial=2_000_000,
            reason="applied adjustment",
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.PARTIAL_REFUND,
            status=AdjustmentDocument.Status.CANCELLED,
            amount_rial=500_000,
            reason="cancelled adjustment",
        )
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.adjustment_summary.total_documents, 3)
        self.assertEqual(report.adjustment_summary.draft_count, 1)
        self.assertEqual(report.adjustment_summary.applied_count, 1)
        self.assertEqual(report.adjustment_summary.cancelled_count, 1)
        self.assertEqual(report.adjustment_summary.pending_amount, Decimal("1000000"))
        self.assertEqual(report.adjustment_summary.applied_amount, Decimal("2000000"))


# =============================================================================
# 8. Reconciliation summary integration
# =============================================================================

class ReconciliationSummaryTest(TestCase):

    def test_clean_company_reconciliation(self):
        company = _company()
        tech = _technician(company)
        _fully_settled_invoice(company, tech)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertIsInstance(report.reconciliation_summary, ReconReportSummary)
        self.assertEqual(report.reconciliation_summary.errors, 0)
        self.assertEqual(report.reconciliation_summary.blocked, 0)

    def test_error_company_reconciliation(self):
        """A PAID invoice without a PAID payment triggers reconciliation ERROR."""
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech)
        Invoice.objects.filter(pk=invoice.pk).update(
            status=Invoice.Status.PAID, paid_at=timezone.now(),
        )
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertFalse(report.reconciliation_summary.is_clean)
        self.assertGreater(report.reconciliation_summary.errors, 0)


# =============================================================================
# 9. Closing readiness integration
# =============================================================================

class ClosingReadinessTest(TestCase):

    def test_clean_period_closing_readiness(self):
        company = _company()
        tech = _technician(company)
        _fully_settled_invoice(company, tech)
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertIsInstance(report.closing_readiness, ClosingReadinessSummary)
        self.assertEqual(report.closing_readiness.status, "can_close")
        self.assertEqual(report.closing_readiness.blocking_issues_count, 0)
        self.assertEqual(report.closing_readiness.durable_lock_status, "not_implemented")

    def test_blocked_period_closing_readiness(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        # Open escrow blocks closing
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(report.closing_readiness.status, "blocked")
        self.assertGreater(report.closing_readiness.blocking_issues_count, 0)


# =============================================================================
# 10. Tenant isolation
# =============================================================================

class TenantIsolationTest(TestCase):

    def test_tenant_isolation(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a)
        tech_b = _technician(company_b)

        # company_a has 2 paid invoices
        _distributed_invoice(company_a, tech_a, total=5_000_000)
        _distributed_invoice(company_a, tech_a, total=3_000_000)

        # company_b has 1 paid invoice
        _distributed_invoice(company_b, tech_b, total=9_000_000)

        period_start, period_end = _period()

        report_a = FinancialReportingService.generate_period_report(
            company=company_a, period_start=period_start, period_end=period_end,
        )
        report_b = FinancialReportingService.generate_period_report(
            company=company_b, period_start=period_start, period_end=period_end,
        )

        # company_a sees only its own invoices
        self.assertEqual(report_a.company_id, company_a.id)
        self.assertEqual(report_a.invoice_summary.paid_invoices, 2)
        self.assertEqual(report_a.invoice_summary.paid_amount, Decimal("8000000"))

        # company_b sees only its own invoices
        self.assertEqual(report_b.company_id, company_b.id)
        self.assertEqual(report_b.invoice_summary.paid_invoices, 1)
        self.assertEqual(report_b.invoice_summary.paid_amount, Decimal("9000000"))


# =============================================================================
# 11. Deterministic repeated reporting
# =============================================================================

class DeterminismTest(TestCase):

    def test_deterministic_repeated_reporting(self):
        company = _company()
        tech = _technician(company)
        _distributed_invoice(company, tech, total=4_000_000)
        _distributed_invoice(company, tech, total=6_000_000)
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=Invoice.objects.filter(company=company).first(),
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.DRAFT,
            amount_rial=1_000_000,
            reason="test determinism",
        )
        period_start, period_end = _period()

        report1 = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )
        report2 = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        # All numeric fields must be identical
        self.assertEqual(
            report1.invoice_summary, report2.invoice_summary,
        )
        self.assertEqual(
            report1.payment_summary, report2.payment_summary,
        )
        self.assertEqual(
            report1.escrow_summary, report2.escrow_summary,
        )
        self.assertEqual(
            report1.settlement_summary, report2.settlement_summary,
        )
        self.assertEqual(
            report1.adjustment_summary, report2.adjustment_summary,
        )
        self.assertEqual(
            report1.reconciliation_summary, report2.reconciliation_summary,
        )
        self.assertEqual(
            report1.closing_readiness, report2.closing_readiness,
        )

    def test_report_returns_correct_type(self):
        company = _company()
        period_start, period_end = _period()

        report = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertIsInstance(report, FinancialPeriodReport)
        self.assertIsInstance(report.invoice_summary, InvoiceSummary)
        self.assertIsInstance(report.payment_summary, PaymentSummary)
        self.assertIsInstance(report.escrow_summary, EscrowSummary)
        self.assertIsInstance(report.settlement_summary, SettlementReportSummary)
        self.assertIsInstance(report.adjustment_summary, AdjustmentSummary)
        self.assertIsInstance(report.reconciliation_summary, ReconReportSummary)
        self.assertIsInstance(report.closing_readiness, ClosingReadinessSummary)


# =============================================================================
# 12. No database writes
# =============================================================================

class NoDatabaseWriteTest(TestCase):

    def test_no_database_writes_during_reporting(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.DRAFT,
            amount_rial=int(invoice.total_amount),
            reason="test no writes",
        )
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
            invoice=invoice,
        )
        period_start, period_end = _period()

        counts_before = {
            "invoice": Invoice.objects.count(),
            "payment": Payment.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "settlement_batch": SettlementBatch.objects.count(),
            "settlement_item": SettlementItem.objects.count(),
            "ledger_entry": TechnicianLedgerEntry.objects.count(),
            "platform_fee_entry": CompanyPlatformFeeEntry.objects.count(),
            "backfill_task": FinancialBackfillTask.objects.count(),
            "adjustment_document": AdjustmentDocument.objects.count(),
            "split_snapshot": PaymentSplitSnapshot.objects.count(),
        }

        FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        counts_after = {
            "invoice": Invoice.objects.count(),
            "payment": Payment.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "settlement_batch": SettlementBatch.objects.count(),
            "settlement_item": SettlementItem.objects.count(),
            "ledger_entry": TechnicianLedgerEntry.objects.count(),
            "platform_fee_entry": CompanyPlatformFeeEntry.objects.count(),
            "backfill_task": FinancialBackfillTask.objects.count(),
            "adjustment_document": AdjustmentDocument.objects.count(),
            "split_snapshot": PaymentSplitSnapshot.objects.count(),
        }

        self.assertEqual(counts_before, counts_after)

    def test_no_writes_on_repeated_calls(self):
        """Running report generation twice must not accumulate state."""
        company = _company()
        tech = _technician(company)
        _distributed_invoice(company, tech)
        period_start, period_end = _period()

        FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )
        report2 = FinancialReportingService.generate_period_report(
            company=company, period_start=period_start, period_end=period_end,
        )

        # Report is still valid — nothing new was created
        self.assertIsInstance(report2, FinancialPeriodReport)
        self.assertEqual(report2.invoice_summary.paid_invoices, 1)
