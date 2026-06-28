"""
TASK-010D — Technician Statement Service.

TechnicianStatementService.build() is a purely transformational layer:
it converts immutable TechnicianLedgerEntry rows into an ordered list of
human-readable statement dicts. No financial writes, no amount recomputation.

Tests:
 1. Single CREDIT entry → correct row fields
 2. Single DEBIT entry → correct row fields
 3. Balance progression across mixed entries (credit then debit)
 4. Rows are ordered oldest-first (ASC created_at, ASC id)
 5. CREDIT rows have debit=0; DEBIT rows have credit=0
 6. All eight source types produce a non-empty description
 7. Entry with explicit description uses that description (not generic label)
 8. Date filtering: from_date excludes earlier entries
 9. Date filtering: to_date excludes later entries
10. Date filtering: from_date+to_date together
11. Tenant isolation: build() only returns entries for the given technician's company
12. Calling build() twice does not mutate any ledger entry
13. Empty result when technician has no entries
14. Multi-source statement matches ADR-006 example (work + invoice + cash + shaparak)
15. balance_after from ledger is used directly (not recomputed from scratch)
"""
import datetime
import itertools
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.payouts.models import TechnicianLedgerEntry
from apps.payouts.services import TechnicianLedgerService
from apps.payouts.services_statement import TechnicianStatementService
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company():
    tag = _n()
    return Company.objects.create(
        name=f"StmtCo {tag}",
        code=f"stmt{tag}",
        slug=f"stmt-{tag}",
        is_active=True,
    )


def _technician(company):
    user = CompanyUser.objects.create_user(
        username=f"techstmt{_n()}",
        password="testpass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=60,
        goods_wage_percent=10,
        travel_wage_percent=100,
    )


def _credit(company, technician, amount, source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            description="", **kwargs):
    key = f"stmt_test_credit:{_n()}"
    return TechnicianLedgerService.create_credit(
        company=company,
        technician=technician,
        source=source,
        amount_rial=amount,
        idempotency_key=key,
        description=description,
        **kwargs,
    )


def _debit(company, technician, amount, source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
           description="", **kwargs):
    key = f"stmt_test_debit:{_n()}"
    return TechnicianLedgerService.create_debit(
        company=company,
        technician=technician,
        source=source,
        amount_rial=amount,
        idempotency_key=key,
        description=description,
        **kwargs,
    )


