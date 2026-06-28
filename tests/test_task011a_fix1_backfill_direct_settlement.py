"""
TASK-011A-FIX-1 — Backfill for Payment Split Snapshot and Direct Gateway Settlement.

When PaymentVerifyService.verify() succeeds but either:
  (a) PaymentSplitDecisionService.create_snapshot() raises, or
  (b) TechnicianDirectSettlementService.post_for_payment() raises,

a FinancialBackfillTask is now created so that automated retries can recover
the missing data without manual intervention.

Tests:
 1. Snapshot failure inside verify() creates PAYMENT_SPLIT_SNAPSHOT backfill task.
 2. Direct settlement failure inside verify() creates DIRECT_GATEWAY_SETTLEMENT backfill task.
 3. Payment remains PAID when snapshot creation fails.
 4. Payment remains PAID when direct settlement posting fails.
 5. process_pending() resolves PAYMENT_SPLIT_SNAPSHOT task end-to-end.
 6. process_pending() resolves DIRECT_GATEWAY_SETTLEMENT task end-to-end.
 7. DIRECT_GATEWAY_SETTLEMENT handler creates missing snapshot before posting DEBIT.
 8. Backfill is idempotent: processing same task twice does not duplicate snapshot or DEBIT.
 9. Company gateway / non-split snapshot: task resolves with no DEBIT created.
10. Existing TASK-010C direct settlement tests are not broken (regression guard).
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.services import PaymentVerifyService
from apps.payouts.models import (
    FinancialBackfillTask,
    PaymentSplitSnapshot,
    TechnicianLedgerEntry,
)
from apps.payouts.services_backfill import FinancialBackfillService
from apps.payouts.services_direct_settlement import TechnicianDirectSettlementService
from apps.payouts.services_split import PaymentSplitDecisionService
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company():
    tag = _n()
    return Company.objects.create(
        name=f"BkfDirect Co {tag}",
        code=f"bkfd{tag}",
        slug=f"bkfd-{tag}",
        is_active=True,
    )


def _technician(company, verified=True):
    user = CompanyUser.objects.create_user(
        username=f"techbkf{_n()}",
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
        shaba_verified=verified,
        sub_merchant_id="SUB-BKF-001" if verified else "",
    )


def _policy(company, strategy=CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN):
    policy, _ = CompanyFinancialPolicy.objects.get_or_create(
        company=company,
        defaults={
            "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
            "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
            "payout_strategy": strategy,
            "platform_fee_percent": Decimal("0"),
        },
    )
    policy.payout_strategy = strategy
    policy.platform_fee_percent = Decimal("0")
    policy.save(update_fields=["payout_strategy", "platform_fee_percent"])
    return policy


def _platform_gateway(company):
    return PaymentGateway.objects.create(
        company=company,
        name=f"Platform FAKE GW {_n()}",
        gateway_type=PaymentGateway.GatewayType.FAKE,
        owner_type=PaymentGateway.OwnerType.PLATFORM,
        is_active=True,
        is_default=True,
    )


def _company_gateway(company):
    return PaymentGateway.objects.create(
        company=company,
        name=f"Company GW {_n()}",
        gateway_type=PaymentGateway.GatewayType.MANUAL,
        owner_type=PaymentGateway.OwnerType.COMPANY,
        is_active=True,
        is_default=False,
    )


def _order(company, technician=None):
    return Order.objects.create(
        company=company,
        title=f"Order {_n()}",
        technician=technician,
        status=Order.Status.DONE,
    )


def _issued_invoice(company, order, total=10_000_000):
    tech = getattr(order, "technician", None) if order else None
    inv = Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-{company.code.upper()}-{Invoice.objects.count() + 1:05d}",
        status=Invoice.Status.ISSUED,
        issued_at=timezone.now(),
        subtotal=total,
        total_amount=total,
        net_amount_before_invoice_discounts=total,
        gross_amount=total,
        technician_service_wage_percent_snapshot=Decimal("60") if tech else Decimal("0"),
        technician_goods_wage_percent_snapshot=Decimal("10") if tech else Decimal("0"),
        technician_travel_wage_percent_snapshot=Decimal("100") if tech else Decimal("0"),
    )
    InvoiceItem.objects.create(
        company=company,
        invoice=inv,
        description="خدمات تست",
        row_type=InvoiceItem.RowType.SERVICE,
        quantity=1,
        unit_price=total,
        total_price=total,
    )
    return inv


def _pending_payment(company, invoice, gateway, total=10_000_000):
    return Payment.objects.create(
        company=company,
        invoice=invoice,
        gateway=gateway,
        amount=total,
        status=Payment.Status.PENDING,
        reference_id=f"SUCCESS-BKF-{_n():012d}",
    )


def _snapshot(company, payment, invoice=None, direct_amount=6_000_000, should_split=True):
    total = int(payment.amount)
    return PaymentSplitSnapshot.objects.create(
        company=company,
        payment=payment,
        invoice=invoice,
        total_amount=total,
        platform_fee_amount=0,
        company_deposit_amount=max(0, total - direct_amount) if should_split else total,
        technician_direct_amount=direct_amount if should_split else 0,
        technician_ledger_amount=0 if should_split else direct_amount,
        payout_strategy_snapshot="split_with_technician" if should_split else "direct_to_company",
        technician_verified_snapshot=should_split,
        technician_sub_merchant_id_snapshot="SUB-BKF-001" if should_split else "",
        platform_fee_percent_snapshot=Decimal("0"),
        should_split_with_technician=should_split,
        reason="split_with_verified_technician" if should_split else "payout_strategy_is_direct_to_company",
    )


# ---------------------------------------------------------------------------
# Tests 1-4: verify() creates backfill tasks and keeps payment PAID
# ---------------------------------------------------------------------------

class VerifyBackfillTaskCreationTest(TestCase):
    """Tests 1-4: verify() creates correct backfill tasks on side-effect failures."""

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        _policy(self.company)
        self.gateway = _platform_gateway(self.company)
        order = _order(self.company, self.technician)
        invoice = _issued_invoice(self.company, order)
        self.payment = _pending_payment(self.company, invoice, self.gateway)

    def test_01_snapshot_failure_creates_payment_split_snapshot_task(self):
        """Snapshot creation failure → PAYMENT_SPLIT_SNAPSHOT backfill task created."""
        with patch.object(
            PaymentSplitDecisionService,
            "create_snapshot",
            side_effect=RuntimeError("snapshot DB down"),
        ):
            PaymentVerifyService.verify(payment=self.payment)

        tasks = FinancialBackfillTask.objects.filter(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.PAYMENT_SPLIT_SNAPSHOT,
        )
        self.assertEqual(tasks.count(), 1)
        task = tasks.first()
        self.assertEqual(task.status, FinancialBackfillTask.Status.PENDING)
        self.assertEqual(task.payment_id, self.payment.pk)

    def test_02_direct_settlement_failure_creates_direct_gateway_settlement_task(self):
        """Direct settlement failure → DIRECT_GATEWAY_SETTLEMENT backfill task created."""
        with patch.object(
            TechnicianDirectSettlementService,
            "post_for_payment",
            side_effect=RuntimeError("settlement service down"),
        ):
            PaymentVerifyService.verify(payment=self.payment)

        tasks = FinancialBackfillTask.objects.filter(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.DIRECT_GATEWAY_SETTLEMENT,
        )
        self.assertEqual(tasks.count(), 1)
        task = tasks.first()
        self.assertEqual(task.status, FinancialBackfillTask.Status.PENDING)
        self.assertEqual(task.payment_id, self.payment.pk)

    def test_03_payment_stays_paid_when_snapshot_fails(self):
        """Payment status must remain PAID when snapshot creation raises."""
        with patch.object(
            PaymentSplitDecisionService,
            "create_snapshot",
            side_effect=RuntimeError("snapshot failure"),
        ):
            success, _ = PaymentVerifyService.verify(payment=self.payment)

        self.assertTrue(success)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)

    def test_04_payment_stays_paid_when_direct_settlement_fails(self):
        """Payment status must remain PAID when direct settlement posting raises."""
        with patch.object(
            TechnicianDirectSettlementService,
            "post_for_payment",
            side_effect=RuntimeError("settlement failure"),
        ):
            success, _ = PaymentVerifyService.verify(payment=self.payment)

        self.assertTrue(success)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)


# ---------------------------------------------------------------------------
# Tests 5-9: process_pending() resolves tasks end-to-end
# ---------------------------------------------------------------------------

class BackfillResolutionTest(TestCase):
    """Tests 5-9: process_pending() correctly resolves the new task types."""

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        _policy(self.company)
        self.gateway = _platform_gateway(self.company)

    def _make_paid_payment(self):
        """Return a PAID payment/invoice pair via verify() with no side effects mocked."""
        order = _order(self.company, self.technician)
        invoice = _issued_invoice(self.company, order)
        payment = _pending_payment(self.company, invoice, self.gateway)
        PaymentVerifyService.verify(payment=payment)
        payment.refresh_from_db()
        return payment

    def test_05_process_pending_resolves_payment_split_snapshot_task(self):
        """process_pending() resolves PAYMENT_SPLIT_SNAPSHOT task and creates the snapshot."""
        order = _order(self.company, self.technician)
        invoice = _issued_invoice(self.company, order)
        payment = _pending_payment(self.company, invoice, self.gateway)

        # Fail snapshot creation during verify() → task created, snapshot missing
        with patch.object(
            PaymentSplitDecisionService,
            "create_snapshot",
            side_effect=RuntimeError("snap fail"),
        ):
            PaymentVerifyService.verify(payment=payment)

        self.assertFalse(PaymentSplitSnapshot.objects.filter(payment=payment).exists())
        task = FinancialBackfillTask.objects.get(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.PAYMENT_SPLIT_SNAPSHOT,
        )

        result = FinancialBackfillService.process_pending()

        task.refresh_from_db()
        self.assertEqual(task.status, FinancialBackfillTask.Status.RESOLVED)
        self.assertIsNotNone(task.resolved_at)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertTrue(PaymentSplitSnapshot.objects.filter(payment=payment).exists())

    def test_06_process_pending_resolves_direct_gateway_settlement_task(self):
        """process_pending() resolves DIRECT_GATEWAY_SETTLEMENT task and creates the DEBIT."""
        order = _order(self.company, self.technician)
        invoice = _issued_invoice(self.company, order)
        payment = _pending_payment(self.company, invoice, self.gateway)

        # Fail direct settlement during verify() → snapshot created, task created, DEBIT missing
        with patch.object(
            TechnicianDirectSettlementService,
            "post_for_payment",
            side_effect=RuntimeError("settle fail"),
        ):
            PaymentVerifyService.verify(payment=payment)

        self.assertTrue(PaymentSplitSnapshot.objects.filter(payment=payment).exists())
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
                payment=payment,
            ).count(),
            0,
        )
        task = FinancialBackfillTask.objects.get(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.DIRECT_GATEWAY_SETTLEMENT,
        )

        result = FinancialBackfillService.process_pending()

        task.refresh_from_db()
        self.assertEqual(task.status, FinancialBackfillTask.Status.RESOLVED)
        self.assertIsNotNone(task.resolved_at)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
                payment=payment,
            ).count(),
            1,
        )

    def test_07_direct_settlement_handler_creates_missing_snapshot_first(self):
        """DIRECT_GATEWAY_SETTLEMENT handler creates missing snapshot before posting DEBIT."""
        order = _order(self.company, self.technician)
        invoice = _issued_invoice(self.company, order)
        payment = _pending_payment(self.company, invoice, self.gateway)

        # Fail BOTH snapshot and settlement during verify()
        with patch.object(
            PaymentSplitDecisionService,
            "create_snapshot",
            side_effect=RuntimeError("snap fail"),
        ):
            with patch.object(
                TechnicianDirectSettlementService,
                "post_for_payment",
                side_effect=RuntimeError("settle fail"),
            ):
                PaymentVerifyService.verify(payment=payment)

        # Two backfill tasks created; snapshot is missing
        self.assertFalse(PaymentSplitSnapshot.objects.filter(payment=payment).exists())
        self.assertTrue(
            FinancialBackfillTask.objects.filter(
                task_type=FinancialBackfillTask.TaskType.PAYMENT_SPLIT_SNAPSHOT,
            ).exists()
        )
        direct_task = FinancialBackfillTask.objects.get(
            task_type=FinancialBackfillTask.TaskType.DIRECT_GATEWAY_SETTLEMENT,
        )

        # Delete the snapshot task so only the direct settlement task remains
        FinancialBackfillTask.objects.filter(
            task_type=FinancialBackfillTask.TaskType.PAYMENT_SPLIT_SNAPSHOT,
        ).delete()

        # process_pending() runs only the DIRECT_GATEWAY_SETTLEMENT task
        result = FinancialBackfillService.process_pending()

        direct_task.refresh_from_db()
        self.assertEqual(direct_task.status, FinancialBackfillTask.Status.RESOLVED)
        self.assertEqual(result["resolved"], 1)

        # Handler must have created the snapshot internally
        self.assertTrue(PaymentSplitSnapshot.objects.filter(payment=payment).exists())

        # And posted the DEBIT
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
                payment=payment,
            ).count(),
            1,
        )

    def test_08_backfill_is_idempotent_no_duplicate_snapshot_or_debit(self):
        """Running DIRECT_GATEWAY_SETTLEMENT backfill twice creates no duplicate entries."""
        order = _order(self.company, self.technician)
        invoice = _issued_invoice(self.company, order)
        payment = _pending_payment(self.company, invoice, self.gateway)

        with patch.object(
            TechnicianDirectSettlementService,
            "post_for_payment",
            side_effect=RuntimeError("settle fail"),
        ):
            PaymentVerifyService.verify(payment=payment)

        # First run: resolves the task, creates snapshot + DEBIT
        FinancialBackfillService.process_pending()

        self.assertEqual(PaymentSplitSnapshot.objects.filter(payment=payment).count(), 1)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
                payment=payment,
            ).count(),
            1,
        )

        # Force-create a second task (simulates a duplicate recovery trigger)
        FinancialBackfillService.create_task(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.DIRECT_GATEWAY_SETTLEMENT,
            payment=payment,
            invoice=payment.invoice,
        )
        # create_task deduplication only covers PENDING/PROCESSING; the first task is RESOLVED,
        # so a second task is created. The second run must still not create duplicates.
        second_result = FinancialBackfillService.process_pending()

        self.assertEqual(second_result["resolved"], 1)
        # Still exactly 1 snapshot and 1 DEBIT
        self.assertEqual(PaymentSplitSnapshot.objects.filter(payment=payment).count(), 1)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
                payment=payment,
            ).count(),
            1,
        )

    def test_09_non_split_company_gateway_resolves_with_no_debit(self):
        """
        DIRECT_GATEWAY_SETTLEMENT task for a non-split payment resolves cleanly.

        When the split snapshot has should_split_with_technician=False (e.g. company
        gateway), the handler calls post_for_payment() which returns [] without raising.
        The task must be marked RESOLVED and no DEBIT must be written.
        """
        company_gw = _company_gateway(self.company)
        order = _order(self.company, self.technician)
        invoice = _issued_invoice(self.company, order)
        # Create a PAID payment (manual, company gateway)
        payment = Payment.objects.create(
            company=self.company,
            invoice=invoice,
            gateway=company_gw,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
            reference_id=f"SUCCESS-NOGW-{_n()}",
        )
        # Snapshot says should_split=False (company gateway blocks direct split)
        _snapshot(self.company, payment, invoice, should_split=False)

        # Simulate a DIRECT_GATEWAY_SETTLEMENT task that was created despite no split
        task, _ = FinancialBackfillService.create_task(
            company=self.company,
            task_type=FinancialBackfillTask.TaskType.DIRECT_GATEWAY_SETTLEMENT,
            payment=payment,
            invoice=invoice,
        )

        result = FinancialBackfillService.process_pending()

        task.refresh_from_db()
        self.assertEqual(task.status, FinancialBackfillTask.Status.RESOLVED)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
                payment=payment,
            ).count(),
            0,
            "No DEBIT must be created when snapshot.should_split_with_technician is False",
        )


# ---------------------------------------------------------------------------
# Test 10: Regression guard — existing 010C verify() tests still pass
# ---------------------------------------------------------------------------

class RegressionVerifyTest(TestCase):
    """Test 10: Backfill changes do not break the baseline verify() behaviour."""

    def setUp(self):
        self.company = _company()
        self.technician = _technician(self.company)
        _policy(self.company)
        self.gateway = _platform_gateway(self.company)

    def _make_pending(self, total=10_000_000):
        order = _order(self.company, self.technician)
        invoice = _issued_invoice(self.company, order)
        return _pending_payment(self.company, invoice, self.gateway, total=total)

    def test_10a_successful_verify_creates_debit_and_no_backfill_task(self):
        """Normal verify() path: DEBIT created, no backfill task left behind."""
        payment = self._make_pending()
        success, msg = PaymentVerifyService.verify(payment=payment)

        self.assertTrue(success, msg)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)

        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=self.company,
                source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
            ).count(),
            1,
        )
        self.assertEqual(
            FinancialBackfillTask.objects.filter(
                company=self.company,
                task_type__in=[
                    FinancialBackfillTask.TaskType.PAYMENT_SPLIT_SNAPSHOT,
                    FinancialBackfillTask.TaskType.DIRECT_GATEWAY_SETTLEMENT,
                ],
            ).count(),
            0,
            "No backfill tasks must exist after a clean verify()",
        )

    def test_10b_verify_does_not_break_when_settlement_hook_raises(self):
        """Verifies the pre-existing guarantee: payment is PAID even when settlement raises."""
        payment = self._make_pending()

        with patch.object(
            TechnicianDirectSettlementService,
            "post_for_payment",
            side_effect=RuntimeError("hook failure"),
        ):
            success, msg = PaymentVerifyService.verify(payment=payment)

        self.assertTrue(success, msg)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
