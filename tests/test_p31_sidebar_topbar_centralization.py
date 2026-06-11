"""
P31-SIDEBAR-TOPBAR-CENTRALIZATION: Tests.

Verifies sidebar/topbar utility classes now use token references
and pages render correctly.
"""
import os
from django.test import TestCase, SimpleTestCase, override_settings
from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P31Mixin:
    def create_company(self, code="p31_co"):
        return Company.objects.create(code=code, name="P31 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p31_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_platform_owner(self, username="p31_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class SidebarTopbarRenderTest(TestCase, P31Mixin):
    """Sidebar/topbar pages render correctly after token migration."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)
        self.owner = self.create_platform_owner()

    def test_company_dashboard_renders(self):
        self.client.login(username="p31_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_company_orders_renders(self):
        self.client.login(username="p31_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/orders/")
        self.assertEqual(response.status_code, 200)

    def test_platform_dashboard_renders(self):
        self.client.login(username="p31_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("theme.css", response.content.decode())

    def test_public_home_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_login_renders(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)


class DashboardCSSTokenTest(SimpleTestCase):
    """dashboard.css utility classes now use token references."""

    def test_dashboard_css_uses_tokens(self):
        """Sidebar color utilities should reference CSS variables, not hardcoded hex."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "dashboard.css")
        with open(path) as f:
            content = f.read()
        # Key sidebar utilities should now use tokens
        self.assertIn("var(--color-slate-900)", content)
        self.assertIn("var(--color-brand-600)", content)
        self.assertIn("var(--color-slate-300)", content)

    def test_dashboard_css_still_has_classes(self):
        """Dashboard.css should still define sidebar utility classes."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "dashboard.css")
        with open(path) as f:
            content = f.read()
        self.assertIn(".bg-slate-900", content)
        self.assertIn(".text-white", content)
        self.assertIn(".text-slate-300", content)
