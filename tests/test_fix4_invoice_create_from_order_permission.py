"""
Fix 4: In-view permission guard for admin_invoice_create_from_order.

Before fix: middleware enforced admin_invoice_create_from_order on GET but
            fell back to admin_invoice_edit on POST (heuristic mismatch).
            The view itself had no in-view permission check.

After fix:  Explicit in-view check using admin_invoice_create_from_order
            for both GET and POST, regardless of middleware heuristics.

Tests verify:
- COMPANY_STAFF with admin_invoice_edit (but NOT admin_invoice_create_from_order)
  is blocked (403).
- COMPANY_STAFF with admin_invoice_create_from_order is allowed through.
- COMPANY_ADMIN bypasses the check.
- No invoice is created when the request is blocked.
"""
from django.test import TestCase

from apps.accounts.models import CompanyUser, OperatorPermission, UserRole
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.tenants.models import Company


_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"fix4{_seq}"
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


def _order(company):
    global _seq
    _seq += 1
    return Order.objects.create(
        company=company,
        title=f"Order {_seq}",
        status=Order.Status.DONE,
    )


class InvoiceCreateFromOrderPermissionTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.order = _order(self.company)

        # Operator with edit permission only (NOT create_from_order).
        self.op_edit_only = _user(self.company, UserRole.COMPANY_STAFF, suffix="edit")
        _grant(self.company, self.op_edit_only, "admin_invoice_edit")
        _grant(self.company, self.op_edit_only, "admin_invoice_detail")

        # Operator with the correct create_from_order permission.
        self.op_create = _user(self.company, UserRole.COMPANY_STAFF, suffix="create")
        _grant(self.company, self.op_create, "admin_invoice_create_from_order")

        # Company admin.
        self.admin = _user(self.company, UserRole.COMPANY_ADMIN, suffix="adm")

    def _url(self):
        return f"/{self.company.code}/admin/orders/{self.order.id}/invoice/create/"

    # -------------------------------------------------------------------------
    # GET requests
    # -------------------------------------------------------------------------

    def test_get_blocked_without_create_permission(self):
        self.client.force_login(self.op_edit_only)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 403)

    def test_get_allowed_with_create_permission(self):
        self.client.force_login(self.op_create)
        resp = self.client.get(self._url())
        # Passes permission gate; may redirect (302) to newly created invoice edit page.
        self.assertNotEqual(resp.status_code, 403)

    def test_get_admin_bypasses(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self._url())
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # POST requests
    # -------------------------------------------------------------------------

    def test_post_blocked_without_create_permission(self):
        self.client.force_login(self.op_edit_only)
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 403)

    def test_post_allowed_with_create_permission(self):
        self.client.force_login(self.op_create)
        resp = self.client.post(self._url())
        self.assertNotEqual(resp.status_code, 403)

    def test_post_admin_bypasses(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self._url())
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # No invoice created when blocked
    # -------------------------------------------------------------------------

    def test_no_invoice_created_when_blocked(self):
        before = Invoice.objects.filter(company=self.company).count()
        self.client.force_login(self.op_edit_only)
        self.client.get(self._url())
        self.client.post(self._url())
        after = Invoice.objects.filter(company=self.company).count()
        self.assertEqual(before, after, "Invoice was created despite blocked permission.")
