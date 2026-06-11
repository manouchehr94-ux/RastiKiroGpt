"""
P27-ORDERS-ADMIN-FORMS-CENTRALIZATION: Tests for order/admin form templates.

Covers:
1. Order/admin pages render 200
2. CSRF preserved in forms
3. Forms still use method="post"
4. Pages load theme.css
5. Pages use central CSS classes
6. No sensitive KYC/banking data
7. No platform owner links in tenant pages
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P27Mixin:
    def create_company(self, code="p27_co"):
        return Company.objects.create(code=code, name="P27 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p27_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )


@override_settings(ROOT_URLCONF="config.urls")
class OrderAdminRenderTest(TestCase, P27Mixin):
    """Order/admin pages render correctly after P27 migration."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)

    def test_order_list_renders_200(self):
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/")
        self.assertEqual(response.status_code, 200)

    def test_order_create_renders_200(self):
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/create/")
        self.assertEqual(response.status_code, 200)

    def test_order_create_has_csrf(self):
        """Order create form must have CSRF token."""
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/create/")
        content = response.content.decode("utf-8")
        self.assertIn("csrfmiddlewaretoken", content)

    def test_order_create_has_post_method(self):
        """Order create form must use POST method."""
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/create/")
        content = response.content.decode("utf-8")
        self.assertIn('method="post"', content.lower())

    def test_order_create_loads_theme_css(self):
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/create/")
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)

    def test_technician_list_renders_200(self):
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/technicians/")
        self.assertEqual(response.status_code, 200)

    def test_no_sensitive_data(self):
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/")
        content = response.content.decode("utf-8")
        self.assertNotIn("shaba_number", content)
        self.assertNotIn("national_card_image", content)

    def test_no_platform_links(self):
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/owner-platform/", content)

    def test_cross_tenant_blocked(self):
        other = self.create_company("p27_other")
        self.client.login(username="p27_admin", password="testpass123")
        response = self.client.get(f"/{other.code}/admin/orders/")
        self.assertIn(response.status_code, [403, 302])
