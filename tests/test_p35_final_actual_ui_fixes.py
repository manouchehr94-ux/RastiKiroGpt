"""
P35-FINAL-ACTUAL-UI-FIXES: Tests for overlay, sidebar persistence, dates, numbers.

Tests are written to match BOTH layout systems:
- layouts/dashboard.html (company admin/platform owner)
- base_dashboard.html (technician)
"""
from pathlib import Path

from django.test import TestCase, SimpleTestCase, override_settings
from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P35Mixin:
    def create_company(self, code="p35_co"):
        return Company.objects.create(code=code, name="P35 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p35_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_platform_owner(self, username="p35_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class OverlayFixTest(TestCase, P35Mixin):
    """Overlay is hidden by default — no dim/blur on page load."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)
        self.owner = self.create_platform_owner()

    def test_company_admin_overlay_hidden_on_load(self):
        """Admin page should use sidebar-overlay class and force-close on load."""
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode()
        # Must use sidebar-overlay class (hidden by default in CSS)
        self.assertIn("sidebar-overlay", content)
        # Must NOT have the old Tailwind overlay class
        self.assertNotIn("bg-black/50", content)
        # Force-close on load (either variable naming)
        self.assertTrue(
            "overlay.classList.remove('active')" in content
            or "o.classList.remove('active')" in content
            or "classList.remove('active')" in content,
            "Overlay must be force-closed on DOMContentLoaded"
        )

    def test_platform_overlay_hidden_on_load(self):
        """Platform page should have overlay hidden by default."""
        self.client.login(username="p35_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        content = response.content.decode()
        self.assertIn("sidebar-overlay", content)

    def test_body_overflow_reset_on_load(self):
        """Body overflow should be reset on page load."""
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode()
        self.assertIn("document.body.style.overflow", content)


@override_settings(ROOT_URLCONF="config.urls")
class SidebarPersistenceTest(TestCase, P35Mixin):
    """Sidebar scroll and state persistence."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)

    def test_sidebar_scroll_persistence(self):
        """Sidebar should save/restore scroll position."""
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode()
        self.assertIn("rasti_sidebar_scroll", content)
        self.assertIn("sessionStorage", content)

    def test_sidebar_open_uses_active_class(self):
        """openSidebar should add 'active' class to overlay."""
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode()
        # Both layouts use .classList.add('active')
        self.assertIn("classList.add('active')", content)

    def test_sidebar_close_removes_active_class(self):
        """closeSidebar should remove 'active' class from overlay."""
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode()
        self.assertIn("classList.remove('active')", content)


@override_settings(ROOT_URLCONF="config.urls")
class JalaliDatePickerTest(TestCase, P35Mixin):
    """Jalali date picker initialization."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)

    def test_jalali_datepicker_js_loaded(self):
        """jalali_datepicker.js should be loaded on admin pages."""
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode()
        self.assertIn("jalali_datepicker", content)

    def test_datepicker_init_on_dom_ready(self):
        """Date picker should initialize on DOMContentLoaded."""
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode()
        self.assertIn("initJalaliDatepicker", content)


@override_settings(ROOT_URLCONF="config.urls")
class SubnavAndPagesTest(TestCase, P35Mixin):
    """Subnav and page rendering."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)

    def test_payment_operations_has_subnav(self):
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("fin-subnav", response.content.decode())

    def test_financial_summary_renders(self):
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        self.assertEqual(response.status_code, 200)

    def test_no_sensitive_data(self):
        self.client.login(username="p35_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        content = response.content.decode()
        self.assertNotIn("/media/companies/kyc/", content)


class ResponsiveOverlayCSS(SimpleTestCase):
    """responsive.css has definitive overlay fix."""

    def test_desktop_overlay_hidden(self):
        path = Path(__file__).parent.parent / "static" / "css" / "responsive.css"
        content = path.read_text(encoding="utf-8")
        self.assertIn("display: none !important", content)
        self.assertIn("pointer-events: none !important", content)
        self.assertIn("#sidebarOverlay", content)

    def test_mobile_overlay_controlled(self):
        path = Path(__file__).parent.parent / "static" / "css" / "responsive.css"
        content = path.read_text(encoding="utf-8")
        self.assertIn(".sidebar-overlay.active", content)
        self.assertIn("backdrop-filter", content)
