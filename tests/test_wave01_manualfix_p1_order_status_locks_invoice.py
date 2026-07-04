"""
EPIC-002 Wave 01 — Manual Test Fix, Problem 1: invoice creation/issuance was
still possible when the ORDER itself was cancel_requested/cancelled.

Root cause: the Issue 005 fix (InvoiceCancellationGuard.has_pending_request)
only locked invoice creation when an existing INVOICE had a pending
cancellation request. It never checked the ORDER's own status. Both
apps.invoices.views_technician.technician_invoice_create and
apps.tenants.views_admin.admin_invoice_create_from_order fetched the order
and went straight to the InvoiceDuplicateGuard check, with no order-status
gate at all — so a technician or admin could still create/issue a brand new
invoice for an order that was cancel_requested or already cancelled (this is
a different code path than the existing-invoice case Issue 005 covered,
since a cancel_requested/cancelled order may have no invoice yet).

Fix: added InvoiceCancellationGuard.order_blocks_invoice_creation(order)
(apps/invoices/services.py), mirroring the existing has_pending_request()
guard shape, and wired it into both entry points:
  - technician_invoice_create: pre-check + re-check inside the transaction
    (same double-check pattern already used for has_pending_request).
  - admin_invoice_create_from_order: pre-check, plus parity fix so this path
    also honors has_pending_request() on an existing active invoice (it
    previously had no cancellation-request check at all, unlike the
    technician path).
Also hid the "create invoice" button/form in the two templates that expose
it (templates/orders/technician_my_orders.html,
apps/tenants/views_admin.py's can_create_invoice flag used by
templates/tenants/admin_order_detail.html) for cancel_requested/cancelled
orders, so the UI doesn't offer an action the server will now reject.

No changes to InvoiceCancellationRequestService, InvoiceCancelService, order
cancellation workflow, or any model/migration.
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice
from apps.invoices.services import InvoiceCreateService, InvoiceIssueService
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"OrderLock Co {n}", code=f"ol{n:03d}", slug=f"orderlock-co-{n}", is_active=True)


def _tech_user(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"olt{n}", password="testpass", company=company, role=UserRole.TECHNICIAN)


def _admin(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"ola{n}", password="testpass", company=company, role=UserRole.COMPANY_ADMIN)


def _technician(company, user):
    return Technician.objects.create(company=company, user=user, is_available=True)


def _order(company, technician, status):
    n = _n()
    return Order.objects.create(company=company, title=f"Order {n}", status=status, technician=technician)


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianInvoiceCreateBlockedByOrderStatusTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.tech_user = _tech_user(self.company)
        self.tech = _technician(self.company, self.tech_user)

    def _create_url(self, order):
        return f"/{self.company.code}/tech/invoices/order/{order.id}/create/"

    def test_cannot_create_invoice_for_cancel_requested_order(self):
        order = _order(self.company, self.tech, Order.Status.CANCEL_REQUESTED)
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.post(self._create_url(order), {
            "description": ["Service"], "quantity": ["1"],
            "unit_price": ["100000"], "discount_amount": ["0"], "row_type": ["service"],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Invoice.objects.filter(order=order).exists())

    def test_cannot_create_invoice_for_cancelled_order(self):
        order = _order(self.company, self.tech, Order.Status.CANCELLED)
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.post(self._create_url(order), {
            "description": ["Service"], "quantity": ["1"],
            "unit_price": ["100000"], "discount_amount": ["0"], "row_type": ["service"],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Invoice.objects.filter(order=order).exists())

    def test_get_form_also_blocked_and_redirects_to_order(self):
        order = _order(self.company, self.tech, Order.Status.CANCELLED)
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.get(self._create_url(order))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"/tech/orders/{order.id}/", resp.url)

    def test_button_hidden_on_my_orders_page_for_cancelled_order(self):
        order = _order(self.company, self.tech, Order.Status.CANCELLED)
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/tech/orders/my/?status=cancelled")
        content = resp.content.decode("utf-8")
        self.assertNotIn(f'/tech/invoices/order/{order.id}/create/', content)


@override_settings(ROOT_URLCONF="config.urls")
class AdminInvoiceCreateFromOrderBlockedByOrderStatusTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.tech_user = _tech_user(self.company)
        self.tech = _technician(self.company, self.tech_user)

    def _create_url(self, order):
        return f"/{self.company.code}/admin/orders/{order.id}/invoice/create/"

    def test_admin_cannot_create_invoice_for_cancel_requested_order(self):
        order = _order(self.company, self.tech, Order.Status.CANCEL_REQUESTED)
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.post(self._create_url(order))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Invoice.objects.filter(order=order).exists())

    def test_admin_cannot_create_invoice_for_cancelled_order(self):
        order = _order(self.company, self.tech, Order.Status.CANCELLED)
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.post(self._create_url(order))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Invoice.objects.filter(order=order).exists())

    def test_create_invoice_button_hidden_on_order_detail_for_cancelled_order(self):
        order = _order(self.company, self.tech, Order.Status.CANCELLED)
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/admin/orders/{order.id}/")
        content = resp.content.decode("utf-8")
        self.assertNotIn(f'/admin/orders/{order.id}/invoice/create/', content)


@override_settings(ROOT_URLCONF="config.urls")
class InvoiceCreationStillWorksForNormalOrdersTest(TestCase):
    """Regression guard: the new order-status lock must not block the normal flow."""

    def setUp(self):
        self.company = _company()
        self.tech_user = _tech_user(self.company)
        self.tech = _technician(self.company, self.tech_user)
        self.admin = _admin(self.company)

    def test_technician_can_still_create_invoice_for_done_order(self):
        order = _order(self.company, self.tech, Order.Status.DONE)
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.post(
            f"/{self.company.code}/tech/invoices/order/{order.id}/create/",
            {
                "description": ["Service"], "quantity": ["1"],
                "unit_price": ["500000"], "discount_amount": ["0"], "row_type": ["service"],
            },
        )
        self.assertEqual(resp.status_code, 302)
        invoice = Invoice.objects.get(order=order)
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)

    def test_admin_can_still_create_invoice_for_done_order(self):
        order = _order(self.company, self.tech, Order.Status.DONE)
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.post(f"/{self.company.code}/admin/orders/{order.id}/invoice/create/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Invoice.objects.filter(order=order, status=Invoice.Status.DRAFT).exists())
