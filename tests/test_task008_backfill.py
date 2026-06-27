"""
TASK-008 — Financial Backfill Tests.

Covers:
  1. Technician ledger failure creates a PENDING FinancialBackfillTask.
  2. Repeated create_task() for same invoice/type → no duplicate task.
  3. Platform fee failure creates a PENDING FinancialBackfillTask.
  4. process_pending() resolves a technician_ledger task on success.
  5. process_pending() resolves a platform_fee task on success.
  6. process_pending() increments attempts and preserves PENDING on failure.
  7. Invoice remains PAID after any ledger/fee failure.
  8. PROCESSING task also blocks a duplicate create.
  9. process_pending() skips already-resolved tasks.
 10. One task failure does not block other tasks from resolving.
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.invoices.services import (
    InvoiceCreateService,
    InvoiceIssueService,
    InvoiceMarkPaidService,
)
from apps.orders.models import Order
from apps.payouts.models import FinancialBackfillTask
from apps.payouts.services import TechnicianLedgerService
from apps.payouts.services_backfill import FinancialBackfillService
from apps.payouts.services_platform_fee import PlatformFeeService
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    tag = _n()
    return Company.objects.create(
        name=f"Backfill Co {tag}",
        code=f"bfco{tag}",
        slug=f"backfill-co-{tag}",
        is_active=True,
    )


def _order(company, technician=None):
    return Order.objects.create(
        company=company,
        title=f"Order {_n()}",
        status=Order.Status.IN_PROGRESS,
        technician=technician,
    )


def _technician(company):
    user = CompanyUser.objects.create_user(
        username=f"tech{_n()}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=Decimal("60"),
        goods_wage_percent=Decimal("10"),
        travel_wage_percent=Decimal("100"),
    )


def _issued_invoice(company, order):
    """Create a fully issued invoice with one 200,000-rial service line."""
    inv = InvoiceCreateService.create(company=company, order=order, items=[])
    InvoiceItem.objects.create(
        company=company,
        invoice=inv,
        description="Repair",
        row_type=InvoiceItem.RowType.SERVICE,
        quantity=1,
        unit_price=200_000,
        discount_amount=0,
        total_price=200_000,
    )
    inv.recalculate_totals(save=True)
    return InvoiceIssueService.issue(invoice=inv)


def _platform_setup(company):
    """
    Return (invoice, payment) for a PAID payment through a platform gateway.
    The invoice is already ISSUED before this function returns.
    """
    from apps.payments.models import Payment, PaymentGateway

    CompanyFinancialPolicy.objects.get_or_create(
        company=company,
        defaults={"platform_fee_percent": Decimal("3.00")},
    )
    gateway = PaymentGateway.objects.create(
        company=company,
        name="Platform GW",
        gateway_type=PaymentGateway.GatewayType.FAKE,
        owner_type=PaymentGateway.OwnerType.PLATFORM,
        is_active=True,
        is_default=True,
    )
    order = _order(company)
    inv = _issued_invoice(company, order)
    payment = Payment.objects.create(
        company=company,
        invoice=inv,
        gateway=gateway,
        amount=inv.total_amount,
        status=Payment.Status.PAID,
    )
    return inv, payment


# =============================================================================
# 1. Technician ledger failure creates a backfill task
# =============================================================================

class TechnicianLedgerFailureCreatesTaskTest(TestCase):

    def setUp(self):
        self.company = _company()
        tech = _technician(self.company)
        order = _order(self.company, technician=tech)
        self.inv = _issued_invoice(self.company, order)

    def test_failure_creates_pending_task(self):
        """Test 1: ledger write failure → one PENDING FinancialBackfillTask."""
        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("ledger DB down"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=self.inv)

        tasks = FinancialBackfillTask.objects.filter(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
        )
        self.assertEqual(tasks.count(), 1)
        task = tasks.first()
        self.assertEqual(task.status, FinancialBackfillTask.Status.PENDING)
        self.assertEqual(task.invoice_id, self.inv.pk)
        self.assertIn("ledger DB down", task.error_message)

    def test_failure_links_correct_invoice(self):
        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("fail"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=self.inv)

        task = FinancialBackfillTask.objects.get(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
        )
        self.assertEqual(task.invoice, self.inv)


# =============================================================================
# 2. Idempotency: no duplicate PENDING tasks
# =============================================================================

class BackfillTaskIdempotencyTest(TestCase):

    def setUp(self):
        self.company = _company()

    def test_duplicate_create_task_returns_existing(self):
        """Test 2: create_task twice for same (company, type, invoice) → one row."""
        order = _order(self.company)
        inv = _issued_invoice(self.company, order)
        Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.PAID)
        inv.refresh_from_db()

        task1, created1 = FinancialBackfillService.create_task(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            invoice=inv,
        )
        task2, created2 = FinancialBackfillService.create_task(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            invoice=inv,
        )

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(task1.pk, task2.pk)
        self.assertEqual(
            FinancialBackfillTask.objects.filter(
                company=self.company,
                task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
                invoice=inv,
            ).count(),
            1,
        )

    def test_two_different_invoices_create_separate_tasks(self):
        """Different invoices → different tasks (not blocked by each other)."""
        order1 = _order(self.company)
        inv1 = _issued_invoice(self.company, order1)
        order2 = _order(self.company)
        inv2 = _issued_invoice(self.company, order2)
        for inv in (inv1, inv2):
            Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.PAID)
            inv.refresh_from_db()

        _, c1 = FinancialBackfillService.create_task(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            invoice=inv1,
        )
        _, c2 = FinancialBackfillService.create_task(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            invoice=inv2,
        )
        self.assertTrue(c1)
        self.assertTrue(c2)
        self.assertEqual(
            FinancialBackfillTask.objects.filter(company=self.company).count(), 2
        )

    def test_processing_task_blocks_duplicate_pending(self):
        """Test 8: a PROCESSING task counts as active and blocks a duplicate."""
        order = _order(self.company)
        inv = _issued_invoice(self.company, order)
        Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.PAID)
        inv.refresh_from_db()

        task, _ = FinancialBackfillService.create_task(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE,
            invoice=inv,
        )
        FinancialBackfillTask.objects.filter(pk=task.pk).update(
            status=FinancialBackfillTask.Status.PROCESSING
        )

        task2, created2 = FinancialBackfillService.create_task(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE,
            invoice=inv,
        )
        self.assertFalse(created2)
        self.assertEqual(task.pk, task2.pk)


# =============================================================================
# 3. Platform fee failure creates a backfill task
# =============================================================================

class PlatformFeeFailureCreatesTaskTest(TestCase):

    def test_platform_fee_failure_creates_pending_task(self):
        """Test 3: platform fee write failure → one PENDING FinancialBackfillTask."""
        company = _company()
        inv, payment = _platform_setup(company)

        with patch.object(
            PlatformFeeService,
            "_write_entry",
            side_effect=RuntimeError("fee DB down"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=inv, payment=payment)

        tasks = FinancialBackfillTask.objects.filter(
            company=company,
            task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE,
        )
        self.assertEqual(tasks.count(), 1)
        task = tasks.first()
        self.assertEqual(task.status, FinancialBackfillTask.Status.PENDING)
        self.assertEqual(task.invoice_id, inv.pk)
        self.assertEqual(task.payment_id, payment.pk)


# =============================================================================
# 4 & 5. process_pending() resolves tasks on success
# =============================================================================

class ProcessPendingResolvesTaskTest(TestCase):

    def test_process_pending_resolves_technician_ledger_task(self):
        """Test 4: process_pending() resolves a technician_ledger task end-to-end."""
        company = _company()
        tech = _technician(company)
        order = _order(company, technician=tech)
        inv = _issued_invoice(company, order)

        # Create the task via a mark_paid failure (sets settled_technician_wage first)
        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("fail"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=inv)

        task = FinancialBackfillTask.objects.get(
            company=company, task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER
        )

        # Run process_pending without the mock → should succeed
        result = FinancialBackfillService.process_pending()

        task.refresh_from_db()
        self.assertEqual(task.status, FinancialBackfillTask.Status.RESOLVED)
        self.assertIsNotNone(task.resolved_at)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(result["failed"], 0)

    def test_process_pending_resolves_platform_fee_task(self):
        """Test 5: process_pending() resolves a platform_fee task end-to-end."""
        company = _company()
        inv, payment = _platform_setup(company)

        with patch.object(
            PlatformFeeService,
            "_write_entry",
            side_effect=RuntimeError("fail"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=inv, payment=payment)

        task = FinancialBackfillTask.objects.get(
            company=company, task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE
        )

        result = FinancialBackfillService.process_pending()

        task.refresh_from_db()
        self.assertEqual(task.status, FinancialBackfillTask.Status.RESOLVED)
        self.assertIsNotNone(task.resolved_at)
        self.assertEqual(result["resolved"], 1)

    def test_process_pending_skips_resolved_tasks(self):
        """Test 9: a second run of process_pending skips already-resolved tasks."""
        company = _company()
        tech = _technician(company)
        order = _order(company, technician=tech)
        inv = _issued_invoice(company, order)

        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("fail"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=inv)

        r1 = FinancialBackfillService.process_pending()
        r2 = FinancialBackfillService.process_pending()

        self.assertEqual(r1["resolved"], 1)
        self.assertEqual(r2["resolved"], 0)
        self.assertEqual(r2["skipped"], 0)  # RESOLVED tasks are not even fetched


# =============================================================================
# 6. process_pending() increments attempts on failure
# =============================================================================

class ProcessPendingFailureTest(TestCase):

    def test_failure_increments_attempts_and_keeps_pending(self):
        """Test 6: process_pending() failure → attempts++, task stays PENDING."""
        company = _company()
        tech = _technician(company)
        order = _order(company, technician=tech)
        inv = _issued_invoice(company, order)

        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("first fail"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=inv)

        task = FinancialBackfillTask.objects.get(
            company=company, task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER
        )
        self.assertEqual(task.attempts, 0)

        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("still broken"),
        ):
            result = FinancialBackfillService.process_pending()

        task.refresh_from_db()
        self.assertEqual(task.status, FinancialBackfillTask.Status.PENDING)
        self.assertEqual(task.attempts, 1)
        self.assertIn("still broken", task.error_message)
        self.assertIsNotNone(task.last_attempt_at)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["resolved"], 0)

    def test_repeated_failure_accumulates_attempts(self):
        """Two consecutive process_pending() failures → attempts = 2."""
        company = _company()
        tech = _technician(company)
        order = _order(company, technician=tech)
        inv = _issued_invoice(company, order)

        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("fail"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=inv)

        task = FinancialBackfillTask.objects.get(
            company=company, task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER
        )

        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("still broken"),
        ):
            FinancialBackfillService.process_pending()
            FinancialBackfillService.process_pending()

        task.refresh_from_db()
        self.assertEqual(task.attempts, 2)
        self.assertEqual(task.status, FinancialBackfillTask.Status.PENDING)

    def test_one_task_failure_does_not_block_others(self):
        """Test 10: failure on task #1 must not prevent task #2 from resolving."""
        company = _company()
        tech = _technician(company)

        order1 = _order(company, technician=tech)
        inv1 = _issued_invoice(company, order1)
        order2 = _order(company, technician=tech)
        inv2 = _issued_invoice(company, order2)

        # Create two backfill tasks via mark_paid with ledger failures
        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("fail"),
        ):
            InvoiceMarkPaidService.mark_paid(invoice=inv1)
            InvoiceMarkPaidService.mark_paid(invoice=inv2)

        task1 = FinancialBackfillTask.objects.get(
            company=company, task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            invoice=inv1,
        )
        task2 = FinancialBackfillTask.objects.get(
            company=company, task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            invoice=inv2,
        )

        call_count = [0]

        def _fail_first_then_succeed(invoice, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first task fails")
            # Second call succeeds (no exception)

        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=_fail_first_then_succeed,
        ):
            result = FinancialBackfillService.process_pending()

        task1.refresh_from_db()
        task2.refresh_from_db()
        self.assertEqual(task1.status, FinancialBackfillTask.Status.PENDING)
        self.assertEqual(task2.status, FinancialBackfillTask.Status.RESOLVED)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(result["failed"], 1)


