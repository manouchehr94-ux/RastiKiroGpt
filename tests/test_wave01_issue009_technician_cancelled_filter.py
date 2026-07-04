"""
EPIC-002 Wave 01, Issue 009: Technician order list requires a "Cancelled" filter.

Root cause: the backend view (apps/orders/views.py::technician_my_orders) already
supported filtering by any Order.Status value including "cancelled", but the
quick-filter pill strip in templates/orders/technician_my_orders.html only
offered: all, waiting, in_progress, done, cancel_requested — no pill for
"cancelled" itself, even though CANCEL_REQUESTED and CANCELLED are distinct
statuses.

Fix: added one filter-pill link for status=cancelled, following the exact
existing pill markup pattern. No backend changes were required.
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
    return Company.objects.create(code=f"tc{n}", name=f"Tech Co {n}", slug=f"tc-co-{n}", is_active=True)


def _technician_user(company, username):
    user = CompanyUser.objects.create_user(
        username=username, password="testpass", company=company, role=UserRole.TECHNICIAN,
    )
    Technician.objects.create(company=company, user=user)
    return user


def _order(company, technician, status):
    n = _n()
    return Order.objects.create(
        company=company, title=f"Order {n}", status=status, technician=technician,
    )


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianCancelledFilterTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = _technician_user(self.company, "cf_tech")
        self.technician = self.user.technician_profile

    def _url(self, status=None):
        base = f"/{self.company.code}/tech/orders/my/"
        return f"{base}?status={status}" if status else base

    def test_cancelled_pill_present_in_filter_strip(self):
        self.client.login(username="cf_tech", password="testpass")
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "status=cancelled")
        self.assertContains(resp, "لغو شده")

    def test_cancelled_status_filter_returns_only_cancelled_orders(self):
        cancelled = _order(self.company, self.technician, Order.Status.CANCELLED)
        _order(self.company, self.technician, Order.Status.IN_PROGRESS)
        self.client.login(username="cf_tech", password="testpass")
        resp = self.client.get(self._url("cancelled"))
        self.assertEqual(resp.status_code, 200)
        entries = resp.context["orders_with_items"]
        self.assertEqual([e["order"].id for e in entries], [cancelled.id])

    def test_cancelled_pill_marked_active_when_selected(self):
        self.client.login(username="cf_tech", password="testpass")
        resp = self.client.get(self._url("cancelled"))
        content = resp.content.decode("utf-8")
        self.assertIn('status=cancelled" class="filter-pill active"', content)
