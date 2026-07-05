"""
Sprint 4 — Settlement Engine, Phase B Step 3: Settlement Batch Builder Tests.

Exercises SettlementBatchBuilder (apps/payouts/services_settlement_batch_builder.py)
against real, already-persisted financial records produced by the existing
Sprint 3 payment/invoice flow (Layer 1) and direct ledger-entry
construction via TechnicianLedgerService (Layer 2) — mirroring the exact
fixture conventions already used in test_sprint4_settlement_planner.py.

This is the first Sprint 4 test file whose subject module actually writes
to the database (SettlementBatch / SettlementItem creation, EscrowRecord
PENDING_SETTLEMENT transition). It never exercises settlement execution
(mark_executing / mark_completed / mark_failed on a Builder-created batch),
bank transfer, refund, or any mutation of Payment/Invoice status.
"""
import itertools
from decimal import Decimal

from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.services import PaymentCallbackService
from apps.payouts.models import (
    EscrowRecord,
    SettlementBatch,
    SettlementItem,
    TechnicianLedgerEntry,
)
from apps.payouts.services import TechnicianLedgerService
from apps.payouts.services_settlement_batch import SettlementBatchService, SettlementItemService
from apps.payouts.services_settlement_batch_builder import (
    BatchBuildResult,
    SettlementBatchBuilder,
    SettlementBatchBuilderError,
)
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Builder Test Co {tag}",
        "code": f"build{tag}",
        "slug": f"build-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"buildtech{_n()}",
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
        title=f"Builder Test Order {_n()}",
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
    payment = _pending_payment(company, invoice, gateway, f"SUCCESS-build-{_n()}")
    success, _, _ = PaymentCallbackService.handle_callback(
        company=company, reference_id=payment.reference_id,
    )
    assert success, "setup failed: payment callback did not succeed"
    invoice.refresh_from_db()
    return invoice, payment


def _period():
    return (
        timezone.now() - timezone.timedelta(days=1),
        timezone.now() + timezone.timedelta(days=1),
    )


