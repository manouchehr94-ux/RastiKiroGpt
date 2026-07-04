"""
EPIC-002 Product Polish — Manual Review Fix, Task 1: Technician Dashboard
Monthly Statistics was only partially implemented.

Manual review: the "تکمیل‌شده این ماه" card showed completed ORDER count for
the current month, but the requirement also needs completed SERVICE ITEM
count (line items, not just orders) for the current Jalali month — a
technician who does 2 completed orders with 5 service line items total
should see "5", not "2".

Root cause: TechnicianDashboardSelector.get_stats (apps/dashboard/selectors.py)
only ever counted Order rows; it had no concept of invoice line items at
all, so there was no way to distinguish "orders completed" from "services
performed" (an order can have multiple InvoiceItem rows of row_type=SERVICE).

Fix: added `completed_service_items_this_month` to get_stats — a single
aggregate InvoiceItem.objects.filter(...).count() query (no per-order loop,
no N+1) scoped to:
  - company = technician.company
  - row_type = InvoiceItem.RowType.SERVICE (service items only, not goods/travel)
  - invoice__order__in = <this technician's completed-this-month orders queryset>
  - excluding invoice__status = CANCELLED (a cancelled invoice's line items
    should not count as "completed service")
Reuses the exact same Jalali month-boundary computation already used for
completed_orders_this_month (Issue 015) — no new date-conversion logic.

Added a companion stat card to templates/dashboard/technician_home.html,
reusing the exact same full-width card markup/CSS classes already used for
the "تکمیل‌شده این ماه" card (col-span-2 utility) — no dashboard redesign.
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.dashboard.selectors import TechnicianDashboardSelector
from apps.invoices.models import Invoice, InvoiceItem
from apps.invoices.services import InvoiceCreateService
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"SvcItem Co {n}", code=f"si{n:03d}", slug=f"svcitem-co-{n}", is_active=True)


def _tech_user(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"sit{n}", password="testpass", company=company, role=UserRole.TECHNICIAN)


def _technician(company, user):
    return Technician.objects.create(company=company, user=user, is_available=True)


def _completed_order_with_invoice(company, technician, items, invoice_status=Invoice.Status.ISSUED):
    n = _n()
    order = Order.objects.create(company=company, title=f"Order {n}", status=Order.Status.DONE, technician=technician)
    invoice = InvoiceCreateService.create(company=company, order=order, items=items)
    Invoice.objects.filter(pk=invoice.pk).update(status=invoice_status)
    return order, invoice


@override_settings(ROOT_URLCONF="config.urls")
class CompletedServiceItemsThisMonthTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = _tech_user(self.company)
        self.tech = _technician(self.company, self.user)

    def test_zero_when_no_orders(self):
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_service_items_this_month"], 0)

    def test_counts_service_line_items_not_orders(self):
        """2 orders, one with 3 service rows and one with 2, must total 5 (not 2)."""
        _completed_order_with_invoice(self.company, self.tech, items=[
            {"description": "Service A", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
            {"description": "Service B", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
            {"description": "Service C", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
        ])
        _completed_order_with_invoice(self.company, self.tech, items=[
            {"description": "Service D", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
            {"description": "Service E", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
        ])
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_orders_this_month"], 2)
        self.assertEqual(stats["completed_service_items_this_month"], 5)

    def test_goods_and_travel_rows_excluded(self):
        """Only row_type=service counts; goods/travel line items must not."""
        _completed_order_with_invoice(self.company, self.tech, items=[
            {"description": "Service A", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
            {"description": "Part X", "quantity": 1, "unit_price": 50000, "discount_amount": 0, "row_type": "goods"},
            {"description": "Travel", "quantity": 1, "unit_price": 20000, "discount_amount": 0, "row_type": "travel"},
        ])
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_service_items_this_month"], 1)

    def test_cancelled_invoice_service_items_excluded(self):
        """Service items on a CANCELLED invoice must not count as completed."""
        _completed_order_with_invoice(
            self.company, self.tech,
            items=[{"description": "Service A", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"}],
            invoice_status=Invoice.Status.CANCELLED,
        )
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_orders_this_month"], 1)
        self.assertEqual(stats["completed_service_items_this_month"], 0)

    def test_non_completed_order_service_items_excluded(self):
        """Service items belonging to an order that isn't DONE must not count."""
        order = Order.objects.create(company=self.company, title="In progress", status=Order.Status.IN_PROGRESS, technician=self.tech)
        invoice = InvoiceCreateService.create(
            company=self.company, order=order,
            items=[{"description": "Service A", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"}],
        )
        Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.ISSUED)
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_service_items_this_month"], 0)

    def test_other_technicians_service_items_excluded(self):
        """Another technician's completed service items must not leak into this one's count."""
        other_user = _tech_user(self.company)
        other_tech = _technician(self.company, other_user)
        _completed_order_with_invoice(self.company, other_tech, items=[
            {"description": "Service A", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
        ])
        stats = TechnicianDashboardSelector.get_stats(technician=self.tech)
        self.assertEqual(stats["completed_service_items_this_month"], 0)

    def test_dashboard_page_renders_service_items_card(self):
        _completed_order_with_invoice(self.company, self.tech, items=[
            {"description": "Service A", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
        ])
        self.client.login(username=self.user.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/tech/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("خدمات انجام‌شده این ماه", content)
        self.assertEqual(resp.context["stats"]["completed_service_items_this_month"], 1)

    def test_get_stats_query_count_does_not_grow_with_order_count(self):
        """
        get_stats() must issue the same number of queries whether the
        technician has 1 or 5 completed orders/items this month — the
        service-item count is a single aggregate query, not a per-order
        loop (no N+1).
        """
        _completed_order_with_invoice(self.company, self.tech, items=[
            {"description": "Service A", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
        ])

        # Warm up any one-time lazy state (e.g. auto-created CompanySettings
        # row) so it doesn't skew the query-count comparison below.
        TechnicianDashboardSelector.get_stats(technician=self.tech)

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as captured_one:
            TechnicianDashboardSelector.get_stats(technician=self.tech)
        count_with_one_order = len(captured_one)

        for _ in range(4):
            _completed_order_with_invoice(self.company, self.tech, items=[
                {"description": "Service A", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
                {"description": "Service B", "quantity": 1, "unit_price": 100000, "discount_amount": 0, "row_type": "service"},
            ])

        with CaptureQueriesContext(connection) as captured_many:
            TechnicianDashboardSelector.get_stats(technician=self.tech)
        count_with_many_orders = len(captured_many)

        self.assertEqual(
            count_with_one_order, count_with_many_orders,
            "Query count must not scale with the number of completed orders/items",
        )
