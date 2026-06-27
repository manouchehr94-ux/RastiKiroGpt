"""
Customer Invoice Visibility — Test Suite.

MVP visibility rules enforced:
    DRAFT     → hidden from customer (404 on detail, excluded from list)
    ISSUED    → visible, payable
    PAID      → visible in history
    CANCELLED → visible in history, not payable

Tests:
  1.  Customer list excludes DRAFT invoices.
  2.  Customer list includes ISSUED invoices.
  3.  Customer list includes PAID invoices.
  4.  Customer list includes CANCELLED invoices.
  5.  Customer cannot access DRAFT invoice detail (404).
  6.  Customer can access ISSUED invoice detail (200).
  7.  Customer can access PAID invoice detail (200).
  8.  Customer can access CANCELLED invoice detail (200).
  9.  Public invoice print blocks DRAFT (404).
  10. Public invoice print blocks CANCELLED (404).
  11. Public invoice print allows ISSUED (200).
  12. Public invoice print allows PAID (200).
  13. Paid customer invoice detail receives payment_info in context.
  14. Unpaid customer invoice detail receives safe (empty) payment_info.
  15. Customer cannot access another customer's invoice detail (403).
  16. Customer cannot access DRAFT invoice of another customer (403 beats 404).

Note on admin visibility:
    These tests do not verify admin or technician visibility — those are
    unchanged. Only the customer-facing code paths are exercised here.
"""
import itertools
from unittest.mock import patch

from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase

from apps.accounts.models import CompanyUser, Customer, UserRole
from apps.invoices.models import Invoice
from apps.invoices.selectors import InvoiceSelector
from apps.invoices.services import InvoiceCreateService, InvoiceCancelService
from apps.invoices import views as invoice_views
from apps.orders.models import Order
from apps.tenants.models import Company

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------
_counter = itertools.count(1)


def _next():
    return next(_counter)


def _company():
    n = _next()
    return Company.objects.create(
        name=f"Test Co {n}",
        code=f"tc{n:03d}",
        slug=f"test-co-{n}",
    )


def _user(company, role=UserRole.CUSTOMER):
    n = _next()
    return CompanyUser.objects.create_user(
        username=f"u{n}",
        password="pw",
        company=company,
        role=role,
    )


def _customer(company, user=None):
    if user is None:
        user = _user(company, role=UserRole.CUSTOMER)
    n = _next()
    return Customer.objects.create(
        company=company,
        user=user,
        first_name="Test",
        last_name=f"Customer{n}",
        phone=f"0900{n:07d}",
    )


def _order(company):
    n = _next()
    return Order.objects.create(
        company=company,
        title=f"Order {n}",
        status=Order.Status.IN_PROGRESS,
    )


def _invoice(company, order, customer=None, status=Invoice.Status.DRAFT):
    inv = InvoiceCreateService.create(
        company=company,
        order=order,
        customer=customer,
        items=[{"description": "Service", "quantity": 1, "unit_price": 300_000, "discount_amount": 0}],
    )
    if status != Invoice.Status.DRAFT:
        Invoice.objects.filter(pk=inv.pk).update(status=status)
        inv.refresh_from_db()
    return inv


def _request(company, user):
    """Build a GET RequestFactory request with company and user attached."""
    rf = RequestFactory()
    req = rf.get("/fake/")
    req.company = company
    req.user = user
    return req


