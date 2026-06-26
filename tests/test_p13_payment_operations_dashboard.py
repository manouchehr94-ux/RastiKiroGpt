"""
P13-PAYMENT-OPERATIONS-DASHBOARD: Tests for payment operations views.

Covers:
1. Company admin can access own payment operations page
2. Company admin cannot access another company's operations page
3. Platform owner can access platform operations page
4. Non-platform owner cannot access platform operations page
5. Company staff behavior (OperatorPermissionMiddleware may block)
6. Technician/customer cannot access
7. Dashboard shows only own company payments
8. Pending/failed counts are correct
9. Old pending count respects PAYMENT_EXPIRATION_MINUTES
10. Cash/manual payments do not pollute gateway-problem counts
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.tenants.models import Company
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway


class OperationsTestMixin:
    """Shared helpers."""

    def create_company(self, code="ops_co", name="Ops Test Co"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_user(self, company, role, username=None):
        username = username or f"{role.lower()}_{company.code}_{CompanyUser.objects.count()}"
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=role,
        )

    def create_platform_owner(self, username="ops_platform_owner"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )

    def create_gateway(self, company):
        gw, _ = PaymentGateway.objects.get_or_create(
            company=company, gateway_type=PaymentGateway.GatewayType.FAKE,
            defaults={"name": "Fake", "is_active": True, "is_default": True},
        )
        return gw

    def create_invoice(self, company, total=5000000):
        order = Order.objects.create(company=company, title="T", status=Order.Status.DONE)
        inv = Invoice.objects.create(
            company=company, order=order, status=Invoice.Status.ISSUED,
            invoice_number=f"INV-{Invoice.objects.count()+1:05d}",
            issued_at=timezone.now(), subtotal=total, total_amount=total,
            gross_amount=total, net_amount_before_invoice_discounts=total,
        )
        InvoiceItem.objects.create(
            company=company, invoice=inv, description="svc",
            row_type=InvoiceItem.RowType.SERVICE, quantity=1, unit_price=total, total_price=total,
        )
        return inv

    def create_gateway_payment(self, company, invoice, gateway, status="pending", age_minutes=0):
        p = Payment.objects.create(
            company=company, invoice=invoice, gateway=gateway,
            amount=invoice.total_amount, status=status,
            reference_id=f"REF-{Payment.objects.count()+1}",
        )
        if age_minutes:
            Payment.objects.filter(pk=p.pk).update(
                created_at=timezone.now() - timedelta(minutes=age_minutes)
            )
            p.refresh_from_db()
        return p


# =============================================================================
# PERMISSION TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class CompanyOperationsPermissionTest(TestCase, OperationsTestMixin):
    """Test access control for company payment operations page."""

    def setUp(self):
        self.company_a = self.create_company("ops_a", "Ops A")
        self.company_b = self.create_company("ops_b", "Ops B")
        self.admin_a = self.create_user(self.company_a, UserRole.COMPANY_ADMIN, "ops_admin_a")
        self.admin_b = self.create_user(self.company_b, UserRole.COMPANY_ADMIN, "ops_admin_b")

    def test_admin_can_access_own_operations(self):
        """Company admin can access own payment operations page."""
        self.client.login(username="ops_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company_a.code}/admin/payments/operations/")
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_access_other_company_operations(self):
        """Company A admin cannot access Company B's operations."""
        self.client.login(username="ops_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company_b.code}/admin/payments/operations/")
        self.assertIn(response.status_code, [403, 302])

    def test_technician_cannot_access(self):
        """Technician cannot access payment operations."""
        tech = self.create_user(self.company_a, UserRole.TECHNICIAN, "ops_tech")
        self.client.login(username="ops_tech", password="testpass123")
        response = self.client.get(f"/{self.company_a.code}/admin/payments/operations/")
        self.assertIn(response.status_code, [403, 302])

    def test_anonymous_cannot_access(self):
        """Anonymous user cannot access."""
        response = self.client.get(f"/{self.company_a.code}/admin/payments/operations/")
        self.assertIn(response.status_code, [302, 403])


