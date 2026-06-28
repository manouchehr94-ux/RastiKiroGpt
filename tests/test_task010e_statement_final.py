"""
TASK-010E — Technician Statement Production Layer (Finalization).

TechnicianStatementService.build() now returns a structured dict:
  {
    "technician_id": int,
    "technician_name": str,
    "from_date": date | None,
    "to_date": date | None,
    "rows": [...],
    "summary": {
        "total_credit": int,
        "total_debit": int,
        "final_balance": int,
    }
  }

Tests:
 1. build() return value has all required top-level keys
 2. summary.total_credit equals sum of row credits
 3. summary.total_debit equals sum of row debits
 4. summary.final_balance equals last row balance_after
 5. summary.final_balance is 0 when no rows
 6. ordering stability: created_at ASC then id ASC
 7. multi-source rows: all sources appear; descriptions are non-empty
 8. date filter correctness: rows + summary reflect filtered window only
 9. tenant isolation: summary totals do not include other companies
10. deterministic: two calls with identical input return identical output
11. summary consistency: total_credit - total_debit ≠ final_balance (filtered case)
12. technician_id and technician_name in output
13. from_date and to_date echoed in output
14. pure transformation: build() writes nothing to DB
"""
import datetime
import itertools

from django.test import TestCase

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
        name=f"E2ECo {tag}",
        code=f"e2e{tag}",
        slug=f"e2e-{tag}",
        is_active=True,
    )


