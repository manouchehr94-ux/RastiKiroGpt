"""
P0-A: Technician acceptance must always transition NEW → WAITING.

Business rules verified:
- TechnicianAcceptService.accept() sets status=WAITING (never IN_PROGRESS).
- accepted_at is set after acceptance.
- technician is assigned after acceptance.
- Orders without service_category are rejected — no legacy IN_PROGRESS fallback.
"""
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, TechnicianCategorySkill, UserRole
from apps.orders.models import Order
from apps.orders.services import TechnicianAcceptService
from apps.tenants.models import Company, CompanyServiceCategory


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company():
    global _seq
    _seq += 1
    code = f"p0a{_seq}"
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _admin(company):
    global _seq
    _seq += 1
    return CompanyUser.objects.create_user(
        username=f"adm_{company.code}_{_seq}",
        password="x",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _tech(company):
    global _seq
    _seq += 1
    user = CompanyUser.objects.create_user(
        username=f"tch_{company.code}_{_seq}",
        password="x",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user, is_available=True)


def _category(company):
    global _seq
    _seq += 1
    return CompanyServiceCategory.objects.create(
        company=company,
        title=f"Category {_seq}",
        is_active=True,
    )


def _skill(tech, category, priority=TechnicianCategorySkill.Priority.P1):
    return TechnicianCategorySkill.objects.create(
        technician=tech,
        category=category,
        priority=priority,
    )


def _order(company, category=None, status=Order.Status.NEW):
    """Create an order. Pass category=None to simulate legacy no-category order."""
    return Order.objects.create(
        company=company,
        title="Test",
        status=status,
        service_category=category,
        # No service_date → passes future-order gate automatically.
    )


# =============================================================================
# TESTS
# =============================================================================

class TechnicianAcceptResultsInWaitingTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.tech = _tech(self.company)
        self.category = _category(self.company)
        _skill(self.tech, self.category)

    def _accept(self, order):
        return TechnicianAcceptService.accept(
            order=order,
            technician=self.tech,
            accepted_by=self.admin,
        )

    # --- Status transition ---

    def test_accept_results_in_waiting(self):
        order = _order(self.company, category=self.category)
        result = self._accept(order)
        result.refresh_from_db()
        self.assertEqual(result.status, Order.Status.WAITING)

    def test_accept_never_results_in_in_progress(self):
        order = _order(self.company, category=self.category)
        result = self._accept(order)
        result.refresh_from_db()
        self.assertNotEqual(result.status, Order.Status.IN_PROGRESS)

    # --- Technician assigned ---

    def test_accept_assigns_technician(self):
        order = _order(self.company, category=self.category)
        result = self._accept(order)
        result.refresh_from_db()
        self.assertEqual(result.technician_id, self.tech.id)

    # --- accepted_at set ---

    def test_accept_sets_accepted_at(self):
        before = timezone.now()
        order = _order(self.company, category=self.category)
        result = self._accept(order)
        result.refresh_from_db()
        self.assertIsNotNone(result.accepted_at)
        self.assertGreaterEqual(result.accepted_at, before)

    # --- Rejection: no service_category ---

    def test_order_without_category_raises_not_falls_back(self):
        """Order with no service_category must be rejected outright — no IN_PROGRESS fallback."""
        order = _order(self.company, category=None)
        with self.assertRaises(ValueError) as ctx:
            self._accept(order)
        self.assertNotEqual(order.status, Order.Status.IN_PROGRESS)
        error = str(ctx.exception)
        self.assertTrue(
            "service category" in error.lower() or "category" in error.lower(),
            msg=f"Expected category-related error, got: {error}",
        )

    def test_order_without_category_technician_not_assigned(self):
        """No technician must be set when category is missing."""
        order = _order(self.company, category=None)
        with self.assertRaises(ValueError):
            self._accept(order)
        order.refresh_from_db()
        self.assertIsNone(order.technician_id)

    def test_order_without_category_status_unchanged(self):
        """Status must remain NEW when category is missing."""
        order = _order(self.company, category=None)
        with self.assertRaises(ValueError):
            self._accept(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)

    # --- Rejection: non-NEW status ---

    def test_waiting_order_cannot_be_accepted(self):
        order = _order(self.company, category=self.category, status=Order.Status.WAITING)
        with self.assertRaises(ValueError):
            self._accept(order)

    def test_in_progress_order_cannot_be_accepted(self):
        order = _order(self.company, category=self.category, status=Order.Status.IN_PROGRESS)
        with self.assertRaises(ValueError):
            self._accept(order)

    # --- Rejection: technician lacks category skill ---

    def test_tech_without_skill_cannot_accept(self):
        other_company = _company()
        other_category = _category(other_company)
        order = _order(self.company, category=self.category)
        # tech has skill for self.category; create order with a different category
        order2 = _order(self.company, category=other_category)
        with self.assertRaises(ValueError):
            self._accept(order2)
