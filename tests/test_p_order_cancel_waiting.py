"""
Fix-1: Customer must be able to request cancellation while order is WAITING.

Business rule: NEW, WAITING, IN_PROGRESS → CANCEL_REQUESTED.
Previously WAITING was missing from allowed_statuses in OrderCancelService.request_cancel().
"""
from django.test import TestCase

from apps.accounts.models import CompanyUser, UserRole
from apps.orders.models import Order, OrderStatusLog
from apps.orders.services import OrderCancelService
from apps.tenants.models import Company, CompanyServiceCategory


def _company(code):
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _admin(company, username):
    return CompanyUser.objects.create_user(
        username=username, password="x", company=company, role=UserRole.COMPANY_ADMIN
    )


def _category(company):
    return CompanyServiceCategory.objects.create(
        company=company, title="General", is_active=True
    )


def _order(company, category, status):
    return Order.objects.create(
        company=company, title="Test", status=status, service_category=category
    )


class CancelFromWaitingTest(TestCase):

    def setUp(self):
        self.company = _company("cwait")
        self.admin = _admin(self.company, "cwait_admin")
        self.category = _category(self.company)

    # --- Fix 1: WAITING is now allowed ---

    def test_cancel_request_from_waiting_succeeds(self):
        order = _order(self.company, self.category, Order.Status.WAITING)
        result = OrderCancelService.request_cancel(order=order, requested_by=self.admin)
        result.refresh_from_db()
        self.assertEqual(result.status, Order.Status.CANCEL_REQUESTED)

    def test_cancel_request_from_waiting_creates_log(self):
        order = _order(self.company, self.category, Order.Status.WAITING)
        OrderCancelService.request_cancel(order=order, requested_by=self.admin, reason="Test")
        log = OrderStatusLog.objects.filter(order=order).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_status, Order.Status.WAITING)
        self.assertEqual(log.new_status, Order.Status.CANCEL_REQUESTED)

    # --- Existing behaviour preserved ---

    def test_cancel_request_from_new_succeeds(self):
        order = _order(self.company, self.category, Order.Status.NEW)
        result = OrderCancelService.request_cancel(order=order, requested_by=self.admin)
        result.refresh_from_db()
        self.assertEqual(result.status, Order.Status.CANCEL_REQUESTED)

    def test_cancel_request_from_in_progress_succeeds(self):
        order = _order(self.company, self.category, Order.Status.IN_PROGRESS)
        result = OrderCancelService.request_cancel(order=order, requested_by=self.admin)
        result.refresh_from_db()
        self.assertEqual(result.status, Order.Status.CANCEL_REQUESTED)

    # --- Terminal and review statuses still rejected ---

    def test_cancel_request_from_done_raises(self):
        order = _order(self.company, self.category, Order.Status.DONE)
        with self.assertRaises(ValueError):
            OrderCancelService.request_cancel(order=order, requested_by=self.admin)

    def test_cancel_request_from_cancelled_raises(self):
        order = _order(self.company, self.category, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            OrderCancelService.request_cancel(order=order, requested_by=self.admin)

    def test_cancel_request_from_cancel_requested_raises(self):
        order = _order(self.company, self.category, Order.Status.CANCEL_REQUESTED)
        with self.assertRaises(ValueError):
            OrderCancelService.request_cancel(order=order, requested_by=self.admin)

    def test_cancel_request_from_pending_review_raises(self):
        order = _order(self.company, self.category, Order.Status.PENDING_REVIEW)
        with self.assertRaises(ValueError):
            OrderCancelService.request_cancel(order=order, requested_by=self.admin)
