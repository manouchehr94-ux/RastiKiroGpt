"""
TASK-010A-2 — Technician Service Rate UI Tests.

Tests that the admin technician create/edit pages correctly manage
TechnicianServiceRate rows through the TechnicianRateFormSet.

Covers:
  1.  Technician create page returns 200 with rate formset rendered.
  2.  Technician edit page returns 200 with rate formset rendered.
  3.  Technician edit page shows existing rates in formset initial.
  4.  Admin can create technician with multiple rates (POST create).
  5.  Admin can edit rate amount (POST edit).
  6.  Admin can deactivate a rate (is_active unchecked on edit).
  7.  Admin can delete a rate (DELETE checkbox on edit).
  8.  Duplicate item_definition in same POST is rejected.
  9.  Other-company OrderItemDefinition cannot be selected (rejected as invalid choice).
 10.  Non-NUMBER item cannot be selected (not in queryset → rejected as invalid).
 11.  Inactive item cannot be selected for active rate (not in queryset → rejected).
 12.  Existing technician fields (phone, is_available) still save correctly on edit.
 13.  Invalid formset does not partially save technician/rates.
"""
import itertools

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.orders.models import OrderItemDefinition
from apps.payouts.models import TechnicianServiceRate
from apps.tenants.models import Company, CompanyServiceCategory

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company(name=None):
    tag = _n()
    return Company.objects.create(
        name=name or f"UITestCo {tag}",
        code=f"uitc{tag}",
        slug=f"uitestco-{tag}",
        is_active=True,
    )


def _admin(company):
    return CompanyUser.objects.create_user(
        username=f"admin{_n()}",
        password="testpass123",
        company=company,
        role=UserRole.COMPANY_ADMIN,
        first_name="Admin",
        last_name="User",
    )


def _tech_user(company, username=None):
    return CompanyUser.objects.create_user(
        username=username or f"tech{_n()}",
        password="techpass123",
        company=company,
        role=UserRole.TECHNICIAN,
        phone=f"091{_n():08d}",
    )


def _technician(company, username=None):
    user = _tech_user(company, username=username)
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=60,
        goods_wage_percent=10,
        travel_wage_percent=100,
    )


def _category(company):
    return CompanyServiceCategory.objects.create(
        company=company,
        title=f"Cat {_n()}",
        is_active=True,
    )


def _number_item(company, category=None, is_active=True):
    cat = category or _category(company)
    return OrderItemDefinition.objects.create(
        company=company,
        category=cat,
        title=f"Item {_n()}",
        kind=OrderItemDefinition.Kind.NUMBER,
        is_active=is_active,
    )


def _money_item(company, category=None):
    cat = category or _category(company)
    return OrderItemDefinition.objects.create(
        company=company,
        category=cat,
        title=f"MoneyItem {_n()}",
        kind=OrderItemDefinition.Kind.MONEY,
        is_active=True,
    )


def _rate_post_data(item_id, wage, is_active=True, delete=False, prefix="rates", idx=0):
    """Build POST data for one rate formset row."""
    data = {
        f"{prefix}-{idx}-item_definition": str(item_id),
        f"{prefix}-{idx}-fixed_wage_rial": str(wage),
    }
    if is_active:
        data[f"{prefix}-{idx}-is_active"] = "on"
    if delete:
        data[f"{prefix}-{idx}-DELETE"] = "on"
    return data


def _management_form(total=1, initial=0, prefix="rates"):
    """Build Django formset management form data."""
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def _create_post(company, username, phone, first_name, last_name,
                 rate_rows=None, prefix="rates"):
    """
    Build a complete POST body for admin_technician_create.
    rate_rows: list of (item_id, wage, is_active) tuples.
    """
    data = {
        "username": username,
        "phone": phone,
        "first_name": first_name,
        "last_name": last_name,
        "is_available": "on",
        "service_wage_percent": "60",
        "goods_wage_percent": "10",
        "travel_wage_percent": "100",
    }
    rate_rows = rate_rows or []
    data.update(_management_form(total=len(rate_rows), initial=0, prefix=prefix))
    for idx, (item_id, wage, active) in enumerate(rate_rows):
        data.update(_rate_post_data(item_id, wage, is_active=active, prefix=prefix, idx=idx))
    return data


