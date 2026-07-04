"""
EPIC-002 Wave 01, Issue 007: Dashboard charts must display Jalali dates.

Root cause: CompanyDashboardSelector.get_chart_data (apps/dashboard/selectors.py)
built the line-chart's day labels from the raw Gregorian day-of-month
(`str(day.day)`), which is not a valid Jalali day number since Jalali and
Gregorian months have different boundaries/lengths.

Fix: convert each day to its Jalali day-of-month via the existing
apps.common.jalali.gregorian_to_jalali helper (no new conversion logic was
written — this function already existed and is reused as-is).
"""
import itertools
import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.common.jalali import gregorian_to_jalali
from apps.dashboard.selectors import CompanyDashboardSelector
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(code=f"jc{n}", name=f"Jalali Chart Co {n}", slug=f"jc-co-{n}", is_active=True)


class DashboardChartJalaliDateTest(TestCase):
    def test_line_chart_labels_are_jalali_day_numbers(self):
        company = _company()
        chart_data = CompanyDashboardSelector.get_chart_data(company=company)
        labels = json.loads(chart_data["line_labels"])

        today = timezone.now().date()
        expected = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            _, _, jalali_day = gregorian_to_jalali(day.year, day.month, day.day)
            expected.append(str(jalali_day))

        self.assertEqual(labels, expected)

    def test_line_chart_has_seven_labels(self):
        company = _company()
        chart_data = CompanyDashboardSelector.get_chart_data(company=company)
        labels = json.loads(chart_data["line_labels"])
        self.assertEqual(len(labels), 7)
