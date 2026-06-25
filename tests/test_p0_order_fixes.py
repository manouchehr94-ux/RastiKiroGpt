"""
P0 Order Domain fixes.

P0-1: admin_order_detail recycle_order action now uses OrderReturnToCycleService,
      not OrderRecycleService. Key differences enforced:
      - Active invoice blocks the action (invoice guard preserved).
      - Replacement order is created and the redirect points to it.
      - customer_name, customer_phone, service_date are copied to the new order.

P0-2: OrderUpdateService.update() rejects terminal-status writes.
      - status=done  → ValueError
      - status=cancelled → ValueError
      - PENDING_REVIEW → NEW (approval flow) still works.
      - Other non-terminal transitions still work.
"""
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Customer, OperatorPermission, UserRole
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.orders.services import OrderUpdateService
from apps.tenants.models import Company, CompanyServiceCategory


_seq = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company():
    global _seq
    _seq += 1
    code = f"p0fix{_seq}"
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _admin(company):
    global _seq
    _seq += 1
    return CompanyUser.objects.create_user(
        username=f"adm_{_seq}",
        password="pass",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _category(company):
    global _seq
    _seq += 1
    return CompanyServiceCategory.objects.create(
        company=company, title=f"Cat {_seq}", is_active=True,
    )


def _customer(company):
    global _seq
    _seq += 1
    return Customer.objects.create(
        company=company,
        first_name=f"Test{_seq}",
        last_name="User",
        phone=f"091{_seq:08d}",
    )


def _order(company, status=Order.Status.CANCEL_REQUESTED, category=None, customer=None):
    global _seq
    _seq += 1
    return Order.objects.create(
        company=company,
        title=f"Order {_seq}",
        customer=customer,
        customer_name=f"مشتری {_seq}" if customer is None else f"{customer.first_name} {customer.last_name}",
        customer_phone=f"091{_seq:08d}" if customer is None else customer.phone,
        status=status,
        service_category=category,
    )


def _order_with_fields(company, status, category, customer, service_date=None, cname=None, cphone=None):
    """Order factory with explicit field overrides for P0-1 field-copy test."""
    global _seq
    _seq += 1
    return Order.objects.create(
        company=company,
        title=f"Order {_seq}",
        customer=customer,
        customer_name=cname or f"{customer.first_name} {customer.last_name}",
        customer_phone=cphone or customer.phone,
        status=status,
        service_category=category,
        service_date=service_date,
    )


def _active_invoice(company, order):
    global _seq
    _seq += 1
    return Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-P0-{_seq:05d}",
        status=Invoice.Status.ISSUED,
        total_amount=100000,
        subtotal=100000,
        public_code=f"P0{_seq:06d}",
        issued_at=timezone.now(),
    )


# =============================================================================
# P0-1: recycle_order inline action uses OrderReturnToCycleService
# =============================================================================


class RecycleOrderUsesCanonicalServiceTest(TestCase):
    """
    admin_order_detail POST recycle_order must behave identically to
    admin_order_return_to_cycle (both now use OrderReturnToCycleService).
    """

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.cat = _category(self.company)
        self.customer = _customer(self.company)

    def _url(self, order):
        return f"/{self.company.code}/admin/orders/{order.id}/"

    def test_active_invoice_blocks_recycle(self):
        """Invoice guard from OrderReturnToCycleService must be enforced."""
        order = _order(
            self.company,
            status=Order.Status.CANCEL_REQUESTED,
            category=self.cat,
            customer=self.customer,
        )
        _active_invoice(self.company, order)

        self.client.force_login(self.admin)
        resp = self.client.post(self._url(order), {"recycle_order": "1"})

        # Must NOT redirect to a new order — stays on the same page with error.
        self.assertNotEqual(resp.status_code, 302)

        # Old order must still be CANCEL_REQUESTED (not CANCELLED).
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCEL_REQUESTED)

        # No new order was created.
        self.assertEqual(
            Order.objects.filter(company=self.company).count(), 1,
            "No replacement order should be created when invoice blocks recycling."
        )

    def test_replacement_order_created_on_recycle(self):
        """Successful recycle creates a new NEW order and redirects to it."""
        order = _order(
            self.company,
            status=Order.Status.CANCEL_REQUESTED,
            category=self.cat,
            customer=self.customer,
        )
        self.client.force_login(self.admin)
        resp = self.client.post(self._url(order), {"recycle_order": "1"})

        self.assertEqual(resp.status_code, 302)

        # Old order should be CANCELLED.
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

        # A new NEW order must exist.
        new_orders = Order.objects.filter(
            company=self.company, status=Order.Status.NEW,
        ).exclude(id=order.id)
        self.assertEqual(new_orders.count(), 1)

        # Redirect points to the new order.
        new_order = new_orders.first()
        self.assertIn(str(new_order.id), resp["Location"])

    def test_customer_fields_copied_to_replacement(self):
        """
        OrderReturnToCycleService copies customer_name, customer_phone, service_date.
        This would NOT happen with the old OrderRecycleService.
        """
        order = _order_with_fields(
            self.company,
            status=Order.Status.CANCEL_REQUESTED,
            category=self.cat,
            customer=self.customer,
            service_date=date(2026, 7, 1),
            cname="زهرا محمدی",
            cphone="09130000002",
        )

        self.client.force_login(self.admin)
        self.client.post(self._url(order), {"recycle_order": "1"})

        new_order = Order.objects.filter(
            company=self.company, status=Order.Status.NEW,
        ).exclude(id=order.id).first()
        self.assertIsNotNone(new_order)
        self.assertEqual(new_order.customer_name, "زهرا محمدی")
        self.assertEqual(new_order.customer_phone, "09130000002")
        self.assertEqual(new_order.service_date, date(2026, 7, 1))

    def test_cancelled_invoice_does_not_block_recycle(self):
        """A CANCELLED invoice must not block the return-to-cycle action."""
        order = _order(
            self.company,
            status=Order.Status.CANCEL_REQUESTED,
            category=self.cat,
            customer=self.customer,
        )
        Invoice.objects.create(
            company=self.company,
            order=order,
            invoice_number="INV-CANC-001",
            status=Invoice.Status.CANCELLED,
            total_amount=50000,
            subtotal=50000,
            public_code="CANCX001",
        )
        self.client.force_login(self.admin)
        resp = self.client.post(self._url(order), {"recycle_order": "1"})

        self.assertEqual(resp.status_code, 302)
        new_order = Order.objects.filter(
            company=self.company, status=Order.Status.NEW,
        ).exclude(id=order.id).first()
        self.assertIsNotNone(new_order)

    def test_permission_still_enforced(self):
        """Operator without admin_order_return_to_cycle gets 403."""
        no_perm = CompanyUser.objects.create_user(
            username="no_perm_u", password="pass",
            company=self.company, role=UserRole.COMPANY_STAFF,
        )
        OperatorPermission.objects.create(
            company=self.company, operator=no_perm,
            permission_key="admin_order_detail", is_allowed=True,
        )
        order = _order(
            self.company,
            status=Order.Status.CANCEL_REQUESTED,
            category=self.cat,
            customer=self.customer,
        )
        self.client.force_login(no_perm)
        resp = self.client.post(self._url(order), {"recycle_order": "1"})
        self.assertEqual(resp.status_code, 403)


