"""
TASK-010B-1 — is_technician_wage_applicable flag on OrderItemDefinition.

Tests:
 1.  Default is False.
 2.  NUMBER item can be wage-applicable.
 3.  Non-NUMBER items cannot be wage-applicable (model clean() raises).
 4.  Admin can create NUMBER item with wage-applicable=True via POST.
 5.  Admin cannot create MONEY item with wage-applicable=True via POST.
 6.  Admin cannot create TEXT item with wage-applicable=True.
 7.  Admin cannot create BOOL item with wage-applicable=True.
 8.  Admin can edit NUMBER item and enable wage-applicable.
 9.  Changing wage-applicable NUMBER item kind to MONEY is rejected unless flag cleared.
10.  Existing is_active and other fields unaffected by the new field.
11.  Multi-tenant: admin cannot modify other company's items.
"""
import itertools

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.orders.models import OrderItemDefinition
from apps.tenants.models import Company, CompanyServiceCategory

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    tag = _n()
    return Company.objects.create(
        name=f"WageFlag Co {tag}",
        code=f"wfco{tag}",
        slug=f"wageflag-{tag}",
        is_active=True,
    )


def _admin(company):
    return CompanyUser.objects.create_user(
        username=f"admin{_n()}",
        password="testpass123",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _category(company):
    return CompanyServiceCategory.objects.create(
        company=company,
        title=f"Cat {_n()}",
        is_active=True,
    )


def _item(company, category=None, kind=OrderItemDefinition.Kind.NUMBER,
          is_wage_applicable=False):
    cat = category or _category(company)
    return OrderItemDefinition.objects.create(
        company=company,
        category=cat,
        title=f"Item {_n()}",
        kind=kind,
        is_technician_wage_applicable=is_wage_applicable,
    )


# ---------------------------------------------------------------------------
# Model-level tests
# ---------------------------------------------------------------------------

class WageApplicableModelTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.category = _category(self.company)

    def test_1_default_is_false(self):
        """Test 1: Default is_technician_wage_applicable is False."""
        item = _item(self.company, category=self.category)
        self.assertFalse(item.is_technician_wage_applicable)

    def test_2_number_item_can_be_wage_applicable(self):
        """Test 2: NUMBER item can have is_technician_wage_applicable=True."""
        item = OrderItemDefinition(
            company=self.company,
            category=self.category,
            title="نصب پکیج",
            kind=OrderItemDefinition.Kind.NUMBER,
            is_technician_wage_applicable=True,
        )
        item.full_clean()  # must not raise
        item.save()
        self.assertTrue(item.is_technician_wage_applicable)

    def test_3_money_item_cannot_be_wage_applicable(self):
        """Test 3: MONEY item with is_technician_wage_applicable=True raises ValidationError."""
        item = OrderItemDefinition(
            company=self.company,
            category=self.category,
            title="هزینه اضافی",
            kind=OrderItemDefinition.Kind.MONEY,
            is_technician_wage_applicable=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("is_technician_wage_applicable", ctx.exception.message_dict)

    def test_3b_text_item_cannot_be_wage_applicable(self):
        """TEXT item with wage_applicable=True raises ValidationError."""
        item = OrderItemDefinition(
            company=self.company,
            category=self.category,
            title="آدرس",
            kind=OrderItemDefinition.Kind.TEXT,
            is_technician_wage_applicable=True,
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_3c_bool_item_cannot_be_wage_applicable(self):
        """BOOL item with wage_applicable=True raises ValidationError."""
        item = OrderItemDefinition(
            company=self.company,
            category=self.category,
            title="تأیید ضمانت",
            kind=OrderItemDefinition.Kind.BOOL,
            is_technician_wage_applicable=True,
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_10_existing_fields_unaffected(self):
        """Test 10: is_active, sort_order, title still work independently."""
        item = _item(self.company, category=self.category, kind=OrderItemDefinition.Kind.TEXT)
        item.is_active = False
        item.sort_order = 5
        item.save(update_fields=["is_active", "sort_order", "updated_at"])
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        self.assertEqual(item.sort_order, 5)
        self.assertFalse(item.is_technician_wage_applicable)  # unchanged


# ---------------------------------------------------------------------------
# Admin UI tests (POST create / edit)
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class WageApplicableAdminUITest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin_user = _admin(self.company)
        self.category = _category(self.company)
        self.client.login(username=self.admin_user.username, password="testpass123")
        self.create_url = f"/{self.company.code}/admin/base-data/items/create/"
        self.list_url = f"/{self.company.code}/admin/base-data/items/"

    def _post_create(self, kind, wage_applicable=False, title=None):
        data = {
            "category_id": self.category.id,
            "title": title or f"آیتم {_n()}",
            "kind": kind,
            "sort_order": "0",
            "is_active": "on",
        }
        if wage_applicable:
            data["is_technician_wage_applicable"] = "on"
        return self.client.post(self.create_url, data)

    def _post_edit(self, item, kind, wage_applicable=False):
        url = f"/{self.company.code}/admin/base-data/items/{item.id}/edit/"
        data = {
            "category_id": self.category.id,
            "title": item.title,
            "kind": kind,
            "sort_order": str(item.sort_order),
            "is_active": "on" if item.is_active else "",
        }
        if wage_applicable:
            data["is_technician_wage_applicable"] = "on"
        return self.client.post(url, data)

    def test_4_admin_can_create_number_item_wage_applicable(self):
        """Test 4: Admin creates NUMBER item with wage-applicable=True — saved."""
        response = self._post_create(kind="number", wage_applicable=True, title="نصب پکیج")
        self.assertEqual(response.status_code, 302, response.content.decode()[:300])
        item = OrderItemDefinition.objects.filter(
            company=self.company, title="نصب پکیج"
        ).first()
        self.assertIsNotNone(item)
        self.assertTrue(item.is_technician_wage_applicable)

    def test_5_admin_cannot_create_money_item_wage_applicable(self):
        """Test 5: MONEY item with wage-applicable=True is rejected."""
        title = f"هزینه {_n()}"
        response = self._post_create(kind="money", wage_applicable=True, title=title)
        self.assertEqual(response.status_code, 200)
        self.assertIn("عدد", response.content.decode())
        self.assertFalse(
            OrderItemDefinition.objects.filter(company=self.company, title=title).exists()
        )

    def test_6_admin_cannot_create_text_item_wage_applicable(self):
        """Test 6: TEXT item with wage-applicable=True is rejected."""
        title = f"آدرس {_n()}"
        response = self._post_create(kind="text", wage_applicable=True, title=title)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            OrderItemDefinition.objects.filter(company=self.company, title=title).exists()
        )

    def test_7_admin_cannot_create_bool_item_wage_applicable(self):
        """Test 7: BOOL item with wage-applicable=True is rejected."""
        title = f"تأیید {_n()}"
        response = self._post_create(kind="bool", wage_applicable=True, title=title)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            OrderItemDefinition.objects.filter(company=self.company, title=title).exists()
        )

    def test_4b_admin_can_create_number_item_without_wage_flag(self):
        """NUMBER item without wage flag defaults to False."""
        title = f"تعداد {_n()}"
        response = self._post_create(kind="number", wage_applicable=False, title=title)
        self.assertEqual(response.status_code, 302)
        item = OrderItemDefinition.objects.filter(company=self.company, title=title).first()
        self.assertIsNotNone(item)
        self.assertFalse(item.is_technician_wage_applicable)

    def test_8_admin_can_edit_number_item_to_enable_wage_applicable(self):
        """Test 8: Editing NUMBER item to enable wage-applicable works."""
        item = _item(self.company, category=self.category,
                     kind=OrderItemDefinition.Kind.NUMBER, is_wage_applicable=False)
        response = self._post_edit(item, kind="number", wage_applicable=True)
        self.assertEqual(response.status_code, 302, response.content.decode()[:300])
        item.refresh_from_db()
        self.assertTrue(item.is_technician_wage_applicable)

    def test_9_changing_wage_applicable_number_to_money_rejected(self):
        """Test 9: Changing a wage-applicable NUMBER item to MONEY is rejected."""
        item = _item(self.company, category=self.category,
                     kind=OrderItemDefinition.Kind.NUMBER, is_wage_applicable=True)
        # Try to change kind to MONEY while keeping wage_applicable=True
        response = self._post_edit(item, kind="money", wage_applicable=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("عدد", response.content.decode())
        item.refresh_from_db()
        # Should still be NUMBER and still wage-applicable
        self.assertEqual(item.kind, OrderItemDefinition.Kind.NUMBER)
        self.assertTrue(item.is_technician_wage_applicable)

    def test_9b_changing_to_money_with_flag_cleared_accepted(self):
        """Changing kind to MONEY is OK if wage_applicable is unchecked."""
        item = _item(self.company, category=self.category,
                     kind=OrderItemDefinition.Kind.NUMBER, is_wage_applicable=True)
        response = self._post_edit(item, kind="money", wage_applicable=False)
        self.assertEqual(response.status_code, 302, response.content.decode()[:300])
        item.refresh_from_db()
        self.assertEqual(item.kind, OrderItemDefinition.Kind.MONEY)
        self.assertFalse(item.is_technician_wage_applicable)

    def test_11_multi_tenant_other_company_item_inaccessible(self):
        """Test 11: Admin cannot edit another company's item."""
        other_co = _company()
        other_cat = _category(other_co)
        other_item = _item(other_co, category=other_cat, kind=OrderItemDefinition.Kind.NUMBER)
        url = f"/{self.company.code}/admin/base-data/items/{other_item.id}/edit/"
        data = {
            "category_id": self.category.id,
            "title": other_item.title,
            "kind": "number",
            "sort_order": "0",
            "is_active": "on",
            "is_technician_wage_applicable": "on",
        }
        response = self.client.post(url, data)
        # Should 404 — item not found for this company
        self.assertEqual(response.status_code, 404)
        other_item.refresh_from_db()
        self.assertFalse(other_item.is_technician_wage_applicable)
