"""
Sprint 4 — Settlement Engine, Phase B Step 2: Settlement Planner Tests.

Exercises SettlementPlanner (apps/payouts/services_settlement_planner.py)
against real, already-persisted financial records produced by the existing
Sprint 3 payment/invoice flow (Layer 1) and direct ledger-entry
construction via TechnicianLedgerService (Layer 2) — mirroring the exact
fixture conventions already used in test_sprint4_settlement_calculator.py.

This test file verifies ONLY eligibility decisions. It does not exercise
any SettlementBatch/SettlementItem creation or settlement execution beyond
constructing pre-existing batches/items as fixtures to test exclusion
logic (via the already-merged, unmodified SettlementBatchService /
SettlementItemService from Sprint 2).
"""
import itertools
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.services import PaymentCallbackService
from apps.payouts.models import (
    AdjustmentDocument,
    EscrowRecord,
    FinancialBackfillTask,
    SettlementBatch,
    TechnicianLedgerEntry,
)
from apps.payouts.services import TechnicianLedgerService
from apps.payouts.services_settlement_batch import SettlementBatchService, SettlementItemService
from apps.payouts.services_settlement_planner import (
    Layer1PlanningItem,
    Layer1PlanningReport,
    Layer2PlanningItem,
    Layer2PlanningReport,
    SettlementPlanner,
)
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Planner Test Co {tag}",
        "code": f"plan{tag}",
        "slug": f"plan-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"plantech{_n()}",
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
        title=f"Planner Test Order {_n()}",
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
    return PaymentGateway.objects.create(
        company=company,
        name="Platform Test Gateway",
        gateway_type=PaymentGateway.GatewayType.FAKE,
        owner_type=PaymentGateway.OwnerType.PLATFORM,
        is_active=True,
        is_default=True,
    )


