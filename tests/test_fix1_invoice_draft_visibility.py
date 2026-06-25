"""
Fix 1: DRAFT invoices must not be visible on the company public invoice URL.

Before fix: public_invoice_detail only blocked CANCELLED.
After fix:  public_invoice_detail blocks both DRAFT and CANCELLED.

The short /i/<code>/ URL already blocked DRAFT correctly — that is not changed.

Tests cover:
- DRAFT  → 404 on company public URL (new behaviour)
- ISSUED → 200 on company public URL
- PAID   → 200 on company public URL
- CANCELLED → 404 on company public URL (pre-existing behaviour)
"""
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, UserRole
from apps.invoices.models import Invoice
from apps.tenants.models import Company


_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"fix1{_seq}"
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _invoice(company, status, public_code=None):
    global _seq
    _seq += 1
    if public_code is None:
        public_code = f"PUB{_seq:06d}"
    return Invoice.objects.create(
        company=company,
        invoice_number=f"INV-FX1-{_seq:05d}",
        status=status,
        total_amount=100000,
        subtotal=100000,
        public_code=public_code,
        issued_at=timezone.now() if status in (Invoice.Status.ISSUED, Invoice.Status.PAID) else None,
        paid_at=timezone.now() if status == Invoice.Status.PAID else None,
        settled_at=timezone.now() if status == Invoice.Status.PAID else None,
    )


class PublicInvoiceDetailDraftVisibilityTest(TestCase):

    def setUp(self):
        self.company = _company()

    def _url(self, public_code):
        return f"/{self.company.code}/invoices/public/{public_code}/"

    def test_draft_invoice_returns_404(self):
        invoice = _invoice(self.company, Invoice.Status.DRAFT)
        resp = self.client.get(self._url(invoice.public_code))
        self.assertEqual(resp.status_code, 404)

    def test_issued_invoice_returns_200(self):
        invoice = _invoice(self.company, Invoice.Status.ISSUED)
        resp = self.client.get(self._url(invoice.public_code))
        self.assertEqual(resp.status_code, 200)

    def test_paid_invoice_returns_200(self):
        invoice = _invoice(self.company, Invoice.Status.PAID)
        resp = self.client.get(self._url(invoice.public_code))
        self.assertEqual(resp.status_code, 200)

    def test_cancelled_invoice_returns_404(self):
        invoice = _invoice(self.company, Invoice.Status.CANCELLED)
        resp = self.client.get(self._url(invoice.public_code))
        self.assertEqual(resp.status_code, 404)
