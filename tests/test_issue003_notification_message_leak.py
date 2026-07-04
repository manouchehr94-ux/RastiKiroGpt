"""
EPIC-002 Issue 003: Notification preview (Django flash messages) must not leak
onto unrelated public pages.

Root cause (fixed):
  apps/invoices/views.py::invoice_pay used django.contrib.messages directly for
  its discount-apply and gateway-start actions, and
  templates/payments/invoice_checkout.html rendered `{% if messages %}`
  unconditionally. Because Django session messages are not scoped to a page,
  a message queued anywhere in a browser session could render on this public,
  unauthenticated payment page the next time it was loaded.

  templates/public/contact.html had the same unguarded `{% if messages %}`
  block with no first-party trigger, but was equally exploitable.

Fix (reusing the existing public-safe pattern already established for
apps/invoices/views.py::_invoice_discount_redirect / templates/invoices/public_detail.html):
  - invoice_pay's discount/gateway error paths now redirect with a `pay_err`
    query-string param instead of queuing a session message.
  - invoice_checkout.html renders `request.GET.pay_err` instead of `messages`.
  - contact.html's dead `{% if messages %}` block was removed (the view never
    queued messages; the block only existed as an exploitable leak surface).

Note: the Notification "bell" preview (notif_latest / notif_unread_count,
apps/notifications/context_processors.py) is a SEPARATE mechanism, already
covered by tests/test_notifications_ux.py, and was not touched by this fix.
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
        code=f"nl{n}", name=f"Notif Leak Co {n}", slug=f"nl-co-{n}", is_active=True
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


def _inject_session_message(client, text: str) -> None:
    """
    Write a Django session message directly into the test-client session,
    simulating a stale message left over from an unrelated admin/staff action
    earlier in the same browser session.
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

    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key


@override_settings(ROOT_URLCONF="config.urls")
class PublicPaymentMessageLeakTest(TestCase):
    """The public payment checkout page must not render stale session messages."""

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)
        self.invoice = _issued_invoice(self.company, self.order)

    def _pay_url(self, invoice=None):
        invoice = invoice or self.invoice
        return f"/{self.company.code}/invoices/{invoice.id}/pay/"

    def test_pay_page_returns_200(self):
        resp = self.client.get(self._pay_url())
        self.assertEqual(resp.status_code, 200)

    def test_pay_page_does_not_render_stale_session_message(self):
        stale = "دریافت نقدی ثبت شد — stale-admin-marker-pay-001"
        _inject_session_message(self.client, stale)
        resp = self.client.get(self._pay_url())
        self.assertNotContains(resp, "stale-admin-marker-pay-001")

    def test_pay_page_invoice_content_still_renders_with_stale_message_present(self):
        stale = "some stale message — marker-pay-002"
        _inject_session_message(self.client, stale)
        resp = self.client.get(self._pay_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.invoice.invoice_number)
        self.assertContains(resp, "پرداخت اینترنتی فاکتور")

    def test_discount_already_applied_error_surfaces_via_query_param_not_session(self):
        """
        Posting apply_discount on an invoice that already has a campaign
        discount must redirect with a `pay_err` query param and must NOT
        leave anything in django.contrib.messages.
        """
        Invoice.objects.filter(pk=self.invoice.pk).update(campaign_discount_amount=5000)
        self.invoice.refresh_from_db()

        resp = self.client.post(self._pay_url(), {"action": "apply_discount", "discount_code": "X"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("pay_err=", resp.url)

        follow = self.client.get(resp.url)
        self.assertContains(follow, "کد تخفیف قبلاً اعمال شده است")
        # No stray messages should be queued by this flow.
        self.assertEqual(len(list(follow.context["messages"])), 0)

    def test_multi_tenant_stale_message_does_not_leak_across_companies(self):
        """
        A message queued while the browser session interacted with company A
        must not render on company B's public payment page in the same session.
        """
        other_company = _company()
        other_order = _order(other_company)
        other_invoice = _issued_invoice(other_company, other_order)

        stale = "پیام داخلی شرکت دیگر — stale-cross-tenant-marker-003"
        _inject_session_message(self.client, stale)

        resp = self.client.get(f"/{other_company.code}/invoices/{other_invoice.id}/pay/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "stale-cross-tenant-marker-003")


@override_settings(ROOT_URLCONF="config.urls")
class PublicContactMessageLeakTest(TestCase):
    """The public marketing contact page must not render stale session messages."""

    def test_contact_page_returns_200(self):
        resp = self.client.get("/contact/")
        self.assertEqual(resp.status_code, 200)

    def test_contact_page_does_not_render_stale_session_message(self):
        stale = "پیام داخلی ادمین — stale-admin-marker-contact-001"
        _inject_session_message(self.client, stale)
        resp = self.client.get("/contact/")
        self.assertNotContains(resp, "stale-admin-marker-contact-001")


class MessageBlockSourceGuardTest(TestCase):
    """
    Defense-in-depth: the fixed templates must not reintroduce a raw
    `{% if messages %}` block, which is what caused the leak.
    """

    def test_invoice_checkout_template_has_no_raw_messages_block(self):
        with open("templates/payments/invoice_checkout.html", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("{% if messages %}", content)

    def test_contact_template_has_no_raw_messages_block(self):
        with open("templates/public/contact.html", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("{% if messages %}", content)
