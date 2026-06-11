"""
P21-FINANCIAL-REPORT-TEMPLATE-MIGRATION: Tests for converted report templates.

Covers:
1. All 6 financial report pages render 200
2. Persian financial labels present
3. No sensitive banking/KYC data exposed
4. Financial subnav present with عملیات پرداخت
5. No payment mutation forms in reports
6. Cross-tenant access blocked
7. New CSS classes are used in templates
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


REPORT_URLS = [
    "financial-reports/summary/",
    "financial-reports/technicians/",
    "financial-reports/invoices/",
    "financial-reports/cash-control/",
    "financial-reports/platform-fees/",
    "financial-reports/audit/",
]


class P21Mixin:
    def create_company(self, code="p21_co"):
        return Company.objects.create(code=code, name="P21 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p21_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )


@override_settings(ROOT_URLCONF="config.urls")
class FinancialReportTemplateRenderTest(TestCase, P21Mixin):
    """All 6 financial report pages render successfully after P21 migration."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)

    def test_all_reports_render_200(self):
        """Each financial report page returns 200."""
        self.client.login(username="p21_admin", password="testpass123")
        for url_suffix in REPORT_URLS:
            url = f"/{self.company.code}/admin/{url_suffix}"
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Failed: {url}")

    def test_summary_has_persian_labels(self):
        """Summary should contain key Persian labels."""
        self.client.login(username="p21_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        content = response.content.decode("utf-8")
        self.assertIn("داشبورد مالی", content)
        self.assertIn("فروش کل", content)
        self.assertIn("کارمزد پلتفرم", content)

    def test_summary_uses_new_css_classes(self):
        """Summary should use P21 classes instead of inline styles."""
        self.client.login(username="p21_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        content = response.content.decode("utf-8")
        self.assertIn("page-header-subtitle", content)
        self.assertIn("stat-card-hint", content)
        self.assertIn("btn-group-wrap", content)
        self.assertIn("report-help", content)

    def test_all_reports_have_subnav(self):
        """All pages should have financial subnav."""
        self.client.login(username="p21_admin", password="testpass123")
        for url_suffix in REPORT_URLS:
            url = f"/{self.company.code}/admin/{url_suffix}"
            response = self.client.get(url)
            content = response.content.decode("utf-8")
            self.assertIn("fin-subnav", content, f"Subnav missing: {url_suffix}")

    def test_subnav_has_payment_operations(self):
        """Subnav should include عملیات پرداخت link."""
        self.client.login(username="p21_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        content = response.content.decode("utf-8")
        self.assertIn("عملیات پرداخت", content)


@override_settings(ROOT_URLCONF="config.urls")
class FinancialReportSecurityMigrationTest(TestCase, P21Mixin):
    """Security remains intact after template migration."""

    def setUp(self):
        self.company_a = self.create_company("p21_a")
        self.company_b = self.create_company("p21_b")
        self.admin_a = self.create_admin(self.company_a, "p21_admin_a")

    def test_cross_tenant_blocked(self):
        """Company A admin cannot access Company B financial reports."""
        self.client.login(username="p21_admin_a", password="testpass123")
        url = f"/{self.company_b.code}/admin/financial-reports/summary/"
        response = self.client.get(url)
        self.assertIn(response.status_code, [403, 302])

    def test_no_sensitive_data(self):
        """Reports should not expose banking/KYC field names."""
        self.client.login(username="p21_admin_a", password="testpass123")
        for url_suffix in REPORT_URLS:
            url = f"/{self.company_a.code}/admin/{url_suffix}"
            response = self.client.get(url)
            content = response.content.decode("utf-8")
            self.assertNotIn("national_card_image", content)
            self.assertNotIn("shaba_number", content)

    def test_no_mutation_forms(self):
        """Reports should not have payment/settlement POST forms."""
        self.client.login(username="p21_admin_a", password="testpass123")
        for url_suffix in REPORT_URLS:
            url = f"/{self.company_a.code}/admin/{url_suffix}"
            response = self.client.get(url)
            content = response.content.decode("utf-8")
            self.assertNotIn("mark_paid_company_cash", content)
            self.assertNotIn("mark_paid_technician_cash", content)

    def test_no_platform_owner_links(self):
        """Company reports should not expose platform owner URLs."""
        self.client.login(username="p21_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company_a.code}/admin/financial-reports/summary/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/owner-platform/", content)
