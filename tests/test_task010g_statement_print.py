"""
TASK-010G — Technician Statement Print/PDF view layer.

Print endpoint:  /<company_code>/admin/technicians/<id>/statement/print/
PDF endpoint:    /<company_code>/admin/technicians/<id>/statement/pdf/

Both endpoints delegate to TechnicianStatementService.build() and apply the
same from_date/to_date filters as the main statement view.

Tests:
 1. Print page returns HTTP 200 for authenticated COMPANY_ADMIN
 2. Print page calls TechnicianStatementService.build() exactly once
 3. Print page forwards from_date / to_date filter params to the service
 4. Cross-company technician ID returns 404 (tenant isolation)
 5. Unauthenticated request redirects; TECHNICIAN role receives 403
"""
import datetime
import itertools
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    tag = _n()
    code = f"g010g{tag}"
    return Company.objects.create(name=f"PrintCo {tag}", code=code, slug=code, is_active=True)


def _user(company, role=UserRole.COMPANY_ADMIN):
    return CompanyUser.objects.create_user(
        username=f"ug{_n()}", password="testpass", company=company, role=role,
    )


def _technician(company):
    user = _user(company, role=UserRole.TECHNICIAN)
    return Technician.objects.create(
        company=company, user=user,
        service_wage_percent=60, goods_wage_percent=10, travel_wage_percent=100,
    )


def _fake_statement(tech):
    return {
        "technician_id": tech.pk,
        "technician_name": "Test Tech",
        "from_date": None,
        "to_date": None,
        "rows": [],
        "summary": {"total_credit": 0, "total_debit": 0, "final_balance": 0},
    }


class TechnicianStatementPrintTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, role=UserRole.COMPANY_ADMIN)
        self.tech = _technician(self.company)
        self.print_url = f"/{self.company.code}/admin/technicians/{self.tech.id}/statement/print/"

    def test_01_print_page_returns_200_for_admin(self):
        """Authenticated COMPANY_ADMIN gets HTTP 200 on the print endpoint."""
        self.client.force_login(self.admin)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ):
            response = self.client.get(self.print_url)
        self.assertEqual(response.status_code, 200)

    def test_02_print_page_calls_service_exactly_once(self):
        """Print page delegates to TechnicianStatementService.build() exactly once."""
        self.client.force_login(self.admin)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build:
            self.client.get(self.print_url)
        mock_build.assert_called_once()

    def test_03_print_page_forwards_date_filters(self):
        """from_date / to_date GET params are parsed and forwarded to the service."""
        self.client.force_login(self.admin)
        with patch(
            "apps.payouts.views.TechnicianStatementService.build",
            return_value=_fake_statement(self.tech),
        ) as mock_build:
            self.client.get(self.print_url + "?from_date=1404/01/01&to_date=1404/06/31")
        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        from_date = kwargs.get("from_date")
        self.assertIsNotNone(from_date, "from_date must be parsed and forwarded")
        self.assertIsInstance(from_date, datetime.date)

    def test_04_cross_company_technician_returns_404(self):
        """Technician from a different company via this company's URL returns 404."""
        company_b = _company()
        tech_b = _technician(company_b)
        cross_url = f"/{self.company.code}/admin/technicians/{tech_b.id}/statement/print/"
        self.client.force_login(self.admin)
        response = self.client.get(cross_url)
        self.assertEqual(response.status_code, 404)

    def test_05_unauthorized_users_are_blocked(self):
        """Anonymous request redirects; TECHNICIAN role receives 403."""
        response = self.client.get(self.print_url)
        self.assertIn(response.status_code, [301, 302], "Anonymous must be redirected")

        tech_user = self.tech.user
        self.client.force_login(tech_user)
        response2 = self.client.get(self.print_url)
        self.assertEqual(response2.status_code, 403)
