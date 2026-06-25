"""
P0 Order Protection Tests.

P0-1: Terminal status protection
    DONE and CANCELLED orders must not be editable via OrderUpdateService.update().

P0-2: IN_PROGRESS technician reassignment protection
    OrderEditAssignService must not change the technician of an IN_PROGRESS order.
"""
from django.test import TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.orders.models import Order
from apps.orders.services import OrderEditAssignService, OrderUpdateService
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company(suffix):
    global _seq
    _seq += 1
    code = f"p0{suffix}{_seq}"
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _admin(company, suffix="adm"):
    global _seq
    _seq += 1
    return CompanyUser.objects.create_user(
        username=f"{suffix}_{company.code}_{_seq}",
        password="x",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _tech(company, suffix="tch"):
    global _seq
    _seq += 1
    user = CompanyUser.objects.create_user(
        username=f"{suffix}_{company.code}_{_seq}",
        password="x",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user)


def _order(company, status, technician=None):
    return Order.objects.create(
        company=company,
        title="Test Order",
        status=status,
        technician=technician,
    )


# =============================================================================
# P0-1: TERMINAL STATUS PROTECTION
# =============================================================================

class TerminalOrderUpdateBlockedTest(TestCase):
    """OrderUpdateService.update() must raise ValueError for DONE and CANCELLED orders."""

    def setUp(self):
        self.company = _company("upd")
        self.admin = _admin(self.company)

    def _update(self, order, new_status):
        OrderUpdateService.update(
            order=order,
            updated_by=self.admin,
            data={"status": new_status, "title": "Changed Title"},
        )

    # --- DONE orders ---

    def test_done_order_blocks_status_change_to_new(self):
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError) as ctx:
            self._update(order, Order.Status.NEW)
        self.assertIn("تکمیل‌شده", str(ctx.exception))

    def test_done_order_blocks_status_change_to_cancelled(self):
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError):
            self._update(order, Order.Status.CANCELLED)

    def test_done_order_blocks_status_change_to_waiting(self):
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError):
            self._update(order, Order.Status.WAITING)

    def test_done_order_blocks_field_only_edit(self):
        """Even if status is not being changed, update is blocked for DONE orders."""
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError):
            OrderUpdateService.update(
                order=order,
                updated_by=self.admin,
                data={"title": "New Title"},
            )

    def test_done_order_not_mutated_after_block(self):
        """Order remains unchanged in DB after the ValueError."""
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError):
            self._update(order, Order.Status.NEW)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DONE)

    # --- CANCELLED orders ---

    def test_cancelled_order_blocks_status_change_to_new(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError) as ctx:
            self._update(order, Order.Status.NEW)
        self.assertIn("لغوشده", str(ctx.exception))

    def test_cancelled_order_blocks_status_change_to_in_progress(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            self._update(order, Order.Status.IN_PROGRESS)

    def test_cancelled_order_blocks_field_only_edit(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            OrderUpdateService.update(
                order=order,
                updated_by=self.admin,
                data={"description": "updated description"},
            )

    def test_cancelled_order_not_mutated_after_block(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            self._update(order, Order.Status.IN_PROGRESS)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    # --- Non-terminal orders must still work ---

    def test_new_order_can_be_updated(self):
        order = _order(self.company, Order.Status.NEW)
        OrderUpdateService.update(
            order=order,
            updated_by=self.admin,
            data={"title": "Updated"},
        )
        order.refresh_from_db()
        self.assertEqual(order.title, "Updated")

    def test_waiting_order_can_be_updated(self):
        order = _order(self.company, Order.Status.WAITING)
        OrderUpdateService.update(
            order=order,
            updated_by=self.admin,
            data={"description": "updated"},
        )
        order.refresh_from_db()
        self.assertEqual(order.description, "updated")

    def test_in_progress_order_can_be_updated(self):
        order = _order(self.company, Order.Status.IN_PROGRESS)
        OrderUpdateService.update(
            order=order,
            updated_by=self.admin,
            data={"address": "new address"},
        )
        order.refresh_from_db()
        self.assertEqual(order.address, "new address")

    def test_cancel_requested_order_can_be_updated(self):
        order = _order(self.company, Order.Status.CANCEL_REQUESTED)
        OrderUpdateService.update(
            order=order,
            updated_by=self.admin,
            data={"title": "still editable"},
        )
        order.refresh_from_db()
        self.assertEqual(order.title, "still editable")


# =============================================================================
# P0-2: IN_PROGRESS TECHNICIAN REASSIGNMENT BLOCKED
# =============================================================================

class InProgressAssignBlockedTest(TestCase):
    """OrderEditAssignService must not reassign technician for IN_PROGRESS orders."""

    def setUp(self):
        self.company = _company("asgn")
        self.admin = _admin(self.company)
        self.tech_a = _tech(self.company, "ta")
        self.tech_b = _tech(self.company, "tb")

    def test_in_progress_not_in_assignable_statuses(self):
        self.assertNotIn(
            Order.Status.IN_PROGRESS,
            OrderEditAssignService.ASSIGNABLE_STATUSES,
        )

    def test_in_progress_order_technician_unchanged(self):
        """handle_assignment silently skips IN_PROGRESS orders."""
        order = _order(self.company, Order.Status.IN_PROGRESS, technician=self.tech_a)
        result = OrderEditAssignService.handle_assignment(
            order=order,
            technician_id=self.tech_b.id,
            assigned_by=self.admin,
            company=self.company,
        )
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech_a.id, "Technician must not change for IN_PROGRESS orders.")

    def test_in_progress_order_status_unchanged(self):
        order = _order(self.company, Order.Status.IN_PROGRESS, technician=self.tech_a)
        OrderEditAssignService.handle_assignment(
            order=order,
            technician_id=self.tech_b.id,
            assigned_by=self.admin,
            company=self.company,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

    def test_in_progress_order_no_log_created(self):
        from apps.orders.models import OrderStatusLog
        order = _order(self.company, Order.Status.IN_PROGRESS, technician=self.tech_a)
        log_count_before = OrderStatusLog.objects.filter(order=order).count()
        OrderEditAssignService.handle_assignment(
            order=order,
            technician_id=self.tech_b.id,
            assigned_by=self.admin,
            company=self.company,
        )
        log_count_after = OrderStatusLog.objects.filter(order=order).count()
        self.assertEqual(log_count_before, log_count_after, "No log entry must be created for a blocked reassignment.")

    # --- ASSIGNABLE_STATUSES coverage ---

    def test_new_order_can_be_assigned(self):
        order = _order(self.company, Order.Status.NEW)
        result = OrderEditAssignService.handle_assignment(
            order=order,
            technician_id=self.tech_a.id,
            assigned_by=self.admin,
            company=self.company,
        )
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech_a.id)
        self.assertEqual(order.status, Order.Status.WAITING)

    def test_pending_review_order_can_be_assigned(self):
        order = _order(self.company, Order.Status.PENDING_REVIEW)
        OrderEditAssignService.handle_assignment(
            order=order,
            technician_id=self.tech_a.id,
            assigned_by=self.admin,
            company=self.company,
        )
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech_a.id)
        self.assertEqual(order.status, Order.Status.WAITING)

    def test_waiting_order_can_change_technician(self):
        """WAITING order: technician A→B is allowed, status stays WAITING."""
        order = _order(self.company, Order.Status.WAITING, technician=self.tech_a)
        OrderEditAssignService.handle_assignment(
            order=order,
            technician_id=self.tech_b.id,
            assigned_by=self.admin,
            company=self.company,
        )
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech_b.id)
        self.assertEqual(order.status, Order.Status.WAITING)

    def test_done_and_cancelled_not_assignable(self):
        """DONE and CANCELLED are also not in ASSIGNABLE_STATUSES."""
        self.assertNotIn(Order.Status.DONE, OrderEditAssignService.ASSIGNABLE_STATUSES)
        self.assertNotIn(Order.Status.CANCELLED, OrderEditAssignService.ASSIGNABLE_STATUSES)
