"""
TASK-015 — Technician Service Rate Management UX Tests.

Covers:
  1.  JS duplicate-prevention script is present in technician form.
  2.  JS behavior present (client-side approach confirmed).
  3.  Backend duplicate validation still rejects duplicate POST.
  4.  Formset renders enough rows for all eligible NUMBER items.
  5.  Non-NUMBER items are not shown in the dropdown.
  6.  Inactive items are not shown for new rows.
  7.  Existing saved rate remains visible even if item is outside current categories.
  8.  Category filtering shows only items from tech's assigned categories.
  9.  Tech with no categories falls back to all company NUMBER items.
 10.  Overview page loads for company admin.
 11.  Overview page shows only current company rates.
 12.  Overview page filters by technician.
 13.  Overview page filters by service category.
 14.  Overview page filters by item definition.
 15.  Overview page filters by active status.
 16.  Overview page displays formatted positive, zero, and negative wage amounts.
 17.  Overview page includes edit technician link.
 18.  Unauthorized access (TECHNICIAN role) is blocked.
 19.  Existing technician create/edit tests still pass (smoke).
"""
import itertools
import re

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, Technician, TechnicianCategorySkill, UserRole
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
        name=name or f"UXTestCo {tag}",
        code=f"uxtc{tag}",
        slug=f"uxtestco-{tag}",
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


def _tech_user(company):
    return CompanyUser.objects.create_user(
        username=f"tech{_n()}",
        password="techpass123",
        company=company,
        role=UserRole.TECHNICIAN,
        phone=f"091{_n():08d}",
    )


def _technician(company):
    user = _tech_user(company)
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
        title=f"NumItem {_n()}",
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


def _rate(company, technician, item, wage=1_000_000, is_active=True):
    return TechnicianServiceRate.objects.create(
        company=company,
        technician=technician,
        item_definition=item,
        fixed_wage_rial=wage,
        is_active=is_active,
    )


