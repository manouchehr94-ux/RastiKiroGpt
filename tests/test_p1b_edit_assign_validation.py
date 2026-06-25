"""
P1-B: OrderEditAssignService.handle_assignment() must raise ValueError for
invalid/inactive/wrong-company technician instead of silently returning.

Business rules verified:
- Nonexistent technician_id raises ValueError.
- Inactive technician raises ValueError.
- Technician from another company raises ValueError.
- Order is not mutated when ValueError is raised.
- dispatch_order_assigned_events is NOT called when ValueError is raised.
- Valid technician is assigned and dispatch fires.
- PENDING_REVIEW + valid technician → WAITING.
- WAITING order can be reassigned from technician A to technician B.
- Same-technician re-submit is a silent no-op (no duplicate log/dispatch).
"""
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.orders.models import Order
from apps.orders.services import OrderEditAssignService
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"p1b{_seq}"
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


def _tech(company, is_available=True):
    global _seq
    _seq += 1
    user = CompanyUser.objects.create_user(
        username=f"tch_{company.code}_{_seq}",
        password="x",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user, is_available=is_available)


def _order(company, status=Order.Status.NEW, technician=None):
    return Order.objects.create(
        company=company,
        title="Test",
        status=status,
        technician=technician,
    )


# =============================================================================
# TESTS
# =============================================================================

class EditAssignValidationTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.tech = _tech(self.company)

    def _handle(self, order, technician_id):
        return OrderEditAssignService.handle_assignment(
            order=order,
            technician_id=technician_id,
            assigned_by=self.admin,
            company=self.company,
        )

    # --- ValueError on invalid technician_id ---

    def test_nonexistent_technician_raises(self):
        order = _order(self.company)
        with self.assertRaises(ValueError) as ctx:
            self._handle(order, technician_id=99999)
        self.assertIn("معتبر", str(ctx.exception))

    def test_inactive_technician_raises(self):
        inactive = _tech(self.company, is_available=False)
        order = _order(self.company)
        with self.assertRaises(ValueError):
            self._handle(order, technician_id=inactive.id)

    def test_wrong_company_technician_raises(self):
        other_company = _company()
        other_tech = _tech(other_company)
        order = _order(self.company)
        with self.assertRaises(ValueError):
            self._handle(order, technician_id=other_tech.id)

    # --- Order not mutated when ValueError is raised ---

    def test_order_not_mutated_on_invalid_technician(self):
        order = _order(self.company, status=Order.Status.NEW)
        with self.assertRaises(ValueError):
            self._handle(order, technician_id=99999)
        order.refresh_from_db()
        self.assertIsNone(order.technician_id)
        self.assertEqual(order.status, Order.Status.NEW)

    # --- No dispatch when ValueError is raised ---

    def test_no_dispatch_on_invalid_technician(self):
        order = _order(self.company)
        with patch("apps.orders.assignment_events.dispatch_order_assigned_events") as mock_d:
            with self.assertRaises(ValueError):
                self._handle(order, technician_id=99999)
        mock_d.assert_not_called()

    # --- Valid assignment still works ---

    def test_valid_technician_is_assigned(self):
        order = _order(self.company)
        self._handle(order, technician_id=self.tech.id)
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech.id)

    def test_valid_assignment_dispatch_fires(self):
        order = _order(self.company)
        with patch("apps.orders.assignment_events.dispatch_order_assigned_events") as mock_d:
            self._handle(order, technician_id=self.tech.id)
        mock_d.assert_called_once()

    # --- PENDING_REVIEW + valid technician → WAITING ---

    def test_pending_review_becomes_waiting_on_assignment(self):
        order = _order(self.company, status=Order.Status.PENDING_REVIEW)
        self._handle(order, technician_id=self.tech.id)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.WAITING)

    # --- WAITING order: reassign from technician A to technician B ---

    def test_waiting_order_reassignment_to_new_tech_succeeds(self):
        tech_a = _tech(self.company)
        tech_b = _tech(self.company)
        order = _order(self.company, status=Order.Status.WAITING, technician=tech_a)
        self._handle(order, technician_id=tech_b.id)
        order.refresh_from_db()
        self.assertEqual(order.technician_id, tech_b.id)
        self.assertEqual(order.status, Order.Status.WAITING)

    # --- Same-technician re-submit is a no-op ---

    def test_same_technician_is_noop_no_dispatch(self):
        order = _order(self.company, status=Order.Status.WAITING, technician=self.tech)
        with patch("apps.orders.assignment_events.dispatch_order_assigned_events") as mock_d:
            self._handle(order, technician_id=self.tech.id)
        mock_d.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech.id)
