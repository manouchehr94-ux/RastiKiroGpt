"""
TASK-010C-FIX-1 — Gate direct split snapshot by platform gateway ownership.

Company-owned gateways cannot instruct Shaparak to split a payment; the platform
has no authority over their merchant account.  After this fix, PaymentSplitSnapshot
must record technician_direct_amount=0 / should_split_with_technician=False whenever
the payment gateway is company-owned, even if every other split condition is met.

Tests:
 1. compute() PLATFORM gateway + split policy + verified tech → should_split=True, direct_amount > 0
 2. compute() COMPANY gateway + split policy + verified tech → should_split=False, direct_amount = 0
 3. compute() COMPANY gateway → technician_ledger_amount equals the tech wage
 4. compute() COMPANY gateway → reason contains 'company_owned'
 5. create_snapshot() COMPANY gateway → snapshot.technician_direct_amount == 0
 6. create_snapshot() COMPANY gateway → snapshot.should_split_with_technician == False
 7. verify() full integration: FAKE COMPANY gateway + split policy → no DIRECT_GATEWAY_SETTLEMENT DEBIT
 8. compute() without payment arg → still uses policy/KYC gates only (backward compat)
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payouts.models import PaymentSplitSnapshot, TechnicianLedgerEntry
from apps.payouts.services_split import PaymentSplitDecisionService
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# Shared helpers (mirror pattern from test_task010c_direct_settlement)
# ---------------------------------------------------------------------------

def _company():
    tag = _n()
    return Company.objects.create(
        name=f"GWSplitCo {tag}",
        code=f"gwsp{tag}",
        slug=f"gwsp-{tag}",
        is_active=True,
    )


def _technician(company, verified=True, sub_merchant="SUB-FIX1-001"):
    user = CompanyUser.objects.create_user(
        username=f"techfix{_n()}",
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


def _company_gateway(company, gateway_type=PaymentGateway.GatewayType.MANUAL):
    return PaymentGateway.objects.create(
        company=company,
        name=f"Company GW {_n()}",
        gateway_type=gateway_type,
        owner_type=PaymentGateway.OwnerType.COMPANY,
        is_active=True,
        is_default=False,
    )


def _fake_company_gateway(company):
    """FAKE provider + COMPANY ownership — allows going through PaymentVerifyService."""
    return PaymentGateway.objects.create(
        company=company,
        name=f"Company FAKE GW {_n()}",
        gateway_type=PaymentGateway.GatewayType.FAKE,
        owner_type=PaymentGateway.OwnerType.COMPANY,
        is_active=True,
        is_default=False,
    )


def _order(company, technician):
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


def _payment(company, invoice, gateway, status=Payment.Status.PENDING):
    ref = f"SUCCESS-FIX1-{_n():012d}"
    return Payment.objects.create(
        company=company,
        invoice=invoice,
        gateway=gateway,
        amount=invoice.total_amount,
        status=status,
        reference_id=ref,
    )


# ---------------------------------------------------------------------------
# Tests: PaymentSplitDecisionService.compute() gateway gate
# ---------------------------------------------------------------------------

class ComputeGatewayGateTest(TestCase):
    """Unit tests for compute() with gateway ownership gate."""

    TOTAL = 10_000_000
    TECH_WAGE = 6_000_000  # 60 % of TOTAL

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        _policy(self.company, strategy=CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN)
        self.order = _order(self.company, self.technician)
        # Build invoice with settled_technician_wage set in memory
        self.invoice = _invoice(self.company, self.order, total=self.TOTAL)
        self.invoice.settled_technician_wage = Decimal(str(self.TECH_WAGE))

    def _payment_with(self, gateway):
        return _payment(self.company, self.invoice, gateway)

    def test_01_platform_gateway_produces_split(self):
        """Platform gateway + split policy → should_split=True, direct_amount > 0."""
        gw = _platform_gateway(self.company)
        pmt = self._payment_with(gw)
        decision = PaymentSplitDecisionService.compute(self.invoice, pmt)
        self.assertTrue(decision["should_split_with_technician"])
        self.assertEqual(decision["technician_direct_amount"], self.TECH_WAGE)
        self.assertEqual(decision["technician_ledger_amount"], 0)

    def test_02_company_gateway_blocks_direct_split(self):
        """Company gateway + split policy → should_split=False, direct_amount = 0."""
        gw = _company_gateway(self.company)
        pmt = self._payment_with(gw)
        decision = PaymentSplitDecisionService.compute(self.invoice, pmt)
        self.assertFalse(decision["should_split_with_technician"])
        self.assertEqual(decision["technician_direct_amount"], 0)

    def test_03_company_gateway_routes_wage_to_ledger_amount(self):
        """Company gateway → technician_ledger_amount equals the tech wage."""
        gw = _company_gateway(self.company)
        pmt = self._payment_with(gw)
        decision = PaymentSplitDecisionService.compute(self.invoice, pmt)
        self.assertEqual(decision["technician_ledger_amount"], self.TECH_WAGE)

    def test_04_company_gateway_reason_names_company_owned(self):
        """Company gateway → reason string contains 'company_owned'."""
        gw = _company_gateway(self.company)
        pmt = self._payment_with(gw)
        decision = PaymentSplitDecisionService.compute(self.invoice, pmt)
        self.assertIn("company_owned", decision["reason"])

    def test_08_compute_without_payment_arg_uses_policy_gates_only(self):
        """compute(invoice) without payment arg must not raise and still apply policy gates."""
        # Without payment, the gateway gate is skipped; result depends purely on policy/KYC.
        # Policy is SPLIT_WITH_TECHNICIAN, tech is verified — expect split.
        decision = PaymentSplitDecisionService.compute(self.invoice)
        self.assertTrue(decision["should_split_with_technician"])
        self.assertEqual(decision["technician_direct_amount"], self.TECH_WAGE)


# ---------------------------------------------------------------------------
# Tests: create_snapshot() snapshot integrity
# ---------------------------------------------------------------------------

class CreateSnapshotGatewayGateTest(TestCase):
    """Tests that create_snapshot() persists the gateway-gated decision correctly."""

    TOTAL = 10_000_000
    TECH_WAGE = 6_000_000

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        _policy(self.company, strategy=CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN)
        self.order = _order(self.company, self.technician)
        self.invoice = _invoice(self.company, self.order, total=self.TOTAL)
        self.invoice.settled_technician_wage = Decimal(str(self.TECH_WAGE))

    def test_05_company_gateway_snapshot_has_zero_direct_amount(self):
        """create_snapshot() company gateway → snapshot.technician_direct_amount == 0."""
        gw = _company_gateway(self.company)
        pmt = _payment(self.company, self.invoice, gw)
        snapshot = PaymentSplitDecisionService.create_snapshot(pmt, self.invoice)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.technician_direct_amount, 0)

    def test_06_company_gateway_snapshot_should_split_false(self):
        """create_snapshot() company gateway → snapshot.should_split_with_technician == False."""
        gw = _company_gateway(self.company)
        pmt = _payment(self.company, self.invoice, gw)
        snapshot = PaymentSplitDecisionService.create_snapshot(pmt, self.invoice)
        self.assertIsNotNone(snapshot)
        self.assertFalse(snapshot.should_split_with_technician)


# ---------------------------------------------------------------------------
# Integration test: full verify() path with FAKE COMPANY gateway
# ---------------------------------------------------------------------------

class CompanyGatewayVerifyIntegrationTest(TestCase):
    """Integration: PaymentVerifyService.verify() with a FAKE COMPANY gateway."""

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        _policy(self.company, strategy=CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN)
        self.gateway = _fake_company_gateway(self.company)

    def _make_pending_payment(self, total=10_000_000):
        order = _order(self.company, self.technician)
        invoice = _invoice_with_item(self.company, order, total=total)
        payment = Payment.objects.create(
            company=self.company,
            invoice=invoice,
            gateway=self.gateway,
            amount=invoice.total_amount,
            status=Payment.Status.PENDING,
            reference_id=f"SUCCESS-CGWFIX1-{_n()}",
        )
        return payment, invoice, order

    def test_07_company_gateway_verify_creates_no_direct_settlement_debit(self):
        """verify() with FAKE COMPANY gateway + SPLIT policy → no DIRECT_GATEWAY_SETTLEMENT DEBIT."""
        from apps.payments.services import PaymentVerifyService

        payment, invoice, order = self._make_pending_payment()
        success, msg = PaymentVerifyService.verify(payment=payment)

        self.assertTrue(success, msg)

        # Snapshot must exist but mark split as not happening directly
        snapshot = PaymentSplitSnapshot.objects.filter(payment=payment).first()
        self.assertIsNotNone(snapshot, "Snapshot must be created even for company gateways")
        self.assertFalse(snapshot.should_split_with_technician)
        self.assertEqual(snapshot.technician_direct_amount, 0)
        self.assertIn("company_owned", snapshot.reason)

        # No DIRECT_GATEWAY_SETTLEMENT DEBIT must be created
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=self.company,
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
            ).count(),
            0,
        )
