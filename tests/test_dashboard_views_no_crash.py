"""
Regression: technician_home and customer_home must not crash with NameError.

Before fix: both views referenced chart_data in their render context but
            never assigned it — NameError on every request.
After fix:  both views pass chart_data={} (empty dict) so templates that
            don't use chart data render safely.
"""
import itertools

from django.test import RequestFactory, TestCase

from apps.accounts.models import CompanyUser, Customer, Technician, UserRole
from apps.dashboard import views as dashboard_views
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(code=f"dv{n}", name=f"DV Co {n}", slug=f"dv-co-{n}", is_active=True)


def _user(company, role):
    n = _n()
    return CompanyUser.objects.create_user(
        username=f"u{n}", password="pw", company=company, role=role,
    )


def _request(company, user, path="/fake/"):
    rf = RequestFactory()
    req = rf.get(path)
    req.company = company
    req.user = user
    return req


class TechnicianHomeNoCrashTest(TestCase):
    """technician_home must return 200 without raising NameError."""

    def setUp(self):
        self.company = _company()
        user = _user(self.company, UserRole.TECHNICIAN)
        self.technician = Technician.objects.create(
            company=self.company, user=user, is_available=True,
        )
        self.user = user

    def test_technician_home_returns_200(self):
        req = _request(self.company, self.user)
        response = dashboard_views.technician_home(req)
        self.assertEqual(response.status_code, 200)

    def test_technician_home_chart_data_is_empty_dict(self):
        from unittest.mock import patch
        from django.http import HttpResponse

        captured = {}

        def _fake_render(request, template, ctx, **kwargs):
            captured.update(ctx)
            return HttpResponse("ok")

        req = _request(self.company, self.user)
        with patch("apps.dashboard.views.render", side_effect=_fake_render):
            dashboard_views.technician_home(req)

        self.assertIn("chart_data", captured)
        self.assertEqual(captured["chart_data"], {})


class CustomerHomeNoCrashTest(TestCase):
    """customer_home must return 200 without raising NameError."""

    def setUp(self):
        self.company = _company()
        user = _user(self.company, UserRole.CUSTOMER)
        self.customer = Customer.objects.create(
            company=self.company,
            user=user,
            first_name="Test",
            last_name="Customer",
            phone="09001234567",
        )
        self.user = user

    def test_customer_home_returns_200(self):
        req = _request(self.company, self.user)
        response = dashboard_views.customer_home(req)
        self.assertEqual(response.status_code, 200)

    def test_customer_home_chart_data_is_empty_dict(self):
        from unittest.mock import patch
        from django.http import HttpResponse

        captured = {}

        def _fake_render(request, template, ctx, **kwargs):
            captured.update(ctx)
            return HttpResponse("ok")

        req = _request(self.company, self.user)
        with patch("apps.dashboard.views.render", side_effect=_fake_render):
            dashboard_views.customer_home(req)

        self.assertIn("chart_data", captured)
        self.assertEqual(captured["chart_data"], {})