def _management_form(total=1, initial=0, prefix="rates"):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def _base_create_post(company_code, username, phone_tag, item_id, wage):
    data = {
        "username": username,
        "phone": f"091{phone_tag:08d}",
        "first_name": "تست",
        "last_name": "نیرو",
        "is_available": "on",
        "service_wage_percent": "60",
        "goods_wage_percent": "10",
        "travel_wage_percent": "100",
        "rates-TOTAL_FORMS": "1",
        "rates-INITIAL_FORMS": "0",
        "rates-MIN_NUM_FORMS": "0",
        "rates-MAX_NUM_FORMS": "1000",
        "rates-0-item_definition": str(item_id),
        "rates-0-fixed_wage_rial": str(wage),
        "rates-0-is_active": "on",
    }
    return data


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class TechnicianFormUXTest(TestCase):
    """Tests for the technician create/edit form UX improvements."""

    def setUp(self):
        self.company = _company("Form UX Co")
        self.admin = _admin(self.company)
        self.tech = _technician(self.company)
        self.cat_a = _category(self.company)
        self.cat_b = _category(self.company)
        self.item_a = _number_item(self.company, category=self.cat_a)
        self.item_b = _number_item(self.company, category=self.cat_b)
        self.client.login(username=self.admin.username, password="testpass123")
        self.create_url = f"/{self.company.code}/admin/technicians/create/"
        self.edit_url = f"/{self.company.code}/admin/technicians/{self.tech.id}/edit/"

    def test_1_js_duplicate_prevention_script_present(self):
        """Test 1: syncItemDropdowns JS function is present in the technician form."""
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("syncItemDropdowns", content)

    def test_2_js_listens_for_item_definition_change(self):
        """Test 2: JS script targets item_definition selects for change events."""
        response = self.client.get(self.create_url)
        content = response.content.decode()
        self.assertIn("item_definition", content)
        self.assertIn("change", content)

    def test_3_backend_duplicate_still_rejected(self):
        """Test 3: Backend validation still rejects duplicate item in same POST."""
        tag = _n()
        data = _base_create_post(self.company.code, f"duptech{tag}", tag, self.item_a.id, 1_000_000)
        data["rates-TOTAL_FORMS"] = "2"
        data["rates-1-item_definition"] = str(self.item_a.id)
        data["rates-1-fixed_wage_rial"] = "2000000"
        data["rates-1-is_active"] = "on"
        response = self.client.post(self.create_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("تکراری", response.content.decode())

    def test_4_formset_renders_enough_rows_for_eligible_items(self):
        """Test 4: Create page renders at least as many rows as eligible NUMBER items."""
        # Currently 2 items exist (item_a, item_b); add 3 more
        for _ in range(3):
            _number_item(self.company)
        total_items = OrderItemDefinition.objects.filter(
            company=self.company, kind=OrderItemDefinition.Kind.NUMBER, is_active=True
        ).count()

        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        match = re.search(r'name="rates-TOTAL_FORMS"[^>]*value="(\d+)"', content)
        if not match:
            match = re.search(r'value="(\d+)"[^>]*name="rates-TOTAL_FORMS"', content)
        self.assertIsNotNone(match, "TOTAL_FORMS not found in management form")
        total_forms = int(match.group(1))
        self.assertGreaterEqual(total_forms, total_items)

    def test_5_non_number_items_not_in_dropdown(self):
        """Test 5: MONEY items are not shown in item_definition dropdown."""
        money = _money_item(self.company, category=self.cat_a)
        response = self.client.get(self.create_url)
        content = response.content.decode()
        self.assertNotIn(money.title, content)

    def test_6_inactive_items_not_shown_for_new_rows(self):
        """Test 6: Inactive items are not shown in dropdown (no existing rate for them)."""
        inactive = _number_item(self.company, is_active=False)
        response = self.client.get(self.create_url)
        content = response.content.decode()
        self.assertNotIn(inactive.title, content)

    def test_7_existing_rate_visible_despite_category_filter(self):
        """Test 7: Existing rate is visible even if its item is outside tech's categories."""
        # Assign tech to cat_a only
        TechnicianCategorySkill.objects.create(
            technician=self.tech, category=self.cat_a, priority=1
        )
        # Save a rate for item_b (which is in cat_b — NOT the tech's category)
        _rate(self.company, self.tech, self.item_b, wage=999_000)

        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # item_b should appear because it has an existing rate
        self.assertIn(self.item_b.title, content)

    def test_8_category_filtering_applied_when_categories_assigned(self):
        """Test 8: Only items from tech's assigned categories appear (plus existing rates)."""
        TechnicianCategorySkill.objects.create(
            technician=self.tech, category=self.cat_a, priority=1
        )
        # item_a is in cat_a (tech's category) — should appear
        # item_b is in cat_b (not tech's category) — should NOT appear

        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.item_a.title, content)
        self.assertNotIn(self.item_b.title, content)

    def test_9_no_categories_falls_back_to_company_wide(self):
        """Test 9: Tech with no categories assigned shows all company NUMBER items."""
        # self.tech has no TechnicianCategorySkill rows
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.item_a.title, content)
        self.assertIn(self.item_b.title, content)


