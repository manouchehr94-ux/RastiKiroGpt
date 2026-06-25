"""
P1-A: OrderAssignService.assign() must be concurrency-safe.

Business rules verified:
- Valid assignment (NEW → WAITING) succeeds.
- PENDING_REVIEW → WAITING succeeds.
- technician FK is set after assignment.
- accepted_at is set after assignment.
- IN_PROGRESS (and other non-assignable) statuses are blocked with ValueError.
- Technician from a different company is blocked with ValueError.
- Same-technician re-submit is a silent no-op (idempotent, no duplicate dispatch).
- dispatch_order_assigned_events fires exactly once on successful assignment.
- Order is not mutated when ValueError is raised.
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.orders.models import Order
from apps.orders.services import OrderAssignService
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"p1a{_seq}"
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

class AssignServiceRaceGuardTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.tech = _tech(self.company)

    def _assign(self, order, technician=None):
        return OrderAssignService.assign(
            order=order,
            technician=technician or self.tech,
            assigned_by=self.admin,
        )

    # --- Happy-path transitions ---

    def test_new_to_waiting(self):
        order = _order(self.company, Order.Status.NEW)
        self._assign(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.WAITING)

    def test_pending_review_to_waiting(self):
        order = _order(self.company, Order.Status.PENDING_REVIEW)
        self._assign(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.WAITING)

    def test_technician_is_assigned(self):
        order = _order(self.company)
        self._assign(order)
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech.id)

    def test_accepted_at_is_set(self):
        before = timezone.now()
        order = _order(self.company)
        self._assign(order)
        order.refresh_from_db()
        self.assertIsNotNone(order.accepted_at)
        self.assertGreaterEqual(order.accepted_at, before)

    # --- dispatch fires exactly once on success ---

    def test_dispatch_fires_once_on_success(self):
        order = _order(self.company)
        with patch("apps.orders.assignment_events.dispatch_order_assigned_events") as mock_d:
            self._assign(order)
        mock_d.assert_called_once()

    # --- Blocked statuses ---

    def test_in_progress_is_blocked(self):
        order = _order(self.company, Order.Status.IN_PROGRESS)
        with self.assertRaises(ValueError) as ctx:
            self._assign(order)
        self.assertIn("NEW", str(ctx.exception))

    def test_waiting_is_blocked(self):
        other_tech = _tech(self.company)
        order = _order(self.company, Order.Status.WAITING, technician=other_tech)
        with self.assertRaises(ValueError):
            self._assign(order)

    def test_done_is_blocked(self):
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError):
            self._assign(order)

    # --- No mutation on blocked assignment ---

    def test_no_mutation_on_blocked_status(self):
        order = _order(self.company, Order.Status.IN_PROGRESS)
        with self.assertRaises(ValueError):
            self._assign(order)
        order.refresh_from_db()
        self.assertIsNone(order.technician_id)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

    # --- Company isolation ---

    def test_wrong_company_technician_raises(self):
        other_company = _company()
        other_tech = _tech(other_company)
        order = _order(self.company)
        with self.assertRaises(ValueError) as ctx:
            self._assign(order, technician=other_tech)
        self.assertIn("company", str(ctx.exception).lower())

    # --- Idempotency ---

    def test_same_technician_is_noop_no_dispatch(self):
        # Simulate: order is still NEW but already has the technician set
        # (e.g. concurrent request committed the technician FK but not the status yet).
        order = _order(self.company, Order.Status.NEW, technician=self.tech)
        with patch("apps.orders.assignment_events.dispatch_order_assigned_events") as mock_d:
            self._assign(order, technician=self.tech)
        mock_d.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    # --- Inactive technician ---

    def test_inactive_technician_raises(self):
        inactive = _tech(self.company, is_available=False)
        order = _order(self.company)
        with self.assertRaises(ValueError) as ctx:
            self._assign(order, technician=inactive)
        self.assertIn("available", str(ctx.exception).lower())
