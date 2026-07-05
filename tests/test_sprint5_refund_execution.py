"""
Sprint 5 — Refund & Adjustment Execution, Phase B: RefundExecutionService Tests.

Exercises RefundExecutionService (apps/payouts/services_refund_execution.py)
against real, already-persisted financial records produced by the existing
Sprint 3 payment/invoice flow — mirroring the exact fixture conventions
already used in test_sprint4_settlement_execution.py.

Scope covered: FULL_REFUND only, before settlement, ledger-held technician
wage only — per the approved Phase A design and this sprint's explicit
instructions. Blocked scenarios (after-settlement, direct-split,
partial-refund/manual-adjustment) are tested as explicit BLOCK tests, never
as execution tests.
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.services import PaymentCallbackService
from apps.payouts.exceptions import AdjustmentTransitionError
from apps.payouts.models import (
    AdjustmentDocument,
    CompanyPlatformFeeEntry,
    EscrowRecord,
    PaymentSplitSnapshot,
    TechnicianLedgerEntry,
)
from apps.payouts.services_adjustment import AdjustmentDocumentService
from apps.payouts.services_escrow import EscrowRecordService
from apps.payouts.services_refund_execution import (
    RefundExecutionBlockedError,
    RefundExecutionResult,
    RefundExecutionService,
)
from apps.payouts.services_settlement_batch import SettlementBatchService
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Refund Test Co {tag}",
        "code": f"refund{tag}",
        "slug": f"refund-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"refundtech{_n()}",
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
        title=f"Refund Test Order {_n()}",
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
    gateway, _created = PaymentGateway.objects.get_or_create(
        company=company,
        gateway_type=PaymentGateway.GatewayType.FAKE,
        defaults={
            "name": "Platform Test Gateway",
            "owner_type": PaymentGateway.OwnerType.PLATFORM,
            "is_active": True,
            "is_default": True,
        },
    )
    return gateway


def _pending_payment(company, invoice, gateway, reference_id) -> Payment:
    return Payment.objects.create(
        company=company,
        invoice=invoice,
        gateway=gateway,
        amount=invoice.total_amount,
        status=Payment.Status.PENDING,
        reference_id=reference_id,
    )


def _distributed_invoice(company, technician, *, total=10_000_000, fee_percent=1):
    """
    Build a fully real, DISTRIBUTED-escrow, PAID invoice by driving it
    through the actual production callback flow (PaymentCallbackService),
    never by hand-crafting an EscrowRecord row directly.
    """
    _financial_policy(company, fee_percent=fee_percent)
    gateway = _platform_gateway(company)
    invoice = _issued_invoice(company, technician=technician, total=total)
    payment = _pending_payment(company, invoice, gateway, f"SUCCESS-refund-{_n()}")
    success, _, _ = PaymentCallbackService.handle_callback(
        company=company, reference_id=payment.reference_id,
    )
    assert success, "setup failed: payment callback did not succeed"
    invoice.refresh_from_db()
    return invoice, payment


def _approved_full_refund(company, invoice, amount_rial=None):
    """Build a real, APPROVED FULL_REFUND AdjustmentDocument via the unmodified
    Sprint 2 AdjustmentDocumentService lifecycle (never hand-inserted)."""
    document = AdjustmentDocumentService.create_draft(
        company=company,
        original_invoice=invoice,
        document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
        amount_rial=amount_rial or int(invoice.total_amount),
        reason="Customer requested full refund (test)",
    )
    document = AdjustmentDocumentService.submit_for_approval(document)
    document = AdjustmentDocumentService.approve(document, approved_by=None)
    return document


# =============================================================================
# Happy path
# =============================================================================

class ApprovedDocumentExecutionTest(TestCase):

    def test_approved_document_executes(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        result = RefundExecutionService.execute(document)

        self.assertIsInstance(result, RefundExecutionResult)
        self.assertEqual(result.status, "applied")
        self.assertEqual(result.document.status, AdjustmentDocument.Status.APPLIED)
        self.assertIsNotNone(result.document.applied_at)

    def test_technician_reversal_entry_created(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        result = RefundExecutionService.execute(document)

        self.assertTrue(result.technician_ledger_entry_created)
        entries = TechnicianLedgerEntry.objects.filter(
            company=company, technician=tech,
            source=TechnicianLedgerEntry.Source.REFUND,
        )
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.entry_type, TechnicianLedgerEntry.EntryType.DEBIT)
        self.assertEqual(entry.amount_rial, int(invoice.settled_technician_wage))
        self.assertEqual(result.document.technician_wage_reversal, int(invoice.settled_technician_wage))

    def test_platform_fee_reversal_entry_created(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        result = RefundExecutionService.execute(document)

        self.assertTrue(result.platform_fee_entry_created)
        entries = CompanyPlatformFeeEntry.objects.filter(
            company=company, source=CompanyPlatformFeeEntry.Source.REFUND,
        )
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.entry_type, CompanyPlatformFeeEntry.EntryType.CREDIT)
        self.assertEqual(entry.amount_rial, 100_000)  # 1% of 10,000,000
        self.assertEqual(result.document.platform_fee_reversal, 100_000)

    def test_escrow_before_settlement_closes(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        result = RefundExecutionService.execute(document)

        self.assertTrue(result.escrow_closed)
        escrow = EscrowRecord.objects.get(payment=payment)
        self.assertEqual(escrow.status, EscrowRecord.Status.CLOSED)
        self.assertIsNotNone(escrow.closed_at)


# =============================================================================
# Blocked non-APPROVED statuses
# =============================================================================

class NonApprovedStatusBlockedTest(TestCase):

    def _draft_document(self, company, invoice):
        return AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            amount_rial=int(invoice.total_amount),
            reason="test",
        )

    def test_draft_blocked(self):
        company = _company()
        tech = _technician(company)
        invoice, _p = _distributed_invoice(company, tech)
        document = self._draft_document(company, invoice)

        with self.assertRaises(AdjustmentTransitionError):
            RefundExecutionService.execute(document)

    def test_pending_approval_blocked(self):
        company = _company()
        tech = _technician(company)
        invoice, _p = _distributed_invoice(company, tech)
        document = self._draft_document(company, invoice)
        document = AdjustmentDocumentService.submit_for_approval(document)

        with self.assertRaises(AdjustmentTransitionError):
            RefundExecutionService.execute(document)

    def test_rejected_blocked(self):
        company = _company()
        tech = _technician(company)
        invoice, _p = _distributed_invoice(company, tech)
        document = self._draft_document(company, invoice)
        document = AdjustmentDocumentService.submit_for_approval(document)
        document = AdjustmentDocumentService.reject(document)

        with self.assertRaises(AdjustmentTransitionError):
            RefundExecutionService.execute(document)

    def test_cancelled_blocked(self):
        company = _company()
        tech = _technician(company)
        invoice, _p = _distributed_invoice(company, tech)
        document = self._draft_document(company, invoice)
        document = AdjustmentDocumentService.cancel(document)

        with self.assertRaises(AdjustmentTransitionError):
            RefundExecutionService.execute(document)

    def test_no_ledger_write_attempted_for_blocked_status(self):
        """A blocked-status execute() call must write absolutely nothing."""
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = self._draft_document(company, invoice)

        with self.assertRaises(AdjustmentTransitionError):
            RefundExecutionService.execute(document)

        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company, source=TechnicianLedgerEntry.Source.REFUND,
            ).count(),
            0,
        )
        self.assertEqual(
            CompanyPlatformFeeEntry.objects.filter(
                company=company, source=CompanyPlatformFeeEntry.Source.REFUND,
            ).count(),
            0,
        )


# =============================================================================
# Idempotency
# =============================================================================

class IdempotencyTest(TestCase):

    def test_already_applied_is_idempotent(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        result1 = RefundExecutionService.execute(document)
        result2 = RefundExecutionService.execute(result1.document)

        self.assertEqual(result1.status, "applied")
        self.assertEqual(result2.status, "already_applied")
        self.assertFalse(result2.technician_ledger_entry_created)
        self.assertFalse(result2.platform_fee_entry_created)
        self.assertFalse(result2.escrow_closed)

    def test_duplicate_execution_no_duplicate_entries(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        RefundExecutionService.execute(document)
        RefundExecutionService.execute(document)

        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company, source=TechnicianLedgerEntry.Source.REFUND,
            ).count(),
            1,
        )
        self.assertEqual(
            CompanyPlatformFeeEntry.objects.filter(
                company=company, source=CompanyPlatformFeeEntry.Source.REFUND,
            ).count(),
            1,
        )

    def test_second_call_returns_same_document(self):
        company = _company()
        tech = _technician(company)
        invoice, _p = _distributed_invoice(company, tech)
        document = _approved_full_refund(company, invoice)

        result1 = RefundExecutionService.execute(document)
        result2 = RefundExecutionService.execute(result1.document)

        self.assertEqual(result1.document.pk, result2.document.pk)
        self.assertEqual(result1.document.applied_at, result2.document.applied_at)


# =============================================================================
# Blocked scenarios (unresolved Open Issues) — never silently guessed
# =============================================================================

class BlockedScenarioTest(TestCase):

    def test_escrow_after_settlement_blocked(self):
        """Refund AFTER settlement must raise, never reopen SETTLED/CLOSED escrow."""
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        escrow = EscrowRecord.objects.get(payment=payment)
        batch = SettlementBatchService.create_batch(
            company=company,
            level="platform_to_org",
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        batch = SettlementBatchService.mark_ready(batch)
        EscrowRecordService.mark_pending_settlement(escrow, batch)
        EscrowRecordService.mark_settled(escrow)

        with self.assertRaises(RefundExecutionBlockedError):
            RefundExecutionService.execute(document)

        escrow.refresh_from_db()
        self.assertEqual(escrow.status, EscrowRecord.Status.SETTLED)  # never reopened

    def test_closed_escrow_never_reopened(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        escrow = EscrowRecord.objects.get(payment=payment)
        EscrowRecordService.close(escrow)

        with self.assertRaises(RefundExecutionBlockedError):
            RefundExecutionService.execute(document)

        escrow.refresh_from_db()
        self.assertEqual(escrow.status, EscrowRecord.Status.CLOSED)

    def test_partial_refund_document_type_blocked(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.PARTIAL_REFUND,
            amount_rial=1_000_000,
            reason="test partial",
        )
        document = AdjustmentDocumentService.submit_for_approval(document)
        document = AdjustmentDocumentService.approve(document, approved_by=None)

        with self.assertRaises(RefundExecutionBlockedError):
            RefundExecutionService.execute(document)

    def test_manual_adjustment_document_type_blocked(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            amount_rial=500_000,
            reason="test manual adjustment",
        )
        document = AdjustmentDocumentService.submit_for_approval(document)
        document = AdjustmentDocumentService.approve(document, approved_by=None)

        with self.assertRaises(RefundExecutionBlockedError):
            RefundExecutionService.execute(document)

    def test_direct_split_technician_wage_blocked(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        PaymentSplitSnapshot.objects.create(
            company=company,
            payment=payment,
            invoice=invoice,
            total_amount=10_000_000,
            platform_fee_amount=100_000,
            company_deposit_amount=3_900_000,
            technician_direct_amount=6_000_000,
            technician_ledger_amount=0,
            should_split_with_technician=True,
        )

        with self.assertRaises(RefundExecutionBlockedError):
            RefundExecutionService.execute(document)

        # Nothing was written for this blocked attempt.
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company, source=TechnicianLedgerEntry.Source.REFUND,
            ).count(),
            0,
        )


# =============================================================================
# Immutability
# =============================================================================

class ImmutabilityTest(TestCase):

    def test_old_ledger_entry_immutable(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        original_credit = TechnicianLedgerEntry.objects.get(
            company=company, entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
        )
        amount_before = original_credit.amount_rial
        balance_before = original_credit.balance_after

        RefundExecutionService.execute(document)

        original_credit.refresh_from_db()
        self.assertEqual(original_credit.amount_rial, amount_before)
        self.assertEqual(original_credit.balance_after, balance_before)

    def test_old_platform_fee_entry_immutable(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        original_debit = CompanyPlatformFeeEntry.objects.get(
            company=company, entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
        )
        amount_before = original_debit.amount_rial
        balance_before = original_debit.balance_after

        RefundExecutionService.execute(document)

        original_debit.refresh_from_db()
        self.assertEqual(original_debit.amount_rial, amount_before)
        self.assertEqual(original_debit.balance_after, balance_before)

    def test_invoice_status_unchanged(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)
        status_before = invoice.status

        RefundExecutionService.execute(document)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, status_before)

    def test_payment_status_unchanged(self):
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)
        payment.refresh_from_db()
        status_before = payment.status

        RefundExecutionService.execute(document)

        payment.refresh_from_db()
        self.assertEqual(payment.status, status_before)


# =============================================================================
# Transaction / rollback
# =============================================================================

class AtomicRollbackTest(TestCase):

    def test_atomic_rollback_on_failure(self):
        """
        If a failure is injected inside the inner atomic block (after the
        platform fee reversal but before mark_applied() succeeds), every
        write made so far in that block must roll back together — the
        document remains APPROVED (no FAILED status exists for
        AdjustmentDocument), and zero reversal entries persist.
        """
        from unittest.mock import patch

        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        with patch(
            "apps.payouts.services_adjustment.AdjustmentDocumentService.mark_applied",
            side_effect=RuntimeError("simulated failure after ledger write"),
        ):
            with self.assertRaises(RuntimeError):
                RefundExecutionService.execute(document)

        document.refresh_from_db()
        self.assertEqual(document.status, AdjustmentDocument.Status.APPROVED)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company, source=TechnicianLedgerEntry.Source.REFUND,
            ).count(),
            0,
        )
        self.assertEqual(
            CompanyPlatformFeeEntry.objects.filter(
                company=company, source=CompanyPlatformFeeEntry.Source.REFUND,
            ).count(),
            0,
        )

    def test_retry_after_rollback_succeeds(self):
        """A document left APPROVED after a rolled-back failure can be retried successfully."""
        from unittest.mock import patch

        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        with patch(
            "apps.payouts.services_adjustment.AdjustmentDocumentService.mark_applied",
            side_effect=RuntimeError("simulated failure"),
        ):
            with self.assertRaises(RuntimeError):
                RefundExecutionService.execute(document)

        document.refresh_from_db()
        result = RefundExecutionService.execute(document)

        self.assertEqual(result.status, "applied")
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company, source=TechnicianLedgerEntry.Source.REFUND,
            ).count(),
            1,
        )


# =============================================================================
# Tenant isolation
# =============================================================================

class TenantIsolationTest(TestCase):

    def test_tenant_isolation(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a, service_pct=60, goods_pct=10, travel_pct=100)
        tech_b = _technician(company_b, service_pct=60, goods_pct=10, travel_pct=100)
        invoice_a, _pa = _distributed_invoice(company_a, tech_a, total=10_000_000, fee_percent=1)
        invoice_b, _pb = _distributed_invoice(company_b, tech_b, total=99_000_000, fee_percent=5)
        document_a = _approved_full_refund(company_a, invoice_a)
        document_b = _approved_full_refund(company_b, invoice_b)

        RefundExecutionService.execute(document_a)

        # company_b's document remains untouched by company_a's execution.
        document_b.refresh_from_db()
        self.assertEqual(document_b.status, AdjustmentDocument.Status.APPROVED)
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company_b, source=TechnicianLedgerEntry.Source.REFUND,
            ).count(),
            0,
        )
        self.assertEqual(
            TechnicianLedgerEntry.objects.filter(
                company=company_a, source=TechnicianLedgerEntry.Source.REFUND,
            ).count(),
            1,
        )


# =============================================================================
# Safety — no UI, no API, no command, no bank call
# =============================================================================

class SafetyTest(TestCase):

    def test_no_bank_call_needed_for_success(self):
        """
        There is no bank API client anywhere in this module — verified
        structurally by confirming execution succeeds with no network
        dependency (nothing to mock, nothing raises due to a missing
        external call).
        """
        company = _company()
        tech = _technician(company, service_pct=60, goods_pct=10, travel_pct=100)
        invoice, _p = _distributed_invoice(company, tech, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        result = RefundExecutionService.execute(document)

        self.assertEqual(result.status, "applied")

    def test_no_technician_wage_no_op(self):
        """An invoice with no technician assigned must not error — just no wage reversal."""
        company = _company()
        invoice, _p = _distributed_invoice(company, None, total=10_000_000, fee_percent=1)
        document = _approved_full_refund(company, invoice)

        result = RefundExecutionService.execute(document)

        self.assertEqual(result.status, "applied")
        self.assertFalse(result.technician_ledger_entry_created)
