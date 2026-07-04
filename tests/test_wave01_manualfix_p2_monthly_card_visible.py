"""
EPIC-002 Wave 01 — Manual Test Fix, Problem 2: the "تکمیل‌شده این ماه"
(completed-this-month) stat card was reported as "not visible" on
/rasti-test/tech/ during manual testing.

Investigation: apps/dashboard/selectors.py (TechnicianDashboardSelector.
get_stats) and apps/dashboard/views.py (technician_home) were confirmed
correct — completed_orders_this_month is computed and passed to the
template. Directly rendering templates/dashboard/technician_home.html
against the real "rasti-test" company/technician (both via an isolated test
client and a live-DB render) confirmed the label "تکمیل‌شده این ماه" and its
value ARE present in the server-rendered HTML in both cases
(assertContains-equivalent checks passed). No server-side rendering defect
was reproduced.

Root cause (most likely, addressed defensively): the 5th stat card was added
as a half-width cell inside a `grid-cols-2` grid that previously had exactly
4 (evenly-divisible) cards. With 5 cards, the last one lands alone in a
3rd row occupying only the first column, leaving a conspicuous empty gap
next to it — easy to overlook or mistake for a layout glitch on a quick
manual pass, especially on narrow/mobile viewports where the technician
panel is meant to be used (Issue 013 of this same wave).

Fix: made the 5th card span the full grid width (new `.col-span-2` utility
in static/css/dashboard.css, added next to the existing `.grid-cols-*`
utilities it's a sibling of) so it renders as its own clearly visible full-
width row instead of a half-width orphan cell. This is separate from, and in
addition to, the pre-existing test in
tests/test_wave01_issue015_technician_monthly_stats.py which already
verifies the label text is present in the response body.
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"Visible Co {n}", code=f"vc{n:03d}", slug=f"visible-co-{n}", is_active=True)


def _tech_user(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"vt{n}", password="testpass", company=company, role=UserRole.TECHNICIAN)


def _technician(company, user):
    return Technician.objects.create(company=company, user=user, is_available=True)


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianMonthlyCardFullWidthVisibleTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = _tech_user(self.company)
        self.tech = _technician(self.company, self.user)

    def test_monthly_card_renders_as_full_width_row(self):
        Order.objects.create(company=self.company, title="Order 1", status=Order.Status.DONE, technician=self.tech)
        self.client.login(username=self.user.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/tech/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("تکمیل‌شده این ماه", content)
        # The card must be marked as spanning both grid columns so it is not
        # an easy-to-miss half-width orphan cell.
        self.assertIn('col-span-2', content)

    def test_col_span_2_utility_defined_in_dashboard_css(self):
        with open("static/css/dashboard.css", encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".col-span-2", css)
