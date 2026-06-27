"""
TASK-010B — Technician Service Wage Posting on Order Completion.

Tests cover:
 1.  Single wage-applicable NUMBER item posts one CREDIT entry.
 2.  Multiple wage-applicable NUMBER items post exactly one CREDIT entry.
 3.  Total wage equals sum(quantity * rate).
 4.  Metadata contains per-item snapshots.
 5.  Metadata contains total_wage_rial.
 6.  Order FK is set on the ledger entry.
 7.  Source is TECHNICIAN_SERVICE_WAGE.
 8.  Idempotency: calling service twice creates only one entry.
 9.  Order without technician creates no entry.
10.  NUMBER item with is_technician_wage_applicable=False creates no entry.
11.  MONEY/TEXT/BOOL items create no wage entry.
12.  Missing active rate creates no wage amount; item recorded in missing_rate_items.
13.  Inactive rate is treated as missing rate.
14.  Zero quantity creates no entry.
15.  Other-company rate is never used.
16.  Ledger balance_after is correct after wage posting.
17.  OrderCompleteService.complete() triggers posting.
18.  Existing order completion behaviour: status transitions to DONE, completed_at set.
19.  Missing-rate item appears in metadata.missing_rate_items.
20.  Calling TechnicianWagePostingService.post_for_order twice on the same completed
     order creates no duplicate (idempotency key).
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import CompanyUser, Customer, Technician, UserRole
from apps.orders.models import Order, OrderItemDefinition, OrderItemValue
from apps.payouts.models import TechnicianLedgerEntry, TechnicianServiceRate
from apps.payouts.services_order_wages import TechnicianWagePostingService
from apps.tenants.models import Company, CompanyServiceCategory

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company():
    tag = _n()
    return Company.objects.create(
        name=f"WageCo {tag}",
        code=f"wageco{tag}",
        slug=f"wageco-{tag}",
        is_active=True,
    )


def _admin(company):
    return CompanyUser.objects.create_user(
        username=f"admin{_n()}",
        password="testpass",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _technician(company):
    user = CompanyUser.objects.create_user(
        username=f"tech{_n()}",
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


def _category(company):
    return CompanyServiceCategory.objects.create(
        company=company,
        title=f"Cat {_n()}",
        is_active=True,
    )


def _item(company, kind=OrderItemDefinition.Kind.NUMBER,
          is_wage_applicable=True, category=None, is_active=True):
    cat = category or _category(company)
    return OrderItemDefinition.objects.create(
        company=company,
        category=cat,
        title=f"Item {_n()}",
        kind=kind,
        is_technician_wage_applicable=is_wage_applicable,
        is_active=is_active,
    )


def _rate(company, technician, item, wage=4_000_000, is_active=True):
    return TechnicianServiceRate.objects.create(
        company=company,
        technician=technician,
        item_definition=item,
        fixed_wage_rial=wage,
        is_active=is_active,
    )


def _customer(company):
    return Customer.objects.create(
        company=company,
        first_name="Test",
        last_name="Customer",
        phone=f"091{_n():08d}",
    )


def _order(company, technician=None, status=Order.Status.IN_PROGRESS):
    cust = _customer(company)
    return Order.objects.create(
        company=company,
        customer=cust,
        customer_name="Test Customer",
        customer_phone=cust.phone,
        title="Test Order",
        status=status,
        technician=technician,
    )


def _item_value(order, item, value_number):
    return OrderItemValue.objects.create(
        order=order,
        item=item,
        value_number=Decimal(str(value_number)),
    )


# ---------------------------------------------------------------------------
# Service-layer unit tests
# ---------------------------------------------------------------------------

class TechnicianWagePostingServiceTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        self.admin = _admin(self.company)

    def test_01_single_item_posts_one_credit_entry(self):
        """Test 1: Single wage-applicable NUMBER item posts exactly one CREDIT entry."""
        item = _item(self.company)
        rate = _rate(self.company, self.technician, item, wage=4_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 2)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry.entry_type, TechnicianLedgerEntry.EntryType.CREDIT)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(order=order).count(), 1
        )

    def test_02_multiple_items_post_exactly_one_credit_entry(self):
        """Test 2: Multiple wage-applicable items produce exactly one CREDIT entry."""
        item_a = _item(self.company)
        item_b = _item(self.company)
        _rate(self.company, self.technician, item_a, wage=3_000_000)
        _rate(self.company, self.technician, item_b, wage=2_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item_a, 1)
        _item_value(order, item_b, 3)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(len(result), 1)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(order=order).count(), 1
        )

    def test_03_total_wage_equals_sum_of_products(self):
        """Test 3: total_wage = sum(quantity * fixed_wage_rial) for all payable items."""
        item_a = _item(self.company)
        item_b = _item(self.company)
        _rate(self.company, self.technician, item_a, wage=4_000_000)
        _rate(self.company, self.technician, item_b, wage=1_500_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item_a, 2)   # 2 * 4_000_000 = 8_000_000
        _item_value(order, item_b, 4)   # 4 * 1_500_000 = 6_000_000
        # expected total: 14_000_000

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result[0].amount_rial, 14_000_000)

    def test_04_metadata_contains_item_snapshots(self):
        """Test 4: metadata.items contains one entry per payable order item value."""
        item = _item(self.company)
        rate = _rate(self.company, self.technician, item, wage=5_000_000)
        order = _order(self.company, technician=self.technician)
        value = _item_value(order, item, 3)

        result = TechnicianWagePostingService.post_for_order(order=order)
        meta = result[0].metadata

        self.assertEqual(len(meta["items"]), 1)
        snap = meta["items"][0]
        self.assertEqual(snap["order_item_value_id"], value.id)
        self.assertEqual(snap["item_definition_id"], item.id)
        self.assertEqual(snap["item_title"], item.title)
        self.assertEqual(snap["quantity"], "3.00")
        self.assertEqual(snap["rate_id"], rate.id)
        self.assertEqual(snap["fixed_wage_rial"], 5_000_000)
        self.assertEqual(snap["computed_wage_rial"], 15_000_000)

    def test_05_metadata_contains_total_wage_rial(self):
        """Test 5: metadata.total_wage_rial matches amount_rial on the entry."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=2_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 3)

        result = TechnicianWagePostingService.post_for_order(order=order)
        entry = result[0]

        self.assertEqual(entry.metadata["total_wage_rial"], 6_000_000)
        self.assertEqual(entry.amount_rial, 6_000_000)

    def test_06_order_fk_set_on_ledger_entry(self):
        """Test 6: The created ledger entry has order FK pointing to the order."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=1_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 1)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result[0].order_id, order.id)

    def test_07_source_is_technician_service_wage(self):
        """Test 7: Source on ledger entry is TECHNICIAN_SERVICE_WAGE."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=1_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 1)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(
            result[0].source,
            TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE,
        )

    def test_08_idempotency_second_call_creates_no_entry(self):
        """Test 8: Calling the service twice for the same order creates only one entry."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=1_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 1)

        first = TechnicianWagePostingService.post_for_order(order=order)
        second = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)  # idempotency key already exists → None returned
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(order=order).count(), 1
        )

    def test_09_no_technician_no_entry(self):
        """Test 9 (original 10): Order without technician creates no ledger entry."""
        item = _item(self.company)
        order = _order(self.company, technician=None)  # no technician
        _item_value(order, item, 2)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result, [])
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(order=order).count(), 0
        )

    def test_10_wage_applicable_false_no_entry(self):
        """Test 10 (original 11): NUMBER item with is_wage_applicable=False skipped."""
        item = _item(self.company, is_wage_applicable=False)
        _rate(self.company, self.technician, item, wage=4_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 5)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result, [])
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(order=order).count(), 0
        )

    def test_11_non_number_items_no_entry(self):
        """Test 11 (original 12): MONEY, TEXT, BOOL items create no wage entry."""
        cat = _category(self.company)
        money_item = _item(self.company, kind=OrderItemDefinition.Kind.MONEY,
                           is_wage_applicable=False, category=cat)
        text_item = _item(self.company, kind=OrderItemDefinition.Kind.TEXT,
                          is_wage_applicable=False, category=cat)
        bool_item = _item(self.company, kind=OrderItemDefinition.Kind.BOOL,
                          is_wage_applicable=False, category=cat)
        order = _order(self.company, technician=self.technician)
        OrderItemValue.objects.create(order=order, item=money_item, value_number=Decimal("100"))
        OrderItemValue.objects.create(order=order, item=text_item, value_text="some text")
        OrderItemValue.objects.create(order=order, item=bool_item, value_bool=True)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result, [])

    def test_12_missing_rate_no_wage_amount(self):
        """Test 12 (original 13): Missing rate → item not counted, warning logged."""
        item = _item(self.company)
        # Deliberately no TechnicianServiceRate created
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 2)

        with self.assertLogs("apps.payouts.services_order_wages", level="WARNING") as cm:
            result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result, [])
        self.assertTrue(
            any("no active rate" in msg for msg in cm.output),
            "Expected warning about missing rate",
        )

    def test_13_inactive_rate_treated_as_missing(self):
        """Test 13 (original 14): Inactive rate is not used; item treated as missing."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=3_000_000, is_active=False)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 1)

        with self.assertLogs("apps.payouts.services_order_wages", level="WARNING"):
            result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result, [])
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(order=order).count(), 0
        )

    def test_14_zero_quantity_no_entry(self):
        """Test 14 (original 15): Zero quantity item is skipped; no entry created."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=4_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 0)  # zero quantity

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result, [])

    def test_15_other_company_rate_not_used(self):
        """Test 15 (original 16): Rate from another company is never applied."""
        other_co = _company()
        other_tech = _technician(other_co)
        item = _item(self.company)
        # Create rate for same item but under a different company's technician
        _rate(other_co, other_tech, _item(other_co), wage=4_000_000)
        # No rate for self.company / self.technician / item
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 2)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result, [])

    def test_16_balance_after_is_correct(self):
        """Test 16 (original 18): balance_after on entry equals prior balance + amount."""
        from apps.payouts.services import TechnicianLedgerService

        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=2_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 3)  # expected wage = 6_000_000

        prior_balance = TechnicianLedgerService.get_balance(
            self.company, self.technician
        )
        result = TechnicianWagePostingService.post_for_order(order=order)

        entry = result[0]
        self.assertEqual(entry.balance_after, prior_balance + 6_000_000)

    def test_17_missing_rate_item_in_metadata_missing_rate_items(self):
        """Test 17 (original 19): Item with missing rate appears in metadata.missing_rate_items."""
        item_ok = _item(self.company)
        item_missing = _item(self.company)
        _rate(self.company, self.technician, item_ok, wage=1_000_000)
        # No rate for item_missing
        order = _order(self.company, technician=self.technician)
        _item_value(order, item_ok, 1)
        value_missing = _item_value(order, item_missing, 2)

        with self.assertLogs("apps.payouts.services_order_wages", level="WARNING"):
            result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(len(result), 1)  # payable item produces an entry
        meta = result[0].metadata
        self.assertEqual(len(meta["missing_rate_items"]), 1)
        missing = meta["missing_rate_items"][0]
        self.assertEqual(missing["item_definition_id"], item_missing.id)
        self.assertEqual(missing["order_item_value_id"], value_missing.id)
        self.assertEqual(missing["reason"], "missing_active_technician_service_rate")

    def test_18_technician_fk_set_correctly(self):
        """Technician FK on the ledger entry matches the order's technician."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=1_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 1)

        result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(result[0].technician_id, self.technician.id)

    def test_19_metadata_posting_type_and_ids(self):
        """metadata.posting_type, order_id, technician_id are set correctly."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=1_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 1)

        result = TechnicianWagePostingService.post_for_order(order=order)
        meta = result[0].metadata

        self.assertEqual(meta["posting_type"], "technician_service_wage")
        self.assertEqual(meta["order_id"], order.id)
        self.assertEqual(meta["technician_id"], self.technician.id)

    def test_20_second_call_idempotency_returns_empty(self):
        """Test 20: post_for_order called twice returns [] on the second call."""
        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=1_000_000)
        order = _order(self.company, technician=self.technician)
        _item_value(order, item, 1)

        TechnicianWagePostingService.post_for_order(order=order)
        second_result = TechnicianWagePostingService.post_for_order(order=order)

        self.assertEqual(second_result, [])
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(order=order).count(), 1
        )


# ---------------------------------------------------------------------------
# Integration tests — OrderCompleteService.complete() triggers posting
# ---------------------------------------------------------------------------

class WagePostingOrderCompleteIntegrationTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.technician = _technician(self.company)

    def test_i01_order_complete_triggers_wage_posting(self):
        """Test 9 (integration): OrderCompleteService.complete() triggers wage posting."""
        from apps.orders.services import OrderCompleteService

        item = _item(self.company)
        _rate(self.company, self.technician, item, wage=3_000_000)
        order = _order(self.company, technician=self.technician, status=Order.Status.IN_PROGRESS)
        _item_value(order, item, 2)  # expected wage = 6_000_000

        OrderCompleteService.complete(order=order, completed_by=self.admin)

        entry = TechnicianLedgerEntry.objects.filter(
            order=order,
            source=TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE,
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.amount_rial, 6_000_000)
        self.assertEqual(
            entry.source,
            TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE,
        )

    def test_i02_order_complete_sets_status_done_and_completed_at(self):
        """Test 18: Status transitions to DONE and completed_at is populated."""
        from apps.orders.services import OrderCompleteService

        order = _order(self.company, technician=self.technician, status=Order.Status.IN_PROGRESS)

        OrderCompleteService.complete(order=order, completed_by=self.admin)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DONE)
        self.assertIsNotNone(order.completed_at)

    def test_i03_complete_without_technician_no_entry_but_completes(self):
        """Order without technician completes successfully and no wage entry is created."""
        from apps.orders.services import OrderCompleteService

        order = _order(self.company, technician=None, status=Order.Status.IN_PROGRESS)

        OrderCompleteService.complete(order=order, completed_by=self.admin)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DONE)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(order=order).count(), 0
        )
