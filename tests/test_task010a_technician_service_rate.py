"""
TASK-010A — TechnicianServiceRate Model Tests.

Covers:
  1. Can create TechnicianServiceRate for technician + NUMBER OrderItemDefinition.
  2. Duplicate rate for same company + technician + item_definition fails.
  3. Same item_definition can have different rates for different technicians.
  4. Same technician can have rates for multiple item_definitions.
  5. Cross-company technician is rejected by clean().
  6. Cross-company item_definition is rejected by clean().
  7. Non-NUMBER item_definition is rejected by clean().
  8. Negative fixed_wage_rial is rejected by full_clean().
  9. Inactive item_definition is rejected for active rate by clean().
 10. Inactive rate (is_active=False) can be saved regardless of definition state.
 11. __str__ contains technician name, item title, and amount.
 12. Migration applies cleanly (verified by test runner using --keepdb or fresh DB).
"""
import itertools

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

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
        name=name or f"TestCo {tag}",
        code=f"tc{tag}",
        slug=f"testco-{tag}",
        is_active=True,
    )


def _technician(company):
    user = CompanyUser.objects.create_user(
        username=f"tech{_n()}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
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
        title=f"Number Item {_n()}",
        kind=OrderItemDefinition.Kind.NUMBER,
        is_active=is_active,
    )


def _money_item(company, category=None):
    cat = category or _category(company)
    return OrderItemDefinition.objects.create(
        company=company,
        category=cat,
        title=f"Money Item {_n()}",
        kind=OrderItemDefinition.Kind.MONEY,
        is_active=True,
    )


def _text_item(company, category=None):
    cat = category or _category(company)
    return OrderItemDefinition.objects.create(
        company=company,
        category=cat,
        title=f"Text Item {_n()}",
        kind=OrderItemDefinition.Kind.TEXT,
        is_active=True,
    )


def _rate(company, technician, item_definition, fixed_wage_rial=4_000_000, is_active=True):
    rate = TechnicianServiceRate(
        company=company,
        technician=technician,
        item_definition=item_definition,
        fixed_wage_rial=fixed_wage_rial,
        is_active=is_active,
    )
    rate.full_clean()
    rate.save()
    return rate


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TechnicianServiceRateCreationTest(TestCase):
    """Basic creation and field validation."""

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.item = _number_item(self.company)

    def test_1_can_create_rate_for_number_item(self):
        """Test 1: Can create TechnicianServiceRate for technician + NUMBER item."""
        rate = _rate(self.company, self.tech, self.item, fixed_wage_rial=4_000_000)
        self.assertEqual(rate.pk is not None, True)
        self.assertEqual(rate.fixed_wage_rial, 4_000_000)
        self.assertTrue(rate.is_active)
        self.assertEqual(rate.company, self.company)
        self.assertEqual(rate.technician, self.tech)
        self.assertEqual(rate.item_definition, self.item)

    def test_2_duplicate_rate_fails(self):
        """Test 2: Duplicate rate for same company + technician + item_definition fails."""
        _rate(self.company, self.tech, self.item)
        with self.assertRaises((IntegrityError, ValidationError)):
            _rate(self.company, self.tech, self.item, fixed_wage_rial=2_000_000)

    def test_3_different_technicians_can_have_same_item_rate(self):
        """Test 3: Same item_definition can have different rates for different technicians."""
        tech2 = _technician(self.company)
        rate1 = _rate(self.company, self.tech, self.item, fixed_wage_rial=4_000_000)
        rate2 = _rate(self.company, tech2, self.item, fixed_wage_rial=2_000_000)
        self.assertNotEqual(rate1.pk, rate2.pk)
        self.assertEqual(rate1.fixed_wage_rial, 4_000_000)
        self.assertEqual(rate2.fixed_wage_rial, 2_000_000)

    def test_4_same_technician_multiple_item_rates(self):
        """Test 4: Same technician can have rates for multiple item_definitions."""
        item2 = _number_item(self.company)
        rate1 = _rate(self.company, self.tech, self.item, fixed_wage_rial=4_000_000)
        rate2 = _rate(self.company, self.tech, item2, fixed_wage_rial=2_000_000)
        self.assertNotEqual(rate1.pk, rate2.pk)
        self.assertEqual(
            TechnicianServiceRate.objects.filter(
                company=self.company, technician=self.tech
            ).count(),
            2,
        )

    def test_11_str_contains_name_title_amount(self):
        """Test 11: __str__ contains technician name, item title, and amount."""
        rate = _rate(self.company, self.tech, self.item, fixed_wage_rial=4_000_000)
        s = str(rate)
        # Technician name portion
        self.assertIn(self.tech.user.get_full_name() or self.tech.user.username, s)
        # Item title
        self.assertIn(self.item.title, s)
        # Amount (formatted with commas or without, but digits must be present)
        self.assertIn("4", s)
        self.assertIn("ریال", s)

    def test_zero_wage_is_allowed(self):
        """Zero fixed_wage_rial is valid (tech earns nothing for this item type)."""
        rate = _rate(self.company, self.tech, self.item, fixed_wage_rial=0)
        self.assertEqual(rate.fixed_wage_rial, 0)


