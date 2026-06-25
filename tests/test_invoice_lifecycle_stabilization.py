"""
Invoice Lifecycle Stabilization — Test Suite.

Covers the five fixes delivered in this batch:
  Fix 1  has_active_invoice flag in admin_order_detail no longer treats PAID as active.
  Fix 2  Path C (orders/views.py:technician_invoice_create) redirects to Path D.
  Fix 3  Customer notification fires when any path issues an invoice, via the
         post_save signal in apps/notifications/signals.py. The duplicate
         view-level call in Path D (views_technician.py line 529) was removed.
  Fix 4  create_from_order / get_or_create_for_order are protected by
         select_for_update — a second call returns the existing invoice.
"""
import itertools
from unittest.mock import patch

from django.test import RequestFactory, TestCase

from apps.accounts.models import CompanyUser, UserRole
from apps.invoices.models import Invoice
from apps.invoices.services import (
    InvoiceCreateService,
    InvoiceDuplicateGuard,
    InvoiceIssueService,
)
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


def _order(company, status=Order.Status.IN_PROGRESS):
    n = _next()
    return Order.objects.create(
        company=company,
        title=f"Test Order {n}",
        status=status,
    )


def _draft_invoice(company, order):
    """Create a DRAFT invoice with one non-zero item so it can be issued."""
    return InvoiceCreateService.create(
        company=company,
        order=order,
        items=[{
            "description": "Service call",
            "quantity": 1,
            "unit_price": 500_000,
            "discount_amount": 0,
        }],
    )


def _zero_invoice(company, order):
    """Create a DRAFT invoice with no items (total_amount = 0)."""
    return InvoiceCreateService.create(
        company=company,
        order=order,
        items=[],
    )