@override_settings(ROOT_URLCONF="config.urls")
class TechnicianRateOverviewTest(TestCase):
    """Tests for the rate overview page."""

    def setUp(self):
        self.company = _company("Overview Co")
        self.admin = _admin(self.company)
        self.tech1 = _technician(self.company)
        self.tech2 = _technician(self.company)
        self.cat = _category(self.company)
        self.item1 = _number_item(self.company, category=self.cat)
        self.item2 = _number_item(self.company, category=self.cat)
        self.rate1 = _rate(self.company, self.tech1, self.item1, wage=4_000_000, is_active=True)
        self.rate2 = _rate(self.company, self.tech2, self.item2, wage=-500_000, is_active=False)
        self.client.login(username=self.admin.username, password="testpass123")
        self.url = f"/{self.company.code}/admin/technicians/rates/"

    def test_10_overview_page_loads(self):
        """Test 10: Overview page returns 200 for company admin."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("مدیریت تعرفه اجرت", content)

    def test_11_overview_shows_only_current_company(self):
        """Test 11: Overview shows only rates for the current company."""
        other_co = _company("Other Overview Co")
        other_tech = _technician(other_co)
        other_item = _number_item(other_co)
        _rate(other_co, other_tech, other_item, wage=9_000_000)

        response = self.client.get(self.url)
        content = response.content.decode()
        # Other company's rate must not appear (check via technician name)
        other_name = other_tech.user.get_full_name() or other_tech.user.username
        self.assertNotIn(other_name, content)

    def test_12_filter_by_technician(self):
        """Test 12: Filtering by technician_id shows only that technician's rates."""
        # rate1 = tech1/item1/4,000,000 ; rate2 = tech2/item2/-500,000
        # Item titles also appear in the filter dropdowns, so we discriminate by amount.
        response = self.client.get(self.url, {"technician_id": self.tech1.id})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("4,000,000", content)    # tech1's rate in table
        self.assertNotIn("-500,000", content)  # tech2's rate not in table

    def test_13_filter_by_category(self):
        """Test 13: Filtering by category_id shows only rates for items in that category."""
        other_cat = _category(self.company)
        other_item = _number_item(self.company, category=other_cat)
        _rate(self.company, self.tech1, other_item, wage=7_777_777)

        # Filter by self.cat → rate1 (4,000,000) and rate2 (-500,000) visible
        response = self.client.get(self.url, {"category_id": self.cat.id})
        content = response.content.decode()
        self.assertIn("4,000,000", content)
        self.assertIn("-500,000", content)
        # other_cat rate not visible in table (unique amount 7,777,777)
        self.assertNotIn("7,777,777", content)

    def test_14_filter_by_item(self):
        """Test 14: Filtering by item_id shows only rates for that item."""
        # rate1 = item1/4,000,000 ; rate2 = item2/-500,000
        response = self.client.get(self.url, {"item_id": self.item1.id})
        content = response.content.decode()
        self.assertIn("4,000,000", content)    # item1's rate in table
        self.assertNotIn("-500,000", content)  # item2's rate not in table

    def test_15_filter_by_active_status(self):
        """Test 15: Filter active=true shows only active rates (rate1=4,000,000 active)."""
        response = self.client.get(self.url, {"active": "true"})
        content = response.content.decode()
        self.assertIn("4,000,000", content)    # rate1 (active) in table
        self.assertNotIn("-500,000", content)  # rate2 (inactive) not in table

    def test_15b_filter_inactive(self):
        """Test 15b: Filter active=false shows only inactive rates (rate2=-500,000)."""
        response = self.client.get(self.url, {"active": "false"})
        content = response.content.decode()
        self.assertNotIn("4,000,000", content)  # rate1 (active) not in table
        self.assertIn("-500,000", content)       # rate2 (inactive) in table

    def test_16_formatted_wage_amounts(self):
        """Test 16: Positive and negative wages are displayed with thousand separators."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("4,000,000", content)
        self.assertIn("-500,000", content)

    def test_17_edit_technician_link_present(self):
        """Test 17: Each row includes a link to edit the technician."""
        response = self.client.get(self.url)
        content = response.content.decode()
        edit_link = f"/admin/technicians/{self.tech1.id}/edit/"
        self.assertIn(edit_link, content)

    def test_18_technician_role_blocked(self):
        """Test 18: A user with TECHNICIAN role cannot access the overview page."""
        tech_user = _tech_user(self.company)
        self.client.logout()
        self.client.login(username=tech_user.username, password="techpass123")
        response = self.client.get(self.url)
        # Should be forbidden or redirect to login
        self.assertIn(response.status_code, [302, 403])

    def test_19_existing_create_edit_still_work(self):
        """Test 19: Technician create and edit pages still load correctly."""
        create_url = f"/{self.company.code}/admin/technicians/create/"
        edit_url = f"/{self.company.code}/admin/technicians/{self.tech1.id}/edit/"

        response_create = self.client.get(create_url)
        self.assertEqual(response_create.status_code, 200)
        self.assertIn("rates-TOTAL_FORMS", response_create.content.decode())

        response_edit = self.client.get(edit_url)
        self.assertEqual(response_edit.status_code, 200)
        self.assertIn("rates-TOTAL_FORMS", response_edit.content.decode())