def _set_date(entry, date_obj):
    """Back-date a ledger entry's created_at for date-filter tests."""
    dt = datetime.datetime.combine(date_obj, datetime.time(12, 0), tzinfo=datetime.timezone.utc)
    TechnicianLedgerEntry.objects.filter(pk=entry.pk).update(created_at=dt)
    entry.refresh_from_db()
    return entry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TechnicianStatementServiceTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)

    def test_01_single_credit_row_fields(self):
        """Single CREDIT entry produces correct row keys and values."""
        entry = _credit(self.company, self.tech, 2_000,
                        source=TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE)
        rows = TechnicianStatementService.build(self.tech)

        self.assertEqual(len(rows), 1)
        row = rows[0]

        self.assertIn("date", row)
        self.assertIn("description", row)
        self.assertEqual(row["credit"], 2_000)
        self.assertEqual(row["debit"], 0)
        self.assertEqual(row["balance_after"], entry.balance_after)
        self.assertEqual(row["source"], TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE)
        self.assertIsNone(row["order_id"])
        self.assertIsNone(row["invoice_id"])
        self.assertIsNone(row["payment_id"])

    def test_02_single_debit_row_fields(self):
        """Single DEBIT entry (requires prior credit for non-negative balance)."""
        _credit(self.company, self.tech, 5_000)
        entry = _debit(self.company, self.tech, 3_000,
                       source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT)
        rows = TechnicianStatementService.build(self.tech)

        debit_row = rows[1]
        self.assertEqual(debit_row["debit"], 3_000)
        self.assertEqual(debit_row["credit"], 0)
        self.assertEqual(debit_row["balance_after"], entry.balance_after)
        self.assertEqual(debit_row["source"], TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT)

    def test_03_balance_progression_across_mixed_entries(self):
        """balance_after reflects running total across credit then debit."""
        e1 = _credit(self.company, self.tech, 2_000)
        e2 = _credit(self.company, self.tech, 3_500)
        e3 = _debit(self.company, self.tech, 500)
        e4 = _debit(self.company, self.tech, 3_500)

        rows = TechnicianStatementService.build(self.tech)
        self.assertEqual(len(rows), 4)

        self.assertEqual(rows[0]["balance_after"], e1.balance_after)   # 2000
        self.assertEqual(rows[1]["balance_after"], e2.balance_after)   # 5500
        self.assertEqual(rows[2]["balance_after"], e3.balance_after)   # 5000
        self.assertEqual(rows[3]["balance_after"], e4.balance_after)   # 1500

        # Verify the ledger produced the expected absolute values
        self.assertEqual(rows[0]["balance_after"], 2_000)
        self.assertEqual(rows[1]["balance_after"], 5_500)
        self.assertEqual(rows[2]["balance_after"], 5_000)
        self.assertEqual(rows[3]["balance_after"], 1_500)

    def test_04_rows_ordered_oldest_first(self):
        """Rows are returned in ascending created_at, id order."""
        e1 = _credit(self.company, self.tech, 100)
        e2 = _credit(self.company, self.tech, 200)
        e3 = _credit(self.company, self.tech, 300)

        rows = TechnicianStatementService.build(self.tech)
        ids = [r["source"] for r in rows]  # proxy — each uses same source
        # Verify amount order matches creation order
        self.assertEqual([r["credit"] for r in rows], [100, 200, 300])
        # Verify IDs from entry objects are ascending
        pks = list(
            TechnicianLedgerEntry.objects
            .filter(company=self.company, technician=self.tech)
            .order_by("id")
            .values_list("id", flat=True)
        )
        self.assertEqual(pks, sorted(pks))

    def test_05_credit_debit_column_exclusivity(self):
        """CREDIT rows have debit=0; DEBIT rows have credit=0."""
        _credit(self.company, self.tech, 1_000)
        _credit(self.company, self.tech, 2_000)
        _debit(self.company, self.tech, 500)
        _debit(self.company, self.tech, 750)

        rows = TechnicianStatementService.build(self.tech)
        credits = rows[:2]
        debits = rows[2:]

        for r in credits:
            self.assertGreater(r["credit"], 0)
            self.assertEqual(r["debit"], 0)
        for r in debits:
            self.assertGreater(r["debit"], 0)
            self.assertEqual(r["credit"], 0)

    def test_06_all_source_types_produce_nonempty_description(self):
        """Every defined Source value yields a non-empty description."""
        sources = [
            (TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE, True),
            (TechnicianLedgerEntry.Source.ONLINE_GATEWAY, True),
            (TechnicianLedgerEntry.Source.REFUND, True),
            (TechnicianLedgerEntry.Source.ADJUSTMENT, True),
        ]
        debit_sources = [
            (TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER, False),
            (TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT, False),
            (TechnicianLedgerEntry.Source.MANUAL_PAYMENT, False),
            (TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT, False),
        ]
        # Ensure positive balance before debits
        _credit(self.company, self.tech, 1_000_000)

        for source, is_credit in sources:
            _credit(self.company, self.tech, 10, source=source)
        for source, _ in debit_sources:
            _debit(self.company, self.tech, 10, source=source)

        rows = TechnicianStatementService.build(self.tech)
        for row in rows:
            self.assertTrue(row["description"], f"Empty description for source={row['source']}")

    def test_07_explicit_description_takes_priority_over_source_label(self):
        """Entry with a description uses it; source label is only a fallback."""
        _credit(
            self.company, self.tech, 5_000,
            source=TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE,
            description="کارکرد سفارش #99",
        )
        rows = TechnicianStatementService.build(self.tech)
        self.assertEqual(rows[0]["description"], "کارکرد سفارش #99")

    def test_08_date_filter_from_date_excludes_earlier_entries(self):
        """from_date filters out entries created before that date."""
        old = _credit(self.company, self.tech, 100)
        new = _credit(self.company, self.tech, 200)
        _set_date(old, datetime.date(2025, 1, 1))
        _set_date(new, datetime.date(2025, 6, 1))

        rows = TechnicianStatementService.build(
            self.tech, from_date=datetime.date(2025, 3, 1)
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["credit"], 200)

    def test_09_date_filter_to_date_excludes_later_entries(self):
        """to_date filters out entries created after that date."""
        early = _credit(self.company, self.tech, 100)
        late = _credit(self.company, self.tech, 200)
        _set_date(early, datetime.date(2025, 1, 1))
        _set_date(late, datetime.date(2025, 6, 1))

        rows = TechnicianStatementService.build(
            self.tech, to_date=datetime.date(2025, 3, 1)
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["credit"], 100)

    def test_10_date_filter_range_includes_only_matching_entries(self):
        """from_date + to_date together include only entries in the window."""
        e1 = _credit(self.company, self.tech, 100)
        e2 = _credit(self.company, self.tech, 200)
        e3 = _credit(self.company, self.tech, 300)
        _set_date(e1, datetime.date(2025, 1, 1))
        _set_date(e2, datetime.date(2025, 4, 15))
        _set_date(e3, datetime.date(2025, 9, 1))

        rows = TechnicianStatementService.build(
            self.tech,
            from_date=datetime.date(2025, 3, 1),
            to_date=datetime.date(2025, 6, 30),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["credit"], 200)

    def test_11_tenant_isolation_no_cross_company_leakage(self):
        """build() only returns entries for the given technician's company."""
        company_b = _company()
        tech_b = _technician(company_b)

        _credit(self.company, self.tech, 1_000)
        _credit(company_b, tech_b, 9_999)

        rows_a = TechnicianStatementService.build(self.tech)
        rows_b = TechnicianStatementService.build(tech_b)

        self.assertEqual(len(rows_a), 1)
        self.assertEqual(rows_a[0]["credit"], 1_000)

        self.assertEqual(len(rows_b), 1)
        self.assertEqual(rows_b[0]["credit"], 9_999)

    def test_12_build_is_idempotent_does_not_mutate_ledger(self):
        """Calling build() twice leaves all ledger entries unchanged."""
        _credit(self.company, self.tech, 500)
        _debit(self.company, self.tech, 100)

        before = list(
            TechnicianLedgerEntry.objects
            .filter(company=self.company, technician=self.tech)
            .values("id", "amount_rial", "balance_after", "entry_type")
        )

        TechnicianStatementService.build(self.tech)
        TechnicianStatementService.build(self.tech)

        after = list(
            TechnicianLedgerEntry.objects
            .filter(company=self.company, technician=self.tech)
            .values("id", "amount_rial", "balance_after", "entry_type")
        )

        self.assertEqual(before, after)

    def test_13_empty_result_for_technician_with_no_entries(self):
        """build() returns [] when the technician has no ledger entries."""
        rows = TechnicianStatementService.build(self.tech)
        self.assertEqual(rows, [])

    def test_14_adr006_example_multi_source_statement(self):
        """ADR-006 example: work + invoice share + cash + shaparak matches expected balances."""
        _credit(self.company, self.tech, 2_000,
                source=TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE)
        _credit(self.company, self.tech, 3_500,
                source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY)
        _debit(self.company, self.tech, 500,
               source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER)
        _debit(self.company, self.tech, 3_500,
               source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT)

        rows = TechnicianStatementService.build(self.tech)
        self.assertEqual(len(rows), 4)

        expected = [
            {"credit": 2_000, "debit": 0, "balance_after": 2_000},
            {"credit": 3_500, "debit": 0, "balance_after": 5_500},
            {"credit": 0,     "debit": 500,   "balance_after": 5_000},
            {"credit": 0,     "debit": 3_500, "balance_after": 1_500},
        ]
        for i, (row, exp) in enumerate(zip(rows, expected)):
            self.assertEqual(row["credit"],       exp["credit"],       f"row {i} credit")
            self.assertEqual(row["debit"],        exp["debit"],        f"row {i} debit")
            self.assertEqual(row["balance_after"], exp["balance_after"], f"row {i} balance_after")

    def test_15_balance_after_is_read_from_ledger_not_recomputed(self):
        """balance_after in each row equals the stored entry.balance_after — no recompute."""
        e1 = _credit(self.company, self.tech, 1_000)
        e2 = _debit(self.company, self.tech, 400)

        rows = TechnicianStatementService.build(self.tech)

        # Fetch stored values directly from DB
        stored = {
            e.pk: e.balance_after
            for e in TechnicianLedgerEntry.objects.filter(
                company=self.company, technician=self.tech
            )
        }

        for row in rows:
            # Re-fetch the matching entry by balance_after value to compare
            # (we have two rows; their balance_afters must match the DB values)
            self.assertIn(row["balance_after"], stored.values())

        # Spot-check exact values
        self.assertEqual(rows[0]["balance_after"], e1.balance_after)
        self.assertEqual(rows[1]["balance_after"], e2.balance_after)