# =============================================================================
# P0-2: OrderUpdateService.update() rejects terminal-status writes
# =============================================================================


class OrderUpdateServiceTerminalGuardTest(TestCase):
    """
    OrderUpdateService.update() must raise ValueError when the caller attempts
    to set status=DONE or status=CANCELLED through the generic edit path.
    """

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.order = _order(
            self.company,
            status=Order.Status.IN_PROGRESS,
        )

    def test_status_done_raises(self):
        with self.assertRaises(ValueError) as cm:
            OrderUpdateService.update(
                order=self.order,
                updated_by=self.admin,
                data={"status": Order.Status.DONE},
            )
        self.assertIn("ویرایش", str(cm.exception))

    def test_status_cancelled_raises(self):
        with self.assertRaises(ValueError) as cm:
            OrderUpdateService.update(
                order=self.order,
                updated_by=self.admin,
                data={"status": Order.Status.CANCELLED},
            )
        self.assertIn("ویرایش", str(cm.exception))

    def test_order_unchanged_after_done_attempt(self):
        """Failed update must leave the order status unchanged."""
        try:
            OrderUpdateService.update(
                order=self.order,
                updated_by=self.admin,
                data={"status": Order.Status.DONE},
            )
        except ValueError:
            pass
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.IN_PROGRESS)

    def test_pending_review_to_new_still_works(self):
        """PENDING_REVIEW → NEW is the admin approval flow and must not be blocked."""
        pending = _order(self.company, status=Order.Status.PENDING_REVIEW)
        OrderUpdateService.update(
            order=pending,
            updated_by=self.admin,
            data={"status": Order.Status.NEW},
        )
        pending.refresh_from_db()
        self.assertEqual(pending.status, Order.Status.NEW)

    def test_non_terminal_transition_still_works(self):
        """Setting status=WAITING (non-terminal) must not be blocked."""
        new_order = _order(self.company, status=Order.Status.NEW)
        OrderUpdateService.update(
            order=new_order,
            updated_by=self.admin,
            data={"status": Order.Status.WAITING},
        )
        new_order.refresh_from_db()
        self.assertEqual(new_order.status, Order.Status.WAITING)

    def test_cancel_requested_transition_still_works(self):
        """CANCEL_REQUESTED is non-terminal and must be settable via update."""
        new_order = _order(self.company, status=Order.Status.NEW)
        OrderUpdateService.update(
            order=new_order,
            updated_by=self.admin,
            data={"status": Order.Status.CANCEL_REQUESTED},
        )
        new_order.refresh_from_db()
        self.assertEqual(new_order.status, Order.Status.CANCEL_REQUESTED)

    def test_existing_terminal_guard_still_applies(self):
        """Editing an already-DONE order still raises (pre-existing guard unchanged)."""
        done_order = _order(self.company, status=Order.Status.DONE)
        with self.assertRaises(ValueError):
            OrderUpdateService.update(
                order=done_order,
                updated_by=self.admin,
                data={"title": "new title"},
            )
