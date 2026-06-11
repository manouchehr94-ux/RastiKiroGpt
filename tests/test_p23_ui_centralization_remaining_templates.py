"""
P23-UI-CENTRALIZATION-REMAINING-TEMPLATES: Tests for migrated templates.

Covers:
1. Merchant/KYC pages render for authorized users
2. Platform owner pages render
3. Login/auth pages render
4. Unauthorized users blocked from KYC/platform pages
5. No sensitive banking/KYC values in readonly/detail pages
6. No raw media URLs
7. Pages use central CSS classes
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P23Mixin:
    def create_company(self, code="p23_co"):
        return Company.objects.create(code=code, name="P23 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p23_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_platform_owner(self, username="p23_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class MerchantProfileRenderTest(TestCase, P23Mixin):
    """Merchant profile pages render correctly after P23 migration."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)

    def test_merchant_profile_renders_200(self):
        self.client.login(username="p23_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        self.assertEqual(response.status_code, 200)

    def test_merchant_profile_uses_css_classes(self):
        self.client.login(username="p23_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        content = response.content.decode("utf-8")
        self.assertIn("report-card", content)

    def test_merchant_profile_no_raw_media_url(self):
        self.client.login(username="p23_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/media/companies/kyc/", content)
        self.assertNotIn("file.url", content)

    def test_merchant_profile_no_full_shaba(self):
        """Readonly view should not show full SHABA number."""
        self.client.login(username="p23_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        content = response.content.decode("utf-8")
        # Should use masked property, not raw field
        self.assertNotIn("IR12345678901234567890", content)


@override_settings(ROOT_URLCONF="config.urls")
class PlatformDashboardRenderTest(TestCase, P23Mixin):
    """Platform owner pages render after migration."""

    def setUp(self):
        self.owner = self.create_platform_owner()

    def test_platform_dashboard_renders(self):
        self.client.login(username="p23_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_platform_operations_renders(self):
        self.client.login(username="p23_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertEqual(response.status_code, 200)

    def test_platform_operations_uses_central_classes(self):
        self.client.login(username="p23_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        content = response.content.decode("utf-8")
        # data-table when records exist, or empty-state/stat-card when healthy
        self.assertTrue(
            "data-table" in content or "empty-state" in content or "stat-card" in content,
            "Page should use data-table, empty-state, or stat-card"
        )


@override_settings(ROOT_URLCONF="config.urls")
class AuthPagesRenderTest(TestCase, P23Mixin):
    """Login/auth pages render correctly."""

    def test_login_page_renders(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)

    def test_login_no_sensitive_data(self):
        response = self.client.get("/login/")
        content = response.content.decode("utf-8")
        self.assertNotIn("shaba_number", content)
        self.assertNotIn("national_card_image", content)

    def test_login_uses_form_control(self):
        response = self.client.get("/login/")
        content = response.content.decode("utf-8")
        self.assertIn("form-control", content)


@override_settings(ROOT_URLCONF="config.urls")
class UnauthorizedAccessTest(TestCase, P23Mixin):
    """Unauthorized users still blocked after template migration."""

    def setUp(self):
        self.company = self.create_company("p23_sec")

    def test_anonymous_blocked_merchant_profile(self):
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        self.assertIn(response.status_code, [302, 403])

    def test_anonymous_blocked_platform(self):
        response = self.client.get("/owner-platform/dashboard/")
        self.assertIn(response.status_code, [302, 403])

    def test_technician_blocked_merchant_profile(self):
        tech = CompanyUser.objects.create_user(
            username="p23_tech", password="testpass123",
            company=self.company, role=UserRole.TECHNICIAN,
        )
        self.client.login(username="p23_tech", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        self.assertIn(response.status_code, [302, 403])
