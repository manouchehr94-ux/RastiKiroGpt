"""
Fix 3: payment_source consistency in technician cash payment.

Before fix: technician_invoice_mark_cash_paid set technician_id in metadata
            but did NOT set payment_source.
After fix:  payment_source = "CASH_RECEIVED_BY_TECHNICIAN" is also set,
            matching the admin-registered technician-cash path.

Ledger behavior guard:
  _payment_collected_by_technician() checks metadata.get("technician_id") OR
  metadata.get("payment_source") == "CASH_RECEIVED_BY_TECHNICIAN".
  Both paths were already sufficient; Fix 3 adds payment_source without removing
  technician_id, so the ledger DEBIT condition is still satisfied.

Tests verify:
- After technician POST to cash-paid, Payment.metadata contains payment_source.
- Payment.metadata still contains technician_id (preserved field).
- Invoice status is PAID after the call.
"""
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.tenants.models import Company


_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"fix3{_seq}"
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _technician_user(company):
    global _seq
    _seq += 1
    user = CompanyUser.objects.create_user(
        username=f"tech_{_seq}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    tech = Technician.objects.create(company=company, user=user, is_available=True)
    return user, tech


def _order(company, technician):
    global _seq
    _seq += 1
    return Order.objects.create(
        company=company,
        title=f"Order {_seq}",
        status=Order.Status.IN_PROGRESS,
        technician=technician,
    )


def _issued_invoice(company, order):
    global _seq
    _seq += 1
    return Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-FX3-{_seq:05d}",
        status=Invoice.Status.ISSUED,
        total_amount=150000,
        subtotal=150000,
        public_code=f"FX3{_seq:06d}",
        issued_at=timezone.now(),
    )


class TechnicianCashPaymentSourceTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech_user, self.technician = _technician_user(self.company)
        self.order = _order(self.company, self.technician)
        self.invoice = _issued_invoice(self.company, self.order)

    def _url(self):
        return f"/{self.company.code}/tech/invoices/{self.invoice.id}/cash-paid/"

    def _post(self):
        self.client.force_login(self.tech_user)
        return self.client.post(self._url())

    def test_payment_source_is_set_in_metadata(self):
        self._post()
        payment = Payment.objects.filter(
            company=self.company,
            invoice=self.invoice,
            status=Payment.Status.PAID,
        ).first()
        self.assertIsNotNone(payment, "No PAID Payment record created.")
        self.assertEqual(
            payment.metadata.get("payment_source"),
            "CASH_RECEIVED_BY_TECHNICIAN",
        )

    def test_technician_id_preserved_in_metadata(self):
        self._post()
        payment = Payment.objects.filter(
            company=self.company,
            invoice=self.invoice,
            status=Payment.Status.PAID,
        ).first()
        self.assertIsNotNone(payment)
        self.assertEqual(
            payment.metadata.get("technician_id"),
            self.technician.id,
        )

    def test_invoice_marked_paid(self):
        self._post()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    def test_ledger_debit_condition_satisfied(self):
        """
        _payment_collected_by_technician() must return True so the DEBIT entry
        can be written when wage > 0. Verify both conditions are present.
        """
        self._post()
        payment = Payment.objects.filter(
            company=self.company,
            invoice=self.invoice,
            status=Payment.Status.PAID,
        ).first()
        self.assertIsNotNone(payment)
        metadata = payment.metadata or {}
        # Either condition is sufficient for the ledger DEBIT.
        technician_id_present = bool(metadata.get("technician_id"))
        payment_source_match = metadata.get("payment_source") == "CASH_RECEIVED_BY_TECHNICIAN"
        self.assertTrue(
            technician_id_present or payment_source_match,
            "Neither ledger DEBIT condition is met in payment metadata.",
        )
        # After Fix 3, both must be present.
        self.assertTrue(technician_id_present, "technician_id missing from metadata.")
        self.assertTrue(payment_source_match, "payment_source missing or wrong in metadata.")
