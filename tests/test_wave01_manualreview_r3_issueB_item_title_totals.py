"""
EPIC-002 Product Polish — Manual Review Round 3, Issue B: technician
dashboard must show item-title totals, not just a single service-item count.

What was misunderstood in the earlier fix: Round 2's Task 1 added
`completed_service_items_this_month`, counting InvoiceItem rows of
row_type=SERVICE. Manual review clarified this was the wrong data source —
the requirement is about the ORDER item system (OrderItemDefinition /
OrderItemValue, filled in by the technician per order, e.g. "شست و شوی
بیمار" / "شست و شوی سرویس" under category "شستشو و خدمات ویژه"), grouped by
item title, NOT invoice line items (which are billing rows created later
and can have arbitrary free-text descriptions unrelated to the order item
system).

Root cause: TechnicianDashboardSelector.get_stats had no concept of
OrderItemDefinition/OrderItemValue at all.

Fix: added `completed_item_totals_this_month` to get_stats — a single
aggregate GROUP BY query:
    OrderItemValue.objects.filter(
        order__in=<this technician's completed-this-month orders>,
        item__kind=OrderItemDefinition.Kind.NUMBER,
        item__is_active=True,
        value_number__isnull=False,
    ).values(title=F("item__title")).annotate(total=Sum("value_number"))
Only NUMBER-kind item values are summed as "quantities" (MONEY-kind values
are pricing data — out of scope, no financial logic touched; TEXT/BOOL have
no meaningful sum). No per-order loop — a single query regardless of how
many completed orders/items exist (no N+1). The existing
`completed_service_items_this_month` card (InvoiceItem-based) was left in
place — this is an additive, more specific breakdown "under the monthly
stats" per the requirement, not a replacement.

templates/dashboard/technician_home.html displays the grouped totals as a
new card directly below the existing stat-card grid, reusing the exact same
card/list markup already used for "سفارش‌های اخیر من" (Recent Orders) —
no dashboard redesign.
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.dashboard.selectors import TechnicianDashboardSelector
from apps.orders.item_services import OrderItemService
from apps.orders.models import Order, OrderItemDefinition, OrderItemValue
from apps.tenants.models import Company, CompanyServiceCategory

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"ItemTotal Co {n}", code=f"it{n:03d}", slug=f"itemtotal-co-{n}", is_active=True)


def _tech_user(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"itt{n}", password="testpass", company=company, role=UserRole.TECHNICIAN)


def _technician(company, user):
    return Technician.objects.create(company=company, user=user, is_available=True)


def _category(company):
    n = _n()
    return CompanyServiceCategory.objects.create(company=company, title=f"شستشو و خدمات ویژه {n}", is_active=True)


def _item_definition(company, category, title, kind=OrderItemDefinition.Kind.NUMBER, is_active=True, sort_order=0):
    return OrderItemDefinition.objects.create(
        company=company, category=category, title=title, kind=kind, is_active=is_active, sort_order=sort_order,
    )


def _completed_order(company, technician, category, created_at=None):
    n = _n()
    order = Order.objects.create(
        company=company, title=f"Order {n}", status=Order.Status.DONE,
        technician=technician, service_category=category,
    )
    if created_at is not None:
        Order.objects.filter(pk=order.pk).update(created_at=created_at)
        order.refresh_from_db()
    return order


def _set_item_value(order, definition, number_value):
    OrderItemValue.objects.create(order=order, item=definition, value_number=number_value)


@override_settings(ROOT_URLCONF="config.urls")
class CompletedItemTitleTotalsThisMonthTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = _tech_user(self.company)
        self.tech = _technician(self.company, self.user)
        self.category = _category(self.company)
        self.item_a = _item_definition(self.company, self.category, "شست و شوی بیمار", sort_order=1)
        self.item_b = _item_definition(self.company, self.category, "شست و شوی سرویس", sort_order=2)

    def test_empty_when_no_orders(self):
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_item_totals_this_month"], [])

    def test_completed_orders_in_current_month_are_counted_and_grouped_by_title(self):
        order1 = _completed_order(self.company, self.tech, self.category)
        _set_item_value(order1, self.item_a, 3)
        _set_item_value(order1, self.item_b, 1)

        order2 = _completed_order(self.company, self.tech, self.category)
        _set_item_value(order2, self.item_a, 2)

        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        totals = {row["title"]: row["total"] for row in stats["completed_item_totals_this_month"]}
        self.assertEqual(totals["شست و شوی بیمار"], 5)
        self.assertEqual(totals["شست و شوی سرویس"], 1)

    def test_previous_jalali_month_orders_excluded(self):
        from datetime import datetime
        from django.utils import timezone as tz
        from apps.common.jalali import gregorian_to_jalali, jalali_to_gregorian

        today = tz.now().date()
        jy, jm, _jd = gregorian_to_jalali(today.year, today.month, today.day)
        prev_jy, prev_jm = (jy - 1, 12) if jm == 1 else (jy, jm - 1)
        py, pm, pd = jalali_to_gregorian(prev_jy, prev_jm, 15)
        old_dt = tz.make_aware(datetime(py, pm, pd, 12, 0, 0))

        old_order = _completed_order(self.company, self.tech, self.category, created_at=old_dt)
        _set_item_value(old_order, self.item_a, 10)

        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_item_totals_this_month"], [])

    def test_other_technicians_orders_excluded(self):
        other_user = _tech_user(self.company)
        other_tech = _technician(self.company, other_user)
        order = _completed_order(self.company, other_tech, self.category)
        _set_item_value(order, self.item_a, 7)

        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_item_totals_this_month"], [])

    def test_non_completed_orders_excluded(self):
        order = Order.objects.create(
            company=self.company, title="In progress", status=Order.Status.IN_PROGRESS,
            technician=self.tech, service_category=self.category,
        )
        _set_item_value(order, self.item_a, 4)
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_item_totals_this_month"], [])

    def test_money_kind_items_excluded_from_totals(self):
        """MONEY-kind item values are pricing data, not quantities — must not appear."""
        money_item = _item_definition(self.company, self.category, "هزینه لوله‌کشی", kind=OrderItemDefinition.Kind.MONEY)
        order = _completed_order(self.company, self.tech, self.category)
        _set_item_value(order, money_item, 150000)
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        titles = [row["title"] for row in stats["completed_item_totals_this_month"]]
        self.assertNotIn("هزینه لوله‌کشی", titles)

    def test_inactive_item_definition_excluded(self):
        inactive_item = _item_definition(self.company, self.category, "آیتم غیرفعال", is_active=False)
        order = _completed_order(self.company, self.tech, self.category)
        _set_item_value(order, inactive_item, 3)
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        titles = [row["title"] for row in stats["completed_item_totals_this_month"]]
        self.assertNotIn("آیتم غیرفعال", titles)

    def test_uses_order_item_service_save_path_correctly(self):
        """
        End-to-end via the real save path (OrderItemService.save_items_from_post)
        instead of creating OrderItemValue rows directly, to prove the
        aggregation works against real technician-submitted data.
        """
        order = _completed_order(self.company, self.tech, self.category)
        OrderItemService.save_items_from_post(
            order=order,
            post_data={f"item_{self.item_a.id}": "3", f"item_{self.item_b.id}": "2"},
            company=self.company,
        )
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        totals = {row["title"]: row["total"] for row in stats["completed_item_totals_this_month"]}
        self.assertEqual(totals["شست و شوی بیمار"], 3)
        self.assertEqual(totals["شست و شوی سرویس"], 2)

    def test_dashboard_page_renders_item_titles_and_totals(self):
        order = _completed_order(self.company, self.tech, self.category)
        _set_item_value(order, self.item_a, 3)
        _set_item_value(order, self.item_b, 2)

        self.client.login(username=self.user.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/tech/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("شست و شوی بیمار", content)
        self.assertIn("شست و شوی سرویس", content)

    def test_query_count_does_not_grow_with_order_count(self):
        """No N+1: get_stats() query count must not scale with order/item volume."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        order = _completed_order(self.company, self.tech, self.category)
        _set_item_value(order, self.item_a, 1)

        # Warm up any one-time lazy state.
        TechnicianDashboardSelector.get_stats(technician=self.tech)

        with CaptureQueriesContext(connection) as captured_one:
            TechnicianDashboardSelector.get_stats(technician=self.tech)

        for _ in range(4):
            o = _completed_order(self.company, self.tech, self.category)
            _set_item_value(o, self.item_a, 1)
            _set_item_value(o, self.item_b, 1)

        with CaptureQueriesContext(connection) as captured_many:
            TechnicianDashboardSelector.get_stats(technician=self.tech)

        self.assertEqual(len(captured_one), len(captured_many))
