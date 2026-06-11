"""
P20-UI-FINANCIAL-REPORTS-POLISH: Smoke tests for financial report pages.

Covers:
1. All six financial report pages render 200 for company admin
2. Cross-tenant access blocked
3. Pages contain financial report subnav with عملیات پرداخت
4. Pages contain known financial labels (not values which depend on data)
5. No sensitive banking/KYC fields exposed
6. No payment mutation forms/actions on report pages
7. Platform owner links not exposed in company reports
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P20TestMixin:
    def create_company(self, code="p20_co"):
        return Company.objects.create(code=code, name="P20 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p20_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )


REPORT_URLS = [
    "financial-reports/summary/",
    "financial-reports/technicians/",
    "financial-reports/invoices/",
    "financial-reports/cash-control/",
    "financial-reports/platform-fees/",
    "financial-reports/audit/",
]


@override_settings(ROOT_URLCONF="config.urls")
class FinancialReportRenderTest(TestCase, P20TestMixin):
    """All six financial report pages render successfully."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)

    def test_all_reports_render_200(self):
        """Each financial report page returns 200 for company admin."""
        self.client.login(username="p20_admin", password="testpass123")
        for url_suffix in REPORT_URLS:
            url = f"/{self.company.code}/admin/{url_suffix}"
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 200,
                f"Expected 200 for {url}, got {response.status_code}"
            )

    def test_summary_contains_financial_labels(self):
        """Summary page should contain key financial labels."""
        self.client.login(username="p20_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        content = response.content.decode("utf-8")
        # These labels should exist regardless of data
        self.assertIn("داشبورد مالی", content)
        self.assertIn("فروش کل", content)

    def test_reports_contain_subnav(self):
        """All report pages should contain the financial subnav."""
        self.client.login(username="p20_admin", password="testpass123")
        for url_suffix in REPORT_URLS:
            url = f"/{self.company.code}/admin/{url_suffix}"
            response = self.client.get(url)
            content = response.content.decode("utf-8")
            self.assertIn("fin-subnav", content, f"Subnav missing in {url_suffix}")

    def test_subnav_contains_payment_operations_link(self):
        """Financial subnav should include عملیات پرداخت link (P14)."""
        self.client.login(username="p20_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/financial-reports/summary/")
        content = response.content.decode("utf-8")
        self.assertIn("عملیات پرداخت", content)
        self.assertIn("/admin/payments/operations/", content)


@override_settings(ROOT_URLCONF="config.urls")
class FinancialReportSecurityTest(TestCase, P20TestMixin):
    """Financial reports do not expose sensitive data or cross-tenant access."""

    def setUp(self):
        self.company_a = self.create_company("p20_a")
        self.company_b = self.create_company("p20_b")
        self.admin_a = self.create_admin(self.company_a, "p20_admin_a")

    def test_cross_tenant_blocked(self):
        """Company A admin cannot access Company B's financial reports."""
        self.client.login(username="p20_admin_a", password="testpass123")
        url = f"/{self.company_b.code}/admin/financial-reports/summary/"
        response = self.client.get(url)
        self.assertIn(response.status_code, [403, 302])

    def test_no_sensitive_kyc_data(self):
        """Financial reports should not expose sensitive banking/KYC terms."""
        self.client.login(username="p20_admin_a", password="testpass123")
        for url_suffix in REPORT_URLS:
            url = f"/{self.company_a.code}/admin/{url_suffix}"
            response = self.client.get(url)
            content = response.content.decode("utf-8")
            self.assertNotIn("national_card_image", content)
            self.assertNotIn("shaba_number", content)
            self.assertNotIn("bank_card_number", content)

    def test_no_platform_owner_links(self):
        """Company financial reports should not contain platform owner links."""
        self.client.login(username="p20_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company_a.code}/admin/financial-reports/summary/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/owner-platform/", content)

    def test_no_payment_mutation_forms(self):
        """Financial report pages should NOT have mark_paid or settlement POST forms."""
        self.client.login(username="p20_admin_a", password="testpass123")
        for url_suffix in REPORT_URLS:
            url = f"/{self.company_a.code}/admin/{url_suffix}"
            response = self.client.get(url)
            content = response.content.decode("utf-8")
            self.assertNotIn("mark_paid_company_cash", content)
            self.assertNotIn("mark_paid_technician_cash", content)
