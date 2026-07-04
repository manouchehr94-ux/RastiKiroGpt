"""
EPIC-002 Wave 01, Issue 010: Standardize page toolbars across related admin
modules.

Root cause: most admin list pages already use a consistent toolbar pattern —
.page-header > .page-header-content (.page-header-title + optional
.page-header-subtitle) + .page-header-actions — established by e.g.
templates/tenants/admin_customers.html. Three templates diverged from it with
a bare, unwrapped <h1> (and, for admin_technicians.html, an action button
sitting directly in .page-header instead of inside .page-header-actions):
  - templates/tenants/admin_technicians.html
  - templates/tenants/admin_invoices.html
  - templates/sms/outbox_list.html

Fix: wrapped each page's existing title (and, for admin_technicians.html,
its existing "+ New" action button) in the same .page-header-content /
.page-header-actions markup already used by admin_customers.html and other
reference pages — no new CSS classes were introduced, no view/context
changes were made, and no page content besides the header markup changed.

Note: templates/sms/outbox_list.html is not currently wired to any URL
(apps/sms/urls.py routes both "" and "outbox/" to sms_outbox_admin_list,
which renders a different template, sms/outbox_admin_list.html) — this is a
pre-existing, unrelated condition, not something introduced or fixed here.
Its toolbar markup is verified at the template-source level instead of via
an HTTP request.
"""
import itertools

from django.template.loader import get_template
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"Toolbar Co {n}", code=f"tb{n:03d}", slug=f"toolbar-co-{n}", is_active=True)


def _admin(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"tba{n}", password="testpass", company=company, role=UserRole.COMPANY_ADMIN)


@override_settings(ROOT_URLCONF="config.urls")
class AdminTechniciansToolbarTest(TestCase):
    def test_page_header_uses_standard_structure(self):
        company = _company()
        admin = _admin(company)
        self.client.login(username=admin.username, password="testpass")
        resp = self.client.get(f"/{company.code}/admin/technicians/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn('<div class="page-header-content">', content)
        self.assertIn('<h1 class="page-header-title">نیروهای خدماتی</h1>', content)
        self.assertIn('<div class="page-header-actions">', content)
        self.assertIn("نیروی خدماتی جدید", content)


@override_settings(ROOT_URLCONF="config.urls")
class AdminInvoicesToolbarTest(TestCase):
    def test_page_header_uses_standard_structure(self):
        company = _company()
        admin = _admin(company)
        self.client.login(username=admin.username, password="testpass")
        resp = self.client.get(f"/{company.code}/admin/invoices/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn('<div class="page-header-content">', content)
        self.assertIn('<h1 class="page-header-title">مدیریت فاکتورها</h1>', content)


class SmsOutboxListTemplateSourceTest(TestCase):
    """sms/outbox_list.html has no live URL (see module docstring) — verified at template-source level."""

    def test_page_header_uses_standard_structure(self):
        with open("templates/sms/outbox_list.html", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('<div class="page-header-content">', content)
        self.assertIn('<h1 class="page-header-title">صندوق پیامک</h1>', content)

    def test_template_still_compiles(self):
        # Regression guard: the markup edit must not break template syntax.
        get_template("sms/outbox_list.html")
