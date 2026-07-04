"""
EPIC-002 Wave 01, Issue 011: Admin Reports page redesigned using the current
Design System.

Root cause: templates/reports/list.html used raw Tailwind-utility-class
markup (bg-white, rounded-2xl, shadow-sm) instead of the project's own
component/token-based Design System (.card, .stat-card, .detail-list,
.table-wrapper/.data-table) already used throughout templates/tenants/ and
templates/tenants/financial_reports/summary.html. It also had a genuine bug:
the "customer segments" teaser card was misplaced INSIDE {% block title %}
(which base.html renders literally inside the <title> HTML tag), making it
non-functional/invisible rather than a real card on the page.

Fix (template-only, no view/selector changes):
  - Moved the customer-segments teaser into {% block content %} as a proper
    .card.
  - Replaced the 5 hand-rolled order-summary divs with .stat-card markup
    inside .stat-grid.stat-grid-4 — the exact CSS classes/structure used by
    components/stat_card.html and admin_customers.html, but written inline
    (see note below) rather than via {% include %}.
  - Replaced the revenue/invoice-status/service-request panels with
    .card/.card-header + .detail-list/.detail-row markup (reusing the exact
    pattern from templates/payments/invoice_checkout.html).
  - Replaced the raw technician-performance <table> with
    .table-wrapper > table.data-table, and added an .empty-state fallback
    (same CSS classes as components/empty_state.html) instead of silently
    hiding the section when there is no data.
  - Added {% load smart_numbers %} and applied |smart_number to money/count
    values that were previously rendered raw.
  - Added a proper .page-header/.page-header-content block, matching the
    convention already used by admin_customers.html and other reference
    pages (also touched in Issue 010 of this same wave).

Known limitation / discovered anomaly (documented, not "fixed" — see
WAVE_01_IMPLEMENTATION_REPORT.md): using {% include "components/stat_card.html" %}
or {% include "components/empty_state.html" %} inside this specific
view/template combination (report_list + reports/list.html, extending
layouts/dashboard.html with its full block-override set) reproducibly causes
a RecursionError during template rendering — confirmed via a real (non-test,
non-instrumented) render, not a test-client artifact, and confirmed absent
when the same two includes are used from templates/tenants/admin_customers.html
with a different view. The root cause was not fully isolated within this
wave's scope (suspected Django template context/BlockContext interaction,
not anything specific to this app's Python code). Per the "reuse Design
System" requirement, this file reuses the exact same CSS classes and visual
structure as components/stat_card.html and components/empty_state.html,
written as literal markup instead of through {% include %}, which is itself
an already-precedented pattern in this codebase (see
templates/tenants/financial_reports/summary.html, which hand-rolls its
.stat-card/.balance-insight markup inline rather than via include).

apps/reports/views.py::report_list and CompanyReportSelector were not
modified — this issue is template-only, per the "reuse existing components,
do not redesign" instruction.
"""
import itertools
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

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
    return Company.objects.create(name=f"Report Co {n}", code=f"rp{n:03d}", slug=f"report-co-{n}", is_active=True)


def _admin(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"ra{n}", password="testpass", company=company, role=UserRole.COMPANY_ADMIN)


def _technician(company):
    n = _n()
    user = CompanyUser.objects.create_user(username=f"rt{n}", password="testpass", company=company, role=UserRole.TECHNICIAN)
    return Technician.objects.create(company=company, user=user, is_available=True)


def _order(company, technician=None, status=Order.Status.DONE):
    n = _n()
    return Order.objects.create(company=company, title=f"Order {n}", status=status, technician=technician)


@override_settings(ROOT_URLCONF="config.urls")
class ReportsPageDesignSystemTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def _url(self):
        return f"/{self.company.code}/admin/reports/"

    def test_page_returns_200(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)

    def test_page_uses_stat_card_component(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        content = resp.content.decode("utf-8")
        self.assertIn('class="stat-card"', content)
        self.assertIn('class="stat-grid stat-grid-4"', content)

    def test_page_uses_card_and_detail_list_markup(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        content = resp.content.decode("utf-8")
        self.assertIn('class="detail-list"', content)
        self.assertIn('class="card-header"', content)

    def test_customer_segments_card_is_in_content_not_title_block(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        content = resp.content.decode("utf-8")
        title_tag_content = content.split("<title>", 1)[1].split("</title>", 1)[0]
        self.assertNotIn("گزارش هدفمند مشتریان", title_tag_content)
        self.assertIn("گزارش هدفمند مشتریان", content)
        self.assertIn("ورود به گزارش", content)

    def test_page_header_uses_standard_structure(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        content = resp.content.decode("utf-8")
        self.assertIn('<div class="page-header-content">', content)
        self.assertIn('<h1 class="page-header-title">گزارش‌ها</h1>', content)

    def test_empty_technician_performance_shows_empty_state(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        content = resp.content.decode("utf-8")
        self.assertIn("empty-state", content)

    def test_revenue_and_summary_numbers_still_render_correctly(self):
        technician = _technician(self.company)
        order = _order(self.company, technician)
        invoice = InvoiceCreateService.create(
            company=self.company, order=order,
            items=[{"description": "Service", "quantity": 1, "unit_price": 1_500_000, "discount_amount": 0}],
        )
        InvoiceIssueService.issue(invoice=invoice)
        Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.PAID)

        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        content = resp.content.decode("utf-8")
        # smart_number-formatted with thousands separator, not raw "1500000"
        self.assertIn("1,500,000", content)
