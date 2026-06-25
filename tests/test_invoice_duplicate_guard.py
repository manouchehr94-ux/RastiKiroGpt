"""
Invoice Duplicate Guard Tests.

Verifies that InvoiceDuplicateGuard correctly treats DRAFT and ISSUED invoices
as "active" (blocking new invoice creation) while PAID and CANCELLED invoices
are treated as "closed" (allowing new invoice creation).

Covers:
1. Unit tests for InvoiceDuplicateGuard.has_active_for_order
2. Unit tests for InvoiceDuplicateGuard.get_active_for_order
3. Admin path integration tests (same guard used in views_admin.py)
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.invoices.models import Invoice
from apps.invoices.services import InvoiceDuplicateGuard
from apps.orders.models import Order
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

def _make_company(code):
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _make_order(company):
    return Order.objects.create(company=company, title="Test Order", status=Order.Status.IN_PROGRESS)


_inv_seq = 0


def _make_invoice(company, order, status):
    global _inv_seq
    _inv_seq += 1
    return Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-{company.code.upper()}-{_inv_seq:05d}",
        status=status,
    )


# =============================================================================
# 1. UNIT TESTS — has_active_for_order
# =============================================================================

class HasActiveForOrderTest(TestCase):
    """InvoiceDuplicateGuard.has_active_for_order returns True only for DRAFT/ISSUED."""

    def setUp(self):
        self.company = _make_company("hag1")
        self.order = _make_order(self.company)

    def test_no_invoice_returns_false(self):
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=self.order
        )
        self.assertFalse(result)

    def test_draft_invoice_returns_true(self):
        _make_invoice(self.company, self.order, Invoice.Status.DRAFT)
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=self.order
        )
        self.assertTrue(result, "DRAFT invoice must block new invoice creation.")

    def test_issued_invoice_returns_true(self):
        _make_invoice(self.company, self.order, Invoice.Status.ISSUED)
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=self.order
        )
        self.assertTrue(result, "ISSUED invoice must block new invoice creation.")

    def test_paid_invoice_returns_false(self):
        _make_invoice(self.company, self.order, Invoice.Status.PAID)
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=self.order
        )
        self.assertFalse(result, "PAID invoice must NOT block new invoice creation.")

    def test_cancelled_invoice_returns_false(self):
        _make_invoice(self.company, self.order, Invoice.Status.CANCELLED)
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=self.order
        )
        self.assertFalse(result, "CANCELLED invoice must NOT block new invoice creation.")

    def test_paid_plus_cancelled_still_returns_false(self):
        """Multiple closed invoices still allow a new one."""
        _make_invoice(self.company, self.order, Invoice.Status.PAID)
        _make_invoice(self.company, self.order, Invoice.Status.CANCELLED)
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=self.order
        )
        self.assertFalse(result)

    def test_paid_plus_draft_returns_true(self):
        """A DRAFT invoice alongside a PAID one still blocks — the DRAFT is the active one."""
        _make_invoice(self.company, self.order, Invoice.Status.PAID)
        _make_invoice(self.company, self.order, Invoice.Status.DRAFT)
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=self.order
        )
        self.assertTrue(result)

    def test_none_order_returns_false(self):
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=None
        )
        self.assertFalse(result)

    def test_different_company_not_counted(self):
        """Invoice from another company does not block creation for this company."""
        other = _make_company("hag2")
        _make_invoice(other, self.order, Invoice.Status.ISSUED)
        result = InvoiceDuplicateGuard.has_active_for_order(
            company=self.company, order=self.order
        )
        self.assertFalse(result)


# =============================================================================
# 2. UNIT TESTS — get_active_for_order
# =============================================================================

class GetActiveForOrderTest(TestCase):
    """InvoiceDuplicateGuard.get_active_for_order returns the open invoice or None."""

    def setUp(self):
        self.company = _make_company("gag1")
        self.order = _make_order(self.company)

    def test_returns_none_when_no_invoice(self):
        result = InvoiceDuplicateGuard.get_active_for_order(
            company=self.company, order=self.order
        )
        self.assertIsNone(result)

    def test_returns_draft_invoice(self):
        inv = _make_invoice(self.company, self.order, Invoice.Status.DRAFT)
        result = InvoiceDuplicateGuard.get_active_for_order(
            company=self.company, order=self.order
        )
        self.assertEqual(result, inv)

    def test_returns_issued_invoice(self):
        inv = _make_invoice(self.company, self.order, Invoice.Status.ISSUED)
        result = InvoiceDuplicateGuard.get_active_for_order(
            company=self.company, order=self.order
        )
        self.assertEqual(result, inv)

    def test_returns_none_for_paid_invoice(self):
        _make_invoice(self.company, self.order, Invoice.Status.PAID)
        result = InvoiceDuplicateGuard.get_active_for_order(
            company=self.company, order=self.order
        )
        self.assertIsNone(result)

    def test_returns_none_for_cancelled_invoice(self):
        _make_invoice(self.company, self.order, Invoice.Status.CANCELLED)
        result = InvoiceDuplicateGuard.get_active_for_order(
            company=self.company, order=self.order
        )
        self.assertIsNone(result)

    def test_returns_draft_when_paid_also_exists(self):
        """When order has a PAID invoice and a DRAFT invoice, returns the DRAFT."""
        _make_invoice(self.company, self.order, Invoice.Status.PAID)
        draft = _make_invoice(self.company, self.order, Invoice.Status.DRAFT)
        result = InvoiceDuplicateGuard.get_active_for_order(
            company=self.company, order=self.order
        )
        self.assertEqual(result, draft)

    def test_returns_none_for_order_none(self):
        result = InvoiceDuplicateGuard.get_active_for_order(
            company=self.company, order=None
        )
        self.assertIsNone(result)


# =============================================================================
# 3. ADMIN PATH INTEGRATION TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class AdminInvoiceCreateGuardTest(TestCase):
    """
    Admin invoice create path enforces the same duplicate guard as technician path.

    URL: POST /{company_code}/admin/orders/{order_id}/invoice/create/
    """

    def setUp(self):
        self.company = _make_company("adm1")
        self.order = _make_order(self.company)
        self.admin = CompanyUser.objects.create_user(
            username="admin_adm1",
            password="testpass123",
            company=self.company,
            role=UserRole.COMPANY_ADMIN,
        )
        self.client.login(username="admin_adm1", password="testpass123")

    def _url(self):
        return f"/{self.company.code}/admin/orders/{self.order.id}/invoice/create/"

    def test_creates_invoice_when_no_existing(self):
        """No existing invoice → creates a new DRAFT and redirects to its edit page."""
        before = Invoice.objects.filter(company=self.company, order=self.order).count()
        response = self.client.get(self._url())
        after = Invoice.objects.filter(company=self.company, order=self.order).count()

        self.assertEqual(after, before + 1, "Should have created exactly one new invoice.")
        self.assertEqual(response.status_code, 302)

    def test_blocked_by_draft_invoice(self):
        """Existing DRAFT invoice → admin is redirected to it, no new invoice created."""
        draft = _make_invoice(self.company, self.order, Invoice.Status.DRAFT)
        response = self.client.get(self._url())

        count = Invoice.objects.filter(company=self.company, order=self.order).count()
        self.assertEqual(count, 1, "No new invoice should be created.")
        self.assertRedirects(
            response,
            f"/{self.company.code}/admin/invoices/{draft.id}/edit/",
            fetch_redirect_response=False,
        )

    def test_blocked_by_issued_invoice(self):
        """Existing ISSUED invoice → admin is redirected to it, no new invoice created."""
        issued = _make_invoice(self.company, self.order, Invoice.Status.ISSUED)
        response = self.client.get(self._url())

        count = Invoice.objects.filter(company=self.company, order=self.order).count()
        self.assertEqual(count, 1, "No new invoice should be created.")
        self.assertRedirects(
            response,
            f"/{self.company.code}/admin/invoices/{issued.id}/edit/",
            fetch_redirect_response=False,
        )

    def test_allowed_after_paid_invoice(self):
        """Existing PAID invoice → admin can create a new invoice (second lifecycle)."""
        _make_invoice(self.company, self.order, Invoice.Status.PAID)
        response = self.client.get(self._url())

        count = Invoice.objects.filter(company=self.company, order=self.order).count()
        self.assertEqual(count, 2, "Should have created a second invoice after PAID.")
        self.assertEqual(response.status_code, 302)

    def test_allowed_after_cancelled_invoice(self):
        """Existing CANCELLED invoice → admin can create a new invoice."""
        _make_invoice(self.company, self.order, Invoice.Status.CANCELLED)
        response = self.client.get(self._url())

        count = Invoice.objects.filter(company=self.company, order=self.order).count()
        self.assertEqual(count, 2, "Should have created a second invoice after CANCELLED.")
        self.assertEqual(response.status_code, 302)

    def test_allowed_after_paid_and_cancelled(self):
        """Multiple closed invoices (PAID + CANCELLED) → still allows new invoice."""
        _make_invoice(self.company, self.order, Invoice.Status.PAID)
        _make_invoice(self.company, self.order, Invoice.Status.CANCELLED)
        response = self.client.get(self._url())

        count = Invoice.objects.filter(company=self.company, order=self.order).count()
        self.assertEqual(count, 3)
        self.assertEqual(response.status_code, 302)
