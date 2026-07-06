"""
Financial Portal — View Tests (Phase 1).

Tests that all portal pages load correctly for authorized users,
reject unauthorized access, maintain tenant isolation, and perform
no database writes on GET requests.
"""
import itertools
from decimal import Decimal

from django.test import TestCase, Client
from django.utils import timezone

from apps.accounts.models import CompanyUser, OperatorPermission, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payouts.models import (
    AdjustmentDocument,
    CompanyPlatformFeeEntry,
    EscrowRecord,
    FinancialBackfillTask,
    SettlementBatch,
    SettlementItem,
    TechnicianLedgerEntry,
)
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n():
    return next(_counter)



def _company(**overrides):
    tag = _n()
    defaults = {
        "name": f"Portal Test Co {tag}",
        "code": f"portal{tag}",
        "slug": f"portal-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _admin_user(company):
    return CompanyUser.objects.create_user(
        username=f"portaladmin{_n()}",
        password="testpass123",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _staff_user(company):
    user = CompanyUser.objects.create_user(
        username=f"portalstaff{_n()}",
        password="testpass123",
        company=company,
        role=UserRole.COMPANY_STAFF,
    )
    # Grant operator permissions for all financial portal pages.
    # The OperatorPermissionMiddleware requires explicit permission records
    # for COMPANY_STAFF users accessing /<code>/admin/ routes.
    portal_permission_keys = [
        "dashboard",
        "technician_list",
        "technician_detail",
        "settlement_list",
        "settlement_detail",
        "escrow_list",
        "adjustment_list",
        "reconciliation",
        "closing",
        "reports",
    ]
    for key in portal_permission_keys:
        OperatorPermission.objects.create(
            company=company,
            operator=user,
            permission_key=key,
            is_allowed=True,
        )
    return user


def _technician_user(company):
    user = CompanyUser.objects.create_user(
        username=f"portaltech{_n()}",
        password="testpass123",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    tech = Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=Decimal("60"),
        goods_wage_percent=Decimal("10"),
        travel_wage_percent=Decimal("100"),
    )
    return user, tech


PORTAL_URLS = [
    "/admin/financial-portal/",
    "/admin/financial-portal/technicians/",
    "/admin/financial-portal/settlements/",
    "/admin/financial-portal/escrows/",
    "/admin/financial-portal/adjustments/",
    "/admin/financial-portal/reconciliation/",
    "/admin/financial-portal/closing/",
    "/admin/financial-portal/reports/",
]



# =============================================================================
# 1. Company admin can access all pages
# =============================================================================

class AdminAccessTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin_user(self.company)
        self.client = Client()
        self.client.login(username=self.admin.username, password="testpass123")

    def test_dashboard_loads(self):
        url = f"/{self.company.code}/admin/financial-portal/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_technician_list_loads(self):
        url = f"/{self.company.code}/admin/financial-portal/technicians/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_settlement_list_loads(self):
        url = f"/{self.company.code}/admin/financial-portal/settlements/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_escrow_list_loads(self):
        url = f"/{self.company.code}/admin/financial-portal/escrows/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_adjustment_list_loads(self):
        url = f"/{self.company.code}/admin/financial-portal/adjustments/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_reconciliation_loads(self):
        url = f"/{self.company.code}/admin/financial-portal/reconciliation/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_closing_loads(self):
        url = f"/{self.company.code}/admin/financial-portal/closing/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_reports_loads(self):
        url = f"/{self.company.code}/admin/financial-portal/reports/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_technician_detail_loads(self):
        _, tech = _technician_user(self.company)
        url = f"/{self.company.code}/admin/financial-portal/technicians/{tech.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# =============================================================================
# 2. Unauthorized user cannot access
# =============================================================================

class UnauthorizedAccessTest(TestCase):

    def test_unauthenticated_user_redirected(self):
        company = _company()
        client = Client()
        for path in PORTAL_URLS:
            url = f"/{company.code}{path}"
            response = client.get(url)
            self.assertIn(
                response.status_code, [301, 302],
                f"Expected redirect for {url}, got {response.status_code}",
            )


# =============================================================================
# 3. Technician/customer cannot access
# =============================================================================

class TechnicianCannotAccessTest(TestCase):

    def test_technician_gets_403(self):
        company = _company()
        tech_user, _ = _technician_user(company)
        client = Client()
        client.login(username=tech_user.username, password="testpass123")

        for path in PORTAL_URLS:
            url = f"/{company.code}{path}"
            response = client.get(url)
            self.assertEqual(
                response.status_code, 403,
                f"Expected 403 for technician at {url}, got {response.status_code}",
            )


# =============================================================================
# 4. Tenant isolation
# =============================================================================

class TenantIsolationTest(TestCase):

    def test_admin_cannot_access_other_company_portal(self):
        company_a = _company()
        company_b = _company()
        admin_a = _admin_user(company_a)
        client = Client()
        client.login(username=admin_a.username, password="testpass123")

        # Try accessing company_b's portal
        url = f"/{company_b.code}/admin/financial-portal/"
        response = client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_settlement_detail_tenant_isolated(self):
        company_a = _company()
        company_b = _company()
        admin_a = _admin_user(company_a)

        # Create a batch in company_b
        from apps.payouts.services_settlement_batch import SettlementBatchService
        from datetime import timedelta
        now = timezone.now()
        batch_b = SettlementBatchService.create_batch(
            company=company_b,
            level="platform_to_org",
            period_start=now - timedelta(days=1),
            period_end=now,
        )

        client = Client()
        client.login(username=admin_a.username, password="testpass123")

        # company_a admin cannot see company_b's batch
        url = f"/{company_a.code}/admin/financial-portal/settlements/{batch_b.id}/"
        response = client.get(url)
        self.assertEqual(response.status_code, 404)



# =============================================================================
# 5. Dashboard loads with empty data
# =============================================================================

class EmptyDataTest(TestCase):

    def test_dashboard_with_no_financial_data(self):
        company = _company()
        admin = _admin_user(company)
        client = Client()
        client.login(username=admin.username, password="testpass123")

        url = f"/{company.code}/admin/financial-portal/"
        response = self.client.get(url) if hasattr(self, 'client') else client.get(url)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_all_pages_with_no_data(self):
        company = _company()
        admin = _admin_user(company)
        client = Client()
        client.login(username=admin.username, password="testpass123")

        for path in PORTAL_URLS:
            url = f"/{company.code}{path}"
            response = client.get(url)
            self.assertEqual(
                response.status_code, 200,
                f"Expected 200 for empty {url}, got {response.status_code}",
            )


# =============================================================================
# 6. No database writes on GET pages
# =============================================================================

class NoDatabaseWriteTest(TestCase):

    def test_no_writes_on_portal_pages(self):
        company = _company()
        admin = _admin_user(company)
        _, tech = _technician_user(company)
        client = Client()
        client.login(username=admin.username, password="testpass123")

        counts_before = {
            "invoice": Invoice.objects.count(),
            "payment": Payment.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "settlement_batch": SettlementBatch.objects.count(),
            "settlement_item": SettlementItem.objects.count(),
            "ledger": TechnicianLedgerEntry.objects.count(),
            "platform_fee": CompanyPlatformFeeEntry.objects.count(),
            "backfill": FinancialBackfillTask.objects.count(),
            "adjustment": AdjustmentDocument.objects.count(),
        }

        # Visit all pages
        for path in PORTAL_URLS:
            url = f"/{company.code}{path}"
            client.get(url)

        # Also visit technician detail
        url = f"/{company.code}/admin/financial-portal/technicians/{tech.id}/"
        client.get(url)

        counts_after = {
            "invoice": Invoice.objects.count(),
            "payment": Payment.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "settlement_batch": SettlementBatch.objects.count(),
            "settlement_item": SettlementItem.objects.count(),
            "ledger": TechnicianLedgerEntry.objects.count(),
            "platform_fee": CompanyPlatformFeeEntry.objects.count(),
            "backfill": FinancialBackfillTask.objects.count(),
            "adjustment": AdjustmentDocument.objects.count(),
        }

        self.assertEqual(counts_before, counts_after)


# =============================================================================
# 7. Staff (operator) can access
# =============================================================================

class StaffAccessTest(TestCase):

    def test_staff_can_access_dashboard(self):
        company = _company()
        staff = _staff_user(company)
        client = Client()
        client.login(username=staff.username, password="testpass123")

        url = f"/{company.code}/admin/financial-portal/"
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_staff_can_access_reconciliation(self):
        company = _company()
        staff = _staff_user(company)
        client = Client()
        client.login(username=staff.username, password="testpass123")

        url = f"/{company.code}/admin/financial-portal/reconciliation/"
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