def _company_gateway(company) -> PaymentGateway:
    return PaymentGateway.objects.create(
        company=company,
        name="Company Test Gateway",
        gateway_type=PaymentGateway.GatewayType.FAKE,
        owner_type=PaymentGateway.OwnerType.COMPANY,
        is_active=True,
    )


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
    through the actual production callback flow (PaymentCallbackService),
    never by hand-crafting an EscrowRecord row directly.
    """
    _financial_policy(company, fee_percent=fee_percent)
    gateway = _platform_gateway(company)
    invoice = _issued_invoice(company, technician=technician, total=total)
    payment = _pending_payment(company, invoice, gateway, f"SUCCESS-plan-{_n()}")
    success, _, _ = PaymentCallbackService.handle_callback(
        company=company, reference_id=payment.reference_id,
    )
    assert success, "setup failed: payment callback did not succeed"
    invoice.refresh_from_db()
    return invoice, payment


def _batch_and_claim_invoice(invoice, *, status=SettlementBatch.Status.READY):
    """
    Build a real SettlementBatch + SettlementItem claiming `invoice`, using
    the already-merged, unmodified Sprint 2 lifecycle services — never by
    hand-inserting rows that bypass those services' own invariants.
    """
    company = invoice.company
    batch = SettlementBatchService.create_batch(
        company=company,
        level=SettlementBatch.Level.PLATFORM_TO_ORG,
        period_start=timezone.now() - timezone.timedelta(days=1),
        period_end=timezone.now(),
    )
    SettlementItemService.add_invoice_item(batch, invoice, amount_rial=1, description="test claim")
    if status == SettlementBatch.Status.READY:
        batch = SettlementBatchService.mark_ready(batch)
    elif status == SettlementBatch.Status.FAILED:
        batch = SettlementBatchService.mark_ready(batch)
        batch = SettlementBatchService.mark_executing(batch)
        batch = SettlementBatchService.mark_failed(batch, "test failure")
    return batch


def _batch_and_claim_ledger_entry(company, ledger_entry, *, status=SettlementBatch.Status.READY):
    batch = SettlementBatchService.create_batch(
        company=company,
        level=SettlementBatch.Level.ORG_TO_PROVIDER,
        period_start=timezone.now() - timezone.timedelta(days=1),
        period_end=timezone.now(),
    )
    SettlementItemService.add_ledger_item(batch, ledger_entry, amount_rial=1, description="test claim")
    if status == SettlementBatch.Status.READY:
        batch = SettlementBatchService.mark_ready(batch)
    elif status == SettlementBatch.Status.FAILED:
        batch = SettlementBatchService.mark_ready(batch)
        batch = SettlementBatchService.mark_executing(batch)
        batch = SettlementBatchService.mark_failed(batch, "test failure")
    return batch


# =============================================================================
# Layer 1 — Platform <-> Organization
# =============================================================================

class Layer1EligibilityTest(TestCase):

    def test_distributed_escrow_invoice_is_eligible(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertIsInstance(item, Layer1PlanningItem)
        self.assertTrue(item.eligible)
        self.assertIsNone(item.blocked_reason)
        self.assertIsNotNone(item.calculation)
        self.assertEqual(item.calculation.net_position_rial, item.calculation.company_payable_base_rial)
        self.assertEqual(item.payment_id, payment.id)

    def test_held_escrow_blocks_layer1(self):
        company = _company()
        tech = _technician(company)
        _financial_policy(company, fee_percent=1)
        gateway = _platform_gateway(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        payment = Payment.objects.create(
            company=company, invoice=invoice, gateway=gateway,
            amount=invoice.total_amount, status=Payment.Status.PAID,
        )
        EscrowRecord.objects.create(
            company=company, payment=payment, invoice=invoice,
            amount_rial=int(invoice.total_amount), status=EscrowRecord.Status.HELD,
        )
        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["status"])

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIn("DISTRIBUTED", item.blocked_reason)

    def test_reserved_escrow_blocks_layer1(self):
        company = _company()
        tech = _technician(company)
        _financial_policy(company, fee_percent=1)
        gateway = _platform_gateway(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        payment = Payment.objects.create(
            company=company, invoice=invoice, gateway=gateway,
            amount=invoice.total_amount, status=Payment.Status.PAID,
        )
        EscrowRecord.objects.create(
            company=company, payment=payment, invoice=invoice,
            amount_rial=int(invoice.total_amount), status=EscrowRecord.Status.RESERVED,
        )
        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["status"])

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIn("DISTRIBUTED", item.blocked_reason)

    def test_company_gateway_payment_blocks_layer1(self):
        company = _company()
        tech = _technician(company)
        _financial_policy(company, fee_percent=1)
        gateway = _company_gateway(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        payment = _pending_payment(company, invoice, gateway, f"SUCCESS-cg-{_n()}")
        success, _, _ = PaymentCallbackService.handle_callback(
            company=company, reference_id=payment.reference_id,
        )
        self.assertTrue(success)
        invoice.refresh_from_db()

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIsNotNone(item.blocked_reason)

    def test_cash_payment_blocks_layer1(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        Payment.objects.create(
            company=company, invoice=invoice, amount=invoice.total_amount,
            status=Payment.Status.PAID, gateway=None,
        )
        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["status"])

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)

    def test_no_escrow_at_all_blocks_layer1(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["status"])

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIsNotNone(item.blocked_reason)
        self.assertIn("No EscrowRecord exists", item.blocked_reason)
        self.assertIsNone(item.escrow_id)
        self.assertIsNone(item.payment_id)

    def test_non_paid_invoice_blocks_layer1_before_calculator_runs(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        # status remains ISSUED — never touched by _distributed_invoice()

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIn("PAID", item.blocked_reason)
        self.assertIsNone(item.calculation)

    def test_pending_adjustment_document_blocks_layer1(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        AdjustmentDocument.objects.create(
            company=company,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            status=AdjustmentDocument.Status.PENDING_APPROVAL,
            original_invoice=invoice,
            amount_rial=100_000,
            reason="test pending adjustment",
        )

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIn("AdjustmentDocument", item.blocked_reason)
        # calculation is still populated for a Planner-level block.
        self.assertIsNotNone(item.calculation)

    def test_applied_adjustment_document_does_not_block_layer1(self):
        """A terminal (APPLIED) AdjustmentDocument is not 'pending' and must not block."""
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        AdjustmentDocument.objects.create(
            company=company,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            status=AdjustmentDocument.Status.APPLIED,
            original_invoice=invoice,
            amount_rial=100_000,
            reason="test applied adjustment",
            applied_at=timezone.now(),
        )

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertTrue(item.eligible)

    def test_unresolved_backfill_task_blocks_layer1(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
            invoice=invoice,
            payment=payment,
            error_message="simulated unresolved failure",
        )

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIn("FinancialBackfillTask", item.blocked_reason)

    def test_resolved_backfill_task_does_not_block_layer1(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.RESOLVED,
            invoice=invoice,
            payment=payment,
            resolved_at=timezone.now(),
        )

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertTrue(item.eligible)

    def test_already_batched_via_ready_batch_excludes_invoice(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        _batch_and_claim_invoice(invoice, status=SettlementBatch.Status.READY)

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIn("SettlementItem", item.blocked_reason)

    def test_already_linked_escrow_batch_excludes_invoice(self):
        """
        EscrowRecord.settlement_batch is set directly by
        EscrowRecordService.mark_pending_settlement() — independent of
        whether a SettlementItem also references the invoice. Both checks
        must work even if only one of the two has actually happened.
        """
        from apps.payouts.services_escrow import EscrowRecordService

        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        escrow = EscrowRecord.objects.get(payment=payment)

        batch = SettlementBatchService.create_batch(
            company=company,
            level=SettlementBatch.Level.PLATFORM_TO_ORG,
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        batch = SettlementBatchService.mark_ready(batch)
        EscrowRecordService.mark_pending_settlement(escrow, batch)

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertFalse(item.eligible)
        self.assertIn("SettlementBatch", item.blocked_reason)

    def test_released_by_failed_batch_becomes_eligible_again(self):
        """
        An invoice claimed only by a FAILED batch's SettlementItem must be
        excluded from the exclusion (i.e. become eligible again) — this is
        the "released item" behavior specified by the approved design.
        """
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        _batch_and_claim_invoice(invoice, status=SettlementBatch.Status.FAILED)

        item = SettlementPlanner.evaluate_layer1_for_invoice(invoice)

        self.assertTrue(item.eligible)

    def test_plan_layer1_for_company_buckets_results(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        eligible_invoice, _ = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        blocked_invoice = _issued_invoice(company, technician=tech, total=1_000_000)
        # blocked_invoice remains ISSUED — never becomes PAID.

        report = SettlementPlanner.plan_layer1_for_company(company)

        self.assertIsInstance(report, Layer1PlanningReport)
        eligible_ids = {i.invoice_id for i in report.eligible_items}
        blocked_ids = {i.invoice_id for i in report.blocked_items}
        self.assertIn(eligible_invoice.id, eligible_ids)
        self.assertIn(blocked_invoice.id, blocked_ids)


# =============================================================================
# Layer 2 — Organization <-> Provider
# =============================================================================

class Layer2EligibilityTest(TestCase):

    def test_payable_balance_is_eligible(self):
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"plan-credit-{_n()}",
        )

        item = SettlementPlanner.evaluate_layer2_for_technician(company, tech)

        self.assertIsInstance(item, Layer2PlanningItem)
        self.assertTrue(item.eligible)
        self.assertIsNone(item.blocked_reason)
        self.assertEqual(item.calculation.net_position_rial, 6_000_000)

    def test_zero_balance_produces_no_payable_item(self):
        company = _company()
        tech = _technician(company)

        item = SettlementPlanner.evaluate_layer2_for_technician(company, tech)

        self.assertFalse(item.eligible)
        self.assertIn("Zero balance", item.blocked_reason)
        self.assertEqual(item.calculation.net_position_rial, 0)

    def test_negative_balance_reported_as_receivable_not_eligible(self):
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=1_000_000, idempotency_key=f"plan-credit-{_n()}",
        )
        TechnicianLedgerService.create_debit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
            amount_rial=4_000_000, idempotency_key=f"plan-debit-{_n()}",
        )

        item = SettlementPlanner.evaluate_layer2_for_technician(company, tech)

        self.assertFalse(item.eligible)
        self.assertIn("receivable", item.blocked_reason.lower())
        self.assertEqual(item.calculation.net_position_rial, -3_000_000)

    def test_already_claimed_ledger_entries_block_technician(self):
        company = _company()
        tech = _technician(company)
        entry = TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"plan-credit-{_n()}",
        )
        _batch_and_claim_ledger_entry(company, entry, status=SettlementBatch.Status.READY)

        item = SettlementPlanner.evaluate_layer2_for_technician(company, tech)

        self.assertFalse(item.eligible)
        self.assertIn("already included", item.blocked_reason)

    def test_released_by_failed_batch_becomes_eligible_again_layer2(self):
        company = _company()
        tech = _technician(company)
        entry = TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"plan-credit-{_n()}",
        )
        _batch_and_claim_ledger_entry(company, entry, status=SettlementBatch.Status.FAILED)

        item = SettlementPlanner.evaluate_layer2_for_technician(company, tech)

        self.assertTrue(item.eligible)

    def test_pending_adjustment_document_blocks_layer2(self):
        company = _company()
        tech = _technician(company)
        entry = TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=5_000_000, idempotency_key=f"plan-credit-{_n()}",
        )
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        AdjustmentDocument.objects.create(
            company=company,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            status=AdjustmentDocument.Status.PENDING_APPROVAL,
            original_invoice=invoice,
            amount_rial=100_000,
            reason="test pending adjustment layer2",
            technician_ledger_entry=entry,
        )

        item = SettlementPlanner.evaluate_layer2_for_technician(company, tech)

        self.assertFalse(item.eligible)
        self.assertIn("AdjustmentDocument", item.blocked_reason)

    def test_unresolved_backfill_task_blocks_layer2(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=5_000_000, idempotency_key=f"plan-credit-{_n()}",
            invoice=invoice,
        )
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
            invoice=invoice,
            error_message="simulated unresolved failure",
        )

        item = SettlementPlanner.evaluate_layer2_for_technician(company, tech)

        self.assertFalse(item.eligible)
        self.assertIn("FinancialBackfillTask", item.blocked_reason)

    def test_cross_company_technician_raises(self):
        company_a = _company()
        company_b = _company()
        tech_b = _technician(company_b)

        with self.assertRaises(ValueError):
            SettlementPlanner.evaluate_layer2_for_technician(company_a, tech_b)

    def test_plan_layer2_for_company_buckets_results(self):
        company = _company()
        payable_tech = _technician(company)
        zero_tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=payable_tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=2_000_000, idempotency_key=f"plan-credit-{_n()}",
        )

        report = SettlementPlanner.plan_layer2_for_company(company)

        self.assertIsInstance(report, Layer2PlanningReport)
        eligible_ids = {i.technician_id for i in report.eligible_items}
        blocked_ids = {i.technician_id for i in report.blocked_items}
        self.assertIn(payable_tech.id, eligible_ids)
        self.assertIn(zero_tech.id, blocked_ids)

    def test_plan_layer2_for_company_with_technician_filter(self):
        company = _company()
        tech_a = _technician(company)
        tech_b = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech_a,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=1_000_000, idempotency_key=f"plan-credit-{_n()}",
        )
        TechnicianLedgerService.create_credit(
            company=company, technician=tech_b,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=99_000_000, idempotency_key=f"plan-credit-{_n()}",
        )

        report = SettlementPlanner.plan_layer2_for_company(company, technician=tech_a)

        all_ids = {i.technician_id for i in report.eligible_items} | {
            i.technician_id for i in report.blocked_items
        }
        self.assertEqual(all_ids, {tech_a.id})


# =============================================================================
# Determinism, read-only guarantee, tenant isolation
# =============================================================================

class DeterminismAndSafetyTest(TestCase):

    def test_deterministic_repeated_planning_layer1(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        results = [SettlementPlanner.evaluate_layer1_for_invoice(invoice) for _ in range(5)]

        self.assertEqual(len(set(results)), 1, "all 5 calls must produce an identical result")

    def test_deterministic_repeated_planning_layer2(self):
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=3_000_000, idempotency_key=f"plan-credit-{_n()}",
        )

        results = [
            SettlementPlanner.evaluate_layer2_for_technician(company, tech) for _ in range(5)
        ]

        self.assertEqual(len(set(results)), 1, "all 5 calls must produce an identical result")

    def test_no_database_writes_occur_during_planning(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        with CaptureQueriesContext(connection) as ctx:
            SettlementPlanner.evaluate_layer1_for_invoice(invoice)
            SettlementPlanner.evaluate_layer2_for_technician(company, tech)
            SettlementPlanner.plan_layer1_for_company(company)
            SettlementPlanner.plan_layer2_for_company(company)

        self.assertGreater(len(ctx.captured_queries), 0, "sanity check: queries were actually issued")
        for query in ctx.captured_queries:
            sql = query["sql"].strip().upper()
            self.assertTrue(
                sql.startswith("SELECT"),
                f"planner issued a non-SELECT statement: {query['sql']}",
            )

    def test_no_row_counts_change_during_planning(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        before = {
            "invoice": Invoice.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "ledger": TechnicianLedgerEntry.objects.count(),
            "batch": SettlementBatch.objects.count(),
        }

        SettlementPlanner.plan_layer1_for_company(company)
        SettlementPlanner.plan_layer2_for_company(company)

        after = {
            "invoice": Invoice.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "ledger": TechnicianLedgerEntry.objects.count(),
            "batch": SettlementBatch.objects.count(),
        }
        self.assertEqual(before, after)

    def test_tenant_isolation_layer1(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a, service_pct=60, goods_pct=10, travel_pct=100)
        tech_b = _technician(company_b, service_pct=60, goods_pct=10, travel_pct=100)

        invoice_a, _ = _distributed_invoice(company_a, tech_a, total=10_000_000, fee_percent=1)
        _invoice_b, _ = _distributed_invoice(company_b, tech_b, total=999_999_999, fee_percent=5)

        report_a = SettlementPlanner.plan_layer1_for_company(company_a)

        eligible_invoice_ids = {i.invoice_id for i in report_a.eligible_items}
        self.assertIn(invoice_a.id, eligible_invoice_ids)
        for item in report_a.eligible_items + report_a.blocked_items:
            self.assertEqual(item.company_id, company_a.id)

    def test_tenant_isolation_layer2(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a)
        tech_b = _technician(company_b)

        TechnicianLedgerService.create_credit(
            company=company_a, technician=tech_a,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=1_000_000, idempotency_key=f"plan-iso-a-{_n()}",
        )
        TechnicianLedgerService.create_credit(
            company=company_b, technician=tech_b,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=99_000_000, idempotency_key=f"plan-iso-b-{_n()}",
        )

        report_a = SettlementPlanner.plan_layer2_for_company(company_a)

        all_items = report_a.eligible_items + report_a.blocked_items
        self.assertEqual({i.technician_id for i in all_items}, {tech_a.id})
        for item in all_items:
            self.assertEqual(item.company_id, company_a.id)
