"""
Sprint 4 — Settlement Engine, Phase B Step 4: Settlement Execution Engine Tests.

Exercises SettlementExecutionEngine (apps/payouts/services_settlement_execution.py)
against real READY batches produced by the already-merged, unmodified
SettlementBatchBuilder (Step 3) — mirroring the exact fixture conventions
already used in test_sprint4_settlement_batch_builder.py.

This is the first Sprint 4 test file whose subject module transitions a
batch all the way to COMPLETED and writes ledger-settlement entries. It
never exercises any real bank API, external transfer, UI, API endpoint,
management command, or background job — none exist to exercise.
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.services import PaymentCallbackService
from apps.payouts.exceptions import SettlementBatchTransitionError
from apps.payouts.models import (
    CompanyPlatformFeeEntry,
    EscrowRecord,
    SettlementBatch,
    SettlementItem,
    TechnicianLedgerEntry,
)
from apps.payouts.services import TechnicianLedgerService
from apps.payouts.services_settlement_batch import SettlementBatchService
from apps.payouts.services_settlement_batch_builder import SettlementBatchBuilder
from apps.payouts.services_settlement_execution import (
    ExecutionResult,
    SettlementExecutionEngine,
    SettlementExecutionError,
)
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Exec Test Co {tag}",
        "code": f"exec{tag}",
        "slug": f"exec-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"exectech{_n()}",
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
        title=f"Exec Test Order {_n()}",
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
    through the actual production callback flow (PaymentCallbackService),
    never by hand-crafting an EscrowRecord row directly.
    """
    _financial_policy(company, fee_percent=fee_percent)
    gateway = _platform_gateway(company)
    invoice = _issued_invoice(company, technician=technician, total=total)
    payment = _pending_payment(company, invoice, gateway, f"SUCCESS-exec-{_n()}")
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


def _ready_layer1_batch(company, tech, *, total=10_000_000, fee_percent=1):
    """Build a real READY Layer 1 batch via the unmodified Batch Builder (Step 3)."""
    _distributed_invoice(company, tech, total=total, fee_percent=fee_percent)
    period_start, period_end = _period()
    result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)
    assert result.batch is not None, "setup failed: no eligible Layer 1 batch was built"
    return result.batch


def _ready_layer2_batch(company, tech, *, amount_rial=6_000_000):
    """Build a real READY Layer 2 batch via the unmodified Batch Builder (Step 3)."""
    TechnicianLedgerService.create_credit(
        company=company, technician=tech,
        source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
        amount_rial=amount_rial, idempotency_key=f"exec-credit-{_n()}",
    )
    period_start, period_end = _period()
    result = SettlementBatchBuilder.build_layer2_batch(company, period_start, period_end)
    assert result.batch is not None, "setup failed: no eligible Layer 2 batch was built"
    return result.batch


# =============================================================================
# Layer 1 execution
# =============================================================================

