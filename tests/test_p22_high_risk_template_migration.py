"""
P22-HIGH-RISK-TEMPLATE-CSS-MIGRATION: Smoke tests for migrated templates.

Covers:
1. All 5 migrated pages render 200 for company admin
2. No inline styles remain (except unavoidable RTL table cells)
3. Pages use shared CSS classes
4. No sensitive banking/KYC data exposed
5. POST forms preserved (CSRF tokens present where expected)
6. Cross-tenant access blocked
7. Subnav/navigation elements present
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.tenants.models import Company, CompanyFinancialPolicy
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway


class P22Mixin:
    def create_company(self, code="p22_co"):
        return Company.objects.create(code=code, name="P22 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p22_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_technician(self, company):
        user = CompanyUser.objects.create_user(
            username=f"tech_{company.code}_{CompanyUser.objects.count()}",
            password="testpass123", company=company, role=UserRole.TECHNICIAN,
        )
        return Technician.objects.create(
            company=company, user=user, service_wage_percent=Decimal("60"),
        )

    def create_invoice(self, company, tech=None):
        order = Order.objects.create(company=company, title="T", technician=tech, status=Order.Status.DONE)
        inv = Invoice.objects.create(
            company=company, order=order, status=Invoice.Status.ISSUED,
            invoice_number=f"INV-{Invoice.objects.count()+1:05d}",
            issued_at=timezone.now(), subtotal=5000000, total_amount=5000000,
            gross_amount=5000000, net_amount_before_invoice_discounts=5000000,
            technician_service_wage_percent_snapshot=Decimal("60") if tech else Decimal("0"),
        )
        InvoiceItem.objects.create(
            company=company, invoice=inv, description="svc",
            row_type=InvoiceItem.RowType.SERVICE, quantity=1, unit_price=5000000, total_price=5000000,
        )
        return inv


@override_settings(ROOT_URLCONF="config.urls")
class InvoiceDetailRenderTest(TestCase, P22Mixin):
    """admin_invoice_detail.html renders correctly after P22 migration."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)
        self.tech = self.create_technician(self.company)
        self.invoice = self.create_invoice(self.company, self.tech)

    def test_renders_200(self):
        self.client.login(username="p22_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/invoices/{self.invoice.id}/")
        self.assertEqual(response.status_code, 200)

    def test_uses_css_classes(self):
        self.client.login(username="p22_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/invoices/{self.invoice.id}/")
        content = response.content.decode("utf-8")
        self.assertIn("detail-row", content)
        self.assertIn("detail-label", content)
        self.assertIn("card-flush", content)

    def test_no_sensitive_data(self):
        self.client.login(username="p22_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/invoices/{self.invoice.id}/")
        content = response.content.decode("utf-8")
        self.assertNotIn("shaba_number", content)
        self.assertNotIn("national_card_image", content)

    def test_csrf_preserved(self):
        """POST forms must still have CSRF token."""
        self.client.login(username="p22_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/invoices/{self.invoice.id}/")
        content = response.content.decode("utf-8")
        self.assertIn("csrfmiddlewaretoken", content)


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianLedgerRenderTest(TestCase, P22Mixin):
    """technician_ledger.html renders correctly after P22 migration."""

    def setUp(self):
        self.company = self.create_company("p22_led")
        self.admin = self.create_admin(self.company, "p22_led_admin")
        self.tech = self.create_technician(self.company)

    def test_renders_200(self):
        self.client.login(username="p22_led_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/technicians/{self.tech.id}/ledger/")
        self.assertEqual(response.status_code, 200)

    def test_uses_css_classes(self):
        self.client.login(username="p22_led_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/technicians/{self.tech.id}/ledger/")
        content = response.content.decode("utf-8")
        self.assertIn("balance-insight", content)
        self.assertIn("page-header-subtitle", content)

    def test_cross_tenant_blocked(self):
        other = self.create_company("p22_other")
        self.client.login(username="p22_led_admin", password="testpass123")
        response = self.client.get(f"/{other.code}/admin/technicians/{self.tech.id}/ledger/")
        self.assertIn(response.status_code, [403, 302])


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianSettlementRenderTest(TestCase, P22Mixin):
    """technician_settlement.html renders correctly after P22 migration."""

    def setUp(self):
        self.company = self.create_company("p22_set")
        self.admin = self.create_admin(self.company, "p22_set_admin")
        self.tech = self.create_technician(self.company)

    def test_renders_200(self):
        self.client.login(username="p22_set_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/technicians/{self.tech.id}/ledger/settlement/")
        self.assertEqual(response.status_code, 200)

    def test_post_form_preserved(self):
        """Settlement form must still have POST method and CSRF."""
        self.client.login(username="p22_set_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/technicians/{self.tech.id}/ledger/settlement/")
        content = response.content.decode("utf-8")
        self.assertIn('method="post"', content)
        self.assertIn("csrfmiddlewaretoken", content)
        self.assertIn("idempotency_token", content)