# ---------------------------------------------------------------------------
# Fix 1: has_active_invoice flag
# ---------------------------------------------------------------------------
class HasActiveInvoiceFlagTest(TestCase):
    """
    InvoiceDuplicateGuard (and the admin_order_detail view's has_active_invoice
    query) must treat PAID invoices as closed — not active.

    Before the fix:  .exclude(status=CANCELLED) — PAID was counted as active,
                     blocking the "Create Invoice" button even after payment.
    After the fix:   .exclude(status__in=[CANCELLED, PAID]) — only DRAFT/ISSUED
                     count as active.
    """

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)

    def test_no_invoice_returns_false(self):
        self.assertFalse(
            InvoiceDuplicateGuard.has_active_for_order(
                company=self.company, order=self.order
            )
        )

    def test_draft_invoice_is_active(self):
        _draft_invoice(self.company, self.order)
        self.assertTrue(
            InvoiceDuplicateGuard.has_active_for_order(
                company=self.company, order=self.order
            )
        )

    def test_issued_invoice_is_active(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["status"])
        self.assertTrue(
            InvoiceDuplicateGuard.has_active_for_order(
                company=self.company, order=self.order
            )
        )

    def test_paid_invoice_is_not_active(self):
        """Core regression: a PAID invoice must NOT block creation of a new one."""
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.PAID
        inv.save(update_fields=["status"])
        self.assertFalse(
            InvoiceDuplicateGuard.has_active_for_order(
                company=self.company, order=self.order
            )
        )

    def test_cancelled_invoice_is_not_active(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.CANCELLED
        inv.save(update_fields=["status"])
        self.assertFalse(
            InvoiceDuplicateGuard.has_active_for_order(
                company=self.company, order=self.order
            )
        )

    def test_paid_then_new_draft_is_active(self):
        """After a PAID invoice is closed, a new DRAFT counts as active."""
        inv_paid = _draft_invoice(self.company, self.order)
        inv_paid.status = Invoice.Status.PAID
        inv_paid.save(update_fields=["status"])

        inv_draft = _draft_invoice(self.company, self.order)
        self.assertEqual(inv_draft.status, Invoice.Status.DRAFT)

        self.assertTrue(
            InvoiceDuplicateGuard.has_active_for_order(
                company=self.company, order=self.order
            )
        )
        active = InvoiceDuplicateGuard.get_active_for_order(
            company=self.company, order=self.order
        )
        self.assertEqual(active.pk, inv_draft.pk)


# ---------------------------------------------------------------------------
# Fix 2: Path C redirect
# ---------------------------------------------------------------------------
class PathCRedirectTest(TestCase):
    """
    Path C (/<code>/tech/orders/<order_id>/invoice/create/) must redirect to
    Path D (/<code>/tech/invoices/order/<order_id>/create/) for all methods.

    Before:  direct DRAFT invoice creation (no issue, no notification to customer).
    After:   302 redirect to the canonical full-form URL that issues + notifies.

    The view body is tested via __wrapped__ (accessible because @require_tenant_role
    uses @functools.wraps) to avoid full middleware/auth setup.
    """

    def _call_inner(self, order_id, company):
        from apps.orders import views as order_views
        inner = order_views.technician_invoice_create.__wrapped__
        factory = RequestFactory()
        request = factory.get("/")
        request.company = company
        return inner(request, order_id=order_id)

    def test_redirect_points_to_path_d(self):
        company = _company()
        order = _order(company)
        response = self._call_inner(order_id=order.pk, company=company)
        self.assertIn(response.status_code, [301, 302])
        self.assertIn(
            f"/tech/invoices/order/{order.pk}/create/",
            response["Location"],
        )

    def test_redirect_includes_company_code(self):
        company = _company()
        order = _order(company)
        response = self._call_inner(order_id=order.pk, company=company)
        self.assertIn(company.code, response["Location"])

    def test_no_invoice_created_by_path_c(self):
        """Path C must not create any DB records — only redirect."""
        company = _company()
        order = _order(company)
        count_before = Invoice.objects.count()
        self._call_inner(order_id=order.pk, company=company)
        self.assertEqual(Invoice.objects.count(), count_before)


# ---------------------------------------------------------------------------
# Fix 3: Customer notification on invoice issue
# ---------------------------------------------------------------------------
class InvoiceIssuedNotificationTest(TestCase):
    """
    The post_save signal (apps/notifications/signals.py:emit_invoice_status_events)
    fires invoice_issued_customer whenever an Invoice is saved with status ISSUED.
    This covers all issue paths: admin, technician, and system.

    The view-level duplicate call in Path D (views_technician.py) was removed
    in this batch so the signal fires exactly once per issue.
    """

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)

    def test_issue_fires_customer_notification_exactly_once(self):
        """Signal emits invoice_issued_customer exactly once per issue()."""
        inv = _draft_invoice(self.company, self.order)

        emit_path = "apps.notifications.services_events.NotificationEventService.emit"
        with patch(emit_path) as mock_emit:
            InvoiceIssueService.issue(invoice=inv)

        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args.kwargs
        self.assertEqual(call_kwargs.get("event_key"), "invoice_issued_customer")
        self.assertEqual(call_kwargs.get("company"), self.company)

    def test_no_notification_when_issue_raises_before_save(self):
        """When issue() raises (zero amount), the invoice.save never happens — no signal."""
        inv = _zero_invoice(self.company, self.order)  # no items → total = 0

        emit_path = "apps.notifications.services_events.NotificationEventService.emit"
        with patch(emit_path) as mock_emit:
            with self.assertRaises(ValueError):
                InvoiceIssueService.issue(invoice=inv)

        # Signal fires on post_save with status=ISSUED. Since the save never
        # happened (ValueError raised before it), the signal never fired.
        issued_calls = [
            c for c in mock_emit.call_args_list
            if (c.kwargs.get("event_key") == "invoice_issued_customer"
                and c.kwargs.get("company") == self.company)
        ]
        self.assertEqual(len(issued_calls), 0)

    def test_issue_changes_status_to_issued(self):
        inv = _draft_invoice(self.company, self.order)
        with patch("apps.notifications.services_events.NotificationEventService.emit"):
            InvoiceIssueService.issue(invoice=inv)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.ISSUED)

    def test_issue_raises_on_already_issued(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            InvoiceIssueService.issue(invoice=inv)

    def test_issue_raises_on_zero_amount(self):
        """invoice with no items has total_amount=0 → recalculate keeps 0 → raises."""
        inv = _zero_invoice(self.company, self.order)
        with self.assertRaises(ValueError):
            InvoiceIssueService.issue(invoice=inv)


# ---------------------------------------------------------------------------
# Fix 4: Race guard — create_from_order and get_or_create_for_order
# ---------------------------------------------------------------------------
class CreateFromOrderRaceGuardTest(TestCase):
    """
    create_from_order() acquires a row-level lock on Order and re-checks for an
    existing active invoice before creating, so two sequential calls (simulating
    a race) return the same invoice rather than creating duplicates.

    Before:  two concurrent callers could both pass InvoiceDuplicateGuard and
             create two active invoices for the same order.
    After:   the second caller finds the first invoice under the lock and returns
             it — only one active invoice exists per order at any time.
    """

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)

    def test_second_call_returns_existing_invoice(self):
        """Two sequential calls to create_from_order return the same invoice."""
        inv1 = InvoiceCreateService.create_from_order(order=self.order)
        inv2 = InvoiceCreateService.create_from_order(order=self.order)

        self.assertEqual(inv1.pk, inv2.pk)
        active_count = Invoice.objects.filter(
            company=self.company,
            order=self.order,
        ).exclude(
            status__in=[Invoice.Status.CANCELLED, Invoice.Status.PAID]
        ).count()
        self.assertEqual(active_count, 1)

    def test_new_invoice_created_when_none_exists(self):
        inv = InvoiceCreateService.create_from_order(order=self.order)
        self.assertIsNotNone(inv.pk)
        self.assertEqual(inv.status, Invoice.Status.DRAFT)
        self.assertEqual(inv.order_id, self.order.pk)
        self.assertEqual(inv.company_id, self.company.pk)

    def test_new_invoice_allowed_after_paid(self):
        """After a PAID invoice is closed, create_from_order must create a new one."""
        inv1 = InvoiceCreateService.create_from_order(order=self.order)
        inv1.status = Invoice.Status.PAID
        inv1.save(update_fields=["status"])

        inv2 = InvoiceCreateService.create_from_order(order=self.order)
        self.assertNotEqual(inv1.pk, inv2.pk)
        self.assertEqual(inv2.status, Invoice.Status.DRAFT)


