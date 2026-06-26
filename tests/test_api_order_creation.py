"""
TASK-005B: API order creation must enforce service_category and status rules.

Tests verify:
1. OrderListAPI (admin/staff) uses OrderCreateByAdminService rules.
2. ServiceRequestListAPI (public) uses ServiceRequestCreateService rules.

Business rules under test:
- service_category_id required on all creation paths.
- category must belong to request.company and be active.
- admin-created order with no technician → NEW.
- admin-created order with technician → WAITING.
- public service request → PENDING_REVIEW.
- no technician SMS dispatched for PENDING_REVIEW order.
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CompanyUser, Customer, Technician, UserRole
from apps.orders.models import Order
from apps.tenants.models import Company, CompanyServiceCategory


# =============================================================================
# HELPERS
# =============================================================================

_seq = 0


def _company(code):
    global _seq
    _seq += 1
    return Company.objects.create(
        code=code, name=f"Co {code}", slug=code, is_active=True
    )


def _admin(company, username):
    global _seq
    _seq += 1
    return CompanyUser.objects.create_user(
        username=username,
        password="testpass",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _customer(company):
    global _seq
    _seq += 1
    return Customer.objects.create(
        company=company,
        first_name="Test",
        last_name=f"Customer{_seq}",
        phone=f"091700000{_seq:02d}",
    )


def _category(company, is_active=True):
    global _seq
    _seq += 1
    return CompanyServiceCategory.objects.create(
        company=company,
        title=f"Category {_seq}",
        is_active=is_active,
    )


def _technician(company):
    global _seq
    _seq += 1
    user = CompanyUser.objects.create_user(
        username=f"tech_{_seq}",
        password="testpass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user, is_available=True)


# =============================================================================
# Fix 1: OrderListAPI (admin order creation)
# =============================================================================

class OrderAPICreateTest(TestCase):
    """API order creation enforces service_category and status rules."""

    def setUp(self):
        self.client = APIClient()
        self.company = _company("apiord")
        self.admin = _admin(self.company, "apiord_admin")
        self.customer = _customer(self.company)
        self.category = _category(self.company)
        self.url = f"/api/{self.company.code}/orders/"
        self.client.force_authenticate(user=self.admin)

    def _post(self, extra=None):
        payload = {
            "title": "API Test Order",
            "customer_id": self.customer.id,
            "service_category_id": self.category.id,
        }
        if extra:
            payload.update(extra)
        return self.client.post(self.url, payload, format="json")

    # --- Test 1: missing category fails ---

    def test_order_create_without_category_fails(self):
        response = self.client.post(
            self.url,
            {"title": "Test", "customer_id": self.customer.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # --- Test 2: valid category succeeds with NEW status ---

    def test_order_create_with_valid_category_succeeds(self):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data["id"])
        self.assertEqual(order.service_category_id, self.category.id)

    # --- Test 3: cross-company category rejected ---

    def test_order_create_with_other_company_category_fails(self):
        other = _company("apiothr")
        foreign_cat = _category(other)
        response = self._post({"service_category_id": foreign_cat.id})
        self.assertEqual(response.status_code, 400)

    # --- Test 4: inactive category rejected ---

    def test_order_create_with_inactive_category_fails(self):
        inactive = _category(self.company, is_active=False)
        response = self._post({"service_category_id": inactive.id})
        self.assertEqual(response.status_code, 400)

    # --- Test 5: technician assigned → WAITING ---

    def test_order_create_with_technician_gives_waiting(self):
        tech = _technician(self.company)
        response = self._post({"technician_id": tech.id})
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data["id"])
        self.assertEqual(order.status, Order.Status.WAITING)
        self.assertEqual(order.technician_id, tech.id)

    # --- Test 6: no technician → NEW ---

    def test_order_create_without_technician_gives_new(self):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data["id"])
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertIsNone(order.technician_id)

    # --- Permission: non-admin cannot create orders ---

    def test_order_create_by_technician_rejected(self):
        tech = _technician(self.company)
        self.client.force_authenticate(user=tech.user)
        response = self._post()
        self.assertEqual(response.status_code, 403)

    # --- Tenant isolation: category must belong to request.company ---

    def test_order_create_nonexistent_category_fails(self):
        response = self._post({"service_category_id": 99999})
        self.assertEqual(response.status_code, 400)


# =============================================================================
# Fix 2: ServiceRequestListAPI (public service request)
# =============================================================================

class ServiceRequestAPICreateTest(TestCase):
    """API public service request creation enforces service_category and PENDING_REVIEW status."""

    def setUp(self):
        self.client = APIClient()
        self.company = _company("apisreq")
        self.category = _category(self.company)
        self.url = f"/api/{self.company.code}/service-requests/"

    def _post(self, extra=None):
        payload = {
            "customer_name": "Ahmad Ahmadi",
            "customer_phone": "09120000001",
            "service_category_id": self.category.id,
        }
        if extra:
            payload.update(extra)
        return self.client.post(self.url, payload, format="json")

    # --- Test 7: service request creates PENDING_REVIEW order ---

    def test_service_request_creates_pending_review_order(self):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data["order"])
        self.assertEqual(order.status, Order.Status.PENDING_REVIEW)

    # --- Test 8: missing category returns 400 ---

    def test_service_request_without_category_fails(self):
        response = self.client.post(
            self.url,
            {"customer_name": "Test", "customer_phone": "09120000002"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # --- Test 9: no technician SMS dispatched before approval ---

    @patch("apps.orders.order_events.dispatch_order_available_events")
    def test_service_request_does_not_dispatch_technician_sms(self, mock_dispatch):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        mock_dispatch.assert_not_called()

    # --- Sanity: cross-company category rejected ---

    def test_service_request_with_other_company_category_fails(self):
        other = _company("apisrother")
        foreign_cat = _category(other)
        response = self._post({"service_category_id": foreign_cat.id})
        self.assertEqual(response.status_code, 400)

    # --- Sanity: inactive category rejected ---

    def test_service_request_with_inactive_category_fails(self):
        inactive = _category(self.company, is_active=False)
        response = self._post({"service_category_id": inactive.id})
        self.assertEqual(response.status_code, 400)

    # --- Tenant isolation: service_category_id must belong to company ---

    def test_service_request_nonexistent_category_fails(self):
        response = self._post({"service_category_id": 99999})
        self.assertEqual(response.status_code, 400)