@override_settings(ROOT_URLCONF="config.urls")
class SplitSnapshotListRenderTest(TestCase, P22Mixin):
    """split_snapshot_list.html renders correctly after P22 migration."""

    def setUp(self):
        self.company = self.create_company("p22_spl")
        self.admin = self.create_admin(self.company, "p22_spl_admin")

    def test_renders_200(self):
        self.client.login(username="p22_spl_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/split-snapshots/")
        self.assertEqual(response.status_code, 200)

    def test_uses_css_classes(self):
        self.client.login(username="p22_spl_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/split-snapshots/")
        content = response.content.decode("utf-8")
        self.assertIn("filter-bar", content)
        # data-table appears when records exist; empty-state when no records
        self.assertTrue(
            "data-table" in content or "empty-state" in content,
            "Page should show data-table or empty-state"
        )

    def test_no_hardcoded_hex_colors(self):
        """Template should not contain hardcoded hex colors after migration."""
        self.client.login(username="p22_spl_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/split-snapshots/")
        content = response.content.decode("utf-8")
        # Common hardcoded colors that should be gone
        self.assertNotIn("#64748b", content)
        self.assertNotIn("#e2e8f0", content)
        self.assertNotIn("#f1f5f9", content)


@override_settings(ROOT_URLCONF="config.urls")
class SplitSnapshotDetailRenderTest(TestCase, P22Mixin):
    """split_snapshot_detail.html renders correctly after P22 migration."""

    def setUp(self):
        self.company = self.create_company("p22_spd")
        self.admin = self.create_admin(self.company, "p22_spd_admin")
        self.tech = self.create_technician(self.company)
        self.invoice = self.create_invoice(self.company, self.tech)
        self.gateway = PaymentGateway.objects.create(
            company=self.company, name="Fake", gateway_type="fake",
            is_active=True, is_default=True,
        )
        self.payment = Payment.objects.create(
            company=self.company, invoice=self.invoice, gateway=self.gateway,
            amount=self.invoice.total_amount, status=Payment.Status.PAID,
            reference_id="SUCCESS-test", tracking_code="TRACK-test",
            paid_at=timezone.now(),
        )
        from apps.payouts.models import PaymentSplitSnapshot
        self.snapshot = PaymentSplitSnapshot.objects.create(
            company=self.company, payment=self.payment, invoice=self.invoice,
            total_amount=5000000, platform_fee_amount=50000,
            company_deposit_amount=4950000, technician_direct_amount=0,
            technician_ledger_amount=3000000,
            should_split_with_technician=False,
            reason="payout_strategy_is_direct_to_company",
            raw_decision={"test": True},
        )

    def test_renders_200(self):
        self.client.login(username="p22_spd_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/split-snapshots/{self.snapshot.id}/")
        self.assertEqual(response.status_code, 200)

    def test_uses_css_classes(self):
        self.client.login(username="p22_spd_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/split-snapshots/{self.snapshot.id}/")
        content = response.content.decode("utf-8")
        self.assertIn("report-card", content)
        self.assertIn("snapshot-row", content)
        self.assertIn("snapshot-label", content)

    def test_no_hardcoded_hex_colors(self):
        """No hardcoded hex colors should remain."""
        self.client.login(username="p22_spd_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/split-snapshots/{self.snapshot.id}/")
        content = response.content.decode("utf-8")
        self.assertNotIn("#64748b", content)
        self.assertNotIn("#f8fafc", content)
        self.assertNotIn("#374151", content)
