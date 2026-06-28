"""
TASK-010F — Technician Statement UI (view layer).

The view at /<company_code>/admin/technicians/<id>/statement/ delegates
exclusively to TechnicianStatementService.build(); it never touches
TechnicianLedgerEntry directly.

Tests:
 1. View returns 200 for an authenticated COMPANY_ADMIN with a valid technician
 2. Unauthenticated request redirects to login
 3. TECHNICIAN role user receives 403 (role gate)
 4. Cross-company technician ID in the URL returns 404 (tenant isolation)
 5. Date filters are forwarded to TechnicianStatementService.build()
 6. Response context includes 'statement' key with rows and summary
 7. TechnicianStatementService is called exactly once per request
 8. View never queries TechnicianLedgerEntry directly (delegates to service)
"""
import datetime
import itertools
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.payouts.models import TechnicianLedgerEntry
from apps.payouts.services import TechnicianLedgerService
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company(code=None):
    tag = _n()
    c = code or f"f010f{tag}"
    return Company.objects.create(
        name=f"StmtUICo {tag}",
        code=c,
        slug=c,
        is_active=True,
    )


def _user(company, role=UserRole.COMPANY_ADMIN, username=None):
    uname = username or f"u{_n()}"
    return CompanyUser.objects.create_user(
        username=uname,
        password="testpass",
        company=company,
        role=role,
    )


def _technician(company):
    user = _user(company, role=UserRole.TECHNICIAN, username=f"tech{_n()}")
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=60,
        goods_wage_percent=10,
        travel_wage_percent=100,
    )


def _credit(company, tech, amount):
    return TechnicianLedgerService.create_credit(
        company=company,
        technician=tech,
        source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
        amount_rial=amount,
        idempotency_key=f"f_credit:{_n()}",
    )


def _debit(company, tech, amount):
    return TechnicianLedgerService.create_debit(
        company=company,
        technician=tech,
        source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
        amount_rial=amount,
        idempotency_key=f"f_debit:{_n()}",
    )


# Minimal fake statement returned by mocked service
def _fake_statement(technician):
    return {
        "technician_id": technician.pk,
        "technician_name": "Test Tech",
        "from_date": None,
        "to_date": None,
        "rows": [
            {
                "date": datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc),
                "description": "سهم تکنسین از فاکتور",
                "credit": 5_000,
                "debit": 0,
                "balance_after": 5_000,
                "source": "online_gateway",
                "order_id": None,
                "invoice_id": None,
                "payment_id": None,
            }
        ],
        "summary": {
            "total_credit": 5_000,
            "total_debit": 0,
            "final_balance": 5_000,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TechnicianStatementViewTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, role=UserRole.COMPANY_ADMIN)
        self.tech = _technician(self.company)
        self.url = f"/{self.company.code}/admin/technicians/{self.tech.id}/statement/"

    def test_01_view_returns_200_for_valid_admin_and_technician(self):
        """Authenticated COMPANY_ADMIN gets HTTP 200 for a valid technician."""
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_02_unauthenticated_request_redirects_to_login(self):
        """Anonymous request is redirected (not 200 or 404)."""
        response = self.client.get(self.url)
        self.assertIn(response.status_code, [301, 302])

    def test_03_technician_role_receives_403(self):
        """A TECHNICIAN-role user cannot access the admin statement page."""
        tech_user = self.tech.user
        self.client.force_login(tech_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_04_cross_company_technician_returns_404(self):
        """Accessing a technician from another company via this company's URL returns 404."""
        company_b = _company()
        tech_b = _technician(company_b)
        # URL uses self.company.code but tech_b belongs to company_b
        cross_url = f"/{self.company.code}/admin/technicians/{tech_b.id}/statement/"
        self.client.force_login(self.admin)
        response = self.client.get(cross_url)
        self.assertEqual(response.status_code, 404)

    def test_05_date_filters_are_forwarded_to_service(self):
        """from_date and to_date GET params are parsed and forwarded to TechnicianStatementService.build()."""
        self.client.force_login(self.admin)

        # Use Jalali dates (1404/01/01 = 2025-03-21 Gregorian).
        # The exact Gregorian value is format-dependent; we only assert
        # that non-None datetime.date objects reach the service.
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build:
            self.client.get(self.url + "?from_date=1404/01/01&to_date=1404/06/31")

        mock_build.assert_called_once()
        args, kwargs = mock_build.call_args
        from_date = kwargs.get("from_date")
        to_date = kwargs.get("to_date")
        self.assertIsNotNone(from_date, "from_date must be parsed and forwarded")
        self.assertIsNotNone(to_date, "to_date must be parsed and forwarded")
        self.assertIsInstance(from_date, datetime.date)
        self.assertIsInstance(to_date, datetime.date)
        # Ensure empty string does not produce a date (null-filter case)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build_no_dates:
            self.client.get(self.url)
        _, kwargs_no = mock_build_no_dates.call_args
        self.assertIsNone(kwargs_no.get("from_date"))
        self.assertIsNone(kwargs_no.get("to_date"))

    def test_06_context_includes_statement_with_rows_and_summary(self):
        """Response context contains 'statement' with rows list and summary dict."""
        _credit(self.company, self.tech, 3_000)
        _debit(self.company, self.tech, 1_000)

        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("statement", response.context)

        statement = response.context["statement"]
        self.assertIn("rows", statement)
        self.assertIn("summary", statement)

        summary = statement["summary"]
        self.assertIn("total_credit", summary)
        self.assertIn("total_debit", summary)
        self.assertIn("final_balance", summary)

        self.assertEqual(summary["total_credit"], 3_000)
        self.assertEqual(summary["total_debit"], 1_000)
        self.assertEqual(len(statement["rows"]), 2)

    def test_07_service_called_exactly_once_per_request(self):
        """TechnicianStatementService.build() is invoked exactly once per page load."""
        self.client.force_login(self.admin)

        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build:
            self.client.get(self.url)

        mock_build.assert_called_once()

    def test_08_view_does_not_query_ledger_directly(self):
        """
        The view must not call TechnicianLedgerEntry.objects directly;
        all data access goes through TechnicianStatementService.
        """
        self.client.force_login(self.admin)

        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build:
            with patch(
                "apps.payouts.models.TechnicianLedgerEntry.objects"
            ) as mock_ledger_mgr:
                self.client.get(self.url)
                # Service was called
                mock_build.assert_called_once()
                # Direct ledger manager was NOT called from the view layer
                mock_ledger_mgr.filter.assert_not_called()
                mock_ledger_mgr.all.assert_not_called()
