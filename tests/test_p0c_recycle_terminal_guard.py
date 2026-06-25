"""
P0-C: OrderRecycleService.recycle() must not accept terminal orders.

Business rules verified:
- DONE order recycle is blocked with ValueError.
- CANCELLED order recycle is blocked with ValueError.
- DONE / CANCELLED orders are not mutated when blocked.
- WAITING, IN_PROGRESS, CANCEL_REQUESTED orders can still be recycled.
"""
from django.test import TestCase

from apps.accounts.models import CompanyUser, Customer, UserRole
from apps.orders.models import Order
from apps.orders.recycle_service import OrderRecycleService
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"p0c{_seq}"
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


def _customer(company):
    global _seq
    _seq += 1
    return Customer.objects.create(
        company=company,
        first_name="Test",
        last_name=f"User{_seq}",
        phone=f"0912000{_seq:04d}",
    )


def _order(company, status, customer=None):
    return Order.objects.create(
        company=company,
        title="Test",
        status=status,
        customer=customer,
    )


# =============================================================================
# TESTS
# =============================================================================

class RecycleTerminalGuardTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.customer = _customer(self.company)

    def _recycle(self, order):
        return OrderRecycleService.recycle(order=order, recycled_by=self.admin)

    # --- Terminal orders are blocked ---

    def test_done_order_recycle_blocked(self):
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError) as ctx:
            self._recycle(order)
        self.assertIn("بازیافت", str(ctx.exception))

    def test_cancelled_order_recycle_blocked(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError) as ctx:
            self._recycle(order)
        self.assertIn("بازیافت", str(ctx.exception))

    # --- Terminal orders are NOT mutated on block ---

    def test_done_order_not_mutated(self):
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError):
            self._recycle(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DONE)

    def test_cancelled_order_not_mutated(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            self._recycle(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_done_order_no_new_order_created(self):
        order = _order(self.company, Order.Status.DONE)
        count_before = Order.objects.filter(company=self.company).count()
        with self.assertRaises(ValueError):
            self._recycle(order)
        self.assertEqual(Order.objects.filter(company=self.company).count(), count_before)

    # --- Non-terminal orders can be recycled ---
    # Customer is required by Order.full_clean() in recycle_service.

    def test_waiting_order_recycle_succeeds(self):
        order = _order(self.company, Order.Status.WAITING, customer=self.customer)
        new_order = self._recycle(order)
        self.assertIsNotNone(new_order.pk)
        self.assertEqual(new_order.status, Order.Status.NEW)

    def test_in_progress_order_recycle_succeeds(self):
        order = _order(self.company, Order.Status.IN_PROGRESS, customer=self.customer)
        new_order = self._recycle(order)
        self.assertIsNotNone(new_order.pk)
        self.assertEqual(new_order.status, Order.Status.NEW)

    def test_cancel_requested_order_recycle_succeeds(self):
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        new_order = self._recycle(order)
        self.assertIsNotNone(new_order.pk)
        self.assertEqual(new_order.status, Order.Status.NEW)

    def test_recycle_creates_new_separate_order(self):
        order = _order(self.company, Order.Status.WAITING, customer=self.customer)
        new_order = self._recycle(order)
        self.assertNotEqual(new_order.pk, order.pk)

    def test_original_order_becomes_cancelled_after_recycle(self):
        order = _order(self.company, Order.Status.WAITING, customer=self.customer)
        original_pk = order.pk
        self._recycle(order)
        original = Order.objects.get(pk=original_pk)
        self.assertEqual(original.status, Order.Status.CANCELLED)
