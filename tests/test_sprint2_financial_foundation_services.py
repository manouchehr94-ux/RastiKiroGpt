"""
Sprint 2 — Financial Foundation Services: Service Unit Tests.

Covers the three purely additive, non-wired service modules introduced in
this sprint:

    - EscrowRecordService     (apps/payouts/services_escrow.py)
    - SettlementBatchService  (apps/payouts/services_settlement_batch.py)
    - SettlementItemService   (apps/payouts/services_settlement_batch.py)
    - AdjustmentDocumentService (apps/payouts/services_adjustment.py)

These tests verify only service-level lifecycle behavior: happy paths,
invalid state transitions, idempotency, amount-consistency enforcement,
and the absence of any side effect on existing ledger/invoice/payment
models. None of these services are called by any existing production
code path, and none of these tests exercise or modify existing payment,
invoice, or payout services.

No existing test in this suite is modified. No existing model, service,
migration, view, API, or signal is touched by this file.
"""
import itertools

from django.test import TestCase
from django.utils import timezone

from apps.payments.models import Payment, PaymentGateway
from apps.payouts.factories import (
    make_adjustment_document,
    make_company,
    make_escrow_record,
    make_invoice,
    make_payment,
    make_payment_gateway,
    make_settlement_batch,
    make_settlement_item,
)
from apps.payouts.models import (
    AdjustmentDocument,
    CompanyPlatformFeeEntry,
    EscrowRecord,
    SettlementBatch,
    SettlementItem,
    TechnicianLedgerEntry,
)
from apps.payouts.services_adjustment import (
    AdjustmentDocumentService,
    AdjustmentTransitionError,
)
from apps.payouts.services_escrow import EscrowRecordService, EscrowTransitionError
from apps.payouts.services_settlement_batch import (
    SettlementBatchService,
    SettlementBatchTransitionError,
    SettlementItemNotAllowedError,
    SettlementItemService,
)

_counter = itertools.count(1)


def _n():
    return next(_counter)



# ---------------------------------------------------------------------------
# EscrowRecordService
# ---------------------------------------------------------------------------

class EscrowRecordServiceEligibilityTest(TestCase):
    def test_01_platform_gateway_online_payment_is_eligible(self):
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)  # default: platform gateway

        self.assertTrue(EscrowRecordService.is_eligible_for_escrow(payment))

    def test_02_company_gateway_payment_is_not_eligible(self):
        company = make_company()
        invoice = make_invoice(company)
        gateway = make_payment_gateway(company, owner_type=PaymentGateway.OwnerType.COMPANY)
        payment = make_payment(company, invoice=invoice, gateway=gateway)

        self.assertFalse(EscrowRecordService.is_eligible_for_escrow(payment))

    def test_03_payment_with_no_gateway_is_not_eligible(self):
        """Cash/manual payments typically have gateway=None."""
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice, gateway=None)

        self.assertFalse(EscrowRecordService.is_eligible_for_escrow(payment))


class EscrowRecordServiceCreateTest(TestCase):
    def test_01_create_for_eligible_payment_succeeds(self):
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)

        record = EscrowRecordService.create_for_payment(payment, invoice=invoice)

        self.assertIsNotNone(record)
        self.assertEqual(record.payment_id, payment.pk)
        self.assertEqual(record.invoice_id, invoice.pk)
        self.assertEqual(record.amount_rial, int(payment.amount))
        self.assertEqual(record.status, EscrowRecord.Status.HELD)

    def test_02_create_for_cash_payment_returns_none(self):
        """Cash/card-to-card/manual payments must never create escrow."""
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice, gateway=None)

        record = EscrowRecordService.create_for_payment(payment, invoice=invoice)

        self.assertIsNone(record)
        self.assertFalse(EscrowRecord.objects.filter(payment=payment).exists())

    def test_03_create_is_idempotent_returns_same_record(self):
        """Calling create_for_payment twice for the same payment must not duplicate."""
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)

        first = EscrowRecordService.create_for_payment(payment, invoice=invoice)
        second = EscrowRecordService.create_for_payment(payment, invoice=invoice)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(EscrowRecord.objects.filter(payment=payment).count(), 1)

    def test_04_create_defaults_invoice_from_payment(self):
        """If invoice is not passed explicitly, it falls back to payment.invoice."""
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)

        record = EscrowRecordService.create_for_payment(payment)

        self.assertEqual(record.invoice_id, invoice.pk)


class EscrowRecordServiceTransitionTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.invoice = make_invoice(self.company)
        self.payment = make_payment(self.company, invoice=self.invoice)

    def test_01_happy_path_full_lifecycle(self):
        record = EscrowRecordService.create_for_payment(self.payment, invoice=self.invoice)
        self.assertEqual(record.status, EscrowRecord.Status.HELD)

        record = EscrowRecordService.reserve_for_invoice(record, self.invoice)
        self.assertEqual(record.status, EscrowRecord.Status.RESERVED)

        record = EscrowRecordService.mark_distributed(
            record,
            platform_commission_rial=50_000,
            organization_share_rial=800_000,
            provider_share_rial=150_000,
        )
        self.assertEqual(record.status, EscrowRecord.Status.DISTRIBUTED)
        self.assertEqual(
            record.platform_commission_rial
            + record.organization_share_rial
            + record.provider_share_rial,
            record.amount_rial,
        )
        self.assertIsNotNone(record.distributed_at)

        batch = make_settlement_batch(company=self.company)
        record = EscrowRecordService.mark_pending_settlement(record, batch)
        self.assertEqual(record.status, EscrowRecord.Status.PENDING_SETTLEMENT)
        self.assertEqual(record.settlement_batch_id, batch.pk)

        record = EscrowRecordService.mark_settled(record)
        self.assertEqual(record.status, EscrowRecord.Status.SETTLED)
        self.assertIsNotNone(record.settled_at)

        record = EscrowRecordService.close(record)
        self.assertEqual(record.status, EscrowRecord.Status.CLOSED)
        self.assertIsNotNone(record.closed_at)

    def test_02_reserve_invalid_from_reserved_raises(self):
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.RESERVED,
        )
        with self.assertRaises(EscrowTransitionError):
            EscrowRecordService.reserve_for_invoice(record, self.invoice)

    def test_03_mark_distributed_invalid_from_held_raises(self):
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.HELD,
        )
        with self.assertRaises(EscrowTransitionError):
            EscrowRecordService.mark_distributed(
                record,
                platform_commission_rial=100,
                organization_share_rial=100,
                provider_share_rial=100,
            )

    def test_04_mark_distributed_amount_mismatch_raises_value_error(self):
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.RESERVED, amount_rial=1_000_000,
        )
        with self.assertRaises(ValueError):
            EscrowRecordService.mark_distributed(
                record,
                platform_commission_rial=50_000,
                organization_share_rial=800_000,
                provider_share_rial=100_000,  # totals 950_000, not 1_000_000
            )
        record.refresh_from_db()
        self.assertEqual(record.status, EscrowRecord.Status.RESERVED)

    def test_05_mark_pending_settlement_invalid_from_settled_raises(self):
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.SETTLED,
        )
        batch = make_settlement_batch(company=self.company)
        with self.assertRaises(EscrowTransitionError):
            EscrowRecordService.mark_pending_settlement(record, batch)

    def test_06_mark_settled_invalid_from_held_raises(self):
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.HELD,
        )
        with self.assertRaises(EscrowTransitionError):
            EscrowRecordService.mark_settled(record)

    def test_07_close_from_held_succeeds_refund_before_settlement(self):
        """Refund-before-settlement path: HELD -> CLOSED directly."""
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.HELD,
        )
        closed = EscrowRecordService.close(record, reason="refund before settlement")
        self.assertEqual(closed.status, EscrowRecord.Status.CLOSED)

    def test_08_close_from_pending_settlement_raises(self):
        """PENDING_SETTLEMENT must resolve to SETTLED first; close() is forbidden."""
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.PENDING_SETTLEMENT,
        )
        with self.assertRaises(EscrowTransitionError):
            EscrowRecordService.close(record)

    def test_09_close_from_closed_raises_terminal(self):
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.CLOSED,
        )
        with self.assertRaises(EscrowTransitionError):
            EscrowRecordService.close(record)

    def test_10_close_from_distributed_succeeds(self):
        record = make_escrow_record(
            company=self.company, payment=self.payment, invoice=self.invoice,
            status=EscrowRecord.Status.DISTRIBUTED,
        )
        closed = EscrowRecordService.close(record)
        self.assertEqual(closed.status, EscrowRecord.Status.CLOSED)



