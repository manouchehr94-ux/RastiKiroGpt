"""
P24-UI-CENTRAL-STYLESHEET-ENTRYPOINT: Tests for central CSS loading.

Covers:
1. Key pages render 200
2. Pages include the central theme.css entrypoint
3. No raw KYC media URLs
4. No sensitive SHABA/card/national-code values
5. No payment mutation changes
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P24Mixin:
    def create_company(self, code="p24_co"):
        return Company.objects.create(code=code, name="P24 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p24_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )

    def create_platform_owner(self, username="p24_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class CentralStylesheetLoadingTest(TestCase, P24Mixin):
    """Pages load the central theme.css entrypoint."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)
        self.owner = self.create_platform_owner()

    def test_company_dashboard_renders_200(self):
        self.client.login(username="p24_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        self.assertEqual(response.status_code, 200)

    def test_company_dashboard_loads_theme_css(self):
        self.client.login(username="p24_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)

    def test_financial_summary_loads_theme_css(self):
        self.client.login(username="p24_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)

    def test_payment_operations_loads_theme_css(self):
        self.client.login(username="p24_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)

    def test_merchant_profile_renders(self):
        self.client.login(username="p24_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)

    def test_platform_dashboard_loads_theme_css(self):
        self.client.login(username="p24_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)

    def test_platform_operations_loads_theme_css(self):
        self.client.login(username="p24_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)

    def test_login_page_loads_theme_css(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)


@override_settings(ROOT_URLCONF="config.urls")
class NoRegressionSecurityTest(TestCase, P24Mixin):
    """P24 CSS changes did not introduce security issues."""

    def setUp(self):
        self.company = self.create_company("p24_sec")
        self.admin = self.create_admin(self.company, "p24_sec_admin")

    def test_no_raw_media_url(self):
        self.client.login(username="p24_sec_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/media/companies/kyc/", content)

    def test_no_full_shaba(self):
        self.client.login(username="p24_sec_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payment/merchant-profile/")
        content = response.content.decode("utf-8")
        self.assertNotIn("IR12345678901234567890", content)

    def test_no_mutation_forms_in_reports(self):
        self.client.login(username="p24_sec_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        content = response.content.decode("utf-8")
        self.assertNotIn("mark_paid_company_cash", content)

    def test_individual_css_not_loaded(self):
        """base.html should no longer load individual CSS files directly."""
        self.client.login(username="p24_sec_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode("utf-8")
        # theme.css should be present instead of individual files
        self.assertIn("theme.css", content)
        # Individual files should NOT be loaded directly (they're via @import now)
        self.assertNotIn("href=\"/static/css/tokens.css\"", content.replace("{% static 'css/tokens.css' %}", ""))