class TechnicianServiceRateTenantIsolationTest(TestCase):
    """Cross-company validation."""

    def setUp(self):
        self.company_a = _company("Company A")
        self.company_b = _company("Company B")
        self.tech_a = _technician(self.company_a)
        self.item_a = _number_item(self.company_a)

    def test_5_cross_company_technician_rejected(self):
        """Test 5: Cross-company technician is rejected by clean()."""
        with self.assertRaises(ValidationError) as ctx:
            _rate(self.company_b, self.tech_a, _number_item(self.company_b))
        errors = ctx.exception.message_dict
        self.assertIn("technician", errors)

    def test_6_cross_company_item_definition_rejected(self):
        """Test 6: Cross-company item_definition is rejected by clean()."""
        tech_b = _technician(self.company_b)
        with self.assertRaises(ValidationError) as ctx:
            _rate(self.company_b, tech_b, self.item_a)
        errors = ctx.exception.message_dict
        self.assertIn("item_definition", errors)


class TechnicianServiceRateItemKindTest(TestCase):
    """Item kind validation."""

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)

    def test_7_non_number_item_money_rejected(self):
        """Test 7: MONEY item_definition is rejected by clean()."""
        money_item = _money_item(self.company)
        with self.assertRaises(ValidationError) as ctx:
            _rate(self.company, self.tech, money_item)
        errors = ctx.exception.message_dict
        self.assertIn("item_definition", errors)
        self.assertIn("NUMBER", errors["item_definition"][0])

    def test_7b_non_number_item_text_rejected(self):
        """Test 7b: TEXT item_definition is rejected by clean()."""
        text_item = _text_item(self.company)
        with self.assertRaises(ValidationError) as ctx:
            _rate(self.company, self.tech, text_item)
        errors = ctx.exception.message_dict
        self.assertIn("item_definition", errors)

    def test_7c_bool_item_rejected(self):
        """Test 7c: BOOL item_definition is rejected by clean()."""
        cat = _category(self.company)
        bool_item = OrderItemDefinition.objects.create(
            company=self.company,
            category=cat,
            title=f"Bool Item {_n()}",
            kind=OrderItemDefinition.Kind.BOOL,
            is_active=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            _rate(self.company, self.tech, bool_item)
        errors = ctx.exception.message_dict
        self.assertIn("item_definition", errors)


class TechnicianServiceRateWageValidationTest(TestCase):
    """Wage amount validation."""

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.item = _number_item(self.company)

    def test_8_negative_wage_rejected(self):
        """Test 8: Negative fixed_wage_rial is rejected by full_clean()."""
        rate = TechnicianServiceRate(
            company=self.company,
            technician=self.tech,
            item_definition=self.item,
            fixed_wage_rial=-1,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            rate.full_clean()


class TechnicianServiceRateActiveInactiveTest(TestCase):
    """Active/inactive item and rate scenarios."""

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)

    def test_9_active_rate_on_inactive_item_rejected(self):
        """Test 9: Active rate on inactive item_definition is rejected by clean()."""
        inactive_item = _number_item(self.company, is_active=False)
        with self.assertRaises(ValidationError) as ctx:
            _rate(self.company, self.tech, inactive_item, is_active=True)
        errors = ctx.exception.message_dict
        self.assertIn("item_definition", errors)
        self.assertIn("غیرفعال", errors["item_definition"][0])

    def test_10_inactive_rate_allowed_regardless_of_item_state(self):
        """Test 10: Inactive rate (is_active=False) can be saved regardless of item state."""
        inactive_item = _number_item(self.company, is_active=False)
        # is_active=False on the rate → clean() does not raise
        rate = TechnicianServiceRate(
            company=self.company,
            technician=self.tech,
            item_definition=inactive_item,
            fixed_wage_rial=1_000_000,
            is_active=False,
        )
        rate.full_clean()
        rate.save()
        self.assertFalse(rate.is_active)
        self.assertFalse(rate.item_definition.is_active)

    def test_10b_inactive_rate_on_active_item_allowed(self):
        """Test 10b: Inactive rate on active item is also allowed."""
        active_item = _number_item(self.company, is_active=True)
        rate = TechnicianServiceRate(
            company=self.company,
            technician=self.tech,
            item_definition=active_item,
            fixed_wage_rial=500_000,
            is_active=False,
        )
        rate.full_clean()
        rate.save()
        self.assertFalse(rate.is_active)
        self.assertTrue(rate.item_definition.is_active)