# ---------------------------------------------------------------------------
# SettlementBatchService
# ---------------------------------------------------------------------------

class SettlementBatchServiceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.now = timezone.now()

    def test_01_create_batch_defaults_to_calculating(self):
        batch = SettlementBatchService.create_batch(
            company=self.company,
            level=SettlementBatch.Level.PLATFORM_TO_ORG,
            period_start=self.now,
            period_end=self.now,
        )
        self.assertEqual(batch.status, SettlementBatch.Status.CALCULATING)
        self.assertEqual(batch.level, SettlementBatch.Level.PLATFORM_TO_ORG)
        self.assertIsNone(batch.created_by)

    def test_02_create_batch_creates_no_items(self):
        """create_batch must not auto-select any invoice or ledger entry."""
        batch = SettlementBatchService.create_batch(
            company=self.company,
            level=SettlementBatch.Level.ORG_TO_PROVIDER,
            period_start=self.now,
            period_end=self.now,
        )
        self.assertEqual(batch.items.count(), 0)

    def test_03_happy_path_full_lifecycle_to_completed(self):
        batch = make_settlement_batch(company=self.company)

        batch = SettlementBatchService.mark_ready(batch)
        self.assertEqual(batch.status, SettlementBatch.Status.READY)

        batch = SettlementBatchService.mark_executing(batch)
        self.assertEqual(batch.status, SettlementBatch.Status.EXECUTING)

        batch = SettlementBatchService.mark_completed(batch, bank_reference="TXN-001")
        self.assertEqual(batch.status, SettlementBatch.Status.COMPLETED)
        self.assertEqual(batch.bank_reference, "TXN-001")
        self.assertIsNotNone(batch.executed_at)

    def test_04_happy_path_to_failed(self):
        batch = make_settlement_batch(company=self.company)
        batch = SettlementBatchService.mark_ready(batch)
        batch = SettlementBatchService.mark_executing(batch)

        batch = SettlementBatchService.mark_failed(batch, "bank rejected transfer")
        self.assertEqual(batch.status, SettlementBatch.Status.FAILED)
        self.assertEqual(batch.failure_reason, "bank rejected transfer")

    def test_05_mark_ready_invalid_from_ready_raises(self):
        batch = make_settlement_batch(company=self.company, status=SettlementBatch.Status.READY)
        with self.assertRaises(SettlementBatchTransitionError):
            SettlementBatchService.mark_ready(batch)

    def test_06_mark_executing_invalid_from_calculating_raises(self):
        """CALCULATING -> EXECUTING directly is forbidden; must pass through READY."""
        batch = make_settlement_batch(company=self.company)
        with self.assertRaises(SettlementBatchTransitionError):
            SettlementBatchService.mark_executing(batch)

    def test_07_mark_completed_invalid_from_ready_raises(self):
        batch = make_settlement_batch(company=self.company, status=SettlementBatch.Status.READY)
        with self.assertRaises(SettlementBatchTransitionError):
            SettlementBatchService.mark_completed(batch)

    def test_08_mark_failed_requires_reason(self):
        batch = make_settlement_batch(company=self.company, status=SettlementBatch.Status.EXECUTING)
        with self.assertRaises(ValueError):
            SettlementBatchService.mark_failed(batch, "")

    def test_09_mark_failed_invalid_from_completed_raises(self):
        """COMPLETED is terminal; no further transition, including to FAILED."""
        batch = make_settlement_batch(company=self.company, status=SettlementBatch.Status.COMPLETED)
        with self.assertRaises(SettlementBatchTransitionError):
            SettlementBatchService.mark_failed(batch, "late failure attempt")

    def test_10_is_terminal_true_for_completed_and_failed(self):
        completed = make_settlement_batch(company=self.company, status=SettlementBatch.Status.COMPLETED)
        failed = make_settlement_batch(company=self.company, status=SettlementBatch.Status.FAILED)

        self.assertTrue(SettlementBatchService.is_terminal(completed))
        self.assertTrue(SettlementBatchService.is_terminal(failed))

    def test_11_is_terminal_false_for_non_terminal_statuses(self):
        calculating = make_settlement_batch(company=self.company)
        ready = make_settlement_batch(company=self.company, status=SettlementBatch.Status.READY)
        executing = make_settlement_batch(company=self.company, status=SettlementBatch.Status.EXECUTING)

        self.assertFalse(SettlementBatchService.is_terminal(calculating))
        self.assertFalse(SettlementBatchService.is_terminal(ready))
        self.assertFalse(SettlementBatchService.is_terminal(executing))

    def test_12_completed_cannot_transition_further(self):
        """No method allows a transition out of COMPLETED (terminal)."""
        batch = make_settlement_batch(company=self.company, status=SettlementBatch.Status.COMPLETED)
        with self.assertRaises(SettlementBatchTransitionError):
            SettlementBatchService.mark_executing(batch)



