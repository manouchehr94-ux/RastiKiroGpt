"""
P32-DASHBOARD-CSS-FULL-CENTRALIZATION: Tests.

Verifies dashboard.css is token-based and all pages still render correctly.
"""
import os
from pathlib import Path

from django.test import TestCase, SimpleTestCase, override_settings
from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P32Mixin:
    def create_company(self, code="p32_co"):
        return Company.objects.create(code=code, name="P32 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p32_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_platform_owner(self, username="p32_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class DashboardCSSCentralizationTest(TestCase, P32Mixin):
    """Key pages render correctly after dashboard.css tokenization."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)
        self.owner = self.create_platform_owner()

    def test_login_renders(self):
        self.assertEqual(self.client.get("/login/").status_code, 200)

    def test_home_renders(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_company_dashboard_renders(self):
        self.client.login(username="p32_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_company_orders_renders(self):
        self.client.login(username="p32_admin", password="testpass123")
        self.assertEqual(self.client.get(f"/{self.company.code}/admin/orders/").status_code, 200)

    def test_financial_summary_renders(self):
        self.client.login(username="p32_admin", password="testpass123")
        self.assertEqual(self.client.get(f"/{self.company.code}/admin/financial-reports/summary/").status_code, 200)

    def test_payment_operations_renders(self):
        self.client.login(username="p32_admin", password="testpass123")
        self.assertEqual(self.client.get(f"/{self.company.code}/admin/payments/operations/").status_code, 200)

    def test_merchant_profile_renders(self):
        self.client.login(username="p32_admin", password="testpass123")
        self.assertEqual(self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/").status_code, 200)

    def test_platform_dashboard_renders(self):
        self.client.login(username="p32_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_platform_operations_renders(self):
        self.client.login(username="p32_platform", password="testpass123")
        self.assertEqual(self.client.get("/owner-platform/payments/operations/").status_code, 200)


class DashboardCSSTokenizationTest(SimpleTestCase):
    """dashboard.css should use token references instead of hardcoded hex."""

    def test_dashboard_css_has_many_token_refs(self):
        """dashboard.css should have 100+ token references."""
        path = Path(__file__).parent.parent / "static" / "css" / "dashboard.css"
        content = path.read_text(encoding="utf-8")
        token_count = content.count("var(--")
        self.assertGreater(token_count, 100, f"dashboard.css should have >100 token refs, has {token_count}")

    def test_dashboard_css_hex_reduced(self):
        """dashboard.css should have fewer than 100 hardcoded hex colors."""
        import re
        path = Path(__file__).parent.parent / "static" / "css" / "dashboard.css"
        content = path.read_text(encoding="utf-8")
        hex_count = len(re.findall(r'#[0-9a-fA-F]{3,6}', content))
        self.assertLess(hex_count, 100, f"dashboard.css should have <100 hex colors, has {hex_count}")

    def test_sidebar_colors_use_tokens(self):
        """Sidebar color classes should use CSS variables."""
        path = Path(__file__).parent.parent / "static" / "css" / "dashboard.css"
        content = path.read_text(encoding="utf-8")
        self.assertIn("var(--color-slate-900)", content)
        self.assertIn("var(--color-brand-600)", content)
        self.assertIn("var(--color-surface-0)", content)