class GetOrCreateForOrderRaceGuardTest(TestCase):
    """
    get_or_create_for_order() acquires a row-level lock before the check so the
    (check → create) sequence is atomic. The created boolean is accurate.
    """

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)

    def test_first_call_creates(self):
        inv, created = InvoiceCreateService.get_or_create_for_order(order=self.order)
        self.assertTrue(created)
        self.assertEqual(inv.status, Invoice.Status.DRAFT)

    def test_second_call_returns_existing_with_created_false(self):
        inv1, created1 = InvoiceCreateService.get_or_create_for_order(order=self.order)
        inv2, created2 = InvoiceCreateService.get_or_create_for_order(order=self.order)

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(inv1.pk, inv2.pk)

    def test_only_one_active_invoice_after_concurrent_simulation(self):
        """Two sequential get_or_create calls produce exactly one active invoice."""
        InvoiceCreateService.get_or_create_for_order(order=self.order)
        InvoiceCreateService.get_or_create_for_order(order=self.order)

        active_count = Invoice.objects.filter(
            company=self.company,
            order=self.order,
        ).exclude(
            status__in=[Invoice.Status.CANCELLED, Invoice.Status.PAID]
        ).count()
        self.assertEqual(active_count, 1)

    def test_new_created_after_paid(self):
        inv_paid, _ = InvoiceCreateService.get_or_create_for_order(order=self.order)
        inv_paid.status = Invoice.Status.PAID
        inv_paid.save(update_fields=["status"])

        inv_new, created = InvoiceCreateService.get_or_create_for_order(order=self.order)
        self.assertTrue(created)
        self.assertNotEqual(inv_paid.pk, inv_new.pk)
        self.assertEqual(inv_new.status, Invoice.Status.DRAFT)