# ---------------------------------------------------------------------------
# SettlementItemService
# ---------------------------------------------------------------------------

class SettlementItemServiceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.batch = make_settlement_batch(company=self.company)  # CALCULATING
        self.invoice = make_invoice(self.company)

    def test_01_add_invoice_item_while_calculating_succeeds(self):
        item = SettlementItemService.add_invoice_item(
            self.batch, self.invoice, 250_000, description="test item",
        )
        self.assertEqual(item.batch_id, self.batch.pk)
        self.assertEqual(item.invoice_id, self.invoice.pk)
        self.assertEqual(item.amount_rial, 250_000)
        self.assertEqual(item.company_id, self.company.pk)

    def test_02_add_invoice_item_preserves_negative_signed_amount(self):
        item = SettlementItemService.add_invoice_item(
            self.batch, self.invoice, -75_000,
        )
        item.refresh_from_db()
        self.assertEqual(item.amount_rial, -75_000)

    def test_03_add_ledger_item_stores_reference_without_touching_ledger(self):
        technician = _make_bare_technician(self.company)
        entry = TechnicianLedgerEntry.objects.create(
            company=self.company,
            technician=technician,
            entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
            source=TechnicianLedgerEntry.Source.MANUAL_PAYMENT,
            amount_rial=10_000,
            balance_after=10_000,
            idempotency_key=f"sprint2-item-test:{_n()}",
        )
        ledger_count_before = TechnicianLedgerEntry.objects.count()

        item = SettlementItemService.add_ledger_item(self.batch, entry, 10_000)

        self.assertEqual(item.ledger_entry_id, entry.pk)
        self.assertEqual(TechnicianLedgerEntry.objects.count(), ledger_count_before)

    def test_04_add_platform_fee_item_stores_reference_without_touching_fee_ledger(self):
        fee_entry = CompanyPlatformFeeEntry.objects.create(
            company=self.company,
            entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
            source=CompanyPlatformFeeEntry.Source.ONLINE_GATEWAY,
            amount_rial=5_000,
            balance_after=5_000,
            idempotency_key=f"sprint2-fee-item-test:{_n()}",
        )
        fee_count_before = CompanyPlatformFeeEntry.objects.count()

        item = SettlementItemService.add_platform_fee_item(self.batch, fee_entry, 5_000)

        self.assertEqual(item.platform_fee_entry_id, fee_entry.pk)
        self.assertEqual(CompanyPlatformFeeEntry.objects.count(), fee_count_before)

    def test_05_add_item_to_ready_batch_raises(self):
        ready_batch = make_settlement_batch(company=self.company, status=SettlementBatch.Status.READY)
        with self.assertRaises(SettlementItemNotAllowedError):
            SettlementItemService.add_invoice_item(ready_batch, self.invoice, 1_000)

    def test_06_add_item_to_executing_batch_raises(self):
        executing_batch = make_settlement_batch(
            company=self.company, status=SettlementBatch.Status.EXECUTING,
        )
        with self.assertRaises(SettlementItemNotAllowedError):
            SettlementItemService.add_invoice_item(executing_batch, self.invoice, 1_000)

    def test_07_add_item_to_completed_batch_raises(self):
        completed_batch = make_settlement_batch(
            company=self.company, status=SettlementBatch.Status.COMPLETED,
        )
        with self.assertRaises(SettlementItemNotAllowedError):
            SettlementItemService.add_invoice_item(completed_batch, self.invoice, 1_000)

    def test_08_add_item_to_failed_batch_raises(self):
        failed_batch = make_settlement_batch(
            company=self.company, status=SettlementBatch.Status.FAILED,
        )
        with self.assertRaises(SettlementItemNotAllowedError):
            SettlementItemService.add_invoice_item(failed_batch, self.invoice, 1_000)

    def test_09_multiple_items_accumulate_on_same_batch(self):
        SettlementItemService.add_invoice_item(self.batch, self.invoice, 100_000)
        SettlementItemService.add_invoice_item(self.batch, self.invoice, 200_000)

        self.assertEqual(self.batch.items.count(), 2)


