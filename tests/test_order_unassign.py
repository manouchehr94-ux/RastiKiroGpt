"""
OrderUnassignService tests.

Business rules:
- Only WAITING orders can be unassigned.
- IN_PROGRESS / DONE / CANCELLED orders are blocked.
- Orders with any non-CANCELLED invoice are blocked.
- On success: technician=None, status=NEW, accepted_at=None.
- dispatch_order_available_events is called on success.
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.orders.services import OrderUnassignService
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"unasn{_seq}"
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


def _tech(company):
    global _seq
    _seq += 1
    user = CompanyUser.objects.create_user(
        username=f"tch_{company.code}_{_seq}",
        password="x",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user)


def _order(company, status, technician=None):
    return Order.objects.create(
        company=company,
        title="Test",
        status=status,
        technician=technician,
        accepted_at=timezone.now() if technician else None,
    )


def _invoice(company, order, status):
    global _seq
    _seq += 1
    return Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-{company.code.upper()}-{_seq:05d}",
        status=status,
    )


# =============================================================================
# TESTS
# =============================================================================

class OrderUnassignServiceTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.tech = _tech(self.company)

    def _unassign(self, order):
        return OrderUnassignService.unassign(order=order, unassigned_by=self.admin)

    # --- success path ---

    def test_waiting_order_unassigns_successfully(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        result = self._unassign(order)
        self.assertIsNotNone(result)

    def test_status_becomes_new(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        self._unassign(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    def test_technician_becomes_null(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        self._unassign(order)
        order.refresh_from_db()
        self.assertIsNone(order.technician_id)

    def test_accepted_at_becomes_null(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        self._unassign(order)
        order.refresh_from_db()
        self.assertIsNone(order.accepted_at)

    def test_dispatch_available_events_called(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        with patch("apps.orders.order_events.dispatch_order_available_events") as mock_dispatch:
            self._unassign(order)
        mock_dispatch.assert_called_once_with(order=order)

    # --- status restrictions ---

    def test_in_progress_blocked(self):
        order = _order(self.company, Order.Status.IN_PROGRESS, technician=self.tech)
        with self.assertRaises(ValueError) as ctx:
            self._unassign(order)
        self.assertIn("WAITING", str(ctx.exception))

    def test_done_blocked(self):
        order = _order(self.company, Order.Status.DONE, technician=self.tech)
        with self.assertRaises(ValueError):
            self._unassign(order)

    def test_cancelled_blocked(self):
        order = _order(self.company, Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            self._unassign(order)

    def test_new_blocked(self):
        order = _order(self.company, Order.Status.NEW)
        with self.assertRaises(ValueError):
            self._unassign(order)

    # --- invoice restrictions ---

    def test_draft_invoice_blocks_unassign(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        _invoice(self.company, order, Invoice.Status.DRAFT)
        with self.assertRaises(ValueError) as ctx:
            self._unassign(order)
        self.assertIn("فاکتور", str(ctx.exception))

    def test_issued_invoice_blocks_unassign(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        _invoice(self.company, order, Invoice.Status.ISSUED)
        with self.assertRaises(ValueError):
            self._unassign(order)

    def test_paid_invoice_blocks_unassign(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        _invoice(self.company, order, Invoice.Status.PAID)
        with self.assertRaises(ValueError):
            self._unassign(order)

    def test_cancelled_invoice_does_not_block(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        result = self._unassign(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    def test_only_cancelled_invoices_does_not_block(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        self._unassign(order)
        order.refresh_from_db()
        self.assertIsNone(order.technician_id)

    def test_order_not_mutated_when_blocked_by_invoice(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech)
        _invoice(self.company, order, Invoice.Status.ISSUED)
        with self.assertRaises(ValueError):
            self._unassign(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.WAITING)
        self.assertEqual(order.technician_id, self.tech.id)

    def test_order_not_mutated_when_blocked_by_status(self):
        order = _order(self.company, Order.Status.IN_PROGRESS, technician=self.tech)
        with self.assertRaises(ValueError):
            self._unassign(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertEqual(order.technician_id, self.tech.id)
