"""
TASK-010H — Shaparak / Gateway Settlement Reconciliation Review.

Page at /<company_code>/admin/payments/gateway-reconciliation/

Shows PaymentSplitSnapshot rows for the current company with optional date and
split-status filters. Read-only — no financial writes or corrections are allowed.

Tests:
 1. Page returns HTTP 200 for authenticated COMPANY_ADMIN
 2. Only current company snapshots appear (tenant isolation)
 3. Both split and non-split rows are visible without a filter
 4. split=yes filter restricts to should_split_with_technician=True rows only
 5. POST request returns 405 (read-only guard)
"""
import itertools

from django.test import TestCase

from apps.accounts.models import CompanyUser, UserRole
from apps.payments.models import Payment
from apps.payouts.models import PaymentSplitSnapshot
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    tag = _n()
    code = f"h010h{tag}"
    return Company.objects.create(name=f"RecoCo {tag}", code=code, slug=code, is_active=True)


def _user(company, role=UserRole.COMPANY_ADMIN):
    return CompanyUser.objects.create_user(
        username=f"rh{_n()}", password="testpass", company=company, role=role,
    )


def _payment(company):
    """Minimal payment — gateway and invoice are nullable."""
    return Payment.objects.create(company=company, amount=10_000, status=Payment.Status.PAID)


def _snapshot(company, payment, should_split=False, total=10_000, direct=0, deposit=10_000):
    return PaymentSplitSnapshot.objects.create(
        company=company,
        payment=payment,
        total_amount=total,
        technician_direct_amount=direct,
        company_deposit_amount=deposit,
        should_split_with_technician=should_split,
        payout_strategy_snapshot="SPLIT_WITH_TECHNICIAN" if should_split else "DIRECT_TO_COMPANY",
        reason="split_with_verified_technician" if should_split else "payout_strategy_is_direct_to_company",
    )


class GatewayReconciliationTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company)
        self.url = f"/{self.company.code}/admin/payments/gateway-reconciliation/"

    def test_01_page_returns_200_for_admin(self):
        """Authenticated COMPANY_ADMIN receives HTTP 200."""
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_02_only_current_company_snapshots_shown(self):
        """PaymentSplitSnapshot rows from other companies must not appear."""
        company_b = _company()
        pmt_a = _payment(self.company)
        pmt_b = _payment(company_b)
        snap_a = _snapshot(self.company, pmt_a)
        _snapshot(company_b, pmt_b)

        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        snapshots = list(response.context["snapshots"])
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].company_id, self.company.id)
        self.assertEqual(snapshots[0].id, snap_a.id)

    def test_03_split_and_non_split_rows_visible_without_filter(self):
        """Both should_split=True and False rows appear when no filter is set."""
        pmt1 = _payment(self.company)
        pmt2 = _payment(self.company)
        _snapshot(self.company, pmt1, should_split=True, direct=5_000, deposit=5_000)
        _snapshot(self.company, pmt2, should_split=False)

        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        snapshots = list(response.context["snapshots"])
        split_flags = {s.should_split_with_technician for s in snapshots}
        self.assertIn(True, split_flags)
        self.assertIn(False, split_flags)

    def test_04_split_filter_restricts_to_split_rows(self):
        """?split=yes returns only should_split_with_technician=True rows."""
        pmt1 = _payment(self.company)
        pmt2 = _payment(self.company)
        _snapshot(self.company, pmt1, should_split=True, direct=5_000, deposit=5_000)
        _snapshot(self.company, pmt2, should_split=False)

        self.client.force_login(self.admin)
        response = self.client.get(self.url + "?split=yes")
        self.assertEqual(response.status_code, 200)
        snapshots = list(response.context["snapshots"])
        self.assertTrue(len(snapshots) >= 1)
        self.assertTrue(all(s.should_split_with_technician for s in snapshots))

    def test_05_post_returns_405(self):
        """POST to the reconciliation page returns 405 Method Not Allowed."""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, data={})
        self.assertEqual(response.status_code, 405)