def _make_bare_technician(company):
    """Local helper mirroring the Sprint 1 test file's pattern exactly."""
    from apps.accounts.models import CompanyUser, Technician, UserRole

    user = CompanyUser.objects.create_user(
        username=f"sprint2tech{_n()}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user)



# ---------------------------------------------------------------------------
# AdjustmentDocumentService
# ---------------------------------------------------------------------------

class AdjustmentDocumentServiceCreateDraftTest(TestCase):
    def test_01_create_draft_on_paid_invoice_succeeds(self):
        company = make_company()
        invoice = make_invoice(company)  # factory default status=PAID

        doc = AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            amount_rial=10_000,
            reason="test correction",
        )

        self.assertEqual(doc.status, AdjustmentDocument.Status.DRAFT)
        self.assertEqual(doc.original_invoice_id, invoice.pk)
        self.assertEqual(doc.amount_rial, 10_000)

    def test_02_create_draft_on_non_paid_invoice_raises(self):
        from apps.invoices.models import Invoice

        company = make_company()
        invoice = make_invoice(company, status=Invoice.Status.ISSUED)

        with self.assertRaises(ValueError):
            AdjustmentDocumentService.create_draft(
                company=company,
                original_invoice=invoice,
                document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
                amount_rial=10_000,
                reason="should fail",
            )

    def test_03_create_draft_zero_amount_raises(self):
        company = make_company()
        invoice = make_invoice(company)

        with self.assertRaises(ValueError):
            AdjustmentDocumentService.create_draft(
                company=company,
                original_invoice=invoice,
                document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
                amount_rial=0,
                reason="zero amount",
            )

    def test_04_create_draft_negative_amount_raises(self):
        company = make_company()
        invoice = make_invoice(company)

        with self.assertRaises(ValueError):
            AdjustmentDocumentService.create_draft(
                company=company,
                original_invoice=invoice,
                document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
                amount_rial=-500,
                reason="negative amount",
            )

    def test_05_create_draft_empty_reason_raises(self):
        company = make_company()
        invoice = make_invoice(company)

        with self.assertRaises(ValueError):
            AdjustmentDocumentService.create_draft(
                company=company,
                original_invoice=invoice,
                document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
                amount_rial=1_000,
                reason="",
            )

    def test_06_create_draft_whitespace_only_reason_raises(self):
        company = make_company()
        invoice = make_invoice(company)

        with self.assertRaises(ValueError):
            AdjustmentDocumentService.create_draft(
                company=company,
                original_invoice=invoice,
                document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
                amount_rial=1_000,
                reason="   ",
            )

    def test_07_full_refund_amount_exceeding_invoice_total_raises(self):
        company = make_company()
        invoice = make_invoice(company, total_amount=1_000_000)

        with self.assertRaises(ValueError):
            AdjustmentDocumentService.create_draft(
                company=company,
                original_invoice=invoice,
                document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
                amount_rial=1_500_000,
                reason="exceeds invoice total",
            )

    def test_08_partial_refund_amount_exceeding_invoice_total_raises(self):
        company = make_company()
        invoice = make_invoice(company, total_amount=1_000_000)

        with self.assertRaises(ValueError):
            AdjustmentDocumentService.create_draft(
                company=company,
                original_invoice=invoice,
                document_type=AdjustmentDocument.DocumentType.PARTIAL_REFUND,
                amount_rial=1_000_001,
                reason="exceeds invoice total by one rial",
            )

    def test_09_full_refund_exactly_equal_to_invoice_total_succeeds(self):
        company = make_company()
        invoice = make_invoice(company, total_amount=1_000_000)

        doc = AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
            amount_rial=1_000_000,
            reason="exact full refund",
        )
        self.assertEqual(doc.amount_rial, 1_000_000)

    def test_10_manual_adjustment_may_exceed_invoice_total(self):
        """The 'must not exceed' rule applies only to refund-type documents."""
        company = make_company()
        invoice = make_invoice(company, total_amount=1_000_000)

        doc = AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            amount_rial=2_000_000,
            reason="manual adjustment can exceed invoice total",
        )
        self.assertEqual(doc.amount_rial, 2_000_000)


class AdjustmentDocumentServiceTransitionTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.invoice = make_invoice(self.company)
        self.admin_user = _make_bare_company_admin(self.company)

    def test_01_happy_path_full_lifecycle_to_applied(self):
        doc = make_adjustment_document(company=self.company, original_invoice=self.invoice)
        self.assertEqual(doc.status, AdjustmentDocument.Status.DRAFT)

        doc = AdjustmentDocumentService.submit_for_approval(doc)
        self.assertEqual(doc.status, AdjustmentDocument.Status.PENDING_APPROVAL)

        doc = AdjustmentDocumentService.approve(doc, approved_by=self.admin_user)
        self.assertEqual(doc.status, AdjustmentDocument.Status.APPROVED)
        self.assertEqual(doc.approved_by_id, self.admin_user.pk)
        self.assertIsNotNone(doc.approved_at)

        doc = AdjustmentDocumentService.mark_applied(doc)
        self.assertEqual(doc.status, AdjustmentDocument.Status.APPLIED)
        self.assertIsNotNone(doc.applied_at)

    def test_02_happy_path_reject(self):
        doc = make_adjustment_document(company=self.company, original_invoice=self.invoice)
        doc = AdjustmentDocumentService.submit_for_approval(doc)

        doc = AdjustmentDocumentService.reject(doc, rejected_by=self.admin_user, reason="not valid")
        self.assertEqual(doc.status, AdjustmentDocument.Status.REJECTED)

    def test_03_happy_path_cancel(self):
        doc = make_adjustment_document(company=self.company, original_invoice=self.invoice)

        doc = AdjustmentDocumentService.cancel(doc, reason="no longer needed")
        self.assertEqual(doc.status, AdjustmentDocument.Status.CANCELLED)

    def test_04_submit_for_approval_invalid_from_pending_raises(self):
        doc = make_adjustment_document(
            company=self.company, original_invoice=self.invoice,
            status=AdjustmentDocument.Status.PENDING_APPROVAL,
        )
        with self.assertRaises(AdjustmentTransitionError):
            AdjustmentDocumentService.submit_for_approval(doc)

    def test_05_approve_invalid_from_draft_raises(self):
        doc = make_adjustment_document(company=self.company, original_invoice=self.invoice)
        with self.assertRaises(AdjustmentTransitionError):
            AdjustmentDocumentService.approve(doc, approved_by=self.admin_user)

    def test_06_reject_invalid_from_draft_raises(self):
        doc = make_adjustment_document(company=self.company, original_invoice=self.invoice)
        with self.assertRaises(AdjustmentTransitionError):
            AdjustmentDocumentService.reject(doc)

    def test_07_cancel_invalid_from_pending_approval_raises(self):
        doc = make_adjustment_document(
            company=self.company, original_invoice=self.invoice,
            status=AdjustmentDocument.Status.PENDING_APPROVAL,
        )
        with self.assertRaises(AdjustmentTransitionError):
            AdjustmentDocumentService.cancel(doc)

    def test_08_mark_applied_invalid_from_pending_approval_raises(self):
        doc = make_adjustment_document(
            company=self.company, original_invoice=self.invoice,
            status=AdjustmentDocument.Status.PENDING_APPROVAL,
        )
        with self.assertRaises(AdjustmentTransitionError):
            AdjustmentDocumentService.mark_applied(doc)

    def test_09_applied_is_terminal_cannot_reject(self):
        doc = make_adjustment_document(
            company=self.company, original_invoice=self.invoice,
            status=AdjustmentDocument.Status.APPLIED,
        )
        with self.assertRaises(AdjustmentTransitionError):
            AdjustmentDocumentService.reject(doc)

    def test_10_rejected_is_terminal_cannot_approve(self):
        """Rejected documents cannot be revived; a new document is required."""
        doc = make_adjustment_document(
            company=self.company, original_invoice=self.invoice,
            status=AdjustmentDocument.Status.REJECTED,
        )
        with self.assertRaises(AdjustmentTransitionError):
            AdjustmentDocumentService.approve(doc, approved_by=self.admin_user)

    def test_11_cancelled_is_terminal_cannot_submit(self):
        doc = make_adjustment_document(
            company=self.company, original_invoice=self.invoice,
            status=AdjustmentDocument.Status.CANCELLED,
        )
        with self.assertRaises(AdjustmentTransitionError):
            AdjustmentDocumentService.submit_for_approval(doc)

    def test_12_mark_applied_does_not_create_reversal_ledger_entries(self):
        """
        mark_applied() must never create a TechnicianLedgerEntry or
        CompanyPlatformFeeEntry — reversal execution is deferred to a
        future RefundExecutionService (Sprint 3+, blocked on OI-07).
        """
        ledger_count_before = TechnicianLedgerEntry.objects.count()
        fee_count_before = CompanyPlatformFeeEntry.objects.count()

        doc = make_adjustment_document(
            company=self.company, original_invoice=self.invoice,
            status=AdjustmentDocument.Status.APPROVED,
        )
        doc = AdjustmentDocumentService.mark_applied(doc)

        self.assertEqual(doc.status, AdjustmentDocument.Status.APPLIED)
        self.assertIsNone(doc.technician_ledger_entry)
        self.assertIsNone(doc.platform_fee_entry)
        self.assertEqual(TechnicianLedgerEntry.objects.count(), ledger_count_before)
        self.assertEqual(CompanyPlatformFeeEntry.objects.count(), fee_count_before)