@override_settings(ROOT_URLCONF="config.urls")
class PlatformOperationsPermissionTest(TestCase, OperationsTestMixin):
    """Test access control for platform payment operations page."""

    def setUp(self):
        self.company = self.create_company("ops_plat", "Ops Platform")
        self.platform_owner = self.create_platform_owner()

    def test_platform_owner_can_access(self):
        """Platform owner can access platform operations page."""
        self.client.login(username="ops_platform_owner", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertEqual(response.status_code, 200)

    def test_company_admin_cannot_access_platform_operations(self):
        """Company admin cannot access platform-level operations."""
        admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "ops_noplat")
        self.client.login(username="ops_noplat", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertIn(response.status_code, [403, 302])


# =============================================================================
# DATA CORRECTNESS TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls", PAYMENT_EXPIRATION_MINUTES=30)
class CompanyOperationsDataTest(TestCase, OperationsTestMixin):
    """Test that operations dashboard shows correct data for the company."""

    def setUp(self):
        self.company = self.create_company("data_co", "Data Co")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "data_admin")
        self.gw = self.create_gateway(self.company)

    def test_shows_only_own_company_payments(self):
        """Dashboard shows only own company's gateway payments."""
        other = self.create_company("other_co", "Other")
        other_gw = self.create_gateway(other)
        inv_own = self.create_invoice(self.company)
        inv_other = self.create_invoice(other)
        self.create_gateway_payment(self.company, inv_own, self.gw, "pending", age_minutes=60)
        self.create_gateway_payment(other, inv_other, other_gw, "pending", age_minutes=60)

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["old_pending_count"], 1)  # Only own

    def test_old_pending_count_respects_threshold(self):
        """Only payments older than PAYMENT_EXPIRATION_MINUTES are counted."""
        inv = self.create_invoice(self.company)
        # Old (60 min) → counted
        self.create_gateway_payment(self.company, inv, self.gw, "pending", age_minutes=60)
        # Fresh (5 min) → not counted
        inv2 = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv2, self.gw, "pending", age_minutes=5)

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["old_pending_count"], 1)

    def test_cash_payments_not_in_gateway_counts(self):
        """Cash/manual payments (no gateway) do not appear in gateway problem counts."""
        inv = self.create_invoice(self.company)
        Payment.objects.create(
            company=self.company, invoice=inv, gateway=None,
            amount=inv.total_amount, status=Payment.Status.PENDING,
            metadata={"method": "cash"},
        )
        # Backdate
        Payment.objects.filter(company=self.company).update(
            created_at=timezone.now() - timedelta(minutes=60)
        )

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["old_pending_count"], 0)

    def test_paid_payment_not_problematic(self):
        """PAID payments should not appear as problematic."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "paid", age_minutes=60)

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["old_pending_count"], 0)
        self.assertEqual(len(health["problematic_payments"]), 0)

    def test_failed_recent_count(self):
        """Failed gateway payments within 7 days are counted."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "failed", age_minutes=60)

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["failed_recent_count"], 1)


# =============================================================================
# TASK-002B: NEEDS_RECONCILIATION VISIBILITY TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls", PAYMENT_EXPIRATION_MINUTES=30)
class NeedsReconciliationDashboardTest(TestCase, OperationsTestMixin):
    """
    TASK-002B: NEEDS_RECONCILIATION payments must be visible in operations dashboards.

    After TASK-002, expired/ambiguous payments land in NEEDS_RECONCILIATION, not FAILED.
    Selectors must surface them so operators are not blind to unresolved payments.
    """

    def setUp(self):
        self.company = self.create_company("nr_dash_co", "NR Dash Co")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "nr_dash_admin")
        self.gw = self.create_gateway(self.company)

    def _make_nr_payment(self, expired_by_cleanup=False):
        inv = self.create_invoice(self.company)
        p = Payment.objects.create(
            company=self.company, invoice=inv, gateway=self.gw,
            amount=inv.total_amount,
            status=Payment.Status.NEEDS_RECONCILIATION,
            reference_id=f"NR-REF-{Payment.objects.count()}",
            metadata={"expired_by_cleanup": True} if expired_by_cleanup else {},
        )
        return p

    def test_nr_payment_appears_in_problematic_payments(self):
        """NEEDS_RECONCILIATION payment must appear in the problematic_payments list."""
        self._make_nr_payment()

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        statuses = [p.status for p in health["problematic_payments"]]
        self.assertIn(Payment.Status.NEEDS_RECONCILIATION, statuses)

    def test_nr_payment_counted_in_status_counts(self):
        """status_counts must include a needs_reconciliation key with correct count."""
        self._make_nr_payment()
        self._make_nr_payment()

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertIn("needs_reconciliation", health["status_counts"])
        self.assertEqual(health["status_counts"]["needs_reconciliation"], 2)

    def test_status_counts_zero_when_no_nr_payments(self):
        """status_counts[needs_reconciliation] is 0 when no NR payments exist."""
        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["status_counts"].get("needs_reconciliation", 0), 0)

    def test_expired_by_cleanup_count_uses_nr_status(self):
        """expired_by_cleanup_count must count NR payments with expired_by_cleanup=True."""
        self._make_nr_payment(expired_by_cleanup=True)
        self._make_nr_payment(expired_by_cleanup=True)
        self._make_nr_payment(expired_by_cleanup=False)  # NR but not from cleanup

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["expired_by_cleanup_count"], 2)

    def test_expired_by_cleanup_count_ignores_failed_with_flag(self):
        """A FAILED payment with expired_by_cleanup=True must NOT count (pre-TASK-002 data)."""
        inv = self.create_invoice(self.company)
        Payment.objects.create(
            company=self.company, invoice=inv, gateway=self.gw,
            amount=inv.total_amount,
            status=Payment.Status.FAILED,
            reference_id="OLD-FAILED-REF",
            metadata={"expired_by_cleanup": True},
        )

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["expired_by_cleanup_count"], 0)

    def test_paid_nr_isolation(self):
        """PAID payments must not appear in problematic list even when NR exists."""
        inv_paid = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv_paid, self.gw, "paid")
        self._make_nr_payment()

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        statuses = [p.status for p in health["problematic_payments"]]
        self.assertNotIn(Payment.Status.PAID, statuses)
        self.assertIn(Payment.Status.NEEDS_RECONCILIATION, statuses)

    def test_cross_tenant_nr_not_visible(self):
        """NR payments from another company must not appear in own company's health."""
        other = self.create_company("other_nr_co", "Other NR")
        other_gw = self.create_gateway(other)
        inv_other = self.create_invoice(other)
        Payment.objects.create(
            company=other, invoice=inv_other, gateway=other_gw,
            amount=inv_other.total_amount,
            status=Payment.Status.NEEDS_RECONCILIATION,
            reference_id="OTHER-NR-REF",
        )

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["status_counts"]["needs_reconciliation"], 0)
        self.assertEqual(len(list(health["problematic_payments"])), 0)
