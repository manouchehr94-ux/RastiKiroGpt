"""
Sprint 4 — Settlement Engine, Phase B Step 1: Settlement Calculator Tests.

Exercises SettlementCalculator (apps/payouts/services_settlement_calculator.py)
against real, already-persisted financial records produced by the existing
Sprint 3 payment/invoice flow (for Layer 1) and direct ledger-entry
construction via TechnicianLedgerService (for Layer 2) — never by
constructing calculator inputs that could not actually occur in production.

This test file verifies ONLY calculation correctness. It does not exercise
any settlement execution, batch creation, or bank transfer, because no such
code exists yet (Step 1 scope).
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
from apps.payouts.models import EscrowRecord, PaymentSplitSnapshot, TechnicianLedgerEntry
from apps.payouts.services import TechnicianLedgerService
from apps.payouts.services_settlement_calculator import (
    Layer1SettlementResult,
    Layer2SettlementResult,
    SettlementCalculator,
    SettlementPosition,
)
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Calc Test Co {tag}",
        "code": f"calc{tag}",
        "slug": f"calc-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"calctech{_n()}",
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
        title=f"Calc Test Order {_n()}",
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
    Build a fully real, DISTRIBUTED-escrow invoice by driving it through
    the actual production callback flow (PaymentCallbackService), never
    by hand-crafting an EscrowRecord row directly. This guarantees the
    calculator is tested against exactly the same data shape production
    code produces.
    """
    _financial_policy(company, fee_percent=fee_percent)
    gateway = _platform_gateway(company)
    invoice = _issued_invoice(company, technician=technician, total=total)
    payment = _pending_payment(company, invoice, gateway, f"SUCCESS-calc-{_n()}")
    success, _, _ = PaymentCallbackService.handle_callback(
        company=company, reference_id=payment.reference_id,
    )
    assert success, "setup failed: payment callback did not succeed"
    invoice.refresh_from_db()
    return invoice, payment


# =============================================================================
# Layer 1 — Platform <-> Organization
# =============================================================================

