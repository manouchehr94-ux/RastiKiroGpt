"""
EPIC-002 Wave 01, Issue 015: Technician dashboard must display current month
completed orders and statistics.

Root cause: TechnicianDashboardSelector.get_stats (apps/dashboard/selectors.py)
only returned an all-time `completed_orders` count, with no date-scoped
"this month" figure at all, and templates/dashboard/technician_home.html only
rendered the all-time value.

Fix: added `completed_orders_this_month` to the selector, computed using the
current *Jalali* month's boundaries (reusing the existing
gregorian_to_jalali/jalali_to_gregorian conversion helpers from
apps/common/jalali.py — no new date-conversion logic was written), and added
one more stat card to the technician dashboard template reusing the exact
same card markup already used by its four siblings on the same page.
"""
import itertools
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.common.jalali import gregorian_to_jalali, jalali_to_gregorian
from apps.dashboard.selectors import TechnicianDashboardSelector
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"Stat Co {n}", code=f"sc{n:03d}", slug=f"stat-co-{n}", is_active=True)


def _user(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"su{n}", password="testpass", company=company, role=UserRole.TECHNICIAN)


def _technician(company, user):
    return Technician.objects.create(company=company, user=user, is_available=True)


def _order(company, technician, status, created_at=None):
    n = _n()
    order = Order.objects.create(company=company, title=f"Order {n}", status=status, technician=technician)
    if created_at is not None:
        Order.objects.filter(pk=order.pk).update(created_at=created_at)
        order.refresh_from_db()
    return order


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianDashboardMonthlyStatsTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = _user(self.company)
        self.technician = _technician(self.company, self.user)

    def test_stats_includes_completed_orders_this_month_key(self):
        stats = TechnicianDashboardSelector.get_stats(technician=self.technician)
        self.assertIn("completed_orders_this_month", stats)
        self.assertEqual(stats["completed_orders_this_month"], 0)

    def test_completed_order_today_counts_toward_this_month(self):
        _order(self.company, self.technician, Order.Status.DONE)
        stats = TechnicianDashboardSelector.get_stats(technician=self.technician)
        self.assertEqual(stats["completed_orders_this_month"], 1)
        self.assertEqual(stats["completed_orders"], 1)

    def test_completed_order_from_previous_jalali_month_excluded(self):
        today = timezone.now().date()
        jy, jm, _jd = gregorian_to_jalali(today.year, today.month, today.day)
        prev_jy, prev_jm = (jy - 1, 12) if jm == 1 else (jy, jm - 1)
        py, pm, pd = jalali_to_gregorian(prev_jy, prev_jm, 15)
        old_dt = timezone.make_aware(datetime(py, pm, pd, 12, 0, 0))

        _order(self.company, self.technician, Order.Status.DONE, created_at=old_dt)
        stats = TechnicianDashboardSelector.get_stats(technician=self.technician)

        # All-time count still includes it; this-month count must not.
        self.assertEqual(stats["completed_orders"], 1)
        self.assertEqual(stats["completed_orders_this_month"], 0)

    def test_non_completed_order_this_month_not_counted(self):
        _order(self.company, self.technician, Order.Status.IN_PROGRESS)
        stats = TechnicianDashboardSelector.get_stats(technician=self.technician)
        self.assertEqual(stats["completed_orders_this_month"], 0)

    def test_technician_home_page_renders_monthly_stat_card(self):
        _order(self.company, self.technician, Order.Status.DONE)
        self.client.login(username=self.user.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/tech/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "تکمیل‌شده این ماه")
        self.assertEqual(resp.context["stats"]["completed_orders_this_month"], 1)
