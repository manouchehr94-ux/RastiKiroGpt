"""
EPIC-002 Wave 01, Issue 005: Technician cancellation request must immediately
lock invoice creation/editing.

Root cause: InvoiceCancellationRequestService.request() creates a PENDING
InvoiceCancellationRequest but nothing downstream was aware of it —
apps.invoices.views_technician.technician_invoice_create would happily keep
reusing/re-issuing the same DRAFT invoice, and
technician_invoice_mark_cash_paid would happily cash-settle the same ISSUED
invoice, while a cancellation request against it was still PENDING review.

Fix: added InvoiceCancellationGuard (apps/invoices/services.py), mirroring
the existing InvoiceDuplicateGuard pattern, and wired a has_pending_request()
check into both entry points (pre-check + re-check inside the locked
transaction, matching the existing duplicate-guard double-check pattern).

No changes were made to InvoiceCancellationRequestService, InvoiceCancelService,
or the InvoiceCancellationRequest model — this is purely an additive guard at
the two vulnerable call sites.
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice
from apps.invoices.services import InvoiceCreateService, InvoiceIssueService
from apps.invoices.services_cancel_request import InvoiceCancellationRequestService
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"Lock Co {n}", code=f"lc{n:03d}", slug=f"lock-co-{n}", is_active=True)


def _user(company, role=UserRole.TECHNICIAN):
    n = _n()
    return CompanyUser.objects.create_user(username=f"lu{n}", password="testpass", company=company, role=role)


def _technician(company, user=None):
    if user is None:
        user = _user(company, role=UserRole.TECHNICIAN)
    return Technician.objects.create(company=company, user=user, is_available=True)


def _order(company, technician, status=Order.Status.IN_PROGRESS):
    n = _n()
    return Order.objects.create(company=company, title=f"Order {n}", status=status, technician=technician)


def _draft_invoice(company, order):
    return InvoiceCreateService.create(
        company=company, order=order,
        items=[{"description": "Service", "quantity": 1, "unit_price": 300_000, "discount_amount": 0}],
    )


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianInvoiceCreateLockedByCancellationRequestTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.tech_user = _user(self.company, role=UserRole.TECHNICIAN)
        self.tech = _technician(self.company, self.tech_user)
        self.order = _order(self.company, self.tech)
        self.invoice = _draft_invoice(self.company, self.order)
        InvoiceCancellationRequestService.request(invoice=self.invoice, requested_by=self.tech_user)

    def _create_url(self):
        # Canonical technician invoice-create URL (apps/invoices/urls_technician.py).
        # /tech/orders/<id>/invoice/create/ is a redirect-only alias to this URL.
        return f"/{self.company.code}/tech/invoices/order/{self.order.id}/create/"

    def test_get_form_redirects_away_when_cancellation_pending(self):
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.get(self._create_url())
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"/tech/invoices/{self.invoice.id}/", resp.url)

    def test_post_does_not_modify_or_issue_invoice_when_cancellation_pending(self):
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.post(self._create_url(), {
            "description": ["New description"],
            "quantity": ["1"],
            "unit_price": ["999999"],
            "discount_amount": ["0"],
            "row_type": ["service"],
        })
        self.assertEqual(resp.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.DRAFT)
        self.assertEqual(self.invoice.items.count(), 1)
        self.assertEqual(self.invoice.items.first().description, "Service")

    def test_issued_invoice_with_pending_cancellation_cannot_be_reissued(self):
        InvoiceIssueService.issue(invoice=self.invoice)
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.get(self._create_url())
        self.assertEqual(resp.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianCashPaidLockedByCancellationRequestTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.tech_user = _user(self.company, role=UserRole.TECHNICIAN)
        self.tech = _technician(self.company, self.tech_user)
        self.order = _order(self.company, self.tech)
        self.invoice = _draft_invoice(self.company, self.order)
        InvoiceIssueService.issue(invoice=self.invoice)
        InvoiceCancellationRequestService.request(invoice=self.invoice, requested_by=self.tech_user)

    def _cash_url(self):
        return f"/{self.company.code}/tech/invoices/{self.invoice.id}/cash-paid/"

    def test_cash_settlement_blocked_when_cancellation_pending(self):
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.post(self._cash_url())
        self.assertEqual(resp.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)
        from apps.payments.models import Payment
        self.assertFalse(Payment.objects.filter(invoice=self.invoice).exists())


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianInvoiceCreateStillWorksWithoutCancellationRequestTest(TestCase):
    """Regression guard: the new locks must not block the normal, unlocked flow."""

    def setUp(self):
        self.company = _company()
        self.tech_user = _user(self.company, role=UserRole.TECHNICIAN)
        self.tech = _technician(self.company, self.tech_user)
        self.order = _order(self.company, self.tech)

    def test_invoice_can_still_be_created_and_issued_without_pending_request(self):
        self.client.login(username=self.tech_user.username, password="testpass")
        resp = self.client.post(
            f"/{self.company.code}/tech/invoices/order/{self.order.id}/create/",
            {
                "description": ["Service"],
                "quantity": ["1"],
                "unit_price": ["500000"],
                "discount_amount": ["0"],
                "row_type": ["service"],
            },
        )
        self.assertEqual(resp.status_code, 302)
        invoice = Invoice.objects.get(order=self.order)
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
