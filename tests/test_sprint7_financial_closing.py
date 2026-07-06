"""
Sprint 7 — Financial Closing Engine Tests.

Exercises FinancialClosingEngine (apps/payouts/services_financial_closing.py)
against real, already-persisted financial records produced by the existing
Sprint 1-6 payment/invoice/escrow/settlement/refund/reconciliation flows.

Scope: read-only evaluation only. No test in this file asserts that the
service mutates anything — several tests explicitly assert the opposite
(no database writes occur as a result of calling evaluate()).
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
from apps.payouts.services_financial_closing import (
    BlockingReason,
    ClosingEvaluationResult,
    ClosingStatus,
    FinancialClosingEngine,
)
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)



def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Closing Test Co {tag}",
        "code": f"close{tag}",
        "slug": f"close-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"closetech{_n()}",
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
        title=f"Closing Test Order {_n()}",
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
    payment = _pending_payment(company, invoice, gateway, f"SUCCESS-close-{_n()}")
    success, _, _ = PaymentCallbackService.handle_callback(
        company=company, reference_id=payment.reference_id,
    )
    assert success, "setup failed: payment callback did not succeed"
    invoice.refresh_from_db()
    return invoice, payment



def _period():
    """Return a broad period window encompassing 'now'."""
    now = timezone.now()
    return now - timedelta(days=1), now + timedelta(days=1)


# =============================================================================
# 1. Clean period — CAN_CLOSE
# =============================================================================

class CleanPeriodTest(TestCase):

    def test_clean_period_returns_can_close(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        # Mark escrow as SETTLED so it's not "open"
        escrow = EscrowRecord.objects.get(payment=payment)
        EscrowRecord.objects.filter(pk=escrow.pk).update(
            status=EscrowRecord.Status.SETTLED,
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company,
            period_start=period_start,
            period_end=period_end,
        )

        self.assertIsInstance(result, ClosingEvaluationResult)
        self.assertEqual(result.status, ClosingStatus.CAN_CLOSE)
        self.assertEqual(result.blocking_issues, ())
        self.assertEqual(result.company_id, company.id)
        self.assertEqual(result.period_start, period_start)
        self.assertEqual(result.period_end, period_end)

    def test_clean_period_reconciliation_summary_is_clean(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        # Reconciliation may have warnings (distributed without settlement
        # item) but no errors/blocked after marking settled
        self.assertEqual(result.reconciliation_summary.errors, 0)
        self.assertEqual(result.reconciliation_summary.blocked, 0)



# =============================================================================
# 2. Reconciliation ERROR blocks closing
# =============================================================================

class ReconciliationErrorBlocksTest(TestCase):

    def test_reconciliation_error_blocks_closing(self):
        """A PAID invoice without any PAID payment = reconciliation ERROR = BLOCKED."""
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech)
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at"])
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        error_reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.RECONCILIATION_ERROR, error_reasons)
        self.assertTrue(result.reconciliation_summary.errors > 0)


# =============================================================================
# 3. Reconciliation BLOCKED blocks closing
# =============================================================================

class ReconciliationBlockedBlocksTest(TestCase):

    def test_reconciliation_blocked_blocks_closing(self):
        """An APPROVED partial refund causes reconciliation BLOCKED severity."""
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        # Mark escrow settled to avoid open-escrow blocking
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        # Create a PARTIAL_REFUND in APPROVED state — this triggers
        # reconciliation's ADJUSTMENT_BLOCKED_UNSUPPORTED_TYPE (BLOCKED severity)
        from apps.payouts.services_adjustment import AdjustmentDocumentService
        doc = AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.PARTIAL_REFUND,
            amount_rial=1_000_000,
            reason="test partial",
        )
        doc = AdjustmentDocumentService.submit_for_approval(doc)
        doc = AdjustmentDocumentService.approve(doc, approved_by=None)
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        blocked_reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.RECONCILIATION_BLOCKED, blocked_reasons)
        self.assertTrue(result.reconciliation_summary.blocked > 0)



# =============================================================================
# 4. Pending FinancialBackfillTask blocks closing
# =============================================================================

class PendingBackfillTaskBlocksTest(TestCase):

    def test_pending_backfill_task_blocks_closing(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
            invoice=invoice,
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.PENDING_BACKFILL_TASK, reasons)

    def test_resolved_backfill_task_does_not_block(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.RESOLVED,
            invoice=invoice,
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        backfill_reasons = [
            i for i in result.blocking_issues
            if i.reason == BlockingReason.PENDING_BACKFILL_TASK
        ]
        self.assertEqual(backfill_reasons, [])



# =============================================================================
# 5. SettlementBatch CALCULATING / READY / EXECUTING blocks closing
# =============================================================================

class SettlementBatchBlocksTest(TestCase):

    def _create_batch(self, company, status):
        from apps.payouts.services_settlement_batch import SettlementBatchService
        period_start, period_end = _period()
        batch = SettlementBatchService.create_batch(
            company=company,
            level="platform_to_org",
            period_start=period_start,
            period_end=period_end,
        )
        if status != SettlementBatch.Status.CALCULATING:
            SettlementBatch.objects.filter(pk=batch.pk).update(status=status)
            batch.refresh_from_db()
        return batch

    def test_calculating_batch_blocks_closing(self):
        company = _company()
        self._create_batch(company, SettlementBatch.Status.CALCULATING)
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.SETTLEMENT_BATCH_IN_PROGRESS, reasons)

    def test_ready_batch_blocks_closing(self):
        company = _company()
        self._create_batch(company, SettlementBatch.Status.READY)
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.SETTLEMENT_BATCH_IN_PROGRESS, reasons)

    def test_executing_batch_blocks_closing(self):
        company = _company()
        self._create_batch(company, SettlementBatch.Status.EXECUTING)
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.SETTLEMENT_BATCH_IN_PROGRESS, reasons)


    def test_completed_batch_does_not_block(self):
        company = _company()
        self._create_batch(company, SettlementBatch.Status.COMPLETED)
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        batch_blocking = [
            i for i in result.blocking_issues
            if i.reason == BlockingReason.SETTLEMENT_BATCH_IN_PROGRESS
        ]
        self.assertEqual(batch_blocking, [])

    def test_failed_batch_does_not_block(self):
        company = _company()
        self._create_batch(company, SettlementBatch.Status.FAILED)
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        batch_blocking = [
            i for i in result.blocking_issues
            if i.reason == BlockingReason.SETTLEMENT_BATCH_IN_PROGRESS
        ]
        self.assertEqual(batch_blocking, [])

    def test_settlement_summary_counts(self):
        company = _company()
        self._create_batch(company, SettlementBatch.Status.CALCULATING)
        self._create_batch(company, SettlementBatch.Status.COMPLETED)
        self._create_batch(company, SettlementBatch.Status.FAILED)
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.settlement_summary.total_batches, 3)
        self.assertEqual(result.settlement_summary.calculating, 1)
        self.assertEqual(result.settlement_summary.completed, 1)
        self.assertEqual(result.settlement_summary.failed, 1)



# =============================================================================
# 6. Pending AdjustmentDocument blocks closing
# =============================================================================

class PendingAdjustmentDocumentBlocksTest(TestCase):

    def test_draft_adjustment_blocks_closing(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.DRAFT,
            amount_rial=int(invoice.total_amount),
            reason="test draft",
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.PENDING_ADJUSTMENT_DOCUMENT, reasons)

    def test_pending_approval_adjustment_blocks_closing(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.PENDING_APPROVAL,
            amount_rial=int(invoice.total_amount),
            reason="test pending approval",
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.PENDING_ADJUSTMENT_DOCUMENT, reasons)


    def test_approved_adjustment_blocks_closing(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.APPROVED,
            amount_rial=int(invoice.total_amount),
            reason="test approved",
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.PENDING_ADJUSTMENT_DOCUMENT, reasons)

    def test_applied_adjustment_does_not_block(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.APPLIED,
            amount_rial=int(invoice.total_amount),
            reason="test applied",
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        adj_blocking = [
            i for i in result.blocking_issues
            if i.reason == BlockingReason.PENDING_ADJUSTMENT_DOCUMENT
        ]
        self.assertEqual(adj_blocking, [])


    def test_rejected_adjustment_does_not_block(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.REJECTED,
            amount_rial=int(invoice.total_amount),
            reason="test rejected",
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        adj_blocking = [
            i for i in result.blocking_issues
            if i.reason == BlockingReason.PENDING_ADJUSTMENT_DOCUMENT
        ]
        self.assertEqual(adj_blocking, [])

    def test_cancelled_adjustment_does_not_block(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.CANCELLED,
            amount_rial=int(invoice.total_amount),
            reason="test cancelled",
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        adj_blocking = [
            i for i in result.blocking_issues
            if i.reason == BlockingReason.PENDING_ADJUSTMENT_DOCUMENT
        ]
        self.assertEqual(adj_blocking, [])



# =============================================================================
# 7. Open EscrowRecord blocks closing
# =============================================================================

class OpenEscrowRecordBlocksTest(TestCase):

    def test_held_escrow_blocks_closing(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        # Force HELD status
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.HELD,
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.status, ClosingStatus.BLOCKED)
        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.OPEN_ESCROW_RECORD, reasons)

    def test_distributed_escrow_blocks_closing(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        # Default from callback is DISTRIBUTED — keep as-is
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        reasons = [i.reason for i in result.blocking_issues]
        self.assertIn(BlockingReason.OPEN_ESCROW_RECORD, reasons)

    def test_settled_escrow_does_not_block(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        escrow_blocking = [
            i for i in result.blocking_issues
            if i.reason == BlockingReason.OPEN_ESCROW_RECORD
        ]
        self.assertEqual(escrow_blocking, [])

    def test_closed_escrow_does_not_block(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.CLOSED,
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        escrow_blocking = [
            i for i in result.blocking_issues
            if i.reason == BlockingReason.OPEN_ESCROW_RECORD
        ]
        self.assertEqual(escrow_blocking, [])



# =============================================================================
# 8. Durable period lock returns NOT_IMPLEMENTED
# =============================================================================

class DurablePeriodLockTest(TestCase):

    def test_durable_period_lock_returns_not_implemented(self):
        company = _company()
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(
            result.durable_period_lock_status, ClosingStatus.NOT_IMPLEMENTED,
        )

    def test_durable_period_lock_is_always_not_implemented(self):
        """Even for a completely clean period, no durable lock is available."""
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(
            result.durable_period_lock_status, ClosingStatus.NOT_IMPLEMENTED,
        )


# =============================================================================
# 9. Tenant isolation
# =============================================================================

class TenantIsolationTest(TestCase):

    def test_tenant_isolation(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a)
        tech_b = _technician(company_b)

        # company_a has a blocking issue: pending backfill task
        invoice_a, payment_a = _distributed_invoice(company_a, tech_a)
        EscrowRecord.objects.filter(payment=payment_a).update(
            status=EscrowRecord.Status.SETTLED,
        )
        FinancialBackfillTask.objects.create(
            company=company_a,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
            invoice=invoice_a,
        )

        # company_b is clean
        invoice_b, payment_b = _distributed_invoice(company_b, tech_b)
        EscrowRecord.objects.filter(payment=payment_b).update(
            status=EscrowRecord.Status.SETTLED,
        )
        period_start, period_end = _period()

        result_a = FinancialClosingEngine.evaluate(
            company=company_a, period_start=period_start, period_end=period_end,
        )
        result_b = FinancialClosingEngine.evaluate(
            company=company_b, period_start=period_start, period_end=period_end,
        )

        # company_a should be BLOCKED
        self.assertEqual(result_a.status, ClosingStatus.BLOCKED)
        self.assertEqual(result_a.company_id, company_a.id)

        # company_b should NOT see company_a's issues
        backfill_blocking_b = [
            i for i in result_b.blocking_issues
            if i.reason == BlockingReason.PENDING_BACKFILL_TASK
        ]
        self.assertEqual(backfill_blocking_b, [])
        self.assertEqual(result_b.company_id, company_b.id)



# =============================================================================
# 10. Deterministic repeated evaluation
# =============================================================================

class DeterminismTest(TestCase):

    def test_deterministic_repeated_evaluation(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        # Create multiple blocking conditions
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE,
            status=FinancialBackfillTask.Status.PENDING,
            invoice=invoice,
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.DRAFT,
            amount_rial=int(invoice.total_amount),
            reason="test determinism",
        )
        period_start, period_end = _period()

        result1 = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )
        result2 = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result1.status, result2.status)
        self.assertEqual(len(result1.blocking_issues), len(result2.blocking_issues))
        self.assertEqual(
            [(i.reason, i.model, i.object_id) for i in result1.blocking_issues],
            [(i.reason, i.model, i.object_id) for i in result2.blocking_issues],
        )
        self.assertEqual(
            [(w.reason, w.model, w.object_id) for w in result1.warnings],
            [(w.reason, w.model, w.object_id) for w in result2.warnings],
        )

    def test_evaluate_returns_correct_type(self):
        company = _company()
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertIsInstance(result, ClosingEvaluationResult)



# =============================================================================
# 11. No database writes
# =============================================================================

class NoDatabaseWriteTest(TestCase):

    def test_no_database_writes_during_evaluation(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        # Create multiple conditions that would trigger all check paths
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
            invoice=invoice,
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.DRAFT,
            amount_rial=int(invoice.total_amount),
            reason="test no writes",
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

        FinancialClosingEngine.evaluate(
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


    def test_no_writes_even_when_blocked(self):
        """Running evaluation twice must not itself create any records."""
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE,
            status=FinancialBackfillTask.Status.PENDING,
        )
        period_start, period_end = _period()

        FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )
        result2 = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        # Same blocking issues count — nothing accumulated
        self.assertEqual(result2.status, ClosingStatus.BLOCKED)


# =============================================================================
# 12. Refund/Adjustment summary
# =============================================================================

class RefundAdjustmentSummaryTest(TestCase):

    def test_refund_adjustment_summary_counts(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).update(
            status=EscrowRecord.Status.SETTLED,
        )
        # Create documents in various states
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.DRAFT,
            amount_rial=1_000_000,
            reason="draft",
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.APPLIED,
            amount_rial=2_000_000,
            reason="applied",
        )
        AdjustmentDocument.objects.create(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            status=AdjustmentDocument.Status.CANCELLED,
            amount_rial=3_000_000,
            reason="cancelled",
        )
        period_start, period_end = _period()

        result = FinancialClosingEngine.evaluate(
            company=company, period_start=period_start, period_end=period_end,
        )

        self.assertEqual(result.refund_adjustment_summary.total_documents, 3)
        self.assertEqual(result.refund_adjustment_summary.draft, 1)
        self.assertEqual(result.refund_adjustment_summary.applied, 1)
        self.assertEqual(result.refund_adjustment_summary.cancelled, 1)