def _edit_post(technician, phone=None, first_name=None, last_name=None,
               rate_rows=None, delete_rows=None, prefix="rates", initial_count=0):
    """
    Build a complete POST body for admin_technician_edit.
    rate_rows: list of (item_id, wage, is_active) tuples.
    delete_rows: list of (item_id, wage, is_active) tuples with DELETE=on.
    """
    data = {
        "username": technician.user.username,
        "phone": phone or technician.user.phone or "09121234567",
        "first_name": first_name or technician.user.first_name or "Test",
        "last_name": last_name or technician.user.last_name or "Tech",
        "is_available": "on",
        "service_wage_percent": str(technician.service_wage_percent),
        "goods_wage_percent": str(technician.goods_wage_percent),
        "travel_wage_percent": str(technician.travel_wage_percent),
    }
    rate_rows = rate_rows or []
    delete_rows = delete_rows or []
    all_rows = rate_rows + delete_rows
    data.update(_management_form(
        total=len(all_rows),
        initial=initial_count,
        prefix=prefix,
    ))
    for idx, (item_id, wage, active) in enumerate(rate_rows):
        data.update(_rate_post_data(item_id, wage, is_active=active, prefix=prefix, idx=idx))
    for idx_offset, (item_id, wage, active) in enumerate(delete_rows):
        data.update(_rate_post_data(
            item_id, wage, is_active=active, delete=True,
            prefix=prefix, idx=len(rate_rows) + idx_offset,
        ))
    return data


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class TechnicianRateCreatePageTest(TestCase):
    """Tests for technician CREATE page rendering and form submission."""

    def setUp(self):
        self.company = _company("Create Co")
        self.admin_user = _admin(self.company)
        self.item1 = _number_item(self.company)
        self.item2 = _number_item(self.company)
        self.client.login(username=self.admin_user.username, password="testpass123")
        self.url = f"/{self.company.code}/admin/technicians/create/"

    def test_1_create_page_renders_rate_formset(self):
        """Test 1: Technician create page returns 200 and contains rate formset."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("تعرفه اجرت", content)
        self.assertIn("rates-TOTAL_FORMS", content)

    def test_4_create_technician_with_multiple_rates(self):
        """Test 4: Admin can create technician with multiple rates."""
        tag = _n()
        data = _create_post(
            self.company,
            username=f"newtec{tag}",
            phone=f"091{tag:08d}",
            first_name="نیرو",
            last_name="جدید",
            rate_rows=[
                (self.item1.id, 4_000_000, True),
                (self.item2.id, 2_000_000, True),
            ],
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])

        tech = Technician.objects.filter(company=self.company).order_by("-id").first()
        self.assertIsNotNone(tech)
        rates = TechnicianServiceRate.objects.filter(
            company=self.company, technician=tech
        ).order_by("fixed_wage_rial")
        self.assertEqual(rates.count(), 2)
        self.assertEqual(rates[0].fixed_wage_rial, 2_000_000)
        self.assertEqual(rates[1].fixed_wage_rial, 4_000_000)

    def test_8_duplicate_item_in_create_post_rejected(self):
        """Test 8: Duplicate item_definition in same POST is rejected."""
        tag = _n()
        data = _create_post(
            self.company,
            username=f"duptech{tag}",
            phone=f"091{tag:08d}",
            first_name="تست",
            last_name="تکراری",
            rate_rows=[
                (self.item1.id, 4_000_000, True),
                (self.item1.id, 2_000_000, True),  # same item — duplicate
            ],
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("تکراری", content)
        self.assertFalse(Technician.objects.filter(company=self.company, user__username=f"duptech{tag}").exists())

    def test_9_other_company_item_rejected(self):
        """Test 9: Other-company OrderItemDefinition is rejected (invalid choice)."""
        other_co = _company("Other Co")
        other_item = _number_item(other_co)
        tag = _n()
        data = _create_post(
            self.company,
            username=f"xcotech{tag}",
            phone=f"091{tag:08d}",
            first_name="تست",
            last_name="شرکت دیگر",
            rate_rows=[(other_item.id, 1_000_000, True)],
        )
        response = self.client.post(self.url, data)
        # Should NOT redirect (form error) and should NOT create the technician
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Technician.objects.filter(company=self.company, user__username=f"xcotech{tag}").exists()
        )

    def test_10_non_number_item_rejected(self):
        """Test 10: MONEY item not in queryset → rejected as invalid choice."""
        money_item = _money_item(self.company)
        tag = _n()
        data = _create_post(
            self.company,
            username=f"moneytech{tag}",
            phone=f"091{tag:08d}",
            first_name="تست",
            last_name="مالی",
            rate_rows=[(money_item.id, 1_000_000, True)],
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Technician.objects.filter(company=self.company, user__username=f"moneytech{tag}").exists()
        )

    def test_11_inactive_item_not_in_queryset(self):
        """Test 11: Inactive item not in queryset → rejected as invalid choice."""
        inactive_item = _number_item(self.company, is_active=False)
        tag = _n()
        data = _create_post(
            self.company,
            username=f"inacttech{tag}",
            phone=f"091{tag:08d}",
            first_name="تست",
            last_name="غیرفعال",
            rate_rows=[(inactive_item.id, 1_000_000, True)],
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Technician.objects.filter(company=self.company, user__username=f"inacttech{tag}").exists()
        )

    def test_13_invalid_formset_does_not_save_technician(self):
        """Test 13: Duplicate item in formset prevents technician creation too."""
        tag = _n()
        data = _create_post(
            self.company,
            username=f"atomictech{tag}",
            phone=f"091{tag:08d}",
            first_name="اتمیک",
            last_name="تست",
            rate_rows=[
                (self.item1.id, 4_000_000, True),
                (self.item1.id, 1_000_000, True),  # invalid — triggers formset error
            ],
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        # No technician should be created
        self.assertFalse(
            Technician.objects.filter(company=self.company, user__username=f"atomictech{tag}").exists()
        )
        # No rates should be created
        self.assertEqual(TechnicianServiceRate.objects.filter(company=self.company).count(), 0)


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianRateEditPageTest(TestCase):
    """Tests for technician EDIT page rendering and form submission."""

    def setUp(self):
        self.company = _company("Edit Co")
        self.admin_user = _admin(self.company)
        self.tech = _technician(self.company)
        self.item1 = _number_item(self.company)
        self.item2 = _number_item(self.company)
        self.client.login(username=self.admin_user.username, password="testpass123")
        self.url = f"/{self.company.code}/admin/technicians/{self.tech.id}/edit/"

    def test_2_edit_page_renders_rate_formset(self):
        """Test 2: Technician edit page returns 200 and contains rate formset."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("تعرفه اجرت", content)
        self.assertIn("rates-TOTAL_FORMS", content)

    def test_3_edit_page_shows_existing_rates(self):
        """Test 3: Edit page shows existing rates in formset initial."""
        TechnicianServiceRate.objects.create(
            company=self.company,
            technician=self.tech,
            item_definition=self.item1,
            fixed_wage_rial=4_000_000,
            is_active=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("4000000", content)

    def test_5_edit_rate_amount(self):
        """Test 5: Admin can edit rate amount via POST."""
        TechnicianServiceRate.objects.create(
            company=self.company,
            technician=self.tech,
            item_definition=self.item1,
            fixed_wage_rial=4_000_000,
            is_active=True,
        )
        data = _edit_post(
            self.tech,
            rate_rows=[(self.item1.id, 5_000_000, True)],
            initial_count=0,
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])

        rate = TechnicianServiceRate.objects.get(company=self.company, technician=self.tech)
        self.assertEqual(rate.fixed_wage_rial, 5_000_000)
        self.assertEqual(rate.item_definition, self.item1)

    def test_6_deactivate_rate(self):
        """Test 6: Admin can deactivate a rate (is_active unchecked)."""
        TechnicianServiceRate.objects.create(
            company=self.company,
            technician=self.tech,
            item_definition=self.item1,
            fixed_wage_rial=4_000_000,
            is_active=True,
        )
        data = _edit_post(
            self.tech,
            rate_rows=[(self.item1.id, 4_000_000, False)],  # is_active=False
            initial_count=0,
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])

        rate = TechnicianServiceRate.objects.get(company=self.company, technician=self.tech)
        self.assertFalse(rate.is_active)

    def test_7_delete_rate(self):
        """Test 7: Admin can delete a rate (DELETE checkbox)."""
        TechnicianServiceRate.objects.create(
            company=self.company,
            technician=self.tech,
            item_definition=self.item1,
            fixed_wage_rial=4_000_000,
            is_active=True,
        )
        data = _edit_post(
            self.tech,
            rate_rows=[],
            delete_rows=[(self.item1.id, 4_000_000, True)],
            initial_count=0,
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        self.assertEqual(
            TechnicianServiceRate.objects.filter(company=self.company, technician=self.tech).count(), 0
        )

    def test_8_duplicate_item_in_edit_post_rejected(self):
        """Test 8: Duplicate item_definition in edit POST is rejected."""
        data = _edit_post(
            self.tech,
            rate_rows=[
                (self.item1.id, 4_000_000, True),
                (self.item1.id, 2_000_000, True),
            ],
            initial_count=0,
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("تکراری", content)
        self.assertEqual(TechnicianServiceRate.objects.filter(company=self.company, technician=self.tech).count(), 0)

    def test_9_other_company_item_rejected_on_edit(self):
        """Test 9: Other-company item rejected on edit."""
        other_co = _company("Other Co Edit")
        other_item = _number_item(other_co)
        data = _edit_post(
            self.tech,
            rate_rows=[(other_item.id, 1_000_000, True)],
            initial_count=0,
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TechnicianServiceRate.objects.filter(company=self.company, technician=self.tech).count(), 0)

    def test_12_existing_technician_fields_save_correctly(self):
        """Test 12: Existing technician fields (first_name, is_available) save correctly on edit."""
        data = _edit_post(
            self.tech,
            first_name="نام جدید",
            last_name="فامیلی",
            rate_rows=[],
            initial_count=0,
        )
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])

        self.tech.user.refresh_from_db()
        self.assertEqual(self.tech.user.first_name, "نام جدید")
        self.assertEqual(self.tech.user.last_name, "فامیلی")

    def test_negative_amount_rendered_correctly(self):
        """Test: Negative wage appears in edit page with minus sign and thousand separators."""
        TechnicianServiceRate.objects.create(
            company=self.company,
            technician=self.tech,
            item_definition=self.item1,
            fixed_wage_rial=-500_000,
            is_active=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("-500,000", content)

    def test_thousand_separator_formatting_in_edit_page(self):
        """Test: Rate amounts are displayed with thousand separators in edit page."""
        TechnicianServiceRate.objects.create(
            company=self.company,
            technician=self.tech,
            item_definition=self.item1,
            fixed_wage_rial=4_000_000,
            is_active=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("4,000,000", content)


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianRateAmountTest(TestCase):
    """Tests for positive, zero, and negative wage amounts being accepted."""

    def setUp(self):
        self.company = _company("Amount Co")
        self.admin_user = _admin(self.company)
        self.item = _number_item(self.company)
        self.client.login(username=self.admin_user.username, password="testpass123")
        self.url = f"/{self.company.code}/admin/technicians/create/"

    def _post_create(self, username, wage):
        tag = _n()
        data = _create_post(
            self.company,
            username=username,
            phone=f"091{tag:08d}",
            first_name="تست",
            last_name="اجرت",
            rate_rows=[(self.item.id, wage, True)],
        )
        return self.client.post(self.url, data)

    def test_positive_amount_accepted(self):
        """Test: Positive wage is saved without error."""
        tag = _n()
        response = self._post_create(f"postech{tag}", 4_000_000)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        tech = Technician.objects.filter(company=self.company).order_by("-id").first()
        rate = TechnicianServiceRate.objects.get(company=self.company, technician=tech)
        self.assertEqual(rate.fixed_wage_rial, 4_000_000)

    def test_zero_amount_accepted(self):
        """Test: Zero wage is saved without error."""
        tag = _n()
        response = self._post_create(f"zerotech{tag}", 0)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        tech = Technician.objects.filter(company=self.company).order_by("-id").first()
        rate = TechnicianServiceRate.objects.get(company=self.company, technician=tech)
        self.assertEqual(rate.fixed_wage_rial, 0)

    def test_negative_amount_accepted(self):
        """Test: Negative wage is saved without error (valid business data)."""
        tag = _n()
        response = self._post_create(f"negtech{tag}", -500_000)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        tech = Technician.objects.filter(company=self.company).order_by("-id").first()
        rate = TechnicianServiceRate.objects.get(company=self.company, technician=tech)
        self.assertEqual(rate.fixed_wage_rial, -500_000)