class Layer1BasicCalculationTest(TestCase):

    def test_platform_gateway_invoice_produces_payable_result(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        self.assertIsInstance(result, Layer1SettlementResult)
        self.assertEqual(result.position, SettlementPosition.PAYABLE)
        self.assertIsNone(result.blocked_reason)
        self.assertEqual(result.gross_invoice_amount_rial, 10_000_000)

    def test_platform_fee_is_read_from_frozen_escrow_split(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        escrow = EscrowRecord.objects.get(payment=payment)
        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        # 1% of 10,000,000 = 100,000
        self.assertEqual(result.platform_commission_rial, 100_000)
        self.assertEqual(result.platform_commission_rial, escrow.platform_commission_rial)
        self.assertEqual(result.provider_share_rial, escrow.provider_share_rial)
        self.assertEqual(result.company_payable_base_rial, escrow.organization_share_rial)

    def test_net_position_equals_organization_share_when_no_direct_split(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        escrow = EscrowRecord.objects.get(payment=payment)
        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        self.assertEqual(result.direct_provider_split_rial, 0)
        self.assertEqual(result.net_position_rial, escrow.organization_share_rial)
        self.assertEqual(result.position, SettlementPosition.PAYABLE)

    def test_direct_split_is_surfaced_but_not_netted(self):
        """
        A PaymentSplitSnapshot with should_split_with_technician=True is
        surfaced in direct_provider_split_rial, but per the module's
        documented, deliberate design, it is NOT subtracted from
        net_position_rial in Step 1 (net_position_rial always equals the
        already-frozen organization_share_rial) — this is the disclosed
        architectural inconsistency the calculator surfaces honestly
        rather than silently reconciling.
        """
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        # _distributed_invoice() drives the real PaymentCallbackService flow,
        # which (via PaymentVerifyService.verify() -> PaymentSplitDecisionService
        # .create_snapshot()) already auto-creates a PaymentSplitSnapshot for
        # this payment as a non-blocking side effect. PaymentSplitSnapshot.payment
        # is a OneToOneField ("Written once per payment", per the model's own
        # docstring) — a second .create() for the same payment violates that
        # constraint. Fetch and update the existing row instead of creating a
        # duplicate, to simulate should_split_with_technician=True for this test.
        snapshot = PaymentSplitSnapshot.objects.get(payment=payment)
        snapshot.total_amount = 10_000_000
        snapshot.platform_fee_amount = 100_000
        snapshot.company_deposit_amount = 3_900_000
        snapshot.technician_direct_amount = 6_000_000
        snapshot.technician_ledger_amount = 0
        snapshot.should_split_with_technician = True
        snapshot.save(update_fields=[
            "total_amount",
            "platform_fee_amount",
            "company_deposit_amount",
            "technician_direct_amount",
            "technician_ledger_amount",
            "should_split_with_technician",
        ])

        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        self.assertEqual(result.direct_provider_split_rial, 6_000_000)
        escrow = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(result.net_position_rial, escrow.organization_share_rial)

    def test_zero_fee_percent_still_produces_correct_result(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=0)

        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        self.assertEqual(result.platform_commission_rial, 0)
        escrow = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(result.company_payable_base_rial, escrow.organization_share_rial)
        self.assertEqual(result.net_position_rial, escrow.organization_share_rial)


class Layer1ExclusionTest(TestCase):
    """Non-platform-gateway / cash / no-escrow invoices must be BLOCKED, never guessed."""

    def test_cash_invoice_is_blocked_not_zero(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        Payment.objects.create(
            company=company,
            invoice=invoice,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
            gateway=None,
        )

        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        self.assertEqual(result.position, SettlementPosition.BLOCKED)
        self.assertIsNotNone(result.blocked_reason)
        self.assertIn("not made through a platform-owned gateway", result.blocked_reason)
        self.assertEqual(result.net_position_rial, 0)

    def test_company_gateway_invoice_is_blocked(self):
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

        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        self.assertEqual(result.position, SettlementPosition.BLOCKED)
        self.assertFalse(EscrowRecord.objects.filter(invoice=invoice).exists())

    def test_no_payment_at_all_is_blocked(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)

        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        self.assertEqual(result.position, SettlementPosition.BLOCKED)

    def test_escrow_held_but_not_yet_distributed_is_blocked(self):
        """
        An EscrowRecord that exists but is still HELD/RESERVED (invoice not
        yet marked PAID) must be BLOCKED, not silently computed with a
        guessed split.
        """
        company = _company()
        tech = _technician(company)
        _financial_policy(company, fee_percent=1)
        gateway = _platform_gateway(company)
        invoice = _issued_invoice(company, technician=tech, total=5_000_000)
        payment = Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=gateway,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
        )
        EscrowRecord.objects.create(
            company=company,
            payment=payment,
            invoice=invoice,
            amount_rial=int(invoice.total_amount),
            status=EscrowRecord.Status.HELD,
        )

        result = SettlementCalculator.calculate_layer1_for_invoice(invoice)

        self.assertEqual(result.position, SettlementPosition.BLOCKED)
        self.assertIn("DISTRIBUTED", result.blocked_reason)


# =============================================================================
# Layer 2 — Organization <-> Provider
# =============================================================================

class Layer2BasicCalculationTest(TestCase):

    def test_simple_credit_balance(self):
        company = _company()
        tech = _technician(company)

        TechnicianLedgerService.create_credit(
            company=company,
            technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000,
            idempotency_key=f"calc-test-credit-{_n()}",
        )

        result = SettlementCalculator.calculate_layer2_for_technician(company, tech)

        self.assertIsInstance(result, Layer2SettlementResult)
        self.assertEqual(result.wage_credit_rial, 6_000_000)
        self.assertEqual(result.net_position_rial, 6_000_000)
        self.assertEqual(result.position, SettlementPosition.PAYABLE)

    def test_direct_split_debit_reduces_outstanding_balance(self):
        company = _company()
        tech = _technician(company)

        TechnicianLedgerService.create_credit(
            company=company,
            technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000,
            idempotency_key=f"calc-test-credit-{_n()}",
        )
        TechnicianLedgerService.create_debit(
            company=company,
            technician=tech,
            source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
            amount_rial=6_000_000,
            idempotency_key=f"calc-test-directdebit-{_n()}",
        )

        result = SettlementCalculator.calculate_layer2_for_technician(company, tech)

        self.assertEqual(result.wage_credit_rial, 6_000_000)
        self.assertEqual(result.direct_split_debit_rial, 6_000_000)
        self.assertEqual(result.net_position_rial, 0)
        self.assertEqual(result.position, SettlementPosition.ZERO)

    def test_zero_balance_case(self):
        company = _company()
        tech = _technician(company)

        result = SettlementCalculator.calculate_layer2_for_technician(company, tech)

        self.assertEqual(result.wage_credit_rial, 0)
        self.assertEqual(result.net_position_rial, 0)
        self.assertEqual(result.position, SettlementPosition.ZERO)
        self.assertIsNone(result.blocked_reason)

    def test_negative_balance_debt_case_is_not_forced_to_zero(self):
        """
        A technician who owes the company (e.g. kept cash beyond their
        wage) must show a negative net_position_rial and RECEIVABLE
        classification — never silently clamped to zero.
        """
        company = _company()
        tech = _technician(company)

        TechnicianLedgerService.create_credit(
            company=company,
            technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=1_000_000,
            idempotency_key=f"calc-test-credit-{_n()}",
        )
        TechnicianLedgerService.create_debit(
            company=company,
            technician=tech,
            source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
            amount_rial=4_000_000,
            idempotency_key=f"calc-test-cashdebit-{_n()}",
        )

        result = SettlementCalculator.calculate_layer2_for_technician(company, tech)

        self.assertEqual(result.net_position_rial, -3_000_000)
        self.assertEqual(result.position, SettlementPosition.RECEIVABLE)
        self.assertEqual(result.other_debit_rial, 4_000_000)

    def test_manual_settlement_debit_reduces_balance(self):
        company = _company()
        tech = _technician(company)

        TechnicianLedgerService.create_credit(
            company=company,
            technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=6_000_000,
            idempotency_key=f"calc-test-credit-{_n()}",
        )
        TechnicianLedgerService.record_manual_settlement(
            company=company,
            technician=tech,
            amount_rial=6_000_000,
            direction="COMPANY_PAID_TECHNICIAN",
        )

        result = SettlementCalculator.calculate_layer2_for_technician(company, tech)

        self.assertEqual(result.settlement_debit_rial, 6_000_000)
        self.assertEqual(result.net_position_rial, 0)
        self.assertEqual(result.position, SettlementPosition.ZERO)

    def test_layer2_matches_existing_get_balance_exactly(self):
        """Regression guard: net_position_rial must equal TechnicianLedgerService.get_balance()."""
        company = _company()
        tech = _technician(company)

        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=7_500_000, idempotency_key=f"calc-test-credit-{_n()}",
        )
        TechnicianLedgerService.create_debit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
            amount_rial=1_200_000, idempotency_key=f"calc-test-debit-{_n()}",
        )

        result = SettlementCalculator.calculate_layer2_for_technician(company, tech)
        expected_balance = TechnicianLedgerService.get_balance(company, tech)

        self.assertEqual(result.net_position_rial, expected_balance)

    def test_cross_company_technician_raises(self):
        company_a = _company()
        company_b = _company()
        tech_b = _technician(company_b)

        with self.assertRaises(ValueError):
            SettlementCalculator.calculate_layer2_for_technician(company_a, tech_b)


# =============================================================================
# Determinism, read-only guarantee, tenant isolation
# =============================================================================

class DeterminismAndSafetyTest(TestCase):

    def test_deterministic_repeated_calculation_layer1(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        results = [SettlementCalculator.calculate_layer1_for_invoice(invoice) for _ in range(5)]

        self.assertEqual(len(set(results)), 1, "all 5 calls must produce an identical result")

    def test_deterministic_repeated_calculation_layer2(self):
        company = _company()
        tech = _technician(company)
        TechnicianLedgerService.create_credit(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=3_000_000, idempotency_key=f"calc-test-credit-{_n()}",
        )

        results = [
            SettlementCalculator.calculate_layer2_for_technician(company, tech) for _ in range(5)
        ]

        self.assertEqual(len(set(results)), 1, "all 5 calls must produce an identical result")

    def test_no_database_writes_occur_during_calculation(self):
        """
        Every SQL statement issued by the calculator must be a SELECT.
        Verifies the module docstring's explicit no-lock / read-only claim
        directly, rather than merely asserting no row counts changed.
        """
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        with CaptureQueriesContext(connection) as ctx:
            SettlementCalculator.calculate_layer1_for_invoice(invoice)
            SettlementCalculator.calculate_layer2_for_technician(company, tech)

        self.assertGreater(len(ctx.captured_queries), 0, "sanity check: queries were actually issued")
        for query in ctx.captured_queries:
            sql = query["sql"].strip().upper()
            self.assertTrue(
                sql.startswith("SELECT"),
                f"calculator issued a non-SELECT statement: {query['sql']}",
            )

    def test_no_row_counts_change_during_calculation(self):
        """Belt-and-suspenders: row counts across every relevant table are unchanged."""
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)

        before = {
            "invoice": Invoice.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "ledger": TechnicianLedgerEntry.objects.count(),
        }

        SettlementCalculator.calculate_layer1_for_invoice(invoice)
        SettlementCalculator.calculate_layer2_for_technician(company, tech)

        after = {
            "invoice": Invoice.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "ledger": TechnicianLedgerEntry.objects.count(),
        }
        self.assertEqual(before, after)

    def test_tenant_isolation_layer1(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a, service_pct=60, goods_pct=10, travel_pct=100)
        tech_b = _technician(company_b, service_pct=60, goods_pct=10, travel_pct=100)

        invoice_a, _ = _distributed_invoice(company_a, tech_a, total=10_000_000, fee_percent=1)
        invoice_b, _ = _distributed_invoice(company_b, tech_b, total=999_999_999, fee_percent=5)

        result_a = SettlementCalculator.calculate_layer1_for_invoice(invoice_a)

        self.assertEqual(result_a.company_id, company_a.id)
        self.assertEqual(result_a.gross_invoice_amount_rial, 10_000_000)
        self.assertNotEqual(result_a.gross_invoice_amount_rial, 999_999_999)

    def test_tenant_isolation_layer2(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a)
        tech_b = _technician(company_b)

        TechnicianLedgerService.create_credit(
            company=company_a, technician=tech_a,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=1_000_000, idempotency_key=f"calc-iso-a-{_n()}",
        )
        TechnicianLedgerService.create_credit(
            company=company_b, technician=tech_b,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=99_000_000, idempotency_key=f"calc-iso-b-{_n()}",
        )

        result_a = SettlementCalculator.calculate_layer2_for_technician(company_a, tech_a)

        self.assertEqual(result_a.net_position_rial, 1_000_000)
        self.assertNotEqual(result_a.net_position_rial, 99_000_000)
