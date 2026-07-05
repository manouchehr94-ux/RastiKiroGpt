"""
Sprint 3 — Escrow Integration Tests.

Wires EscrowRecordService (Sprint 2) into the real online payment
callback flow (PaymentVerifyService.verify() / PaymentCallbackService)
and the real invoice-paid flow (InvoiceMarkPaidService.mark_paid()).

Covers:
  1. Platform-gateway payment creates an EscrowRecord (HELD).
  2. Company-gateway payment creates no EscrowRecord.
  3. No-gateway (cash/manual) payment creates no EscrowRecord.
  4. Failed payment creates no EscrowRecord.
  5. Duplicate callback does not duplicate the EscrowRecord.
  6. Invoice paid reserves (HELD -> RESERVED) and distributes
     (RESERVED -> DISTRIBUTED) the EscrowRecord with a split that is
     consistent with the existing platform-fee and settled-wage formulas.
  7. Escrow creation/transition failures are non-blocking and create a
     FinancialBackfillTask("escrow_record") instead of raising to the
     caller — Payment/Invoice status transitions are never affected.
  8. FinancialBackfillService.process_pending() resolves escrow_record
     tasks for both failure points (creation, transition).
  9. [OPEN-ISSUE: OI-03] guard: if the platform commission + provider
     share would exceed the escrowed amount, the split is never silently
     clamped or invented — it raises and is escalated to a backfill task.
 10. Existing technician ledger / platform fee behavior is unchanged by
     this wiring (regression guard).

No signal, view, API, or background job is added. No migration is
added. No existing model, service, or business rule is modified beyond
the two additive call sites in apps/payments/services.py and
apps/invoices/services.py.
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.invoices.services import InvoiceMarkPaidService
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.services import PaymentCallbackService, PaymentVerifyService
from apps.payouts.models import (
    CompanyPlatformFeeEntry,
    EscrowRecord,
    FinancialBackfillTask,
    TechnicianLedgerEntry,
)
from apps.payouts.services_backfill import FinancialBackfillService
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Escrow Wiring Co {tag}",
        "code": f"ewc{tag}",
        "slug": f"escrow-wiring-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"ewtech{_n()}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=Decimal(str(service_pct)),
        goods_wage_percent=Decimal(str(goods_pct)),
        travel_wage_percent=Decimal(str(travel_pct)),
    )


def _order(company, technician=None) -> Order:
    return Order.objects.create(
        company=company,
        title=f"Escrow Wiring Order {_n()}",
        status=Order.Status.DONE,
        technician=technician,
    )


def _financial_policy(company, fee_percent=1) -> CompanyFinancialPolicy:
    policy, _ = CompanyFinancialPolicy.objects.get_or_create(
        company=company,
        defaults={
            "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
            "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
            "platform_fee_percent": Decimal(str(fee_percent)),
        },
    )
    policy.platform_fee_percent = Decimal(str(fee_percent))
    policy.save(update_fields=["platform_fee_percent"])
    return policy


def _issued_invoice(company, technician=None, total=10_000_000) -> Invoice:
    order = _order(company, technician=technician)
    invoice = Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-{company.code.upper()}-{Invoice.objects.count() + 1:05d}",
        status=Invoice.Status.ISSUED,
        issued_at=timezone.now(),
        subtotal=total,
        total_amount=total,
        net_amount_before_invoice_discounts=total,
        gross_amount=total,
        technician_service_wage_percent_snapshot=(
            Decimal(str(technician.service_wage_percent)) if technician else Decimal("0")
        ),
        technician_goods_wage_percent_snapshot=(
            Decimal(str(technician.goods_wage_percent)) if technician else Decimal("0")
        ),
        technician_travel_wage_percent_snapshot=(
            Decimal(str(technician.travel_wage_percent)) if technician else Decimal("0")
        ),
    )
    InvoiceItem.objects.create(
        company=company,
        invoice=invoice,
        description="خدمات تست",
        row_type=InvoiceItem.RowType.SERVICE,
        quantity=1,
        unit_price=total,
        total_price=total,
    )
    return invoice


def _platform_gateway(company) -> PaymentGateway:
    return PaymentGateway.objects.create(
        company=company,
        name="Platform Test Gateway",
        gateway_type=PaymentGateway.GatewayType.FAKE,
        owner_type=PaymentGateway.OwnerType.PLATFORM,
        is_active=True,
        is_default=True,
    )


def _company_gateway(company) -> PaymentGateway:
    # Uses GatewayType.FAKE (not MANUAL) so this gateway can actually be
    # driven through the real PaymentVerifyService.verify() flow in tests
    # below — only FAKE has a registered provider implementation
    # (apps/payments/providers/registry.py). owner_type=COMPANY is the
    # only field that matters for escrow eligibility.
    return PaymentGateway.objects.create(
        company=company,
        name="Company Test Gateway",
        gateway_type=PaymentGateway.GatewayType.FAKE,
        owner_type=PaymentGateway.OwnerType.COMPANY,
        is_active=True,
    )


def _pending_payment(company, invoice, gateway, reference_id) -> Payment:
    return Payment.objects.create(
        company=company,
        invoice=invoice,
        gateway=gateway,
        amount=invoice.total_amount,
        status=Payment.Status.PENDING,
        reference_id=reference_id,
    )


# =============================================================================
# 1-5. Escrow creation via the real PaymentVerifyService / callback flow
# =============================================================================

class EscrowCreationOnPaymentVerifyTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.policy = _financial_policy(self.company, fee_percent=1)

    def test_01_platform_gateway_payment_creates_escrow_held(self):
        """Successful callback through a platform-owned gateway creates HELD escrow."""
        gateway = _platform_gateway(self.company)
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, gateway, "SUCCESS-e1")

        success, msg, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-e1",
        )
        self.assertTrue(success)

        record = EscrowRecord.objects.filter(payment=payment).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.amount_rial, int(invoice.total_amount))
        # By the time the callback returns, mark_paid() has already run and
        # advanced the record past HELD (see test_06 for the full chain);
        # this test only asserts that an EscrowRecord was created at all.

    def test_02_company_gateway_payment_creates_no_escrow(self):
        """Company-owned gateway payments must never create an EscrowRecord."""
        gateway = _company_gateway(self.company)
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, gateway, "SUCCESS-e2")

        success, msg, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-e2",
        )
        self.assertTrue(success)
        self.assertFalse(EscrowRecord.objects.filter(payment=payment).exists())

    def test_03_cash_manual_payment_creates_no_escrow(self):
        """A cash mark_paid (payment.gateway=None) never creates an EscrowRecord."""
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = Payment.objects.create(
            company=self.company,
            invoice=invoice,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
            gateway=None,
            metadata={"payment_source": "CASH_RECEIVED_BY_COMPANY", "method": "cash"},
        )
        InvoiceMarkPaidService.mark_paid(invoice=invoice, payment=payment, payment_method="cash")

        self.assertFalse(EscrowRecord.objects.filter(payment=payment).exists())
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_04_manual_mark_paid_without_payment_object_creates_no_escrow(self):
        """mark_paid(payment=None) — the legacy admin path — never touches escrow."""
        invoice = _issued_invoice(self.company, technician=self.tech)
        InvoiceMarkPaidService.mark_paid(invoice=invoice, payment_method="cash")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(EscrowRecord.objects.filter(invoice=invoice).count(), 0)

    def test_05_failed_payment_creates_no_escrow(self):
        """A FAIL-prefixed callback (provider rejects) creates no EscrowRecord."""
        gateway = _platform_gateway(self.company)
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, gateway, "FAIL-e5")

        success, msg, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="FAIL-e5",
        )
        self.assertFalse(success)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertFalse(EscrowRecord.objects.filter(payment=payment).exists())

    def test_06_duplicate_callback_does_not_duplicate_escrow(self):
        """Calling the callback twice for the same payment creates exactly one EscrowRecord."""
        gateway = _platform_gateway(self.company)
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, gateway, "SUCCESS-e6")

        success1, _, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-e6",
        )
        success2, msg2, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-e6",
        )
        self.assertTrue(success1)
        self.assertTrue(success2)
        self.assertIn("already", msg2.lower())

        self.assertEqual(EscrowRecord.objects.filter(payment=payment).count(), 1)

    def test_07_verify_called_directly_twice_is_idempotent(self):
        """Calling PaymentVerifyService.verify() directly twice never duplicates escrow."""
        gateway = _platform_gateway(self.company)
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, gateway, "SUCCESS-e7")

        PaymentVerifyService.verify(payment=payment)
        payment.refresh_from_db()
        PaymentVerifyService.verify(payment=payment)  # already PAID -> early return

        self.assertEqual(EscrowRecord.objects.filter(payment=payment).count(), 1)


# =============================================================================
# 6. Invoice paid reserves + distributes escrow correctly
# =============================================================================

class EscrowReserveAndDistributeOnInvoicePaidTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company, service_pct=60, goods_pct=10, travel_pct=100)
        self.policy = _financial_policy(self.company, fee_percent=1)
        self.gateway = _platform_gateway(self.company)

    def test_01_full_online_flow_reaches_distributed_with_correct_split(self):
        invoice = _issued_invoice(self.company, technician=self.tech, total=10_000_000)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-d1")

        success, _, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-d1",
        )
        self.assertTrue(success)

        record = EscrowRecord.objects.get(payment=payment)
        invoice.refresh_from_db()

        self.assertEqual(record.status, EscrowRecord.Status.DISTRIBUTED)
        self.assertEqual(record.invoice_id, invoice.pk)
        # fee_percent=1% of 10,000,000 = 100,000
        self.assertEqual(record.platform_commission_rial, 100_000)
        # service wage 60% of 10,000,000 = 6,000,000 (matches settled_technician_wage)
        self.assertEqual(record.provider_share_rial, int(invoice.settled_technician_wage))
        self.assertEqual(record.provider_share_rial, 6_000_000)
        # organization gets the residual: 10,000,000 - 100,000 - 6,000,000
        self.assertEqual(record.organization_share_rial, 3_900_000)
        self.assertEqual(
            record.platform_commission_rial
            + record.organization_share_rial
            + record.provider_share_rial,
            record.amount_rial,
        )

    def test_02_no_technician_still_distributes_with_zero_provider_share(self):
        """No technician on the order → provider_share_rial is 0, split still balances."""
        invoice = _issued_invoice(self.company, technician=None, total=10_000_000)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-d2")

        success, _, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-d2",
        )
        self.assertTrue(success)

        record = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(record.status, EscrowRecord.Status.DISTRIBUTED)
        self.assertEqual(record.provider_share_rial, 0)
        self.assertEqual(record.platform_commission_rial, 100_000)
        self.assertEqual(record.organization_share_rial, 9_900_000)

    def test_03_zero_fee_percent_still_distributes(self):
        """platform_fee_percent=0 → commission is 0, organization gets the rest."""
        self.policy.platform_fee_percent = Decimal("0")
        self.policy.save(update_fields=["platform_fee_percent"])

        invoice = _issued_invoice(self.company, technician=self.tech, total=10_000_000)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-d3")

        success, _, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-d3",
        )
        self.assertTrue(success)

        record = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(record.status, EscrowRecord.Status.DISTRIBUTED)
        self.assertEqual(record.platform_commission_rial, 0)
        self.assertEqual(record.provider_share_rial, 6_000_000)
        self.assertEqual(record.organization_share_rial, 4_000_000)


# =============================================================================
# 7 & 8. Non-blocking failure handling + backfill recovery
# =============================================================================

class EscrowCreationFailureBackfillTest(TestCase):
    """Escrow creation failure at payment-verify time is non-blocking."""

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.policy = _financial_policy(self.company, fee_percent=1)
        self.gateway = _platform_gateway(self.company)

    def test_creation_failure_does_not_block_payment_paid(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-f1")

        with patch(
            "apps.payouts.services_escrow.EscrowRecordService.create_for_payment",
            side_effect=RuntimeError("escrow DB down"),
        ):
            success, msg, _ = PaymentCallbackService.handle_callback(
                company=self.company, reference_id="SUCCESS-f1",
            )

        self.assertTrue(success)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)

    def test_creation_failure_creates_backfill_task(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-f2")

        with patch(
            "apps.payouts.services_escrow.EscrowRecordService.create_for_payment",
            side_effect=RuntimeError("escrow DB down"),
        ):
            PaymentCallbackService.handle_callback(
                company=self.company, reference_id="SUCCESS-f2",
            )

        tasks = FinancialBackfillTask.objects.filter(
            company=self.company, task_type="escrow_record", payment=payment,
        )
        self.assertEqual(tasks.count(), 1)
        self.assertEqual(tasks.first().status, FinancialBackfillTask.Status.PENDING)
        self.assertIn("escrow DB down", tasks.first().error_message)

    def test_backfill_process_pending_resolves_creation_failure(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-f3")

        with patch(
            "apps.payouts.services_escrow.EscrowRecordService.create_for_payment",
            side_effect=RuntimeError("escrow DB down"),
        ):
            PaymentCallbackService.handle_callback(
                company=self.company, reference_id="SUCCESS-f3",
            )

        self.assertFalse(EscrowRecord.objects.filter(payment=payment).exists())

        result = FinancialBackfillService.process_pending()

        self.assertEqual(result["resolved"], 1)
        task = FinancialBackfillTask.objects.get(
            company=self.company, task_type="escrow_record", payment=payment,
        )
        self.assertEqual(task.status, FinancialBackfillTask.Status.RESOLVED)
        # The retry re-runs create_for_payment (now unmocked) AND the
        # reserve+distribute transition, since invoice is already PAID by
        # the time this backfill task is processed.
        record = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(record.status, EscrowRecord.Status.DISTRIBUTED)

    def test_backfill_handler_creates_missing_escrow_idempotently(self):
        """
        Explicit idempotency test for the backfill handler itself: calling
        _retry_escrow_record's underlying logic (via process_pending, then
        directly a second time) never creates a second EscrowRecord and
        never re-raises once the record is already DISTRIBUTED.
        """
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-f4")

        with patch(
            "apps.payouts.services_escrow.EscrowRecordService.create_for_payment",
            side_effect=RuntimeError("escrow DB down"),
        ):
            PaymentCallbackService.handle_callback(
                company=self.company, reference_id="SUCCESS-f4",
            )

        # First resolution: creates the missing EscrowRecord and distributes it.
        result1 = FinancialBackfillService.process_pending()
        self.assertEqual(result1["resolved"], 1)
        self.assertEqual(EscrowRecord.objects.filter(payment=payment).count(), 1)

        # Directly re-invoke the same idempotent retry path a second time
        # (simulating a stale/duplicate task or manual re-trigger) — must
        # not create a second EscrowRecord or raise.
        from apps.invoices.services import reserve_and_distribute_escrow_for_invoice
        from apps.payouts.services_escrow import EscrowRecordService

        EscrowRecordService.create_for_payment(payment, invoice=invoice)
        reserve_and_distribute_escrow_for_invoice(invoice=invoice, payment=payment)

        self.assertEqual(EscrowRecord.objects.filter(payment=payment).count(), 1)
        record = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(record.status, EscrowRecord.Status.DISTRIBUTED)


class EscrowTransitionFailureBackfillTest(TestCase):
    """Escrow reserve/distribute failure at invoice-mark-paid time is non-blocking."""

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.policy = _financial_policy(self.company, fee_percent=1)
        self.gateway = _platform_gateway(self.company)

    def test_transition_failure_does_not_block_invoice_paid(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-t1")

        with patch(
            "apps.payouts.services_escrow.EscrowRecordService.reserve_for_invoice",
            side_effect=RuntimeError("db down mid-transition"),
        ):
            success, _, _ = PaymentCallbackService.handle_callback(
                company=self.company, reference_id="SUCCESS-t1",
            )

        self.assertTrue(success)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

        record = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(record.status, EscrowRecord.Status.HELD)  # never advanced

        tasks = FinancialBackfillTask.objects.filter(
            company=self.company, task_type="escrow_record", invoice=invoice,
        )
        self.assertEqual(tasks.count(), 1)

    def test_backfill_process_pending_resolves_transition_failure(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-t2")

        with patch(
            "apps.payouts.services_escrow.EscrowRecordService.reserve_for_invoice",
            side_effect=RuntimeError("db down mid-transition"),
        ):
            PaymentCallbackService.handle_callback(
                company=self.company, reference_id="SUCCESS-t2",
            )

        result = FinancialBackfillService.process_pending()
        self.assertEqual(result["resolved"], 1)

        record = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(record.status, EscrowRecord.Status.DISTRIBUTED)


# =============================================================================
# 9. [OPEN-ISSUE: OI-03] guard — never silently invent a split
# =============================================================================

class EscrowOI03SplitOverflowGuardTest(TestCase):
    """
    When the technician wage percentage is high enough that the platform
    commission (charged on the FULL invoice total, per R09) plus the
    technician's already-frozen wage share would exceed the escrowed
    amount, this sprint must never invent a proportional-reduction policy
    ([OPEN-ISSUE: OI-03] is unresolved). The transition must fail loudly
    and be escalated to a backfill task for manual Product Owner review,
    exactly like any other escrow transition failure — Invoice.status
    must still reach PAID.
    """

    def setUp(self):
        self.company = _company()
        # 100% service wage share -> technician_gross_share == subtotal,
        # leaving company_gross_share == 0. Any positive platform
        # commission then makes organization_share_rial negative.
        self.tech = _technician(self.company, service_pct=100, goods_pct=0, travel_pct=0)
        self.policy = _financial_policy(self.company, fee_percent=5)
        self.gateway = _platform_gateway(self.company)

    def test_split_overflow_blocks_distribution_but_not_invoice_paid(self):
        invoice = _issued_invoice(self.company, technician=self.tech, total=10_000_000)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-oi3")

        success, _, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-oi3",
        )

        # Payment + Invoice flow must complete successfully regardless.
        self.assertTrue(success)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)

        # Escrow never silently reached DISTRIBUTED with an invented split.
        record = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(record.status, EscrowRecord.Status.RESERVED)
        self.assertEqual(record.platform_commission_rial, 0)
        self.assertEqual(record.organization_share_rial, 0)
        self.assertEqual(record.provider_share_rial, 0)

        # A backfill task exists so a human can resolve OI-03 and retry.
        task = FinancialBackfillTask.objects.get(
            company=self.company, task_type="escrow_record", invoice=invoice,
        )
        self.assertEqual(task.status, FinancialBackfillTask.Status.PENDING)
        self.assertIn("OI-03", task.error_message)

    def test_retrying_without_policy_resolution_fails_again_safely(self):
        """
        Retrying the backfill task before the Product Owner resolves OI-03
        must keep failing safely (PENDING, attempts incremented) rather
        than ever inventing a clamped split.
        """
        invoice = _issued_invoice(self.company, technician=self.tech, total=10_000_000)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-oi3b")

        PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-oi3b",
        )

        result = FinancialBackfillService.process_pending()

        self.assertEqual(result["resolved"], 0)
        self.assertEqual(result["failed"], 1)

        task = FinancialBackfillTask.objects.get(
            company=self.company, task_type="escrow_record", invoice=invoice,
        )
        self.assertEqual(task.status, FinancialBackfillTask.Status.PENDING)
        self.assertEqual(task.attempts, 1)

        record = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(record.status, EscrowRecord.Status.RESERVED)


# =============================================================================
# 10. Regression guard: existing ledger / platform fee behavior unchanged
# =============================================================================

class ExistingLedgerAndFeeBehaviorUnchangedTest(TestCase):
    """
    The escrow wiring must not alter technician ledger or platform fee
    entries in any way — same counts, same amounts, same idempotency —
    for a full real online-payment flow through a platform gateway.
    """

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company, service_pct=60, goods_pct=10, travel_pct=100)
        self.policy = _financial_policy(self.company, fee_percent=1)
        self.gateway = _platform_gateway(self.company)

    def test_ledger_and_fee_entries_created_exactly_as_before(self):
        invoice = _issued_invoice(self.company, technician=self.tech, total=10_000_000)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-reg1")

        success, _, _ = PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-reg1",
        )
        self.assertTrue(success)

        credits = TechnicianLedgerEntry.objects.filter(
            company=self.company, technician=self.tech,
            entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
        )
        self.assertEqual(credits.count(), 1)
        self.assertEqual(credits.first().amount_rial, 6_000_000)

        fee_entries = CompanyPlatformFeeEntry.objects.filter(
            company=self.company,
            entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
        )
        self.assertEqual(fee_entries.count(), 1)
        self.assertEqual(fee_entries.first().amount_rial, 100_000)

    def test_duplicate_callback_still_does_not_duplicate_ledger_or_fee(self):
        invoice = _issued_invoice(self.company, technician=self.tech, total=10_000_000)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-reg2")

        PaymentCallbackService.handle_callback(company=self.company, reference_id="SUCCESS-reg2")
        PaymentCallbackService.handle_callback(company=self.company, reference_id="SUCCESS-reg2")

        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(company=self.company).count(), 1,
        )
        self.assertEqual(
            CompanyPlatformFeeEntry.objects.filter(company=self.company).count(), 1,
        )
        self.assertEqual(
            EscrowRecord.objects.filter(payment=payment).count(), 1,
        )



class InvoiceAndPaymentStatusCorrectnessTest(TestCase):
    """
    Explicit, dedicated checks that Invoice.status and Payment.status reach
    their correct terminal values across every escrow scenario (success,
    ineligible gateway, failure, and escrow-layer exception) — i.e. the
    escrow wiring never leaves either status field in an unexpected state.

    Each scenario below is already partially covered elsewhere in this file
    (e.g. test_02_company_gateway_payment_creates_no_escrow already asserts
    success=True; test_creation_failure_does_not_block_payment_paid already
    asserts payment.status == PAID under the same mock), but no existing
    test asserts BOTH Payment.status and Invoice.status together for these
    scenarios. This class closes that specific gap without duplicating the
    escrow-specific assertions already made elsewhere.
    """

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.policy = _financial_policy(self.company, fee_percent=1)
        self.gateway = _platform_gateway(self.company)

    def test_successful_platform_payment_reaches_paid_status_on_both(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-s1")

        PaymentCallbackService.handle_callback(company=self.company, reference_id="SUCCESS-s1")

        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_company_gateway_payment_reaches_paid_status_on_both(self):
        gateway = _company_gateway(self.company)
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, gateway, "SUCCESS-s2")

        PaymentCallbackService.handle_callback(company=self.company, reference_id="SUCCESS-s2")

        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_failed_payment_leaves_payment_failed_and_invoice_issued(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "FAIL-s3")

        PaymentCallbackService.handle_callback(company=self.company, reference_id="FAIL-s3")

        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)

    def test_escrow_creation_exception_still_reaches_paid_status_on_both(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-s4")

        with patch(
            "apps.payouts.services_escrow.EscrowRecordService.create_for_payment",
            side_effect=RuntimeError("escrow DB down"),
        ):
            PaymentCallbackService.handle_callback(company=self.company, reference_id="SUCCESS-s4")

        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_escrow_transition_exception_still_reaches_paid_status_on_both(self):
        invoice = _issued_invoice(self.company, technician=self.tech)
        payment = _pending_payment(self.company, invoice, self.gateway, "SUCCESS-s5")

        with patch(
            "apps.payouts.services_escrow.EscrowRecordService.reserve_for_invoice",
            side_effect=RuntimeError("db down mid-transition"),
        ):
            PaymentCallbackService.handle_callback(company=self.company, reference_id="SUCCESS-s5")

        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(invoice.status, Invoice.Status.PAID)
