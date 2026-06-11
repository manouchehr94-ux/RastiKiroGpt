"""
P30-DESIGN-SYSTEM-ENFORCEMENT: Full site design system tests.

Covers:
1. Key pages render 200
2. theme.css loaded on all pages
3. Central classes are used
4. POST forms preserved
5. No sensitive data exposed
6. Inline style threshold check
"""
import os

from django.test import TestCase, SimpleTestCase, override_settings
from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P30Mixin:
    def create_company(self, code="p30_co"):
        return Company.objects.create(code=code, name="P30 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p30_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_platform_owner(self, username="p30_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class DesignSystemEnforcementTest(TestCase, P30Mixin):
    """Key pages use central design system."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)
        self.owner = self.create_platform_owner()

    def test_login_renders_with_theme(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_home_renders_with_theme(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_company_dashboard_renders(self):
        self.client.login(username="p30_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_orders_renders(self):
        self.client.login(username="p30_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/")
        self.assertEqual(response.status_code, 200)

    def test_order_create_preserves_csrf(self):
        self.client.login(username="p30_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/create/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("csrfmiddlewaretoken", content)
        self.assertIn('method="post"', content.lower())

    def test_financial_summary_renders(self):
        self.client.login(username="p30_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_payment_operations_renders(self):
        self.client.login(username="p30_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        self.assertEqual(response.status_code, 200)

    def test_merchant_profile_renders(self):
        self.client.login(username="p30_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        self.assertEqual(response.status_code, 200)

    def test_platform_dashboard_renders(self):
        self.client.login(username="p30_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_platform_operations_renders(self):
        self.client.login(username="p30_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertEqual(response.status_code, 200)

    def test_no_sensitive_data_in_merchant(self):
        self.client.login(username="p30_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        content = response.content.decode()
        self.assertNotIn("/media/companies/kyc/", content)
        self.assertNotIn("IR12345678901234567890", content)


class InlineStyleThresholdTest(SimpleTestCase):
    """Track inline style reduction progress."""

    def test_inline_styles_under_threshold(self):
        """Total inline styles should be under 600 after P30 (pure Python, Windows-safe)."""
        from pathlib import Path
        templates_dir = Path(os.path.dirname(__file__)).parent / "templates"
        total = 0
        for html_file in templates_dir.rglob("*.html"):
            total += html_file.read_text(encoding="utf-8", errors="ignore").count('style="')
        self.assertLess(total, 600, f"Inline styles ({total}) should be < 600")

    def test_theme_css_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "theme.css")
        self.assertTrue(os.path.exists(path))