# ---------------------------------------------------------------------------
# 1–4: Customer invoice list filtering
# ---------------------------------------------------------------------------
class CustomerInvoiceListFilterTest(TestCase):
    """
    InvoiceSelector.get_for_customer() must return ISSUED, PAID, CANCELLED
    and must never return DRAFT invoices.
    """

    def setUp(self):
        self.company = _company()
        customer_user = _user(self.company, role=UserRole.CUSTOMER)
        self.customer = _customer(self.company, user=customer_user)
        self.order = _order(self.company)

    def _make(self, status):
        # Each invoice needs its own order: the DB constraint allows only one
        # DRAFT or ISSUED invoice per order at a time.
        return _invoice(self.company, _order(self.company), customer=self.customer, status=status)

    def test_draft_invoice_excluded_from_customer_list(self):
        """Test 1: DRAFT invoice must not appear in the customer queryset."""
        inv = self._make(Invoice.Status.DRAFT)
        qs = InvoiceSelector.get_for_customer(customer=self.customer)
        self.assertNotIn(inv, qs)

    def test_issued_invoice_included_in_customer_list(self):
        """Test 2: ISSUED invoice must appear in the customer queryset."""
        inv = self._make(Invoice.Status.ISSUED)
        qs = InvoiceSelector.get_for_customer(customer=self.customer)
        self.assertIn(inv, qs)

    def test_paid_invoice_included_in_customer_list(self):
        """Test 3: PAID invoice must appear in the customer queryset."""
        inv = self._make(Invoice.Status.PAID)
        qs = InvoiceSelector.get_for_customer(customer=self.customer)
        self.assertIn(inv, qs)

    def test_cancelled_invoice_included_in_customer_list(self):
        """Test 4: CANCELLED invoice must remain in customer history."""
        inv = self._make(Invoice.Status.CANCELLED)
        qs = InvoiceSelector.get_for_customer(customer=self.customer)
        self.assertIn(inv, qs)

    def test_only_non_draft_statuses_are_in_visible_constant(self):
        """Defensive: CUSTOMER_VISIBLE_STATUSES must not contain DRAFT."""
        self.assertNotIn(
            Invoice.Status.DRAFT,
            InvoiceSelector.CUSTOMER_VISIBLE_STATUSES,
        )
        for status in (Invoice.Status.ISSUED, Invoice.Status.PAID, Invoice.Status.CANCELLED):
            self.assertIn(status, InvoiceSelector.CUSTOMER_VISIBLE_STATUSES)

    def test_customer_only_sees_own_invoices(self):
        """Boundary: invoices belonging to a different customer are excluded."""
        other_user = _user(self.company, role=UserRole.CUSTOMER)
        other_customer = _customer(self.company, user=other_user)
        other_inv = _invoice(
            self.company, self.order,
            customer=other_customer,
            status=Invoice.Status.ISSUED,
        )
        qs = InvoiceSelector.get_for_customer(customer=self.customer)
        self.assertNotIn(other_inv, qs)

    def test_invoice_list_view_excludes_draft(self):
        """
        View-level test: invoice_list renders only non-DRAFT for customer role.

        django.shortcuts.render returns a plain HttpResponse, so we patch it
        to capture the context dict rather than trying to parse rendered HTML.
        """
        draft_inv = self._make(Invoice.Status.DRAFT)
        issued_inv = self._make(Invoice.Status.ISSUED)

        captured = {}

        def _fake_render(request, template, ctx, **kwargs):
            captured.update(ctx)
            return HttpResponse("ok")

        req = _request(self.company, self.customer.user)
        with patch("apps.invoices.views.render", side_effect=_fake_render):
            response = invoice_views.invoice_list(req)

        self.assertEqual(response.status_code, 200)
        invoices_in_ctx = list(captured.get("invoices", []))
        self.assertNotIn(draft_inv, invoices_in_ctx)
        self.assertIn(issued_inv, invoices_in_ctx)