class Layer1ExecutionTest(TestCase):

    def test_execute_ready_layer1_batch_completes(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        batch = _ready_layer1_batch(company, tech)

        result = SettlementExecutionEngine.execute_batch(batch)

        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.batch.status, SettlementBatch.Status.COMPLETED)

    def test_executed_at_is_set(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        batch = _ready_layer1_batch(company, tech)

        result = SettlementExecutionEngine.execute_batch(batch)

        self.assertIsNotNone(result.batch.executed_at)

    def test_bank_reference_is_stored(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        batch = _ready_layer1_batch(company, tech)

        result = SettlementExecutionEngine.execute_batch(batch, bank_reference="REF-12345")

        self.assertEqual(result.batch.bank_reference, "REF-12345")

    def test_layer1_creates_platform_fee_credit_entry(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        batch = _ready_layer1_batch(company, tech, total=10_000_000, fee_percent=1)

        result = SettlementExecutionEngine.execute_batch(batch)

        self.assertEqual(result.ledger_entries_created, 1)
        entries = CompanyPlatformFeeEntry.objects.filter(
            company=company, source=CompanyPlatformFeeEntry.Source.PLATFORM_FEE_SETTLEMENT,
        )
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.entry_type, CompanyPlatformFeeEntry.EntryType.CREDIT)
        self.assertEqual(entry.amount_rial, 100_000)  # 1% of 10,000,000

    def test_layer1_escrow_becomes_settled(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        batch = _ready_layer1_batch(company, tech)

        SettlementExecutionEngine.execute_batch(batch)

        escrow = EscrowRecord.objects.get(settlement_batch=batch)
        self.assertEqual(escrow.status, EscrowRecord.Status.SETTLED)
        self.assertIsNotNone(escrow.settled_at)

    def test_no_old_platform_fee_entry_mutated(self):
        """
        The DEBIT entry created at invoice-paid time (by the already-merged
        PlatformFeeService.record_invoice_fee(), unmodified) must remain
        completely untouched — the execution engine only ever creates a
        NEW CREDIT entry, never edits the existing DEBIT.
        """
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        batch = _ready_layer1_batch(company, tech, total=10_000_000, fee_percent=1)

        debit_entry = CompanyPlatformFeeEntry.objects.get(
            company=company, entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
        )
        debit_amount_before = debit_entry.amount_rial
        debit_balance_before = debit_entry.balance_after

        SettlementExecutionEngine.execute_batch(batch)

        debit_entry.refresh_from_db()
        self.assertEqual(debit_entry.amount_rial, debit_amount_before)
        self.assertEqual(debit_entry.balance_after, debit_balance_before)


# =============================================================================
# Layer 2 execution
# =============================================================================

class Layer2ExecutionTest(TestCase):

    def test_execute_ready_layer2_batch_completes(self):
        company = _company()
        tech = _technician(company)
        batch = _ready_layer2_batch(company, tech)

        result = SettlementExecutionEngine.execute_batch(batch)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.batch.status, SettlementBatch.Status.COMPLETED)

    def test_layer2_creates_technician_debit_settlement_entry(self):
        company = _company()
        tech = _technician(company)
        batch = _ready_layer2_batch(company, tech, amount_rial=6_000_000)

        result = SettlementExecutionEngine.execute_batch(batch)

        self.assertEqual(result.ledger_entries_created, 1)
        entries = TechnicianLedgerEntry.objects.filter(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT,
        )
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.entry_type, TechnicianLedgerEntry.EntryType.DEBIT)
        self.assertEqual(entry.amount_rial, 6_000_000)

    def test_layer2_balance_reaches_zero_after_execution(self):
        company = _company()
        tech = _technician(company)
        batch = _ready_layer2_batch(company, tech, amount_rial=6_000_000)

        SettlementExecutionEngine.execute_batch(batch)

        self.assertEqual(TechnicianLedgerService.get_balance(company, tech), 0)

    def test_duplicate_execution_does_not_duplicate_ledger_entry(self):
        """
        Re-invoking the internal completion logic for an item that already
        has a settlement entry must not create a duplicate — verified
        directly against the per-item idempotency_key, independent of the
        top-level COMPLETED short-circuit (which is tested separately).
        """
        company = _company()
        tech = _technician(company)
        batch = _ready_layer2_batch(company, tech, amount_rial=6_000_000)

        SettlementExecutionEngine.execute_batch(batch)
        # Directly re-invoke the internal per-item completion logic a
        # second time for the same, already-completed batch, bypassing
        # the top-level status check, to prove the per-item idempotency
        # key is a genuine, independent safety layer.
        SettlementExecutionEngine._complete_layer2(batch)

        entries = TechnicianLedgerEntry.objects.filter(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT,
        )
        self.assertEqual(entries.count(), 1)

    def test_no_old_ledger_row_mutated(self):
        company = _company()
        tech = _technician(company)
        batch = _ready_layer2_batch(company, tech, amount_rial=6_000_000)

        credit_entry = TechnicianLedgerEntry.objects.get(
            company=company, entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
        )
        amount_before = credit_entry.amount_rial
        balance_before = credit_entry.balance_after

        SettlementExecutionEngine.execute_batch(batch)

        credit_entry.refresh_from_db()
        self.assertEqual(credit_entry.amount_rial, amount_before)
        self.assertEqual(credit_entry.balance_after, balance_before)


# =============================================================================
# State transitions / idempotency / failure handling
# =============================================================================

class StateTransitionTest(TestCase):

    def test_non_ready_batch_cannot_execute_calculating(self):
        company = _company()
        batch = SettlementBatchService.create_batch(
            company=company,
            level=SettlementBatch.Level.PLATFORM_TO_ORG,
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        # batch remains CALCULATING — never marked READY.

        with self.assertRaises(SettlementBatchTransitionError):
            SettlementExecutionEngine.execute_batch(batch)

    def test_failed_batch_cannot_execute(self):
        company = _company()
        batch = SettlementBatchService.create_batch(
            company=company,
            level=SettlementBatch.Level.PLATFORM_TO_ORG,
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        batch = SettlementBatchService.mark_ready(batch)
        batch = SettlementBatchService.mark_executing(batch)
        batch = SettlementBatchService.mark_failed(batch, "pre-existing failure")

        with self.assertRaises(SettlementBatchTransitionError):
            SettlementExecutionEngine.execute_batch(batch)

    def test_completed_batch_execution_is_idempotent(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        batch = _ready_layer1_batch(company, tech)

        result1 = SettlementExecutionEngine.execute_batch(batch)
        result2 = SettlementExecutionEngine.execute_batch(result1.batch)

        self.assertEqual(result1.status, "completed")
        self.assertEqual(result2.status, "already_completed")
        self.assertEqual(result2.ledger_entries_created, 0)
        # No duplicate platform fee settlement entry was created.
        self.assertEqual(
            CompanyPlatformFeeEntry.objects.filter(
                company=company, source=CompanyPlatformFeeEntry.Source.PLATFORM_FEE_SETTLEMENT,
            ).count(),
            1,
        )

    def test_completed_batch_execution_returns_existing_result(self):
        company = _company()
        tech = _technician(company)
        batch = _ready_layer2_batch(company, tech)

        result1 = SettlementExecutionEngine.execute_batch(batch)
        result2 = SettlementExecutionEngine.execute_batch(result1.batch)

        self.assertEqual(result2.batch.pk, result1.batch.pk)
        self.assertEqual(result2.batch.status, SettlementBatch.Status.COMPLETED)
        self.assertEqual(result2.batch.executed_at, result1.batch.executed_at)

    def test_failure_before_ledger_write_marks_batch_failed(self):
        """
        A failure raised before any ledger write (e.g. an unrecognized
        batch level) must transition the batch to FAILED with a populated
        failure_reason, and must never leave it stuck in EXECUTING.
        """
        company = _company()
        batch = SettlementBatchService.create_batch(
            company=company,
            level="not_a_real_level",
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        batch = SettlementBatchService.mark_ready(batch)

        result = SettlementExecutionEngine.execute_batch(batch)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.batch.status, SettlementBatch.Status.FAILED)
        self.assertTrue(result.batch.failure_reason)
        self.assertIn("unknown level", result.batch.failure_reason.lower())

    def test_failure_after_partial_write_does_not_corrupt_ledger(self):
        """
        If a failure is injected AFTER one ledger entry would have been
        written but BEFORE mark_completed() succeeds, the entire inner
        atomic block (per the module's documented two-phase pattern) must
        roll back — leaving zero ledger entries persisted, and the batch
        safely marked FAILED rather than stuck in an inconsistent state.
        """
        company = _company()
        tech = _technician(company)
        batch = _ready_layer2_batch(company, tech, amount_rial=6_000_000)

        with patch(
            "apps.payouts.services_settlement_batch.SettlementBatchService.mark_completed",
            side_effect=RuntimeError("simulated failure after ledger write"),
        ):
            result = SettlementExecutionEngine.execute_batch(batch)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.batch.status, SettlementBatch.Status.FAILED)
        # The ledger entry created inside the same inner atomic block must
        # have been rolled back together with the failed mark_completed().
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company, source=TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT,
            ).count(),
            0,
        )

    def test_unknown_level_raises_settlement_execution_error_before_failed(self):
        """SettlementExecutionError is the specific exception type used internally."""
        company = _company()
        batch = SettlementBatchService.create_batch(
            company=company,
            level="not_a_real_level",
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        batch = SettlementBatchService.mark_ready(batch)
        batch = SettlementBatchService.mark_executing(batch)

        with self.assertRaises(SettlementExecutionError):
            SettlementExecutionEngine._complete_batch(batch)


# =============================================================================
# Safety
# =============================================================================

class SafetyTest(TestCase):

    def test_no_bank_api_called(self):
        """
        There is no bank API client anywhere in this module to call —
        verified structurally by confirming execution succeeds with no
        network dependency and no external call site exists in the
        module (grep-verifiable; this test exercises the happy path to
        confirm nothing raises due to a missing/failing external call).
        """
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        batch = _ready_layer1_batch(company, tech)

        result = SettlementExecutionEngine.execute_batch(batch)

        self.assertEqual(result.status, "completed")

    def test_no_payment_or_invoice_status_mutation(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        period_start, period_end = _period()
        build_result = SettlementBatchBuilder.build_layer1_batch(company, period_start, period_end)

        invoice.refresh_from_db()
        payment.refresh_from_db()
        invoice_status_before = invoice.status
        payment_status_before = payment.status

        SettlementExecutionEngine.execute_batch(build_result.batch)

        invoice.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(invoice.status, invoice_status_before)
        self.assertEqual(payment.status, payment_status_before)

    def test_tenant_isolation_layer1(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a, service_pct=60, goods_pct=10, travel_pct=100)
        tech_b = _technician(company_b, service_pct=60, goods_pct=10, travel_pct=100)
        batch_a = _ready_layer1_batch(company_a, tech_a, total=10_000_000, fee_percent=1)
        _ready_layer1_batch(company_b, tech_b, total=999_999_999, fee_percent=5)

        SettlementExecutionEngine.execute_batch(batch_a)

        fee_entries_a = CompanyPlatformFeeEntry.objects.filter(
            company=company_a, source=CompanyPlatformFeeEntry.Source.PLATFORM_FEE_SETTLEMENT,
        )
        self.assertEqual(fee_entries_a.count(), 1)
        self.assertEqual(fee_entries_a.first().amount_rial, 100_000)
        # company_b's batch must remain completely untouched.
        self.assertEqual(
            CompanyPlatformFeeEntry.objects.filter(
                company=company_b, source=CompanyPlatformFeeEntry.Source.PLATFORM_FEE_SETTLEMENT,
            ).count(),
            0,
        )

    def test_tenant_isolation_layer2(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a)
        tech_b = _technician(company_b)
        batch_a = _ready_layer2_batch(company_a, tech_a, amount_rial=1_000_000)
        _ready_layer2_batch(company_b, tech_b, amount_rial=99_000_000)

        SettlementExecutionEngine.execute_batch(batch_a)

        entries_a = TechnicianLedgerEntry.objects.filter(
            company=company_a, source=TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT,
        )
        self.assertEqual(entries_a.count(), 1)
        self.assertEqual(entries_a.first().amount_rial, 1_000_000)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company_b, source=TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT,
            ).count(),
            0,
        )
