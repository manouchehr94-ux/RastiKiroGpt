"""
P0-B: Approving a PENDING_REVIEW order must dispatch availability events to technicians.

Business rules verified:
- PENDING_REVIEW → NEW triggers dispatch_order_available_events.
- Other status changes (e.g. NEW → NEW, WAITING → NEW) do NOT trigger it.
- PENDING_REVIEW → WAITING (direct, without approval path) does NOT trigger it.
- Only the PENDING_REVIEW → NEW transition is the approval gate.
"""
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import CompanyUser, UserRole
from apps.orders.models import Order
from apps.orders.services import OrderUpdateService
from apps.tenants.models import Company, CompanyServiceCategory


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"p0b{_seq}"
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _admin(company):
    global _seq
    _seq += 1
    return CompanyUser.objects.create_user(
        username=f"adm_{company.code}_{_seq}",
        password="x",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _category(company):
    global _seq
    _seq += 1
    return CompanyServiceCategory.objects.create(
        company=company,
        title=f"Cat {_seq}",
        is_active=True,
    )


def _order(company, status, category=None):
    return Order.objects.create(
        company=company,
        title="Test",
        status=status,
        service_category=category,
    )


def _update(order, admin, new_status):
    """Helper to call OrderUpdateService.update() with a status change."""
    return OrderUpdateService.update(
        order=order,
        updated_by=admin,
        data={"status": new_status, "title": order.title},
    )


# =============================================================================
# TESTS
# =============================================================================

class PendingReviewApprovalDispatchTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.category = _category(self.company)

    # --- dispatch fires on approval ---

    def test_pending_review_to_new_dispatches_available_events(self):
        order = _order(self.company, Order.Status.PENDING_REVIEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.NEW)
        mock_dispatch.assert_called_once_with(order=order)

    def test_dispatch_receives_the_approved_order(self):
        order = _order(self.company, Order.Status.PENDING_REVIEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.NEW)
        called_order = mock_dispatch.call_args.kwargs["order"]
        self.assertEqual(called_order.pk, order.pk)

    def test_approved_order_status_is_new(self):
        order = _order(self.company, Order.Status.PENDING_REVIEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events"):
            _update(order, self.admin, Order.Status.NEW)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    # --- dispatch does NOT fire on other transitions ---

    def test_new_to_new_does_not_dispatch(self):
        order = _order(self.company, Order.Status.NEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.NEW)
        mock_dispatch.assert_not_called()

    def test_pending_review_to_waiting_does_not_dispatch_available_events(self):
        """If admin sets status directly to WAITING, no available events."""
        order = _order(self.company, Order.Status.PENDING_REVIEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.WAITING)
        mock_dispatch.assert_not_called()

    def test_new_to_waiting_does_not_dispatch(self):
        order = _order(self.company, Order.Status.NEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.WAITING)
        mock_dispatch.assert_not_called()

    def test_new_to_in_progress_does_not_dispatch(self):
        order = _order(self.company, Order.Status.NEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.IN_PROGRESS)
        mock_dispatch.assert_not_called()

    def test_pending_review_to_in_progress_does_not_dispatch(self):
        order = _order(self.company, Order.Status.PENDING_REVIEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.IN_PROGRESS)
        mock_dispatch.assert_not_called()

    def test_waiting_to_new_does_not_dispatch(self):
        """Reverting WAITING → NEW (e.g. manual correction) must not fire approval dispatch."""
        order = _order(self.company, Order.Status.WAITING, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.NEW)
        mock_dispatch.assert_not_called()

    def test_in_progress_to_new_does_not_dispatch(self):
        order = _order(self.company, Order.Status.IN_PROGRESS, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            _update(order, self.admin, Order.Status.NEW)
        mock_dispatch.assert_not_called()

    # --- field edits without status change do not dispatch ---

    def test_field_only_edit_on_pending_review_does_not_dispatch(self):
        order = _order(self.company, Order.Status.PENDING_REVIEW, category=self.category)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            OrderUpdateService.update(
                order=order,
                updated_by=self.admin,
                data={"title": "Updated Title"},
            )
        mock_dispatch.assert_not_called()
