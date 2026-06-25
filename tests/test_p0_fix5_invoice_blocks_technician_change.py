"""
Fix-5: Invoice blocks technician change.

Business rule:
    If an order has any non-CANCELLED invoice (DRAFT, ISSUED, or PAID),
    the assigned technician must not be changed.

Covers:
1. OrderAssignService.assign() — standalone admin assignment endpoint
2. OrderEditAssignService.handle_assignment() — admin edit-page assignment
"""
from django.test import TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.orders.services import OrderAssignService, OrderEditAssignService
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company(label):
    global _seq
    _seq += 1
    code = f"fix5{label}{_seq}"
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


def _tech(company, label="t"):
    global _seq
    _seq += 1
    user = CompanyUser.objects.create_user(
        username=f"{label}_{company.code}_{_seq}",
        password="x",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user)


def _order(company, status=Order.Status.NEW, technician=None):
    return Order.objects.create(
        company=company,
        title="Test Order",
        status=status,
        technician=technician,
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
# 1. OrderAssignService.assign()
# =============================================================================

class OrderAssignServiceInvoiceGuardTest(TestCase):
    """OrderAssignService.assign() must raise ValueError when a non-CANCELLED invoice exists."""

    def setUp(self):
        self.company = _company("as")
        self.admin = _admin(self.company)
        self.tech = _tech(self.company)

    def test_draft_invoice_blocks_assign(self):
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.DRAFT)
        with self.assertRaises(ValueError) as ctx:
            OrderAssignService.assign(order=order, technician=self.tech, assigned_by=self.admin)
        self.assertIn("فاکتور", str(ctx.exception))

    def test_issued_invoice_blocks_assign(self):
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.ISSUED)
        with self.assertRaises(ValueError):
            OrderAssignService.assign(order=order, technician=self.tech, assigned_by=self.admin)

    def test_paid_invoice_blocks_assign(self):
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.PAID)
        with self.assertRaises(ValueError):
            OrderAssignService.assign(order=order, technician=self.tech, assigned_by=self.admin)

    def test_cancelled_invoice_does_not_block_assign(self):
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        # Must not raise
        result = OrderAssignService.assign(order=order, technician=self.tech, assigned_by=self.admin)
        self.assertEqual(result.technician_id, self.tech.id)
        self.assertEqual(result.status, Order.Status.WAITING)

    def test_no_invoice_does_not_block_assign(self):
        order = _order(self.company, Order.Status.NEW)
        result = OrderAssignService.assign(order=order, technician=self.tech, assigned_by=self.admin)
        self.assertEqual(result.technician_id, self.tech.id)

    def test_only_cancelled_invoices_does_not_block(self):
        """Multiple CANCELLED invoices — still allowed."""
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        result = OrderAssignService.assign(order=order, technician=self.tech, assigned_by=self.admin)
        self.assertEqual(result.technician_id, self.tech.id)

    def test_draft_plus_cancelled_still_blocks(self):
        """A DRAFT alongside a CANCELLED invoice → blocked (DRAFT is active)."""
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        _invoice(self.company, order, Invoice.Status.DRAFT)
        with self.assertRaises(ValueError):
            OrderAssignService.assign(order=order, technician=self.tech, assigned_by=self.admin)

    def test_order_not_mutated_when_blocked(self):
        """Order technician remains None after a blocked assign."""
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.ISSUED)
        with self.assertRaises(ValueError):
            OrderAssignService.assign(order=order, technician=self.tech, assigned_by=self.admin)
        order.refresh_from_db()
        self.assertIsNone(order.technician_id)
        self.assertEqual(order.status, Order.Status.NEW)


# =============================================================================
# 2. OrderEditAssignService.handle_assignment()
# =============================================================================

class OrderEditAssignServiceInvoiceGuardTest(TestCase):
    """OrderEditAssignService.handle_assignment() must raise ValueError when a non-CANCELLED invoice exists."""

    def setUp(self):
        self.company = _company("ea")
        self.admin = _admin(self.company)
        self.tech_a = _tech(self.company, "ta")
        self.tech_b = _tech(self.company, "tb")

    def _handle(self, order, to_tech):
        return OrderEditAssignService.handle_assignment(
            order=order,
            technician_id=to_tech.id,
            assigned_by=self.admin,
            company=self.company,
        )

    def test_draft_invoice_blocks_edit_assign(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech_a)
        _invoice(self.company, order, Invoice.Status.DRAFT)
        with self.assertRaises(ValueError) as ctx:
            self._handle(order, self.tech_b)
        self.assertIn("فاکتور", str(ctx.exception))

    def test_issued_invoice_blocks_edit_assign(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech_a)
        _invoice(self.company, order, Invoice.Status.ISSUED)
        with self.assertRaises(ValueError):
            self._handle(order, self.tech_b)

    def test_paid_invoice_blocks_edit_assign(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech_a)
        _invoice(self.company, order, Invoice.Status.PAID)
        with self.assertRaises(ValueError):
            self._handle(order, self.tech_b)

    def test_cancelled_invoice_does_not_block_edit_assign(self):
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        self._handle(order, self.tech_a)
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech_a.id)

    def test_no_invoice_does_not_block_edit_assign(self):
        order = _order(self.company, Order.Status.NEW)
        self._handle(order, self.tech_a)
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech_a.id)

    def test_only_cancelled_invoices_does_not_block_edit(self):
        order = _order(self.company, Order.Status.NEW)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        self._handle(order, self.tech_a)
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech_a.id)

    def test_draft_plus_cancelled_still_blocks_edit(self):
        order = _order(self.company, Order.Status.WAITING, technician=self.tech_a)
        _invoice(self.company, order, Invoice.Status.CANCELLED)
        _invoice(self.company, order, Invoice.Status.DRAFT)
        with self.assertRaises(ValueError):
            self._handle(order, self.tech_b)

    def test_order_not_mutated_when_blocked_on_edit(self):
        """Technician must remain tech_a after a blocked edit-assign."""
        order = _order(self.company, Order.Status.WAITING, technician=self.tech_a)
        _invoice(self.company, order, Invoice.Status.ISSUED)
        with self.assertRaises(ValueError):
            self._handle(order, self.tech_b)
        order.refresh_from_db()
        self.assertEqual(order.technician_id, self.tech_a.id)
        self.assertEqual(order.status, Order.Status.WAITING)
