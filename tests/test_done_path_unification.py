"""
DONE path unification: both /complete/ (OrderCompleteService) and
/status/?new_status=done (TechnicianStatusUpdateService) must execute
identical business logic.

Business rules verified:
- Both paths → status DONE.
- Both paths → completed_at set.
- Both paths → OrderStatusLog(IN_PROGRESS → DONE) created.
- Both paths → invoice placeholder (_create_invoice_placeholder) called.
- Both paths → order_completed_customer + survey_request_customer events fired.
- Both paths → IN_PROGRESS required (ValueError otherwise).
- WAITING → IN_PROGRESS is unaffected by the change (regression guard).
- WAITING → IN_PROGRESS does NOT call invoice placeholder.
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.orders.models import Order, OrderStatusLog
from apps.orders.services import OrderCompleteService, TechnicianStatusUpdateService
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"dpu{_seq}"
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
    return Technician.objects.create(company=company, user=user, is_available=True)


def _order(company, status=Order.Status.IN_PROGRESS, technician=None):
    return Order.objects.create(
        company=company,
        title="Test",
        status=status,
        technician=technician,
    )


# =============================================================================
# TESTS
# =============================================================================

class DonePathUnificationTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.tech = _tech(self.company)

    # -------------------------------------------------------------------------
    # Path A — OrderCompleteService.complete()
    # -------------------------------------------------------------------------

    def test_complete_path_sets_done(self):
        order = _order(self.company)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder'):
            OrderCompleteService.complete(order=order, completed_by=self.admin)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DONE)

    def test_complete_path_sets_completed_at(self):
        before = timezone.now()
        order = _order(self.company)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder'):
            OrderCompleteService.complete(order=order, completed_by=self.admin)
        order.refresh_from_db()
        self.assertIsNotNone(order.completed_at)
        self.assertGreaterEqual(order.completed_at, before)

    def test_complete_path_creates_status_log(self):
        order = _order(self.company)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder'):
            OrderCompleteService.complete(order=order, completed_by=self.admin)
        self.assertTrue(
            OrderStatusLog.objects.filter(
                order=order,
                old_status=Order.Status.IN_PROGRESS,
                new_status=Order.Status.DONE,
            ).exists()
        )

    def test_complete_path_calls_invoice_placeholder(self):
        order = _order(self.company)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder') as mock_inv:
            OrderCompleteService.complete(order=order, completed_by=self.admin)
        mock_inv.assert_called_once_with(order=order)

    def test_complete_path_fires_notifications(self):
        order = _order(self.company)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder'):
            with patch('apps.orders.services._emit_order_notification_event') as mock_n:
                OrderCompleteService.complete(order=order, completed_by=self.admin)
        keys = [c.args[0] for c in mock_n.call_args_list]
        self.assertIn('order_completed_customer', keys)
        self.assertIn('survey_request_customer', keys)

    def test_complete_path_requires_in_progress(self):
        order = _order(self.company, status=Order.Status.WAITING)
        with self.assertRaises(ValueError):
            OrderCompleteService.complete(order=order, completed_by=self.admin)

    # -------------------------------------------------------------------------
    # Path B — TechnicianStatusUpdateService.update_status(new_status=DONE)
    # -------------------------------------------------------------------------

    def test_status_update_done_sets_done(self):
        order = _order(self.company, technician=self.tech)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder'):
            TechnicianStatusUpdateService.update_status(
                order=order, technician=self.tech,
                new_status=Order.Status.DONE, updated_by=self.admin,
            )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DONE)

    def test_status_update_done_sets_completed_at(self):
        before = timezone.now()
        order = _order(self.company, technician=self.tech)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder'):
            TechnicianStatusUpdateService.update_status(
                order=order, technician=self.tech,
                new_status=Order.Status.DONE, updated_by=self.admin,
            )
        order.refresh_from_db()
        self.assertIsNotNone(order.completed_at)
        self.assertGreaterEqual(order.completed_at, before)

    def test_status_update_done_creates_status_log(self):
        order = _order(self.company, technician=self.tech)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder'):
            TechnicianStatusUpdateService.update_status(
                order=order, technician=self.tech,
                new_status=Order.Status.DONE, updated_by=self.admin,
            )
        self.assertTrue(
            OrderStatusLog.objects.filter(
                order=order,
                old_status=Order.Status.IN_PROGRESS,
                new_status=Order.Status.DONE,
            ).exists()
        )

    def test_status_update_done_calls_invoice_placeholder(self):
        order = _order(self.company, technician=self.tech)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder') as mock_inv:
            TechnicianStatusUpdateService.update_status(
                order=order, technician=self.tech,
                new_status=Order.Status.DONE, updated_by=self.admin,
            )
        mock_inv.assert_called_once()

    def test_status_update_done_fires_notifications(self):
        order = _order(self.company, technician=self.tech)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder'):
            with patch('apps.orders.services._emit_order_notification_event') as mock_n:
                TechnicianStatusUpdateService.update_status(
                    order=order, technician=self.tech,
                    new_status=Order.Status.DONE, updated_by=self.admin,
                )
        keys = [c.args[0] for c in mock_n.call_args_list]
        self.assertIn('order_completed_customer', keys)
        self.assertIn('survey_request_customer', keys)

    def test_status_update_done_requires_in_progress(self):
        order = _order(self.company, status=Order.Status.WAITING, technician=self.tech)
        with self.assertRaises(ValueError):
            TechnicianStatusUpdateService.update_status(
                order=order, technician=self.tech,
                new_status=Order.Status.DONE, updated_by=self.admin,
            )

    def test_status_update_done_requires_own_order(self):
        other_tech = _tech(self.company)
        order = _order(self.company, technician=other_tech)
        with self.assertRaises(ValueError) as ctx:
            TechnicianStatusUpdateService.update_status(
                order=order, technician=self.tech,
                new_status=Order.Status.DONE, updated_by=self.admin,
            )
        self.assertIn("not assigned", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Regression — WAITING → IN_PROGRESS must be unaffected
    # -------------------------------------------------------------------------

    def test_waiting_to_in_progress_sets_status(self):
        order = _order(self.company, status=Order.Status.WAITING, technician=self.tech)
        TechnicianStatusUpdateService.update_status(
            order=order, technician=self.tech,
            new_status=Order.Status.IN_PROGRESS, updated_by=self.admin,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)

    def test_waiting_to_in_progress_creates_status_log(self):
        order = _order(self.company, status=Order.Status.WAITING, technician=self.tech)
        TechnicianStatusUpdateService.update_status(
            order=order, technician=self.tech,
            new_status=Order.Status.IN_PROGRESS, updated_by=self.admin,
        )
        self.assertTrue(
            OrderStatusLog.objects.filter(
                order=order,
                old_status=Order.Status.WAITING,
                new_status=Order.Status.IN_PROGRESS,
            ).exists()
        )

    def test_waiting_to_in_progress_does_not_call_invoice_placeholder(self):
        order = _order(self.company, status=Order.Status.WAITING, technician=self.tech)
        with patch.object(OrderCompleteService, '_create_invoice_placeholder') as mock_inv:
            TechnicianStatusUpdateService.update_status(
                order=order, technician=self.tech,
                new_status=Order.Status.IN_PROGRESS, updated_by=self.admin,
            )
        mock_inv.assert_not_called()
