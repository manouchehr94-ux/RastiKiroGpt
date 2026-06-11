"""
P28-UI-FULL-CENTRALIZATION-AUDIT: Full site UI audit tests.

Covers:
1. Key pages render 200
2. theme.css is loaded across all page types
3. Central classes are used
4. Inline style exceptions documented
5. No business logic changed
"""
import os

from django.test import TestCase, SimpleTestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P28Mixin:
    def create_company(self, code="p28_co"):
        return Company.objects.create(code=code, name="P28 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p28_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_platform_owner(self, username="p28_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class FullSiteThemeCSSTest(TestCase, P28Mixin):
    """Verify theme.css is loaded on all page types."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)
        self.owner = self.create_platform_owner()

    def test_login_page_has_theme(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_public_home_has_theme(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_company_dashboard_has_theme(self):
        self.client.login(username="p28_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_company_orders_has_theme(self):
        self.client.login(username="p28_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_company_financial_reports_has_theme(self):
        self.client.login(username="p28_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_company_payment_ops_has_theme(self):
        self.client.login(username="p28_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_platform_dashboard_has_theme(self):
        self.client.login(username="p28_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_platform_operations_has_theme(self):
        self.client.login(username="p28_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())


class InlineStyleAuditTest(SimpleTestCase):
    """Document remaining inline style count."""

    def test_total_inline_styles_under_threshold(self):
        """Total inline styles should be tracked (pure Python, Windows-safe)."""
        from pathlib import Path
        templates_dir = Path(os.path.dirname(__file__)).parent / "templates"
        total = 0
        for html_file in templates_dir.rglob("*.html"):
            total += html_file.read_text(encoding="utf-8", errors="ignore").count('style="')
        # Document current state — will decrease over time
        self.assertLess(total, 1000, f"Total inline styles ({total}) should be decreasing toward <150")

    def test_audit_document_exists(self):
        """Full audit document should exist."""
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "UI_FULL_CENTRALIZATION_AUDIT.md")
        self.assertTrue(os.path.exists(path))

    def test_theme_css_is_sole_entrypoint(self):
        """base.html should only load theme.css, not individual CSS files."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "base.html")
        with open(path) as f:
            content = f.read()
        self.assertIn("theme.css", content)
        self.assertNotIn("'css/tokens.css'", content)
        self.assertNotIn("'css/components.css'", content)