def _make_bare_company_admin(company):
    from apps.accounts.models import CompanyUser, UserRole

    return CompanyUser.objects.create_user(
        username=f"sprint2admin{_n()}",
        password="pass",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


# ---------------------------------------------------------------------------
# Cross-service no-side-effect guard
# ---------------------------------------------------------------------------

class NoSideEffectOnExistingFlowsTest(TestCase):
    """
    Sanity check: exercising every Sprint 2 service through a full happy
    path must never write to TechnicianLedgerEntry or
    CompanyPlatformFeeEntry, must never change Invoice.status away from
    what the factory set, and must never change Payment.status. This
    guards against a future regression where a service accidentally
    starts touching existing financial models or flows.
    """

    def test_full_service_exercise_leaves_existing_models_untouched(self):
        ledger_count_before = TechnicianLedgerEntry.objects.count()
        fee_count_before = CompanyPlatformFeeEntry.objects.count()

        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)

        invoice_status_before = invoice.status
        payment_status_before = payment.status

        # Exercise EscrowRecordService end to end.
        escrow = EscrowRecordService.create_for_payment(payment, invoice=invoice)
        escrow = EscrowRecordService.reserve_for_invoice(escrow, invoice)
        escrow = EscrowRecordService.mark_distributed(
            escrow,
            platform_commission_rial=escrow.amount_rial,
            organization_share_rial=0,
            provider_share_rial=0,
        )
        batch = SettlementBatchService.create_batch(
            company=company,
            level=SettlementBatch.Level.PLATFORM_TO_ORG,
            period_start=timezone.now(),
            period_end=timezone.now(),
        )
        SettlementItemService.add_invoice_item(batch, invoice, escrow.amount_rial)
        escrow = EscrowRecordService.mark_pending_settlement(escrow, batch)
        batch = SettlementBatchService.mark_ready(batch)
        batch = SettlementBatchService.mark_executing(batch)
        batch = SettlementBatchService.mark_completed(batch, bank_reference="TXN-GUARD")
        escrow = EscrowRecordService.mark_settled(escrow)
        EscrowRecordService.close(escrow)

        # Exercise AdjustmentDocumentService end to end.
        doc = AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            amount_rial=1_000,
            reason="no-side-effect guard test",
        )
        doc = AdjustmentDocumentService.submit_for_approval(doc)
        admin_user = _make_bare_company_admin(company)
        doc = AdjustmentDocumentService.approve(doc, approved_by=admin_user)
        AdjustmentDocumentService.mark_applied(doc)

        invoice.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(
            TechnicianLedgerEntry.objects.count(), ledger_count_before,
        )
        self.assertEqual(
            CompanyPlatformFeeEntry.objects.count(), fee_count_before,
        )
        self.assertEqual(invoice.status, invoice_status_before)
        self.assertEqual(payment.status, payment_status_before)
