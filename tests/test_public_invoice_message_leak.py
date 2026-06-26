"""
Regression: public invoice pages must not render stale admin/tech session messages.

Root cause (fixed):
  templates/invoices/public_detail.html had an explicit {% if messages %} block
  that rendered ALL Django session messages.  Admin/tech flash messages accumulated
  in the shared session and leaked onto the public invoice page.

Fix:
  - Removed {% if messages %} block from public_detail.html.
  - _invoice_discount_redirect now uses URL query param ?disc_err=... for error
    feedback on the public path instead of session messages.

Coverage:
  1. /i/<public_code>/                          - short public URL (no tenant ctx)
  2. /<company_code>/invoices/public/<code>/    - tenant-scoped public URL
"""
import itertools
from importlib import import_module

from django.conf import settings
from django.contrib.messages import constants as msg_const
from django.contrib.messages.storage.session import SessionStorage
from django.test import TestCase, override_settings

from apps.invoices.models import Invoice
from apps.invoices.services import InvoiceCreateService
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(
        code=f"ml{n}", name=f"Message Leak Co {n}", slug=f"ml-co-{n}", is_active=True
    )


def _order(company):
    n = _n()
    return Order.objects.create(
        company=company, title=f"Order {n}", status=Order.Status.IN_PROGRESS
    )


def _issued_invoice(company, order):
    inv = InvoiceCreateService.create(
        company=company,
        order=order,
        items=[{"description": "خدمت تست", "quantity": 1, "unit_price": 50_000, "discount_amount": 0}],
    )
    Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.ISSUED)
    inv.refresh_from_db()
    return inv


@override_settings(ROOT_URLCONF="config.urls")
class PublicInvoiceMessageLeakTest(TestCase):
    """Public invoice pages must not expose Django session messages from admin/tech workflows."""

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)
        self.invoice = _issued_invoice(self.company, self.order)

    def _inject_session_message(self, text: str) -> None:
        """
        Write a Django session message directly into the test-client session,
        simulating stale admin/tech flash messages left in the shared session.
        """
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session.save()

        from django.test import RequestFactory
        req = RequestFactory().get("/")
        req.session = session

        storage = SessionStorage(req)
        storage.add(msg_const.ERROR, text)
        storage._store(storage._queued_messages, None)
        session.save()

        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    # ------------------------------------------------------------------
    # /i/<public_code>/ — short public URL (no tenant context)
    # ------------------------------------------------------------------

    def test_short_url_returns_200(self):
        resp = self.client.get(f"/i/{self.invoice.public_code}/")
        self.assertEqual(resp.status_code, 200)

    def test_short_url_contains_company_name(self):
        resp = self.client.get(f"/i/{self.invoice.public_code}/")
        self.assertContains(resp, self.company.name)

    def test_short_url_does_not_render_stale_session_message(self):
        """
        Stale admin/tech messages in the session must NOT appear on /i/<code>/.
        Before fix: the template {% if messages %} block rendered ALL session messages.
        After fix:  the block is gone; session messages are never consumed or rendered.
        """
        stale = "دریافت نقدی ثبت شد — stale-admin-marker-xyz123"
        self._inject_session_message(stale)
        resp = self.client.get(f"/i/{self.invoice.public_code}/")
        self.assertNotContains(resp, "stale-admin-marker-xyz123")

    def test_short_url_invoice_content_still_renders(self):
        """Invoice content must remain visible after removing the messages block."""
        stale = "some stale message — marker-aaa999"
        self._inject_session_message(stale)
        resp = self.client.get(f"/i/{self.invoice.public_code}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.company.name)

    # ------------------------------------------------------------------
    # /<company_code>/invoices/public/<public_code>/ — tenant-scoped public URL
    # ------------------------------------------------------------------

    def test_tenant_public_url_returns_200(self):
        url = f"/{self.company.code}/invoices/public/{self.invoice.public_code}/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_tenant_public_url_contains_company_name(self):
        url = f"/{self.company.code}/invoices/public/{self.invoice.public_code}/"
        resp = self.client.get(url)
        self.assertContains(resp, self.company.name)

    def test_tenant_public_url_does_not_render_stale_session_message(self):
        """
        Same guarantee for the tenant-scoped public URL.
        Both paths render the same template — removing the messages block fixes both.
        """
        stale = "فاکتور صادر شد — stale-admin-marker-abc456"
        self._inject_session_message(stale)
        url = f"/{self.company.code}/invoices/public/{self.invoice.public_code}/"
        resp = self.client.get(url)
        self.assertNotContains(resp, "stale-admin-marker-abc456")

    def test_tenant_public_url_invoice_content_still_renders(self):
        """Invoice content must remain visible after removing the messages block."""
        stale = "another stale message — marker-bbb888"
        self._inject_session_message(stale)
        url = f"/{self.company.code}/invoices/public/{self.invoice.public_code}/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.company.name)
