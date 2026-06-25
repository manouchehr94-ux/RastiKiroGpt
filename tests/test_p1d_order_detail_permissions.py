"""
P1-D: Server-side permission enforcement for admin_order_detail sub-actions.

Each POST sub-action inside admin_order_detail now requires:
  assign_technician    → admin_order_assign
  unassign_technician  → admin_order_assign
  force_cancel         → admin_cancel_request_approve
  confirm_cancel       → admin_cancel_request_approve
  recycle_order        → admin_order_return_to_cycle

Verified:
- Operator with only admin_order_detail permission receives 403 for each action.
- Operator granted the specific action permission is not blocked (not 403).
- COMPANY_ADMIN bypasses all permission checks.
"""
from django.test import TestCase

from apps.accounts.models import CompanyUser, OperatorPermission, Technician, UserRole
from apps.orders.models import Order
from apps.tenants.models import Company


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"p1d{_seq}"
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _user(company, role, suffix="u"):
    global _seq
    _seq += 1
    return CompanyUser.objects.create_user(
        username=f"{suffix}_{_seq}",
        password="pass",
        company=company,
        role=role,
    )


def _grant(company, operator, permission_key):
    OperatorPermission.objects.create(
        company=company,
        operator=operator,
        permission_key=permission_key,
        is_allowed=True,
    )


def _order(company, status=Order.Status.NEW, customer=None):
    return Order.objects.create(
        company=company, title="T", status=status, customer=customer,
    )


# =============================================================================
# TESTS
# =============================================================================

class OrderDetailSubActionPermissionTest(TestCase):
    """
    Test that each POST sub-action in admin_order_detail is guarded server-side.
    """

    def setUp(self):
        self.company = _company()

        # Operator: has page-level access (middleware passes) but no sub-action permissions yet.
        self.operator = _user(self.company, UserRole.COMPANY_STAFF, suffix="op")
        _grant(self.company, self.operator, "admin_order_detail")

        # Admin: bypasses all permission checks.
        self.admin = _user(self.company, UserRole.COMPANY_ADMIN, suffix="adm")

        self.order = _order(self.company)

    def _url(self):
        return f"/{self.company.code}/admin/orders/{self.order.id}/"

    def _post_as_operator(self, data):
        self.client.force_login(self.operator)
        return self.client.post(self._url(), data)

    def _post_as_admin(self, data):
        self.client.force_login(self.admin)
        return self.client.post(self._url(), data)

    # -------------------------------------------------------------------------
    # assign_technician
    # -------------------------------------------------------------------------

    def test_assign_technician_forbidden_without_permission(self):
        resp = self._post_as_operator({"assign_technician": "1", "technician_id": ""})
        self.assertEqual(resp.status_code, 403)

    def test_assign_technician_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_order_assign")
        resp = self._post_as_operator({"assign_technician": "1", "technician_id": ""})
        # No technician_id supplied → no assignment attempted → renders detail page (200).
        self.assertNotEqual(resp.status_code, 403)

    def test_assign_technician_admin_not_blocked(self):
        resp = self._post_as_admin({"assign_technician": "1", "technician_id": ""})
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # unassign_technician
    # -------------------------------------------------------------------------

    def test_unassign_technician_forbidden_without_permission(self):
        resp = self._post_as_operator({"unassign_technician": "1"})
        self.assertEqual(resp.status_code, 403)

    def test_unassign_technician_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_order_assign")
        # Order is NEW (not WAITING), so service raises ValueError — but permission gate passed.
        resp = self._post_as_operator({"unassign_technician": "1"})
        self.assertNotEqual(resp.status_code, 403)

    def test_unassign_technician_admin_not_blocked(self):
        resp = self._post_as_admin({"unassign_technician": "1"})
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # force_cancel
    # -------------------------------------------------------------------------

    def test_force_cancel_forbidden_without_permission(self):
        resp = self._post_as_operator({"force_cancel": "1"})
        self.assertEqual(resp.status_code, 403)

    def test_force_cancel_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_cancel_request_approve")
        resp = self._post_as_operator({"force_cancel": "1"})
        self.assertNotEqual(resp.status_code, 403)

    def test_force_cancel_admin_not_blocked(self):
        resp = self._post_as_admin({"force_cancel": "1"})
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # confirm_cancel
    # -------------------------------------------------------------------------

    def test_confirm_cancel_forbidden_without_permission(self):
        resp = self._post_as_operator({"confirm_cancel": "1"})
        self.assertEqual(resp.status_code, 403)

    def test_confirm_cancel_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_cancel_request_approve")
        resp = self._post_as_operator({"confirm_cancel": "1"})
        self.assertNotEqual(resp.status_code, 403)

    def test_confirm_cancel_admin_not_blocked(self):
        resp = self._post_as_admin({"confirm_cancel": "1"})
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # recycle_order
    # -------------------------------------------------------------------------

    def test_recycle_order_forbidden_without_permission(self):
        resp = self._post_as_operator({"recycle_order": "1"})
        self.assertEqual(resp.status_code, 403)

    def test_recycle_order_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_order_return_to_cycle")
        # Use a DONE order: service raises ValueError (terminal guard), view catches it, renders 200.
        # This proves the permission gate passed without needing a full recycle fixture.
        done_order = _order(self.company, Order.Status.DONE)
        self.client.force_login(self.operator)
        resp = self.client.post(f"/{self.company.code}/admin/orders/{done_order.id}/", {"recycle_order": "1"})
        self.assertNotEqual(resp.status_code, 403)

    def test_recycle_order_admin_not_blocked(self):
        done_order = _order(self.company, Order.Status.DONE)
        self.client.force_login(self.admin)
        resp = self.client.post(f"/{self.company.code}/admin/orders/{done_order.id}/", {"recycle_order": "1"})
        self.assertNotEqual(resp.status_code, 403)
