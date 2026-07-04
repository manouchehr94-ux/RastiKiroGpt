"""
EPIC-002 Issue 001: Public payment checkout page must not use the admin dashboard layout.

Root cause (fixed):
  templates/payments/invoice_checkout.html extended layouts/dashboard.html and
  unconditionally overrode the sidebar_nav block to force-include
  includes/nav_admin.html — the full internal admin navigation menu — on an
  anonymous, unauthenticated public payment page.

Fix:
  - New dedicated templates/layouts/public_payment.html (no sidebar, no admin
    nav, no logout link, no dark-mode/notification controls).
  - invoice_checkout.html now extends layouts/public_payment.html instead of
    layouts/dashboard.html.

Coverage:
  /<company_code>/invoices/<invoice_id>/pay/ for anonymous visitors.
"""
import itertools

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
        code=f"pp{n}", name=f"Public Pay Co {n}", slug=f"pp-co-{n}", is_active=True
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


def _paid_invoice(company, order):
    inv = InvoiceCreateService.create(
        company=company,
        order=order,
        items=[{"description": "خدمت تست", "quantity": 1, "unit_price": 50_000, "discount_amount": 0}],
    )
    Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.PAID)
    inv.refresh_from_db()
    return inv


# Admin-only nav labels from templates/includes/nav_admin.html that must never
# appear on the anonymous public payment page.
ADMIN_NAV_LABELS = [
    "اپراتورها",
    "نیروهای خدماتی",
    "تعرفه‌های اجرت",
    "اعتبار پیامک",
    "گزارش مالی",
]

# Admin-only nav URLs from templates/includes/nav_admin.html that must never
# appear on the anonymous public payment page.
ADMIN_NAV_URL_FRAGMENTS = [
    "/admin/settings/operators/",
    "/admin/technicians/",
    "/admin/technicians/rates/",
    "/admin/sms-credit/",
    "/admin/financial-reports/summary/",
    "/admin/payment-gateway/",
]


@override_settings(ROOT_URLCONF="config.urls")
class PublicPaymentLayoutTest(TestCase):
    """The public payment checkout page must not leak admin dashboard chrome."""

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)
        self.invoice = _issued_invoice(self.company, self.order)

    def _pay_url(self, invoice):
        return f"/{self.company.code}/invoices/{invoice.id}/pay/"

    def test_anonymous_get_returns_200_for_payable_invoice(self):
        resp = self.client.get(self._pay_url(self.invoice))
        self.assertEqual(resp.status_code, 200)

    def test_response_does_not_contain_admin_nav_labels(self):
        resp = self.client.get(self._pay_url(self.invoice))
        content = resp.content.decode("utf-8")
        for label in ADMIN_NAV_LABELS:
            self.assertNotIn(label, content, f"Admin nav label leaked onto public payment page: {label}")

    def test_response_does_not_contain_admin_nav_urls(self):
        resp = self.client.get(self._pay_url(self.invoice))
        content = resp.content.decode("utf-8")
        for fragment in ADMIN_NAV_URL_FRAGMENTS:
            self.assertNotIn(fragment, content, f"Admin nav URL leaked onto public payment page: {fragment}")

    def test_response_contains_payment_content(self):
        resp = self.client.get(self._pay_url(self.invoice))
        self.assertContains(resp, self.invoice.invoice_number)
        self.assertContains(resp, "پرداخت اینترنتی فاکتور")

    def test_response_contains_company_branding(self):
        resp = self.client.get(self._pay_url(self.invoice))
        self.assertContains(resp, self.company.name)

    def test_non_payable_invoice_renders_safely(self):
        """A PAID (non-payable) invoice must still render 200 without admin nav leakage."""
        invoice = _paid_invoice(self.company, _order(self.company))
        resp = self.client.get(self._pay_url(invoice))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        for label in ADMIN_NAV_LABELS:
            self.assertNotIn(label, content, f"Admin nav label leaked onto non-payable public payment page: {label}")