# ---------------------------------------------------------------------------
# 5–8: Customer invoice detail access
# ---------------------------------------------------------------------------
class CustomerInvoiceDetailAccessTest(TestCase):

    def setUp(self):
        self.company = _company()
        customer_user = _user(self.company, role=UserRole.CUSTOMER)
        self.customer = _customer(self.company, user=customer_user)
        self.order = _order(self.company)

    def _detail(self, invoice):
        req = _request(self.company, self.customer.user)
        return invoice_views.invoice_detail(req, invoice_id=invoice.id)

    def test_customer_cannot_access_draft_invoice_detail(self):
        """Test 5: DRAFT detail returns 404 for customer."""
        inv = _invoice(self.company, self.order, customer=self.customer,
                       status=Invoice.Status.DRAFT)
        with self.assertRaises(Http404):
            self._detail(inv)

    def test_customer_can_access_issued_invoice_detail(self):
        """Test 6: ISSUED detail returns 200 for customer."""
        inv = _invoice(self.company, self.order, customer=self.customer,
                       status=Invoice.Status.ISSUED)
        response = self._detail(inv)
        self.assertEqual(response.status_code, 200)

    def test_customer_can_access_paid_invoice_detail(self):
        """Test 7: PAID detail returns 200 for customer."""
        inv = _invoice(self.company, self.order, customer=self.customer,
                       status=Invoice.Status.PAID)
        response = self._detail(inv)
        self.assertEqual(response.status_code, 200)

    def test_customer_can_access_cancelled_invoice_detail(self):
        """Test 8: CANCELLED detail returns 200 for customer."""
        inv = _invoice(self.company, self.order, customer=self.customer,
                       status=Invoice.Status.CANCELLED)
        response = self._detail(inv)
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_access_another_customers_invoice(self):
        """Test 15: Owning-customer check returns 403 before status check."""
        other_user = _user(self.company, role=UserRole.CUSTOMER)
        other_customer = _customer(self.company, user=other_user)
        inv = _invoice(self.company, self.order, customer=other_customer,
                       status=Invoice.Status.ISSUED)

        req = _request(self.company, self.customer.user)
        response = invoice_views.invoice_detail(req, invoice_id=inv.id)
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_access_draft_of_another_customer(self):
        """Test 16: Foreign DRAFT invoice returns 403 (ownership check fires first)."""
        other_user = _user(self.company, role=UserRole.CUSTOMER)
        other_customer = _customer(self.company, user=other_user)
        inv = _invoice(self.company, self.order, customer=other_customer,
                       status=Invoice.Status.DRAFT)

        req = _request(self.company, self.customer.user)
        response = invoice_views.invoice_detail(req, invoice_id=inv.id)
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# 9–12: Public invoice print access
# ---------------------------------------------------------------------------
class PublicInvoicePrintAccessTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)

    def _print(self, invoice):
        rf = RequestFactory()
        req = rf.get("/fake/")
        req.company = self.company
        # invoice_print is not auth-gated — no user needed.
        return invoice_views.invoice_print(req, public_code=invoice.public_code)

    def test_print_blocks_draft(self):
        """Test 9: DRAFT invoice print returns 404."""
        inv = _invoice(self.company, self.order, status=Invoice.Status.DRAFT)
        self.assertIsNotNone(inv.public_code, "DRAFT invoice must have a public_code")
        with self.assertRaises(Http404):
            self._print(inv)

    def test_print_blocks_cancelled(self):
        """Test 10: CANCELLED invoice print returns 404."""
        inv = _invoice(self.company, self.order, status=Invoice.Status.CANCELLED)
        with self.assertRaises(Http404):
            self._print(inv)

    def test_print_allows_issued(self):
        """Test 11: ISSUED invoice print returns 200."""
        inv = _invoice(self.company, self.order, status=Invoice.Status.ISSUED)
        response = self._print(inv)
        self.assertEqual(response.status_code, 200)

    def test_print_allows_paid(self):
        """Test 12: PAID invoice print returns 200."""
        inv = _invoice(self.company, self.order, status=Invoice.Status.PAID)
        response = self._print(inv)
        self.assertEqual(response.status_code, 200)

    def test_print_behavior_matches_public_detail(self):
        """
        Regression: invoice_print and public_invoice_detail must block
        the same statuses. Previously invoice_print did not block DRAFT.
        """
        # Each invoice needs its own order: the DB constraint allows only one
        # DRAFT or ISSUED invoice per order at a time.
        draft_inv = _invoice(self.company, _order(self.company), status=Invoice.Status.DRAFT)
        cancelled_inv = _invoice(self.company, _order(self.company), status=Invoice.Status.CANCELLED)
        issued_inv = _invoice(self.company, _order(self.company), status=Invoice.Status.ISSUED)

        def _public_detail(invoice):
            rf = RequestFactory()
            req = rf.get("/fake/")
            req.company = self.company
            return invoice_views.public_invoice_detail(req, public_code=invoice.public_code)

        # Both views must 404 on DRAFT
        with self.assertRaises(Http404):
            self._print(draft_inv)
        with self.assertRaises(Http404):
            _public_detail(draft_inv)

        # Both views must 404 on CANCELLED
        with self.assertRaises(Http404):
            self._print(cancelled_inv)
        with self.assertRaises(Http404):
            _public_detail(cancelled_inv)

        # Both views must 200 on ISSUED
        self.assertEqual(self._print(issued_inv).status_code, 200)
        self.assertEqual(_public_detail(issued_inv).status_code, 200)


