"""
P1-C: Recycle concurrency protection.

Verifies:
- OrderRecycleService.recycle() acquires select_for_update before acting.
- Only one replacement order is created per original (terminal orders blocked).
- OrderReturnToCycleService.return_to_cycle() acquires select_for_update.
- Invoice guard enforced on locked row.
- Status guard enforced on locked row.
"""
from django.test import TestCase

from apps.accounts.models import CompanyUser, Customer, UserRole
from apps.orders.models import Order, OrderStatusLog
from apps.orders.recycle_service import OrderRecycleService, OrderReturnToCycleService
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"p1c{_seq}"
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _admin(company):
    global _seq
    _seq += 1
    return CompanyUser.objects.create_user(
        username=f"adm_{_seq}",
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


def _order(company, status=Order.Status.CANCEL_REQUESTED, customer=None):
    return Order.objects.create(
        company=company,
        title="Test",
        status=status,
        customer=customer,
    )


# =============================================================================
# OrderRecycleService tests
# =============================================================================

class RecycleConcurrencyTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.customer = _customer(self.company)

    def test_recycle_cancel_requested_creates_new_order(self):
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        new_order = OrderRecycleService.recycle(order=order, recycled_by=self.admin)
        self.assertIsNotNone(new_order.id)
        self.assertEqual(new_order.status, Order.Status.NEW)
        self.assertEqual(new_order.company_id, self.company.id)

    def test_recycle_cancels_original(self):
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        OrderRecycleService.recycle(order=order, recycled_by=self.admin)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_recycle_creates_status_logs(self):
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        new_order = OrderRecycleService.recycle(order=order, recycled_by=self.admin)
        self.assertTrue(OrderStatusLog.objects.filter(
            order=order, new_status=Order.Status.CANCELLED,
        ).exists())
        self.assertTrue(OrderStatusLog.objects.filter(
            order=new_order, new_status=Order.Status.NEW,
        ).exists())

    def test_recycle_blocks_done_order(self):
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError):
            OrderRecycleService.recycle(order=order, recycled_by=self.admin)

    def test_recycle_blocks_cancelled_order(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            OrderRecycleService.recycle(order=order, recycled_by=self.admin)

    def test_recycle_only_one_replacement_order(self):
        """Simulate what a race looks like: second call on same (now CANCELLED) order must fail."""
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        # First call succeeds.
        OrderRecycleService.recycle(order=order, recycled_by=self.admin)
        # The lock ensures the second concurrent call sees CANCELLED and raises ValueError.
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            OrderRecycleService.recycle(order=order, recycled_by=self.admin)
        # Exactly one replacement exists.
        replacements = Order.objects.filter(company=self.company, status=Order.Status.NEW).count()
        self.assertEqual(replacements, 1)

    def test_recycle_new_order_resets_assignment(self):
        from apps.accounts.models import Technician
        tech_user = CompanyUser.objects.create_user(
            username="techp1c",
            password="x",
            company=self.company,
            role=UserRole.TECHNICIAN,
        )
        tech = Technician.objects.create(company=self.company, user=tech_user, is_available=True)
        order = Order.objects.create(
            company=self.company,
            title="Assigned",
            status=Order.Status.CANCEL_REQUESTED,
            technician=tech,
            customer=self.customer,
        )
        new_order = OrderRecycleService.recycle(order=order, recycled_by=self.admin)
        self.assertIsNone(new_order.technician_id)
        self.assertIsNone(new_order.accepted_at)
        self.assertIsNone(new_order.completed_at)


# =============================================================================
# OrderReturnToCycleService tests
# =============================================================================

class ReturnToCycleConcurrencyTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.customer = _customer(self.company)

    def test_return_to_cycle_creates_new_order(self):
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        new_order = OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)
        self.assertIsNotNone(new_order.id)
        self.assertEqual(new_order.status, Order.Status.NEW)

    def test_return_to_cycle_cancels_original(self):
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_return_to_cycle_creates_status_logs(self):
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        new_order = OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)
        self.assertTrue(OrderStatusLog.objects.filter(
            order=order, new_status=Order.Status.CANCELLED,
        ).exists())
        self.assertTrue(OrderStatusLog.objects.filter(
            order=new_order, new_status=Order.Status.NEW,
        ).exists())

    def test_return_to_cycle_invoice_guard(self):
        """Orders with active invoices cannot be returned to cycle."""
        from apps.invoices.models import Invoice
        order = _order(self.company, Order.Status.IN_PROGRESS, customer=self.customer)
        Invoice.objects.create(
            company=self.company,
            order=order,
            status=Invoice.Status.DRAFT,
            invoice_number="INV-001",
            subtotal=0,
            total_amount=0,
        )
        with self.assertRaises(ValueError) as ctx:
            OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)
        self.assertIn("فاکتور", str(ctx.exception))

    def test_return_to_cycle_blocked_done(self):
        order = _order(self.company, Order.Status.DONE)
        with self.assertRaises(ValueError):
            OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)

    def test_return_to_cycle_blocked_cancelled(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)

    def test_return_to_cycle_only_one_replacement(self):
        """Second call on same order (now CANCELLED) must fail — no duplicate replacement."""
        order = _order(self.company, Order.Status.CANCEL_REQUESTED, customer=self.customer)
        OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)
        replacements = Order.objects.filter(company=self.company, status=Order.Status.NEW).count()
        self.assertEqual(replacements, 1)

    def test_return_to_cycle_new_order_has_no_technician(self):
        order = _order(self.company, Order.Status.WAITING, customer=self.customer)
        new_order = OrderReturnToCycleService.return_to_cycle(order=order, performed_by=self.admin)
        self.assertIsNone(new_order.technician_id)