def _batch_and_claim_invoice(invoice, *, status=SettlementBatch.Status.READY):
    company = invoice.company
    batch = SettlementBatchService.create_batch(
        company=company,
        level=SettlementBatch.Level.PLATFORM_TO_ORG,
        period_start=timezone.now() - timezone.timedelta(days=2),
        period_end=timezone.now() - timezone.timedelta(hours=1),
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
        period_start=timezone.now() - timezone.timedelta(days=2),
        period_end=timezone.now() - timezone.timedelta(hours=1),
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

class Layer1BatchBuilderTest(TestCase):

    def test_creates_ready_batch_from_eligible_distributed_escrow(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        self.assertIsInstance(result, BatchBuildResult)
        self.assertIsNotNone(result.batch)
        self.assertEqual(result.batch.status, SettlementBatch.Status.READY)
        self.assertEqual(result.batch.level, SettlementBatch.Level.PLATFORM_TO_ORG)
        self.assertEqual(result.batch.company_id, company.id)
        self.assertEqual(result.items_created, 1)

    def test_creates_correct_settlement_item(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        escrow = EscrowRecord.objects.get(payment=payment)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        items = SettlementItem.objects.filter(batch=result.batch)
        self.assertEqual(items.count(), 1)
        item = items.first()
        self.assertEqual(item.invoice_id, invoice.id)
        self.assertEqual(item.company_id, company.id)
        self.assertEqual(item.amount_rial, escrow.organization_share_rial)

    def test_batch_totals_equal_item_totals(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        _distributed_invoice(company, tech, total=5_000_000, fee_percent=1)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        item_sum = sum(
            SettlementItem.objects.filter(batch=result.batch).values_list("amount_rial", flat=True)
        )
        self.assertEqual(item_sum, result.batch.net_amount_rial)
        self.assertEqual(result.net_amount_rial, item_sum)
        self.assertEqual(result.batch.items_count, 2)

    def test_escrow_becomes_pending_settlement(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        period_start, period_end = _period()

        SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        escrow = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(escrow.status, EscrowRecord.Status.PENDING_SETTLEMENT)
        self.assertIsNotNone(escrow.settlement_batch_id)

    def test_running_twice_does_not_duplicate_items(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        period_start, period_end = _period()

        result1 = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)
        result2 = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        self.assertEqual(result1.items_created, 1)
        self.assertIsNone(result2.batch, "second run must find nothing eligible left")
        self.assertEqual(SettlementItem.objects.filter(company=company).count(), 1)
        self.assertEqual(
            SettlementBatch.objects.filter(company=company, level=SettlementBatch.Level.PLATFORM_TO_ORG).count(),
            1,
        )

    def test_no_eligible_items_creates_no_batch(self):
        company = _company()
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        self.assertIsNone(result.batch)
        self.assertEqual(result.items_created, 0)
        self.assertEqual(SettlementBatch.objects.filter(company=company).count(), 0)

    def test_already_batched_invoice_excluded(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        _batch_and_claim_invoice(invoice, status=SettlementBatch.Status.READY)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        self.assertIsNone(result.batch)

    def test_failed_batch_releases_item_eligibility(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        _batch_and_claim_invoice(invoice, status=SettlementBatch.Status.FAILED)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        self.assertIsNotNone(result.batch)
        self.assertEqual(result.items_created, 1)
        items = SettlementItem.objects.filter(batch=result.batch)
        self.assertEqual(items.first().invoice_id, invoice.id)

    def test_tenant_isolation(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a, service_pct=60, goods_pct=10, travel_pct=100)
        tech_b = _technician(company_b, service_pct=60, goods_pct=10, travel_pct=100)
        _distributed_invoice(company_a, tech_a, total=10_000_000, fee_percent=1)
        _distributed_invoice(company_b, tech_b, total=999_999_999, fee_percent=5)
        period_start, period_end = _period()

        result_a = SettlementBatchBuilder.build_layer1_batch(company_a, period_start, period_end)

        self.assertIsNotNone(result_a.batch)
        self.assertEqual(result_a.batch.company_id, company_a.id)
        for item in SettlementItem.objects.filter(batch=result_a.batch):
            self.assertEqual(item.company_id, company_a.id)
        # company_b's invoice must never appear in company_a's batch.
        self.assertNotEqual(result_a.net_amount_rial, 999_999_999)

    def test_invalid_period_raises(self):
        company = _company()
        now = timezone.now()

        with self.assertRaises(SettlementBatchBuilderError):
            SettlementBatchBuilder.build_layer1_batch(company, now, now - timezone.timedelta(days=1))


# =============================================================================
# Layer 2 — Organization <-> Provider
# =============================================================================

class Layer2BatchBuilderTest(TestCase):

    def test_creates_ready_batch_from_payable_balance(self):
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertIsNotNone(result.batch)
        self.assertEqual(result.batch.status, SettlementBatch.Status.READY)
        self.assertEqual(result.batch.level, SettlementBatch.Level.ORG_TO_PROVIDER)
        self.assertEqual(result.net_amount_rial, 6_000_000)

    def test_creates_correct_settlement_item_from_ledger_entry(self):
        company = _company()
        tech = _technician(company)
        entry = TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        items = SettlementItem.objects.filter(batch=result.batch)
        self.assertEqual(items.count(), 1)
        item = items.first()
        self.assertEqual(item.ledger_entry_id, entry.id)
        self.assertEqual(item.amount_rial, 6_000_000)
        self.assertEqual(item.company_id, company.id)

    def test_zero_balance_creates_no_batch(self):
        company = _company()
        _technician(company)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertIsNone(result.batch)

    def test_negative_balance_creates_no_payable_item(self):
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=1_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        TechnicianLedgerService.create_debit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
            amount_rial=4_000_000, idempotency_key=f"build-debit-{_n()}",
        )
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertIsNone(result.batch)
        self.assertEqual(SettlementItem.objects.filter(company=company).count(), 0)

    def test_running_twice_does_not_duplicate_ledger_items(self):
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        period_start, period_end = _period()

        result1 = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)
        result2 = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertEqual(result1.items_created, 1)
        self.assertIsNone(result2.batch, "second run must find nothing eligible left")
        self.assertEqual(SettlementItem.objects.filter(company=company).count(), 1)

    def test_already_batched_ledger_entry_excluded(self):
        company = _company()
        tech = _technician(company)
        entry = TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        _batch_and_claim_ledger_entry(company, entry, status=SettlementBatch.Status.READY)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertIsNone(result.batch)

    def test_failed_batch_releases_ledger_entry_eligibility(self):
        company = _company()
        tech = _technician(company)
        entry = TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        _batch_and_claim_ledger_entry(company, entry, status=SettlementBatch.Status.FAILED)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertIsNotNone(result.batch)
        self.assertEqual(result.items_created, 1)

    def test_technician_filter_scopes_to_one_technician(self):
        company = _company()
        tech_a = _technician(company)
        tech_b = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech_a,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=1_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        TechnicianLedgerService.create_credit(
            company=company, technician=tech_b,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=2_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer2_batch(
            company, period_start, period_end, technician=tech_a,
        )

        self.assertEqual(result.net_amount_rial, 1_000_000)
        item = SettlementItem.objects.get(batch=result.batch)
        self.assertEqual(item.ledger_entry.technician_id, tech_a.id)

    def test_tenant_isolation(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a)
        tech_b = _technician(company_b)
        TechnicianLedgerService.create_credit(
            company=company_a, technician=tech_a,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=1_000_000, idempotency_key=f"build-iso-a-{_n()}",
        )
        TechnicianLedgerService.create_credit(
            company=company_b, technician=tech_b,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=99_000_000, idempotency_key=f"build-iso-b-{_n()}",
        )
        period_start, period_end = _period()

        result_a = SettlementBatchBuilder.build_layer2_batch(company_a, period_start, period_end)

        self.assertEqual(result_a.net_amount_rial, 1_000_000)
        for item in SettlementItem.objects.filter(batch=result_a.batch):
            self.assertEqual(item.company_id, company_a.id)


# =============================================================================
# Concurrency
# =============================================================================

class ConcurrencyTest(TestCase):

    def test_layer1_builder_locks_company_financial_policy_row(self):
        """
        Verify the company-level lock is actually acquired: after
        build_layer1_batch() completes, a CompanyFinancialPolicy row must
        exist for the company (created via get_or_create as part of
        acquiring the lock, per the approved ADR), even if none was
        explicitly created beforehand.
        """
        company = _company()  # no _financial_policy() call — none exists yet
        tech = _technician(company)
        # Deliberately does not call _financial_policy(); build_layer1_batch
        # itself must get_or_create it as part of locking.
        period_start, period_end = _period()

        self.assertFalse(CompanyFinancialPolicy.objects.filter(company=company).exists())

        SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        self.assertTrue(CompanyFinancialPolicy.objects.filter(company=company).exists())

    def test_layer2_builder_locks_company_financial_policy_row(self):
        company = _company()
        _technician(company)
        period_start, period_end = _period()

        self.assertFalse(CompanyFinancialPolicy.objects.filter(company=company).exists())

        SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertTrue(CompanyFinancialPolicy.objects.filter(company=company).exists())

    def test_build_layer1_batch_runs_inside_atomic_transaction(self):
        """
        Verify transaction.atomic() usage indirectly: forcing a failure
        after the batch row is created (by making a defensive integrity
        check fail) must roll back the batch itself too — proving the
        whole operation is one atomic unit, not partially committed.
        """
        from unittest.mock import patch

        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        period_start, period_end = _period()

        with patch(
            "apps.payouts.services_settlement_batch_builder._assert_batch_totals_match_items",
            side_effect=SettlementBatchBuilderError("forced failure for atomicity test"),
        ):
            with self.assertRaises(SettlementBatchBuilderError):
                SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        # If the transaction were NOT atomic, the batch row created before
        # the forced failure would still exist. It must not.
        self.assertEqual(SettlementBatch.objects.filter(company=company).count(), 0)
        self.assertEqual(SettlementItem.objects.filter(company=company).count(), 0)

    def test_build_layer2_batch_runs_inside_atomic_transaction(self):
        from unittest.mock import patch

        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        period_start, period_end = _period()

        with patch(
            "apps.payouts.services_settlement_batch_builder._assert_batch_totals_match_items",
            side_effect=SettlementBatchBuilderError("forced failure for atomicity test"),
        ):
            with self.assertRaises(SettlementBatchBuilderError):
                SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertEqual(SettlementBatch.objects.filter(company=company).count(), 0)
        self.assertEqual(SettlementItem.objects.filter(company=company).count(), 0)


# =============================================================================
# Safety — no execution, no bank transfer, no unrelated mutation
# =============================================================================

class SafetyTest(TestCase):

    def test_no_bank_transfer_no_completion_layer1(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        self.assertEqual(result.batch.status, SettlementBatch.Status.READY)
        self.assertIsNone(result.batch.executed_at)
        self.assertEqual(result.batch.bank_reference, "")
        self.assertEqual(result.batch.failure_reason, "")

    def test_no_bank_transfer_no_completion_layer2(self):
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        period_start, period_end = _period()

        result = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        self.assertEqual(result.batch.status, SettlementBatch.Status.READY)
        self.assertIsNone(result.batch.executed_at)
        self.assertEqual(result.batch.bank_reference, "")

    def test_no_ledger_settlement_completion_entry_created(self):
        """
        The Builder must never create a NEW TechnicianLedgerEntry (e.g. a
        settlement-completion DEBIT) — it only references EXISTING entries
        via SettlementItem.ledger_entry.
        """
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000, idempotency_key=f"build-credit-{_n()}",
        )
        before_count = TechnicianLedgerEntry.objects.filter(company=company).count()
        period_start, period_end = _period()

        SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)

        after_count = TechnicianLedgerEntry.objects.filter(company=company).count()
        self.assertEqual(before_count, after_count, "no new ledger entry must be created")

    def test_no_payment_or_invoice_status_mutation(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        invoice_status_before = invoice.status
        payment_status_before = payment.status
        period_start, period_end = _period()

        SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        invoice.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(invoice.status, invoice_status_before)
        self.assertEqual(payment.status, payment_status_before)
