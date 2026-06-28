"""
TASK-010I — Technician Statement CSV Export.

Endpoint: /<company_code>/admin/technicians/<id>/statement/export/

Produces a UTF-8-with-BOM CSV file suitable for Persian text in Excel.
Delegates entirely to TechnicianStatementService.build() — never reads the
ledger directly.

Tests:
 1. Export endpoint returns Content-Type: text/csv
 2. First CSV row contains Persian column headers
 3. Data rows correspond to TechnicianStatementService output (integration)
 4. Response content starts with the UTF-8 BOM bytes (EF BB BF)
 5. from_date / to_date GET params are forwarded to the service
 6. Cross-company technician ID returns 404 (tenant isolation)
 7. TechnicianStatementService.build() is called exactly once per export
 8. View does not query TechnicianLedgerEntry.objects directly
"""
import csv
import datetime
import io
import itertools
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.payouts.models import TechnicianLedgerEntry
from apps.payouts.services import TechnicianLedgerService
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    tag = _n()
    code = f"i010i{tag}"
    return Company.objects.create(name=f"ExportCo {tag}", code=code, slug=code, is_active=True)


def _user(company, role=UserRole.COMPANY_ADMIN):
    return CompanyUser.objects.create_user(
        username=f"ui{_n()}", password="testpass", company=company, role=role,
    )


def _technician(company):
    user = _user(company, role=UserRole.TECHNICIAN)
    return Technician.objects.create(
        company=company, user=user,
        service_wage_percent=60, goods_wage_percent=10, travel_wage_percent=100,
    )


def _credit(company, tech, amount):
    return TechnicianLedgerService.create_credit(
        company=company, technician=tech,
        source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
        amount_rial=amount,
        idempotency_key=f"i_credit:{_n()}",
    )


def _fake_statement(tech):
    return {
        "technician_id": tech.pk,
        "technician_name": "Export Tech",
        "from_date": None,
        "to_date": None,
        "rows": [
            {
                "date": datetime.datetime(2025, 6, 1, 12, 0, tzinfo=datetime.timezone.utc),
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
        "summary": {"total_credit": 5_000, "total_debit": 0, "final_balance": 5_000},
    }


def _read_csv(response):
    """Strip BOM from response content and parse as CSV."""
    content = response.content
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]
    return list(csv.reader(io.StringIO(content.decode("utf-8"))))


class StatementExportTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company)
        self.tech = _technician(self.company)
        self.url = f"/{self.company.code}/admin/technicians/{self.tech.id}/statement/export/"

    def test_01_export_returns_csv_content_type(self):
        """Export endpoint returns a response with Content-Type: text/csv."""
        _credit(self.company, self.tech, 1_000)
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_02_csv_first_row_has_persian_headers(self):
        """First CSV row contains the expected Persian column names."""
        self.client.force_login(self.admin)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ):
            response = self.client.get(self.url)
        rows = _read_csv(response)
        header = rows[0]
        self.assertIn("تاریخ", header)
        self.assertIn("شرح", header)
        self.assertIn("بستانکار", header)
        self.assertIn("بدهکار", header)
        self.assertIn("مانده", header)

    def test_03_csv_data_rows_match_service_output(self):
        """Data rows in the CSV correspond to TechnicianStatementService output."""
        _credit(self.company, self.tech, 3_000)
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        rows = _read_csv(response)
        # 1 header row + 1 data row
        self.assertEqual(len(rows), 2, f"Expected 2 rows (header+data), got {len(rows)}")
        # Credit is at index 2 in the data row
        self.assertEqual(rows[1][2], "3000")

    def test_04_response_starts_with_utf8_bom(self):
        """Response bytes begin with the UTF-8 BOM (0xEF 0xBB 0xBF)."""
        self.client.force_login(self.admin)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ):
            response = self.client.get(self.url)
        self.assertTrue(
            response.content.startswith(b"\xef\xbb\xbf"),
            f"BOM missing. First bytes: {response.content[:10]!r}",
        )

    def test_05_date_filters_forwarded_to_service(self):
        """from_date / to_date GET params are parsed and forwarded to TechnicianStatementService."""
        self.client.force_login(self.admin)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build:
            self.client.get(self.url + "?from_date=1404/01/01&to_date=1404/06/31")
        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        self.assertIsNotNone(kwargs.get("from_date"), "from_date must be parsed and forwarded")
        self.assertIsInstance(kwargs.get("from_date"), datetime.date)

    def test_06_cross_company_technician_returns_404(self):
        """Accessing a technician from another company returns 404."""
        company_b = _company()
        tech_b = _technician(company_b)
        cross_url = f"/{self.company.code}/admin/technicians/{tech_b.id}/statement/export/"
        self.client.force_login(self.admin)
        response = self.client.get(cross_url)
        self.assertEqual(response.status_code, 404)

    def test_07_service_called_exactly_once(self):
        """TechnicianStatementService.build() is invoked exactly once per export request."""
        self.client.force_login(self.admin)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build:
            self.client.get(self.url)
        mock_build.assert_called_once()

    def test_08_no_direct_ledger_query_in_export_view(self):
        """Export view must not access TechnicianLedgerEntry.objects directly."""
        self.client.force_login(self.admin)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build:
            with patch(
                "apps.payouts.models.TechnicianLedgerEntry.objects"
            ) as mock_ledger:
                self.client.get(self.url)
                mock_build.assert_called_once()
                mock_ledger.filter.assert_not_called()
                mock_ledger.all.assert_not_called()
