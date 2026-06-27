"""
TASK-010C — Direct Gateway Settlement DEBIT on Online Payment Success.

Tests:
 1. Creates one DEBIT when snapshot says split=True and amount > 0.
 2. DEBIT amount equals PaymentSplitSnapshot.technician_direct_amount.
 3. Source is DIRECT_GATEWAY_SETTLEMENT.
 4. Order FK is set on DEBIT entry.
 5. Invoice FK is set on DEBIT entry.
 6. Payment FK is set on DEBIT entry.
 7. Metadata contains metadata_version=1.
 8. Metadata contains payment_id, invoice_id, order_id, technician_id.
 9. Idempotency: calling service twice creates only one DEBIT.
10. No DEBIT when no PaymentSplitSnapshot exists.
11. No DEBIT when should_split_with_technician=False.
12. No DEBIT when technician_direct_amount=0.
13. No DEBIT when gateway owner_type is COMPANY.
14. No DEBIT when payment has no invoice.
15. No DEBIT when invoice has no order.
16. No DEBIT when order has no technician.
17. No DEBIT on cross-company technician mismatch.
18. balance_after decreases by direct settlement amount after DEBIT.
19. Description is canonical Persian string.
20. PaymentVerifyService.verify() integration creates DEBIT for platform split payment.
21. PaymentVerifyService.verify() integration does not create DEBIT for non-split payment.
22. Unexpected failure in direct settlement hook does not crash PaymentVerifyService.verify().
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
from apps.payouts.models import PaymentSplitSnapshot, TechnicianLedgerEntry
from apps.payouts.services import TechnicianLedgerService
from apps.payouts.services_direct_settlement import TechnicianDirectSettlementService
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company():
    tag = _n()
    return Company.objects.create(
        name=f"DirectSettleCo {tag}",
        code=f"dsettle{tag}",
        slug=f"dsettle-{tag}",
        is_active=True,
    )


def _technician(company, verified=True, sub_merchant="SUB-TEST-001"):
    user = CompanyUser.objects.create_user(
        username=f"tech{_n()}",
        password="testpass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=60,
        goods_wage_percent=10,
        travel_wage_percent=100,
        shaba_verified=verified,
        sub_merchant_id=sub_merchant if verified else "",
    )


def _policy(company, strategy=CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN):
    policy, _ = CompanyFinancialPolicy.objects.get_or_create(
        company=company,
        defaults={
            "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
            "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
            "payout_strategy": strategy,
            "platform_fee_percent": Decimal("0"),
        },
    )
    policy.payout_strategy = strategy
    policy.platform_fee_percent = Decimal("0")
    policy.save(update_fields=["payout_strategy", "platform_fee_percent"])
    return policy


def _platform_gateway(company):
    return PaymentGateway.objects.create(
        company=company,
        name=f"Platform FAKE GW {_n()}",
        gateway_type=PaymentGateway.GatewayType.FAKE,
        owner_type=PaymentGateway.OwnerType.PLATFORM,
        is_active=True,
        is_default=True,
    )


def _company_gateway(company):
    return PaymentGateway.objects.create(
        company=company,
        name=f"Company Manual GW {_n()}",
        gateway_type=PaymentGateway.GatewayType.MANUAL,
        owner_type=PaymentGateway.OwnerType.COMPANY,
        is_active=True,
        is_default=False,
    )


def _order(company, technician=None):
    return Order.objects.create(
        company=company,
        title=f"Order {_n()}",
        technician=technician,
        status=Order.Status.DONE,
    )


def _invoice(company, order, total=10_000_000):
    tech = getattr(order, "technician", None) if order else None
    return Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-{company.code.upper()}-{Invoice.objects.count() + 1:05d}",
        status=Invoice.Status.ISSUED,
        issued_at=timezone.now(),
        subtotal=total,
        total_amount=total,
        net_amount_before_invoice_discounts=total,
        gross_amount=total,
        technician_service_wage_percent_snapshot=Decimal("60") if tech else Decimal("0"),
        technician_goods_wage_percent_snapshot=Decimal("10") if tech else Decimal("0"),
        technician_travel_wage_percent_snapshot=Decimal("100") if tech else Decimal("0"),
    )


def _invoice_with_item(company, order, total=10_000_000):
    inv = _invoice(company, order, total)
    InvoiceItem.objects.create(
        company=company,
        invoice=inv,
        description="خدمات تست",
        row_type=InvoiceItem.RowType.SERVICE,
        quantity=1,
        unit_price=total,
        total_price=total,
    )
    return inv


def _payment(company, invoice, gateway, status=Payment.Status.PAID, reference_id=None):
    ref = reference_id or f"SUCCESS-{_n():012d}"
    amount = invoice.total_amount if invoice else Decimal("10000000")
    return Payment.objects.create(
        company=company,
        invoice=invoice,
        gateway=gateway,
        amount=amount,
        status=status,
        reference_id=ref,
    )


def _snapshot(company, payment, invoice=None, direct_amount=6_000_000, should_split=True):
    total = int(payment.amount)
    return PaymentSplitSnapshot.objects.create(
        company=company,
        payment=payment,
        invoice=invoice,
        total_amount=total,
        platform_fee_amount=0,
        company_deposit_amount=max(0, total - direct_amount),
        technician_direct_amount=direct_amount if should_split else 0,
        technician_ledger_amount=0 if should_split else direct_amount,
        payout_strategy_snapshot="split_with_technician" if should_split else "direct_to_company",
        technician_verified_snapshot=should_split,
        technician_sub_merchant_id_snapshot="SUB-TEST-001" if should_split else "",
        platform_fee_percent_snapshot=Decimal("0"),
        should_split_with_technician=should_split,
        reason="split_with_verified_technician" if should_split else "payout_strategy_is_direct_to_company",
    )


# ---------------------------------------------------------------------------
# Unit tests: TechnicianDirectSettlementService
# ---------------------------------------------------------------------------

class TechnicianDirectSettlementServiceTest(TestCase):

    DIRECT_AMOUNT = 6_000_000  # 60% of 10M invoice

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        self.gateway = _platform_gateway(self.company)
        self.order = _order(self.company, self.technician)
        self.invoice = _invoice(self.company, self.order)
        self.payment = _payment(self.company, self.invoice, self.gateway)
        self.snapshot = _snapshot(
            self.company, self.payment, self.invoice,
            direct_amount=self.DIRECT_AMOUNT,
            should_split=True,
        )

    def test_01_creates_one_debit_when_split_true_and_amount_positive(self):
        """Creates exactly one DEBIT entry when snapshot qualifies."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].entry_type, TechnicianLedgerEntry.EntryType.DEBIT)

    def test_02_debit_amount_equals_snapshot_technician_direct_amount(self):
        """DEBIT amount must equal PaymentSplitSnapshot.technician_direct_amount."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        self.assertEqual(result[0].amount_rial, self.DIRECT_AMOUNT)

    def test_03_source_is_direct_gateway_settlement(self):
        """Source must be DIRECT_GATEWAY_SETTLEMENT."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        self.assertEqual(
            result[0].source,
            TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
        )

    def test_04_order_fk_set_on_debit_entry(self):
        """DEBIT entry must carry the order FK."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        self.assertEqual(result[0].order_id, self.order.id)

    def test_05_invoice_fk_set_on_debit_entry(self):
        """DEBIT entry must carry the invoice FK."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        self.assertEqual(result[0].invoice_id, self.invoice.id)

    def test_06_payment_fk_set_on_debit_entry(self):
        """DEBIT entry must carry the payment FK."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        self.assertEqual(result[0].payment_id, self.payment.id)

    def test_07_metadata_contains_metadata_version_1(self):
        """Metadata must include metadata_version=1."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        self.assertEqual(result[0].metadata["metadata_version"], 1)

    def test_08_metadata_contains_required_ids(self):
        """Metadata must include payment_id, invoice_id, order_id, technician_id."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        meta = result[0].metadata
        self.assertEqual(meta["payment_id"], self.payment.id)
        self.assertEqual(meta["invoice_id"], self.invoice.id)
        self.assertEqual(meta["order_id"], self.order.id)
        self.assertEqual(meta["technician_id"], self.technician.id)

    def test_09_idempotency_second_call_returns_empty(self):
        """Calling the service twice for the same payment creates only one DEBIT."""
        TechnicianDirectSettlementService.post_for_payment(self.payment)
        result2 = TechnicianDirectSettlementService.post_for_payment(self.payment)
        self.assertEqual(result2, [])
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                idempotency_key=f"direct_gateway_settlement:payment:{self.payment.id}"
            ).count(),
            1,
        )

    def test_10_no_debit_when_no_snapshot_exists(self):
        """No DEBIT when payment has no PaymentSplitSnapshot."""
        payment2 = _payment(
            self.company, self.invoice, self.gateway,
            reference_id=f"SUCCESS-NOSNAPSHOT-{_n()}",
        )
        result = TechnicianDirectSettlementService.post_for_payment(payment2)
        self.assertEqual(result, [])
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(payment=payment2).count(), 0
        )

    def test_11_no_debit_when_should_split_false(self):
        """No DEBIT when snapshot.should_split_with_technician is False."""
        payment2 = _payment(self.company, self.invoice, self.gateway)
        _snapshot(
            self.company, payment2, self.invoice,
            direct_amount=self.DIRECT_AMOUNT,
            should_split=False,
        )
        result = TechnicianDirectSettlementService.post_for_payment(payment2)
        self.assertEqual(result, [])

    def test_12_no_debit_when_technician_direct_amount_is_zero(self):
        """No DEBIT when snapshot.technician_direct_amount == 0."""
        payment2 = _payment(self.company, self.invoice, self.gateway)
        PaymentSplitSnapshot.objects.create(
            company=self.company,
            payment=payment2,
            invoice=self.invoice,
            total_amount=int(self.invoice.total_amount),
            platform_fee_amount=0,
            company_deposit_amount=int(self.invoice.total_amount),
            technician_direct_amount=0,
            technician_ledger_amount=self.DIRECT_AMOUNT,
            payout_strategy_snapshot="split_with_technician",
            technician_verified_snapshot=True,
            technician_sub_merchant_id_snapshot="SUB-TEST-001",
            platform_fee_percent_snapshot=Decimal("0"),
            should_split_with_technician=True,
            reason="technician_wage_is_zero",
        )
        result = TechnicianDirectSettlementService.post_for_payment(payment2)
        self.assertEqual(result, [])

    def test_13_no_debit_when_gateway_owner_type_is_company(self):
        """No DEBIT when payment.gateway.owner_type == COMPANY."""
        co_gateway = _company_gateway(self.company)
        payment_co = _payment(self.company, self.invoice, co_gateway)
        _snapshot(self.company, payment_co, self.invoice, direct_amount=self.DIRECT_AMOUNT)
        result = TechnicianDirectSettlementService.post_for_payment(payment_co)
        self.assertEqual(result, [])

    def test_14_no_debit_when_payment_has_no_invoice(self):
        """No DEBIT when payment.invoice is None."""
        payment_no_inv = Payment.objects.create(
            company=self.company,
            invoice=None,
            gateway=self.gateway,
            amount=Decimal("10000000"),
            status=Payment.Status.PAID,
            reference_id=f"SUCCESS-NOINV-{_n()}",
        )
        PaymentSplitSnapshot.objects.create(
            company=self.company,
            payment=payment_no_inv,
            invoice=None,
            total_amount=10_000_000,
            platform_fee_amount=0,
            company_deposit_amount=4_000_000,
            technician_direct_amount=self.DIRECT_AMOUNT,
            technician_ledger_amount=0,
            payout_strategy_snapshot="split_with_technician",
            technician_verified_snapshot=True,
            technician_sub_merchant_id_snapshot="SUB-TEST-001",
            platform_fee_percent_snapshot=Decimal("0"),
            should_split_with_technician=True,
            reason="split_with_verified_technician",
        )
        result = TechnicianDirectSettlementService.post_for_payment(payment_no_inv)
        self.assertEqual(result, [])

    def test_15_no_debit_when_invoice_has_no_order(self):
        """No DEBIT when invoice.order is None."""
        invoice_no_order = _invoice(self.company, order=None)
        payment_no_order = _payment(self.company, invoice_no_order, self.gateway)
        _snapshot(
            self.company, payment_no_order, invoice_no_order,
            direct_amount=self.DIRECT_AMOUNT,
        )
        result = TechnicianDirectSettlementService.post_for_payment(payment_no_order)
        self.assertEqual(result, [])

    def test_16_no_debit_when_order_has_no_technician(self):
        """No DEBIT when order.technician is None."""
        order_no_tech = _order(self.company, technician=None)
        invoice_no_tech = _invoice(self.company, order_no_tech)
        payment_no_tech = _payment(self.company, invoice_no_tech, self.gateway)
        _snapshot(
            self.company, payment_no_tech, invoice_no_tech,
            direct_amount=self.DIRECT_AMOUNT,
        )
        result = TechnicianDirectSettlementService.post_for_payment(payment_no_tech)
        self.assertEqual(result, [])

    def test_17_no_debit_on_cross_company_technician_mismatch(self):
        """No DEBIT when technician.company != payment.company."""
        company_b = _company()
        technician_b = _technician(company_b)
        # Order assigned to technician_b but belonging to company_a
        cross_order = Order.objects.create(
            company=self.company,
            title="Cross-Company Order",
            technician=technician_b,
            status=Order.Status.DONE,
        )
        cross_invoice = _invoice(self.company, cross_order)
        cross_payment = _payment(self.company, cross_invoice, self.gateway)
        _snapshot(
            self.company, cross_payment, cross_invoice,
            direct_amount=self.DIRECT_AMOUNT,
        )
        result = TechnicianDirectSettlementService.post_for_payment(cross_payment)
        self.assertEqual(result, [])

    def test_18_balance_after_decreases_by_direct_settlement_amount(self):
        """After DEBIT, balance_after reflects the reduction."""
        # First create a CREDIT to give the technician a positive balance
        prior_credit_key = f"prior_credit_test18:{self.payment.id}"
        TechnicianLedgerService.create_credit(
            company=self.company,
            technician=self.technician,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            amount_rial=self.DIRECT_AMOUNT,
            idempotency_key=prior_credit_key,
            description="test prior credit",
        )
        balance_before = TechnicianLedgerService.get_balance(self.company, self.technician)
        self.assertEqual(balance_before, self.DIRECT_AMOUNT)

        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        debit_entry = result[0]

        expected_balance_after = self.DIRECT_AMOUNT - self.DIRECT_AMOUNT  # = 0
        self.assertEqual(debit_entry.balance_after, expected_balance_after)
        self.assertEqual(
            TechnicianLedgerService.get_balance(self.company, self.technician),
            expected_balance_after,
        )

    def test_19_description_is_canonical_persian_string(self):
        """DEBIT description must be the canonical Persian format."""
        result = TechnicianDirectSettlementService.post_for_payment(self.payment)
        expected = f"تسویه مستقیم شاپرک سفارش #{self.order.id}"
        self.assertEqual(result[0].description, expected)


# ---------------------------------------------------------------------------
# Integration tests: through PaymentVerifyService.verify()
# ---------------------------------------------------------------------------

class DirectSettlementIntegrationTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        self.policy = _policy(
            self.company,
            strategy=CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN,
        )
        self.gateway = _platform_gateway(self.company)

    def _make_pending_payment(self, total=10_000_000):
        """Create an order → ISSUED invoice → PENDING payment ready for verify()."""
        order = _order(self.company, self.technician)
        invoice = _invoice_with_item(self.company, order, total=total)
        payment = Payment.objects.create(
            company=self.company,
            invoice=invoice,
            gateway=self.gateway,
            amount=invoice.total_amount,
            status=Payment.Status.PENDING,
            reference_id=f"SUCCESS-INTEG-{_n()}",
        )
        return payment, invoice, order

    def test_20_verify_creates_debit_for_platform_split_payment(self):
        """PaymentVerifyService.verify() posts DIRECT_GATEWAY_SETTLEMENT DEBIT for a qualifying split."""
        from apps.payments.services import PaymentVerifyService

        payment, invoice, order = self._make_pending_payment()
        success, msg = PaymentVerifyService.verify(payment=payment)

        self.assertTrue(success, msg)

        debits = TechnicianLedgerEntry.objects.filter(
            company=self.company,
            source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
        )
        self.assertEqual(debits.count(), 1)

        debit = debits.first()
        self.assertEqual(debit.payment_id, payment.id)
        self.assertEqual(debit.order_id, order.id)
        self.assertEqual(debit.invoice_id, invoice.id)
        self.assertEqual(debit.entry_type, TechnicianLedgerEntry.EntryType.DEBIT)

    def test_21_verify_does_not_create_debit_for_non_split_payment(self):
        """No DEBIT when payout_strategy=DIRECT_TO_COMPANY."""
        from apps.payments.services import PaymentVerifyService

        self.policy.payout_strategy = CompanyFinancialPolicy.PayoutStrategy.DIRECT_TO_COMPANY
        self.policy.save(update_fields=["payout_strategy"])

        payment, _invoice, _order = self._make_pending_payment()
        success, msg = PaymentVerifyService.verify(payment=payment)

        self.assertTrue(success, msg)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=self.company,
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
            ).count(),
            0,
        )

    def test_22_verify_succeeds_even_if_direct_settlement_hook_raises(self):
        """Payment verification must succeed even if TechnicianDirectSettlementService raises."""
        from apps.payments.services import PaymentVerifyService

        payment, _, _ = self._make_pending_payment()

        with patch.object(
            TechnicianDirectSettlementService,
            "post_for_payment",
            side_effect=RuntimeError("simulated settlement failure"),
        ):
            success, msg = PaymentVerifyService.verify(payment=payment)

        self.assertTrue(success, msg)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
