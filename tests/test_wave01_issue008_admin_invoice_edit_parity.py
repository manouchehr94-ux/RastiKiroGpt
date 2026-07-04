"""
EPIC-002 Wave 01, Issue 008: Admin invoice edit page must reach feature
parity with the technician invoice page.

Root cause: templates/tenants/admin_invoice_edit.html rendered a static,
fixed-row-count table with no add/remove-row controls, no live total
calculation, and no per-row service/goods type selector — even though the
backend (InvoiceUpdateService.update / InvoiceItemBulkService.replace_items,
apps/invoices/services.py) already fully supported an arbitrary number of
rows and a row_type per row (already used by the technician invoice-create
flow). This was purely a template/view-glue gap, not a missing business
capability.

Fix:
  - apps/tenants/views_admin.py::_parse_invoice_items_from_post now also
    reads item_row_type (POST.getlist), mapping "product" -> "goods" the
    same way apps/invoices/views_technician.py::technician_invoice_create
    already does. Falls back to "service" if absent (backward compatible).
  - templates/tenants/admin_invoice_edit.html: added a per-row type <select>,
    an add-row button using a <template>-clone pattern (same technique as
    templates/orders/technician_invoice_create.html), a per-row remove
    button, and a live totals summary block reusing the existing
    .detail-list/.detail-row markup already used on
    templates/payments/invoice_checkout.html.

No changes were made to InvoiceUpdateService, InvoiceItemBulkService, the
Invoice/InvoiceItem models, or any permission decorator.
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.invoices.services import InvoiceCreateService
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"Parity Co {n}", code=f"pc{n:03d}", slug=f"parity-co-{n}", is_active=True)


def _admin(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"pa{n}", password="testpass", company=company, role=UserRole.COMPANY_ADMIN)


def _technician(company):
    n = _n()
    user = CompanyUser.objects.create_user(username=f"pt{n}", password="testpass", company=company, role=UserRole.TECHNICIAN)
    return Technician.objects.create(company=company, user=user, is_available=True)


def _order(company, technician):
    n = _n()
    return Order.objects.create(company=company, title=f"Order {n}", status=Order.Status.IN_PROGRESS, technician=technician)


def _draft_invoice(company, order):
    return InvoiceCreateService.create(
        company=company, order=order,
        items=[{"description": "Service A", "quantity": 1, "unit_price": 100_000, "discount_amount": 0}],
    )


@override_settings(ROOT_URLCONF="config.urls")
class AdminInvoiceEditPageRendersNewControlsTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.order = _order(self.company, _technician(self.company))
        self.invoice = _draft_invoice(self.company, self.order)

    def _url(self):
        return f"/{self.company.code}/admin/invoices/{self.invoice.id}/edit/"

    def test_page_renders_row_type_select_and_add_row_button(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn('name="item_row_type"', content)
        self.assertIn('id="invoiceAddRowBtn"', content)
        self.assertIn('id="invoiceRowTemplate"', content)
        self.assertIn('data-remove-row', content)

    def test_page_renders_live_totals_summary_block(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        content = resp.content.decode("utf-8")
        self.assertIn('id="invoiceSumGross"', content)
        self.assertIn('id="invoiceSumRowDiscount"', content)
        self.assertIn('id="invoiceSumPayable"', content)

    def test_existing_row_type_is_preselected(self):
        InvoiceItem.objects.filter(invoice=self.invoice).update(row_type=InvoiceItem.RowType.GOODS)
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._url())
        content = resp.content.decode("utf-8")
        self.assertIn('<option value="product" selected>کالا</option>', content)


@override_settings(ROOT_URLCONF="config.urls")
class AdminInvoiceEditRowTypeSaveTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.order = _order(self.company, _technician(self.company))
        self.invoice = _draft_invoice(self.company, self.order)

    def _url(self):
        return f"/{self.company.code}/admin/invoices/{self.invoice.id}/edit/"

    def test_post_with_product_row_type_saves_as_goods(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.post(self._url(), {
            "item_description": ["Part X"],
            "item_quantity": ["2"],
            "item_unit_price": ["50000"],
            "item_discount_amount": ["0"],
            "item_row_type": ["product"],
            "tax_amount": ["0"],
            "discount_amount": ["0"],
        })
        self.assertEqual(resp.status_code, 302)
        item = InvoiceItem.objects.get(invoice=self.invoice)
        self.assertEqual(item.row_type, InvoiceItem.RowType.GOODS)

    def test_post_without_row_type_still_defaults_to_service(self):
        """Backward compatibility: a form submission with no item_row_type field must still work."""
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.post(self._url(), {
            "item_description": ["Service B"],
            "item_quantity": ["1"],
            "item_unit_price": ["70000"],
            "item_discount_amount": ["0"],
            "tax_amount": ["0"],
            "discount_amount": ["0"],
        })
        self.assertEqual(resp.status_code, 302)
        item = InvoiceItem.objects.get(invoice=self.invoice)
        self.assertEqual(item.row_type, InvoiceItem.RowType.SERVICE)

    def test_multiple_rows_with_mixed_types_all_saved(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.post(self._url(), {
            "item_description": ["Labor", "Part"],
            "item_quantity": ["1", "3"],
            "item_unit_price": ["100000", "20000"],
            "item_discount_amount": ["0", "0"],
            "item_row_type": ["service", "product"],
            "tax_amount": ["0"],
            "discount_amount": ["0"],
        })
        self.assertEqual(resp.status_code, 302)
        items = list(InvoiceItem.objects.filter(invoice=self.invoice).order_by("sort_order"))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].row_type, InvoiceItem.RowType.SERVICE)
        self.assertEqual(items[1].row_type, InvoiceItem.RowType.GOODS)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.DRAFT)