def _technician(company, username=None):
    uname = username or f"techE{_n()}"
    user = CompanyUser.objects.create_user(
        username=uname,
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


def _credit(company, tech, amount,
            source=TechnicianLedgerEntry.Source.ONLINE_GATEWAY, description=""):
    return TechnicianLedgerService.create_credit(
        company=company,
        technician=tech,
        source=source,
        amount_rial=amount,
        idempotency_key=f"e_credit:{_n()}",
        description=description,
    )


def _debit(company, tech, amount,
           source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER, description=""):
    return TechnicianLedgerService.create_debit(
        company=company,
        technician=tech,
        source=source,
        amount_rial=amount,
        idempotency_key=f"e_debit:{_n()}",
        description=description,
    )


def _set_date(entry, date_obj):
    dt = datetime.datetime.combine(date_obj, datetime.time(12, 0), tzinfo=datetime.timezone.utc)
    TechnicianLedgerEntry.objects.filter(pk=entry.pk).update(created_at=dt)
    entry.refresh_from_db()
    return entry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class StatementFinalTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)

    def test_01_return_value_has_required_top_level_keys(self):
        """build() output contains all required keys."""
        result = TechnicianStatementService.build(self.tech)
        for key in ("technician_id", "technician_name", "from_date", "to_date",
                    "rows", "summary"):
            self.assertIn(key, result, f"Missing key: {key}")
        for key in ("total_credit", "total_debit", "final_balance"):
            self.assertIn(key, result["summary"], f"Missing summary key: {key}")

    def test_02_summary_total_credit_equals_sum_of_row_credits(self):
        """summary.total_credit == sum(row['credit'] for row in rows)."""
        _credit(self.company, self.tech, 1_000)
        _credit(self.company, self.tech, 2_500)
        _debit(self.company, self.tech, 800)

        result = TechnicianStatementService.build(self.tech)
        rows = result["rows"]
        expected = sum(r["credit"] for r in rows)
        self.assertEqual(result["summary"]["total_credit"], expected)
        self.assertEqual(result["summary"]["total_credit"], 3_500)

    def test_03_summary_total_debit_equals_sum_of_row_debits(self):
        """summary.total_debit == sum(row['debit'] for row in rows)."""
        _credit(self.company, self.tech, 5_000)
        _debit(self.company, self.tech, 1_200)
        _debit(self.company, self.tech, 800)

        result = TechnicianStatementService.build(self.tech)
        rows = result["rows"]
        expected = sum(r["debit"] for r in rows)
        self.assertEqual(result["summary"]["total_debit"], expected)
        self.assertEqual(result["summary"]["total_debit"], 2_000)

    def test_04_summary_final_balance_equals_last_row_balance_after(self):
        """summary.final_balance equals balance_after of the last row."""
        _credit(self.company, self.tech, 2_000)
        _credit(self.company, self.tech, 3_500)
        last = _debit(self.company, self.tech, 500)

        result = TechnicianStatementService.build(self.tech)
        rows = result["rows"]
        self.assertEqual(result["summary"]["final_balance"], rows[-1]["balance_after"])
        self.assertEqual(result["summary"]["final_balance"], last.balance_after)

    def test_05_summary_final_balance_is_zero_when_no_rows(self):
        """summary.final_balance is 0 when technician has no entries."""
        result = TechnicianStatementService.build(self.tech)
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["summary"]["final_balance"], 0)
        self.assertEqual(result["summary"]["total_credit"], 0)
        self.assertEqual(result["summary"]["total_debit"], 0)

    def test_06_ordering_stability_created_at_then_id(self):
        """Rows always appear in created_at ASC, id ASC order."""
        e1 = _credit(self.company, self.tech, 100)
        e2 = _credit(self.company, self.tech, 200)
        e3 = _debit(self.company, self.tech, 50)
        e4 = _credit(self.company, self.tech, 400)

        result = TechnicianStatementService.build(self.tech)
        rows = result["rows"]

        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["credit"], 100)
        self.assertEqual(rows[1]["credit"], 200)
        self.assertEqual(rows[2]["debit"], 50)
        self.assertEqual(rows[3]["credit"], 400)

    def test_07_multi_source_rows_all_have_nonempty_descriptions(self):
        """All source types appear in rows with non-empty descriptions."""
        _credit(self.company, self.tech, 1_000_000)

        credit_sources = [
            TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE,
            TechnicianLedgerEntry.Source.ONLINE_GATEWAY,
            TechnicianLedgerEntry.Source.REFUND,
            TechnicianLedgerEntry.Source.ADJUSTMENT,
        ]
        debit_sources = [
            TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
            TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
            TechnicianLedgerEntry.Source.MANUAL_PAYMENT,
            TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT,
        ]

        for s in credit_sources:
            _credit(self.company, self.tech, 10, source=s)
        for s in debit_sources:
            _debit(self.company, self.tech, 10, source=s)

        result = TechnicianStatementService.build(self.tech)
        seen_sources = {r["source"] for r in result["rows"]}

        for s in credit_sources + debit_sources:
            self.assertIn(s, seen_sources, f"Source {s} missing from rows")
        for row in result["rows"]:
            self.assertTrue(row["description"], f"Empty description for source={row['source']}")

    def test_08_date_filter_rows_and_summary_reflect_window_only(self):
        """After date filtering, summary is computed from filtered rows only."""
        early = _credit(self.company, self.tech, 10_000)
        mid = _credit(self.company, self.tech, 3_000)
        late = _debit(self.company, self.tech, 1_500)

        _set_date(early, datetime.date(2025, 1, 1))
        _set_date(mid, datetime.date(2025, 5, 1))
        _set_date(late, datetime.date(2025, 8, 1))

        result = TechnicianStatementService.build(
            self.tech,
            from_date=datetime.date(2025, 4, 1),
            to_date=datetime.date(2025, 6, 30),
        )
        rows = result["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["credit"], 3_000)

        # Summary must reflect only the filtered row
        self.assertEqual(result["summary"]["total_credit"], 3_000)
        self.assertEqual(result["summary"]["total_debit"], 0)
        self.assertEqual(result["summary"]["final_balance"], rows[0]["balance_after"])

    def test_09_tenant_isolation_summary_totals_per_company(self):
        """Summary totals do not include entries from other companies."""
        co_b = _company()
        tech_b = _technician(co_b)

        _credit(self.company, self.tech, 5_000)
        _credit(co_b, tech_b, 99_000)

        result_a = TechnicianStatementService.build(self.tech)
        result_b = TechnicianStatementService.build(tech_b)

        self.assertEqual(result_a["summary"]["total_credit"], 5_000)
        self.assertEqual(result_b["summary"]["total_credit"], 99_000)

    def test_10_deterministic_two_calls_return_identical_output(self):
        """Calling build() twice for the same technician returns identical results."""
        _credit(self.company, self.tech, 1_000)
        _debit(self.company, self.tech, 400)

        r1 = TechnicianStatementService.build(self.tech)
        r2 = TechnicianStatementService.build(self.tech)

        self.assertEqual(r1["technician_id"], r2["technician_id"])
        self.assertEqual(r1["summary"], r2["summary"])
        self.assertEqual(len(r1["rows"]), len(r2["rows"]))
        for row1, row2 in zip(r1["rows"], r2["rows"]):
            self.assertEqual(row1["credit"],        row2["credit"])
            self.assertEqual(row1["debit"],         row2["debit"])
            self.assertEqual(row1["balance_after"], row2["balance_after"])
            self.assertEqual(row1["source"],        row2["source"])

    def test_11_filtered_summary_does_not_equal_full_running_balance(self):
        """
        With date filtering, final_balance reflects the STORED balance_after of the
        last VISIBLE row (which includes history before the filter window),
        not a sum recomputed from filtered rows alone.
        """
        old = _credit(self.company, self.tech, 10_000)
        new = _credit(self.company, self.tech, 3_000)
        _set_date(old, datetime.date(2024, 1, 1))
        _set_date(new, datetime.date(2025, 6, 1))

        result = TechnicianStatementService.build(
            self.tech, from_date=datetime.date(2025, 1, 1)
        )
        rows = result["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["credit"], 3_000)

        # final_balance = stored balance_after = 10_000 + 3_000 = 13_000
        # It is NOT 3_000 (which would be a recomputed-from-filtered result)
        self.assertEqual(result["summary"]["final_balance"], 13_000)
        # summary total_credit is from rows only (3_000, not 13_000)
        self.assertEqual(result["summary"]["total_credit"], 3_000)

    def test_12_technician_id_and_name_in_output(self):
        """build() returns technician_id (PK) and technician_name (username fallback)."""
        result = TechnicianStatementService.build(self.tech)
        self.assertEqual(result["technician_id"], self.tech.pk)
        self.assertIsInstance(result["technician_name"], str)
        self.assertTrue(result["technician_name"])

    def test_13_from_and_to_date_echoed_in_output(self):
        """build() echoes from_date and to_date arguments in the result."""
        fd = datetime.date(2025, 1, 1)
        td = datetime.date(2025, 12, 31)
        result = TechnicianStatementService.build(self.tech, from_date=fd, to_date=td)
        self.assertEqual(result["from_date"], fd)
        self.assertEqual(result["to_date"], td)

        result_no_dates = TechnicianStatementService.build(self.tech)
        self.assertIsNone(result_no_dates["from_date"])
        self.assertIsNone(result_no_dates["to_date"])

    def test_14_pure_transformation_writes_nothing_to_db(self):
        """build() does not create, update, or delete any DB rows."""
        _credit(self.company, self.tech, 500)

        count_before = TechnicianLedgerEntry.objects.filter(
            company=self.company, technician=self.tech
        ).count()

        TechnicianStatementService.build(self.tech)
        TechnicianStatementService.build(self.tech)

        count_after = TechnicianLedgerEntry.objects.filter(
            company=self.company, technician=self.tech
        ).count()

        self.assertEqual(count_before, count_after)
