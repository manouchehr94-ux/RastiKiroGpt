"""
Fix-3 & Fix-4: service_category is mandatory on all order creation paths.

Fix-3: OrderCreateByAdminService.create() must reject missing/invalid/inactive category.
Fix-4: ServiceRequestCreateService.create() must reject missing/invalid/inactive category.

Every test in this file verifies that the order does NOT reach the database when
the category is absent or invalid, and DOES reach the database when the category
is present and active.
"""
from django.test import TestCase

from apps.accounts.models import CompanyUser, UserRole
from apps.orders.models import Order
from apps.orders.services import OrderCreateByAdminService
from apps.tenants.models import Company, CompanyServiceCategory
from apps.tenants.services import ServiceRequestCreateService


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company(label="c"):
    global _seq
    _seq += 1
    code = f"sc{label}{_seq}"
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


def _category(company, is_active=True):
    global _seq
    _seq += 1
    return CompanyServiceCategory.objects.create(
        company=company,
        title=f"Category {_seq}",
        is_active=is_active,
    )


# =============================================================================
# Fix-3: OrderCreateByAdminService
# =============================================================================

class AdminOrderCategoryRequiredTest(TestCase):
    """OrderCreateByAdminService.create() must reject missing or invalid service_category."""

    def setUp(self):
        self.company = _company("adm")
        self.admin = _admin(self.company)
        self.category = _category(self.company)

    def _create(self, service_category_id):
        return OrderCreateByAdminService.create(
            company=self.company,
            created_by=self.admin,
            title="Test Order",
            customer_name="علی رضایی",
            customer_phone="09123456789",
            service_category_id=service_category_id,
        )

    # --- rejection cases ---

    def test_no_category_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._create(service_category_id=None)
        self.assertIn("دسته‌بندی", str(ctx.exception))

    def test_zero_category_raises(self):
        """Passing 0 (common from HTML forms) is treated the same as None."""
        with self.assertRaises(ValueError):
            self._create(service_category_id=0)

    def test_nonexistent_id_raises(self):
        with self.assertRaises(ValueError):
            self._create(service_category_id=99999)

    def test_category_from_other_company_raises(self):
        other_company = _company("oth")
        foreign_category = _category(other_company)
        with self.assertRaises(ValueError):
            self._create(service_category_id=foreign_category.id)

    def test_inactive_category_raises(self):
        inactive = _category(self.company, is_active=False)
        with self.assertRaises(ValueError):
            self._create(service_category_id=inactive.id)

    # --- no order created on rejection ---

    def test_no_order_created_when_category_missing(self):
        before = Order.objects.filter(company=self.company).count()
        with self.assertRaises(ValueError):
            self._create(service_category_id=None)
        after = Order.objects.filter(company=self.company).count()
        self.assertEqual(before, after)

    def test_no_order_created_when_category_inactive(self):
        inactive = _category(self.company, is_active=False)
        before = Order.objects.filter(company=self.company).count()
        with self.assertRaises(ValueError):
            self._create(service_category_id=inactive.id)
        after = Order.objects.filter(company=self.company).count()
        self.assertEqual(before, after)

    # --- success case ---

    def test_valid_category_creates_order(self):
        order = self._create(service_category_id=self.category.id)
        self.assertIsNotNone(order.pk)
        self.assertEqual(order.service_category_id, self.category.id)
        self.assertEqual(order.status, Order.Status.NEW)

    def test_valid_category_order_saved_to_db(self):
        order = self._create(service_category_id=self.category.id)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())


# =============================================================================
# Fix-4: ServiceRequestCreateService
# =============================================================================

class PublicRequestCategoryRequiredTest(TestCase):
    """ServiceRequestCreateService.create() must reject missing or invalid service_category."""

    def setUp(self):
        self.company = _company("pub")
        self.category = _category(self.company)

    def _create(self, service_category_id):
        return ServiceRequestCreateService.create(
            company=self.company,
            customer_name="مریم محمدی",
            customer_phone="09191234567",
            service_category_id=service_category_id,
        )

    # --- rejection cases ---

    def test_no_category_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._create(service_category_id=None)
        self.assertIn("دسته‌بندی", str(ctx.exception))

    def test_zero_category_raises(self):
        with self.assertRaises(ValueError):
            self._create(service_category_id=0)

    def test_nonexistent_id_raises(self):
        with self.assertRaises(ValueError):
            self._create(service_category_id=99999)

    def test_category_from_other_company_raises(self):
        other_company = _company("oth2")
        foreign_category = _category(other_company)
        with self.assertRaises(ValueError):
            self._create(service_category_id=foreign_category.id)

    def test_inactive_category_raises(self):
        inactive = _category(self.company, is_active=False)
        with self.assertRaises(ValueError):
            self._create(service_category_id=inactive.id)

    # --- no order created on rejection ---

    def test_no_order_created_when_category_missing(self):
        before = Order.objects.filter(company=self.company).count()
        with self.assertRaises(ValueError):
            self._create(service_category_id=None)
        after = Order.objects.filter(company=self.company).count()
        self.assertEqual(before, after)

    def test_no_order_created_when_category_inactive(self):
        inactive = _category(self.company, is_active=False)
        before = Order.objects.filter(company=self.company).count()
        with self.assertRaises(ValueError):
            self._create(service_category_id=inactive.id)
        after = Order.objects.filter(company=self.company).count()
        self.assertEqual(before, after)

    # --- success case ---

    def test_valid_category_creates_pending_review_order(self):
        service_request = self._create(service_category_id=self.category.id)
        order = service_request.order
        self.assertIsNotNone(order.pk)
        self.assertEqual(order.service_category_id, self.category.id)
        self.assertEqual(order.status, Order.Status.PENDING_REVIEW)

    def test_valid_category_order_saved_to_db(self):
        service_request = self._create(service_category_id=self.category.id)
        self.assertTrue(Order.objects.filter(pk=service_request.order.pk).exists())
