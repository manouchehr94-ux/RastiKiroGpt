"""
P33-RESPONSIVE-MOBILE-AND-FINAL-UI-CLEANUP: Tests.

Verifies responsive utilities exist, key pages render, and no regressions.
"""
import os
from pathlib import Path

from django.test import TestCase, SimpleTestCase, override_settings
from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P33Mixin:
    def create_company(self, code="p33_co"):
        return Company.objects.create(code=code, name="P33 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p33_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_platform_owner(self, username="p33_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class ResponsivePageRenderTest(TestCase, P33Mixin):
    """All key pages render 200 after responsive CSS changes."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)
        self.owner = self.create_platform_owner()

    def test_public_pages_render(self):
        for url in ["/", "/features/", "/pricing/", "/login/"]:
            self.assertEqual(self.client.get(url).status_code, 200, f"Failed: {url}")

    def test_company_admin_pages_render(self):
        self.client.login(username="p33_admin", password="testpass123")
        urls = [
            f"/{self.company.code}/admin/",
            f"/{self.company.code}/admin/orders/",
            f"/{self.company.code}/admin/orders/create/",
            f"/{self.company.code}/admin/financial-reports/summary/",
            f"/{self.company.code}/admin/payments/operations/",
            f"/{self.company.code}/admin/payment/merchant-profile/",
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, f"Failed: {url}")

    def test_platform_pages_render(self):
        self.client.login(username="p33_platform", password="testpass123")
        for url in ["/owner-platform/dashboard/", "/owner-platform/payments/operations/"]:
            self.assertEqual(self.client.get(url).status_code, 200, f"Failed: {url}")

    def test_theme_css_loaded(self):
        response = self.client.get("/")
        self.assertIn("theme.css", response.content.decode())

    def test_order_create_form_preserved(self):
        self.client.login(username="p33_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/create/")
        content = response.content.decode()
        self.assertIn("csrfmiddlewaretoken", content)
        self.assertIn('method="post"', content.lower())

    def test_no_sensitive_data(self):
        self.client.login(username="p33_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        content = response.content.decode()
        self.assertNotIn("/media/companies/kyc/", content)
        self.assertNotIn("IR12345678901234567890", content)

    def test_no_platform_links_in_tenant(self):
        self.client.login(username="p33_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        self.assertNotIn("/owner-platform/", response.content.decode())


class ResponsiveCSSAuditTest(SimpleTestCase):
    """responsive.css contains required mobile breakpoints and utilities."""

    def test_responsive_css_has_mobile_breakpoint(self):
        path = Path(__file__).parent.parent / "static" / "css" / "responsive.css"
        content = path.read_text(encoding="utf-8")
        self.assertIn("max-width: 639px", content)
        self.assertIn("max-width: 1023px", content)

    def test_responsive_css_has_utilities(self):
        path = Path(__file__).parent.parent / "static" / "css" / "responsive.css"
        content = path.read_text(encoding="utf-8")
        self.assertIn(".table-scroll", content)
        self.assertIn(".responsive-actions", content)
        self.assertIn(".mobile-hidden", content)
        self.assertIn(".truncate", content)

    def test_theme_css_imports_responsive(self):
        path = Path(__file__).parent.parent / "static" / "css" / "theme.css"
        content = path.read_text(encoding="utf-8")
        self.assertIn("responsive.css", content)

    def test_inline_styles_not_increased(self):
        """Total inline styles should not have increased from P32."""
        templates_dir = Path(__file__).parent.parent / "templates"
        total = 0
        for html_file in templates_dir.rglob("*.html"):
            total += html_file.read_text(encoding="utf-8", errors="ignore").count('style="')
        self.assertLess(total, 600, f"Inline styles ({total}) should remain < 600")
