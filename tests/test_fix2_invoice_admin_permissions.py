"""
Fix 2: Server-side permission enforcement for admin_invoice_detail sub-actions.

Before fix: any COMPANY_STAFF could issue, cancel, or mark invoices paid via direct URL.
After fix:
  issue_invoice          → requires admin_invoice_edit
  mark_paid_company_cash → requires admin_invoice_edit
  mark_paid_technician_cash → requires admin_invoice_edit
  cancel_invoice         → requires admin_invoice_cancel

Permission keys used match the existing synthetic keys defined in
apps/accounts/operator_access.py:
  - admin_invoice_edit   ("ویرایش یا تغییر وضعیت فاکتور")
  - admin_invoice_cancel ("لغو فاکتور")

Tests verify:
- Operator without permission → 403 for each sub-action.
- Operator WITH the required permission → not 403 (action may succeed or fail on
  business logic, but the permission gate is passed).
- COMPANY_ADMIN always bypasses.
"""
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, OperatorPermission, UserRole
from apps.invoices.models import Invoice
from apps.tenants.models import Company


_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"fix2{_seq}"
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


def _invoice(company, status=Invoice.Status.DRAFT):
    global _seq
    _seq += 1
    return Invoice.objects.create(
        company=company,
        invoice_number=f"INV-FX2-{_seq:05d}",
        status=status,
        total_amount=100000,
        subtotal=100000,
        public_code=f"FX2{_seq:06d}",
        issued_at=timezone.now() if status in (Invoice.Status.ISSUED, Invoice.Status.PAID) else None,
    )


class InvoiceDetailSubActionPermissionTest(TestCase):
    """
    Each POST sub-action in admin_invoice_detail must be guarded by an operator
    permission, exactly like order sub-actions in admin_order_detail.
    """

    def setUp(self):
        self.company = _company()

        # Operator: has page-level access (admin_invoice_detail) but no sub-action permissions.
        self.operator = _user(self.company, UserRole.COMPANY_STAFF, suffix="op")
        _grant(self.company, self.operator, "admin_invoice_detail")

        # Admin: bypasses all permission checks.
        self.admin = _user(self.company, UserRole.COMPANY_ADMIN, suffix="adm")

        # One DRAFT invoice for issue/cancel tests.
        self.draft_invoice = _invoice(self.company, Invoice.Status.DRAFT)
        # One ISSUED invoice for mark-paid tests.
        self.issued_invoice = _invoice(self.company, Invoice.Status.ISSUED)

    def _url(self, invoice):
        return f"/{self.company.code}/admin/invoices/{invoice.id}/"

    def _post_as_operator(self, invoice, data):
        self.client.force_login(self.operator)
        return self.client.post(self._url(invoice), data)

    def _post_as_admin(self, invoice, data):
        self.client.force_login(self.admin)
        return self.client.post(self._url(invoice), data)

    # -------------------------------------------------------------------------
    # issue_invoice
    # -------------------------------------------------------------------------

    def test_issue_invoice_forbidden_without_permission(self):
        resp = self._post_as_operator(self.draft_invoice, {"issue_invoice": "1"})
        self.assertEqual(resp.status_code, 403)

    def test_issue_invoice_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_invoice_edit")
        resp = self._post_as_operator(self.draft_invoice, {"issue_invoice": "1"})
        # Invoice has zero total_amount → issue raises ValueError → renders 200 with error.
        self.assertNotEqual(resp.status_code, 403)

    def test_issue_invoice_admin_not_blocked(self):
        resp = self._post_as_admin(self.draft_invoice, {"issue_invoice": "1"})
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # cancel_invoice
    # -------------------------------------------------------------------------

    def test_cancel_invoice_forbidden_without_permission(self):
        resp = self._post_as_operator(self.draft_invoice, {"cancel_invoice": "1"})
        self.assertEqual(resp.status_code, 403)

    def test_cancel_invoice_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_invoice_cancel")
        resp = self._post_as_operator(self.draft_invoice, {"cancel_invoice": "1"})
        # Cancel succeeds → 302 redirect (or 200 if already cancelled).
        self.assertNotEqual(resp.status_code, 403)

    def test_cancel_invoice_admin_not_blocked(self):
        resp = self._post_as_admin(self.draft_invoice, {"cancel_invoice": "1"})
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # mark_paid_company_cash
    # -------------------------------------------------------------------------

    def test_mark_paid_company_cash_forbidden_without_permission(self):
        resp = self._post_as_operator(self.issued_invoice, {"mark_paid_company_cash": "1"})
        self.assertEqual(resp.status_code, 403)

    def test_mark_paid_company_cash_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_invoice_edit")
        resp = self._post_as_operator(self.issued_invoice, {"mark_paid_company_cash": "1"})
        # mark_paid may succeed or raise (e.g., wage service) but must not return 403.
        self.assertNotEqual(resp.status_code, 403)

    def test_mark_paid_company_cash_admin_not_blocked(self):
        resp = self._post_as_admin(self.issued_invoice, {"mark_paid_company_cash": "1"})
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # mark_paid_technician_cash
    # -------------------------------------------------------------------------

    def test_mark_paid_technician_cash_forbidden_without_permission(self):
        resp = self._post_as_operator(self.issued_invoice, {"mark_paid_technician_cash": "1"})
        self.assertEqual(resp.status_code, 403)

    def test_mark_paid_technician_cash_allowed_with_permission(self):
        _grant(self.company, self.operator, "admin_invoice_edit")
        resp = self._post_as_operator(self.issued_invoice, {"mark_paid_technician_cash": "1"})
        self.assertNotEqual(resp.status_code, 403)

    def test_mark_paid_technician_cash_admin_not_blocked(self):
        resp = self._post_as_admin(self.issued_invoice, {"mark_paid_technician_cash": "1"})
        self.assertNotEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # cancel uses admin_invoice_cancel, not admin_invoice_edit
    # Verify that admin_invoice_edit alone does NOT grant cancel.
    # -------------------------------------------------------------------------

    def test_cancel_requires_cancel_key_not_edit_key(self):
        _grant(self.company, self.operator, "admin_invoice_edit")
        resp = self._post_as_operator(self.draft_invoice, {"cancel_invoice": "1"})
        self.assertEqual(resp.status_code, 403)
