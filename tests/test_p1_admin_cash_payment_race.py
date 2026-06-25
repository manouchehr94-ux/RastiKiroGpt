"""
P1 fix: Admin cash payment race guard.

Before fix: Payment.objects.create() ran BEFORE Invoice row was locked,
            allowing a concurrent double-click to produce an orphaned
            Payment(status=PAID) with no settlement ledger entry.

After fix:  Both mark_paid_company_cash and mark_paid_technician_cash
            wrap the entire block in transaction.atomic() + select_for_update()
            on the Invoice row, then re-check status == ISSUED under the lock
            before creating the Payment.

Tests:
1. Company cash: ISSUED invoice is marked PAID; exactly one Payment row created.
2. Company cash: non-ISSUED invoice is rejected; zero Payment rows created.
3. Technician cash: ISSUED invoice is marked PAID; exactly one Payment row created.
4. Technician cash: non-ISSUED invoice is rejected; zero Payment rows created.
5. Company cash: second call on already-PAID invoice is rejected; still only one Payment row.
6. Technician cash: second call on already-PAID invoice is rejected; still only one Payment row.
"""
import itertools

from django.test import RequestFactory, TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice
from apps.invoices.services import InvoiceCreateService
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.tenants.models import Company
from apps.tenants import views_admin


_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(code=f"ar{n}", name=f"AR Co {n}", slug=f"ar-co-{n}", is_active=True)


def _admin_user(company):
    n = _n()
    return CompanyUser.objects.create_user(
        username=f"adm{n}", password="pw", company=company, role=UserRole.COMPANY_ADMIN,
    )


def _technician(company):
    n = _n()
    user = CompanyUser.objects.create_user(
        username=f"tech{n}", password="pw", company=company, role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user, is_available=True)


def _order(company):
    n = _n()
    return Order.objects.create(company=company, title=f"Order {n}", status=Order.Status.IN_PROGRESS)


def _invoice(company, order, status=Invoice.Status.ISSUED):
    inv = InvoiceCreateService.create(
        company=company,
        order=order,
        items=[{"description": "Service", "quantity": 1, "unit_price": 100_000, "discount_amount": 0}],
    )
    if status != Invoice.Status.DRAFT:
        Invoice.objects.filter(pk=inv.pk).update(status=status)
        inv.refresh_from_db()
    return inv


def _post(company, admin_user, invoice_id, action):
    rf = RequestFactory()
    req = rf.post("/fake/", {action: "1"})
    req.company = company
    req.user = admin_user
    return views_admin.admin_invoice_detail(req, invoice_id=invoice_id)


# ---------------------------------------------------------------------------
# Company cash
# ---------------------------------------------------------------------------

class AdminCompanyCashPaymentTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin_user(self.company)
        self.order = _order(self.company)

    def test_issued_invoice_is_marked_paid(self):
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_company_cash")
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.PAID)

    def test_exactly_one_payment_row_created(self):
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_company_cash")
        count = Payment.objects.filter(invoice=inv).count()
        self.assertEqual(count, 1)

    def test_payment_source_is_company_cash(self):
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_company_cash")
        p = Payment.objects.get(invoice=inv)
        self.assertEqual(p.metadata.get("payment_source"), "CASH_RECEIVED_BY_COMPANY")

    def test_draft_invoice_rejected_no_payment_created(self):
        inv = _invoice(self.company, self.order, Invoice.Status.DRAFT)
        _post(self.company, self.admin, inv.id, "mark_paid_company_cash")
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.DRAFT)
        self.assertEqual(Payment.objects.filter(invoice=inv).count(), 0)

    def test_already_paid_invoice_rejected_no_extra_payment(self):
        """Second call on a PAID invoice must not create an extra Payment row."""
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_company_cash")
        # Second call — simulates admin double-click or stale page re-submit.
        _post(self.company, self.admin, inv.id, "mark_paid_company_cash")
        self.assertEqual(Payment.objects.filter(invoice=inv).count(), 1)


# ---------------------------------------------------------------------------
# Technician cash
# ---------------------------------------------------------------------------

class AdminTechnicianCashPaymentTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin_user(self.company)
        self.tech = _technician(self.company)
        self.order = _order(self.company)
        self.order.technician = self.tech
        self.order.save(update_fields=["technician"])

    def test_issued_invoice_is_marked_paid(self):
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_technician_cash")
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.PAID)

    def test_exactly_one_payment_row_created(self):
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_technician_cash")
        count = Payment.objects.filter(invoice=inv).count()
        self.assertEqual(count, 1)

    def test_payment_source_is_technician_cash(self):
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_technician_cash")
        p = Payment.objects.get(invoice=inv)
        self.assertEqual(p.metadata.get("payment_source"), "CASH_RECEIVED_BY_TECHNICIAN")

    def test_technician_id_stored_in_metadata(self):
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_technician_cash")
        p = Payment.objects.get(invoice=inv)
        self.assertEqual(p.metadata.get("technician_id"), self.tech.id)

    def test_draft_invoice_rejected_no_payment_created(self):
        inv = _invoice(self.company, self.order, Invoice.Status.DRAFT)
        _post(self.company, self.admin, inv.id, "mark_paid_technician_cash")
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.DRAFT)
        self.assertEqual(Payment.objects.filter(invoice=inv).count(), 0)

    def test_already_paid_invoice_rejected_no_extra_payment(self):
        """Second call on a PAID invoice must not create an extra Payment row."""
        inv = _invoice(self.company, self.order, Invoice.Status.ISSUED)
        _post(self.company, self.admin, inv.id, "mark_paid_technician_cash")
        _post(self.company, self.admin, inv.id, "mark_paid_technician_cash")
        self.assertEqual(Payment.objects.filter(invoice=inv).count(), 1)