# ---------------------------------------------------------------------------
# 13–14: payment_info in customer invoice detail context
# ---------------------------------------------------------------------------
class CustomerInvoiceDetailPaymentInfoTest(TestCase):
    """
    invoice_detail must pass payment_info to the template context for all
    invoice statuses. For PAID invoices with a recorded Payment, payment_info
    must carry real data. For all others it must be the safe empty dict.
    """

    def setUp(self):
        self.company = _company()
        customer_user = _user(self.company, role=UserRole.CUSTOMER)
        self.customer = _customer(self.company, user=customer_user)
        self.order = _order(self.company)

    def _context(self, invoice):
        """
        Call invoice_detail and return the template context dict.

        django.shortcuts.render returns a plain HttpResponse (not TemplateResponse),
        so we patch render to capture the context rather than accessing .context_data.
        """
        captured = {}

        def _fake_render(request, template, ctx, **kwargs):
            captured.update(ctx)
            return HttpResponse("ok")

        req = _request(self.company, self.customer.user)
        with patch("apps.invoices.views.render", side_effect=_fake_render):
            response = invoice_views.invoice_detail(req, invoice_id=invoice.id)

        self.assertEqual(response.status_code, 200)
        return captured

    def test_paid_invoice_detail_receives_payment_info_key(self):
        """Test 13: PAID invoice detail context contains payment_info dict."""
        inv = _invoice(self.company, self.order, customer=self.customer,
                       status=Invoice.Status.PAID)
        ctx = self._context(inv)
        self.assertIn("payment_info", ctx)
        payment_info = ctx["payment_info"]
        self.assertIsInstance(payment_info, dict)
        # Must have the exists key (built by PaymentSelector.build_display_info)
        self.assertIn("exists", payment_info)

    def test_issued_invoice_detail_receives_payment_info_key(self):
        """Test 14: ISSUED invoice detail also has payment_info (safe empty dict)."""
        inv = _invoice(self.company, self.order, customer=self.customer,
                       status=Invoice.Status.ISSUED)
        ctx = self._context(inv)
        self.assertIn("payment_info", ctx)
        payment_info = ctx["payment_info"]
        self.assertIsInstance(payment_info, dict)
        # No payment exists for an ISSUED invoice
        self.assertFalse(payment_info.get("exists", True))

    def test_cancelled_invoice_detail_receives_payment_info_key(self):
        """CANCELLED invoice detail also has payment_info (safe empty dict)."""
        inv = _invoice(self.company, self.order, customer=self.customer,
                       status=Invoice.Status.CANCELLED)
        ctx = self._context(inv)
        self.assertIn("payment_info", ctx)
        self.assertFalse(ctx["payment_info"].get("exists", True))

    def test_paid_invoice_without_payment_record_gets_safe_dict(self):
        """
        Edge case: invoice is PAID but no Payment row exists (e.g. manually
        set). build_display_info(None) must return a safe dict, not raise.
        """
        inv = _invoice(self.company, self.order, customer=self.customer,
                       status=Invoice.Status.PAID)
        ctx = self._context(inv)
        # No Payment row was created, so exists=False is the safe fallback.
        payment_info = ctx["payment_info"]
        self.assertIsInstance(payment_info, dict)
        self.assertIn("exists", payment_info)