# =============================================================================
# 7. Invoice remains PAID after any failure
# =============================================================================

class InvoiceStaysPaidAfterFailureTest(TestCase):

    def test_invoice_stays_paid_after_ledger_failure(self):
        """Test 7a: ledger failure must not revert invoice to ISSUED."""
        company = _company()
        tech = _technician(company)
        order = _order(company, technician=tech)
        inv = _issued_invoice(company, order)

        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("DB down"),
        ):
            result = InvoiceMarkPaidService.mark_paid(invoice=inv)

        result.refresh_from_db()
        self.assertEqual(result.status, Invoice.Status.PAID)

    def test_invoice_stays_paid_after_platform_fee_failure(self):
        """Test 7b: platform fee failure must not revert invoice to ISSUED."""
        company = _company()
        inv, payment = _platform_setup(company)

        with patch.object(
            PlatformFeeService,
            "_write_entry",
            side_effect=RuntimeError("fee failure"),
        ):
            result = InvoiceMarkPaidService.mark_paid(invoice=inv, payment=payment)

        result.refresh_from_db()
        self.assertEqual(result.status, Invoice.Status.PAID)

    def test_invoice_stays_paid_when_backfill_creation_also_fails(self):
        """Backfill task creation failure must not affect invoice PAID status."""
        company = _company()
        tech = _technician(company)
        order = _order(company, technician=tech)
        inv = _issued_invoice(company, order)

        with patch.object(
            TechnicianLedgerService,
            "create_invoice_entries",
            side_effect=RuntimeError("ledger down"),
        ), patch.object(
            FinancialBackfillService,
            "create_task",
            side_effect=RuntimeError("backfill creation also down"),
        ):
            result = InvoiceMarkPaidService.mark_paid(invoice=inv)

        result.refresh_from_db()
        self.assertEqual(result.status, Invoice.Status.PAID)
