"""
Sprint 1 — Financial Foundation Models: Model Unit Tests.

Covers the four purely additive, schema-only models introduced in this
sprint per docs/13_Financial_Core/target_architecture/19_DATA_MODEL.md:

    - EscrowRecord
    - SettlementBatch
    - SettlementItem
    - AdjustmentDocument

These tests verify only model-level behavior (field defaults, choices,
constraints, relationships, __str__, indexes). No service, view, signal,
or API is exercised — none exists yet for these models by design.

No existing test in this suite is modified. No existing model, service,
or migration is touched by this file.
"""
import itertools

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.payouts.factories import (
    make_adjustment_document,
    make_company,
    make_escrow_record,
    make_invoice,
    make_payment,
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

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# EscrowRecord
# ---------------------------------------------------------------------------

class EscrowRecordModelTest(TestCase):
    def test_01_create_with_defaults(self):
        """A minimal EscrowRecord defaults to status=HELD and zero shares."""
        record = make_escrow_record()

        self.assertEqual(record.status, EscrowRecord.Status.HELD)
        self.assertEqual(record.platform_commission_rial, 0)
        self.assertEqual(record.organization_share_rial, 0)
        self.assertEqual(record.provider_share_rial, 0)
        self.assertIsNotNone(record.held_at)
        self.assertIsNone(record.distributed_at)
        self.assertIsNone(record.settled_at)
        self.assertIsNone(record.closed_at)
        self.assertIsNone(record.settlement_batch)

    def test_02_status_choices_are_exact(self):
        """The Status enum must expose exactly the six documented values."""
        expected = {
            "held", "reserved", "distributed",
            "pending_settlement", "settled", "closed",
        }
        actual = {choice[0] for choice in EscrowRecord.Status.choices}
        self.assertEqual(actual, expected)

    def test_03_one_to_one_payment_constraint(self):
        """A second EscrowRecord for the same Payment must raise IntegrityError."""
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)
        make_escrow_record(company=company, payment=payment, invoice=invoice)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EscrowRecord.objects.create(
                    company=company,
                    payment=payment,
                    invoice=invoice,
                    amount_rial=1_000,
                )

    def test_04_invoice_is_nullable(self):
        """EscrowRecord.invoice may be null (per spec: 'nullable' field)."""
        record = make_escrow_record(invoice=None)
        self.assertIsNone(record.invoice)

    def test_05_settlement_batch_set_null_on_delete(self):
        """Deleting a SettlementBatch must not delete the EscrowRecord (SET_NULL)."""
        company = make_company()
        batch = make_settlement_batch(company=company)
        record = make_escrow_record(company=company, settlement_batch=batch)

        batch.delete()
        record.refresh_from_db()

        self.assertIsNone(record.settlement_batch_id)

    def test_06_cascade_delete_with_payment(self):
        """Deleting the linked Payment must cascade-delete the EscrowRecord."""
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)
        record = make_escrow_record(company=company, payment=payment, invoice=invoice)
        record_id = record.pk

        payment.delete()

        self.assertFalse(EscrowRecord.objects.filter(pk=record_id).exists())

    def test_07_amount_fields_reject_negative_at_db_level(self):
        """
        amount_rial and the three share fields are PositiveBigIntegerField;
        Django enforces this via full_clean(), not at raw INSERT time, so we
        verify via the model validator rather than expecting a DB constraint.
        """
        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)
        record = EscrowRecord(
            company=company,
            payment=payment,
            invoice=invoice,
            amount_rial=-500,
        )
        with self.assertRaises(Exception):
            record.full_clean()

    def test_08_str_representation(self):
        record = make_escrow_record()
        text = str(record)
        self.assertIn(str(record.pk), text)
        self.assertIn(record.status, text)

    def test_09_index_exists_on_company_status(self):
        """The composite (company, status) index must be present in Meta."""
        index_names = {idx.name for idx in EscrowRecord._meta.indexes}
        self.assertIn("escrow_company_status_idx", index_names)

    def test_10_company_owned_model_inheritance(self):
        """EscrowRecord must be tenant-scoped via company FK (CompanyOwnedModel)."""
        record = make_escrow_record()
        self.assertIsNotNone(record.company_id)
        self.assertTrue(hasattr(record, "created_at"))
        self.assertTrue(hasattr(record, "updated_at"))



# ---------------------------------------------------------------------------
# SettlementBatch
# ---------------------------------------------------------------------------

class SettlementBatchModelTest(TestCase):
    def test_01_create_with_defaults(self):
        """A minimal SettlementBatch defaults to status=CALCULATING."""
        batch = make_settlement_batch()

        self.assertEqual(batch.status, SettlementBatch.Status.CALCULATING)
        self.assertEqual(batch.net_amount_rial, 0)
        self.assertEqual(batch.total_credits, 0)
        self.assertEqual(batch.total_debits, 0)
        self.assertEqual(batch.items_count, 0)
        self.assertIsNone(batch.executed_at)
        self.assertEqual(batch.bank_reference, "")
        self.assertEqual(batch.failure_reason, "")

    def test_02_level_choices_are_exact(self):
        expected = {"platform_to_org", "org_to_provider"}
        actual = {choice[0] for choice in SettlementBatch.Level.choices}
        self.assertEqual(actual, expected)

    def test_03_status_choices_are_exact(self):
        expected = {"calculating", "ready", "executing", "completed", "failed"}
        actual = {choice[0] for choice in SettlementBatch.Status.choices}
        self.assertEqual(actual, expected)

    def test_04_net_amount_rial_allows_negative(self):
        """
        net_amount_rial is a signed BigIntegerField per spec: negative means
        the Organization owes the Platform.
        """
        batch = make_settlement_batch(net_amount_rial=-250_000)
        batch.refresh_from_db()
        self.assertEqual(batch.net_amount_rial, -250_000)

    def test_05_created_by_is_nullable(self):
        batch = make_settlement_batch()
        self.assertIsNone(batch.created_by)

    def test_06_ordering_is_newest_first(self):
        company = make_company()
        older = make_settlement_batch(company=company)
        newer = make_settlement_batch(company=company)

        results = list(SettlementBatch.objects.filter(company=company))
        self.assertEqual(results[0].pk, newer.pk)
        self.assertEqual(results[1].pk, older.pk)

    def test_07_str_representation(self):
        batch = make_settlement_batch()
        text = str(batch)
        self.assertIn(str(batch.pk), text)
        self.assertIn(batch.level, text)
        self.assertIn(batch.status, text)

    def test_08_indexes_exist(self):
        index_names = {idx.name for idx in SettlementBatch._meta.indexes}
        self.assertIn("settlement_batch_idx", index_names)
        self.assertIn("settlement_period_idx", index_names)

    def test_09_period_start_and_end_required(self):
        """period_start/period_end have no default; omitting both must fail validation."""
        company = make_company()
        batch = SettlementBatch(
            company=company,
            level=SettlementBatch.Level.PLATFORM_TO_ORG,
        )
        with self.assertRaises(Exception):
            batch.full_clean()

    def test_10_items_reverse_relation_name(self):
        """SettlementItem.batch related_name must be 'items'."""
        company = make_company()
        batch = make_settlement_batch(company=company)
        make_settlement_item(company=company, batch=batch)
        make_settlement_item(company=company, batch=batch)

        self.assertEqual(batch.items.count(), 2)



# ---------------------------------------------------------------------------
# SettlementItem
# ---------------------------------------------------------------------------

class SettlementItemModelTest(TestCase):
    def test_01_create_with_defaults(self):
        item = make_settlement_item()
        self.assertEqual(item.amount_rial, 100_000)
        self.assertEqual(item.description, "")

    def test_02_amount_rial_allows_negative(self):
        """amount_rial is signed BigIntegerField per spec (contribution to net position)."""
        item = make_settlement_item(amount_rial=-42_000)
        item.refresh_from_db()
        self.assertEqual(item.amount_rial, -42_000)

    def test_03_cascade_delete_with_batch(self):
        """Deleting the parent SettlementBatch must cascade-delete its items."""
        company = make_company()
        batch = make_settlement_batch(company=company)
        item = make_settlement_item(company=company, batch=batch)
        item_id = item.pk

        batch.delete()

        self.assertFalse(SettlementItem.objects.filter(pk=item_id).exists())

    def test_04_invoice_set_null_on_delete(self):
        """Deleting the linked Invoice must not delete the SettlementItem (SET_NULL)."""
        company = make_company()
        invoice = make_invoice(company)
        item = make_settlement_item(company=company, invoice=invoice)

        invoice.delete()
        item.refresh_from_db()

        self.assertIsNone(item.invoice_id)

    def test_05_invoice_is_nullable(self):
        item = make_settlement_item(invoice=None)
        self.assertIsNone(item.invoice)

    def test_06_ledger_entry_and_platform_fee_entry_are_nullable(self):
        item = make_settlement_item()
        self.assertIsNone(item.ledger_entry)
        self.assertIsNone(item.platform_fee_entry)

    def test_07_ledger_entry_fk_target(self):
        """SettlementItem.ledger_entry must reference TechnicianLedgerEntry."""
        field = SettlementItem._meta.get_field("ledger_entry")
        self.assertIs(field.related_model, TechnicianLedgerEntry)

    def test_08_platform_fee_entry_fk_target(self):
        """SettlementItem.platform_fee_entry must reference CompanyPlatformFeeEntry."""
        field = SettlementItem._meta.get_field("platform_fee_entry")
        self.assertIs(field.related_model, CompanyPlatformFeeEntry)

    def test_09_str_representation(self):
        item = make_settlement_item()
        text = str(item)
        self.assertIn(str(item.pk), text)
        self.assertIn(str(item.batch_id), text)

    def test_10_index_exists_on_batch_invoice(self):
        index_names = {idx.name for idx in SettlementItem._meta.indexes}
        self.assertIn("settlement_item_batch_inv_idx", index_names)

    def test_11_ordering_is_insertion_order(self):
        company = make_company()
        batch = make_settlement_batch(company=company)
        first = make_settlement_item(company=company, batch=batch)
        second = make_settlement_item(company=company, batch=batch)

        results = list(SettlementItem.objects.filter(batch=batch))
        self.assertEqual(results[0].pk, first.pk)
        self.assertEqual(results[1].pk, second.pk)



# ---------------------------------------------------------------------------
# AdjustmentDocument
# ---------------------------------------------------------------------------

class AdjustmentDocumentModelTest(TestCase):
    def test_01_create_with_defaults(self):
        """A minimal AdjustmentDocument defaults to status=DRAFT."""
        doc = make_adjustment_document()

        self.assertEqual(doc.status, AdjustmentDocument.Status.DRAFT)
        self.assertIsNone(doc.approved_by)
        self.assertIsNone(doc.approved_at)
        self.assertIsNone(doc.applied_at)
        self.assertIsNone(doc.technician_ledger_entry)
        self.assertIsNone(doc.platform_fee_entry)
        self.assertIsNone(doc.technician_wage_reversal)
        self.assertIsNone(doc.platform_fee_reversal)
        self.assertIsNone(doc.company_share_reversal)

    def test_02_document_type_choices_are_exact(self):
        expected = {
            "full_refund", "partial_refund", "credit_note",
            "debit_note", "manual_adjustment",
        }
        actual = {choice[0] for choice in AdjustmentDocument.DocumentType.choices}
        self.assertEqual(actual, expected)

    def test_03_status_choices_are_exact(self):
        expected = {
            "draft", "pending_approval", "approved",
            "applied", "rejected", "cancelled",
        }
        actual = {choice[0] for choice in AdjustmentDocument.Status.choices}
        self.assertEqual(actual, expected)

    def test_04_reason_is_required_at_validation_level(self):
        """reason has no blank=True, so full_clean() must reject an empty value."""
        company = make_company()
        invoice = make_invoice(company)
        doc = AdjustmentDocument(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            amount_rial=1_000,
            reason="",
        )
        with self.assertRaises(Exception):
            doc.full_clean()

    def test_05_original_invoice_cascade_delete(self):
        """Deleting original_invoice must cascade-delete the AdjustmentDocument."""
        company = make_company()
        invoice = make_invoice(company)
        doc = make_adjustment_document(company=company, original_invoice=invoice)
        doc_id = doc.pk

        invoice.delete()

        self.assertFalse(AdjustmentDocument.objects.filter(pk=doc_id).exists())

    def test_06_technician_ledger_entry_set_null_on_delete(self):
        """Deleting a referenced TechnicianLedgerEntry must not delete the document."""
        company = make_company()
        entry = TechnicianLedgerEntry.objects.create(
            company=company,
            technician=_make_bare_technician(company),
            entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
            source=TechnicianLedgerEntry.Source.ADJUSTMENT,
            amount_rial=1_000,
            balance_after=1_000,
            idempotency_key=f"sprint1-test:{_n()}",
        )
        doc = make_adjustment_document(
            company=company, technician_ledger_entry=entry,
        )

        entry.delete()
        doc.refresh_from_db()

        self.assertIsNone(doc.technician_ledger_entry_id)

    def test_07_amount_rial_is_positive_big_integer(self):
        """amount_rial rejects negative values at full_clean() validation."""
        company = make_company()
        invoice = make_invoice(company)
        doc = AdjustmentDocument(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
            amount_rial=-1,
            reason="invalid negative amount",
        )
        with self.assertRaises(Exception):
            doc.full_clean()

    def test_08_str_representation(self):
        doc = make_adjustment_document()
        text = str(doc)
        self.assertIn(str(doc.pk), text)
        self.assertIn(doc.document_type, text)
        self.assertIn(doc.status, text)
        self.assertIn(str(doc.original_invoice_id), text)

    def test_09_indexes_exist(self):
        index_names = {idx.name for idx in AdjustmentDocument._meta.indexes}
        self.assertIn("adj_doc_status_type_idx", index_names)
        self.assertIn("adj_doc_invoice_idx", index_names)

    def test_10_reverse_relation_from_invoice(self):
        """Invoice.adjustment_documents must expose related AdjustmentDocuments."""
        company = make_company()
        invoice = make_invoice(company)
        make_adjustment_document(company=company, original_invoice=invoice)
        make_adjustment_document(company=company, original_invoice=invoice)

        self.assertEqual(invoice.adjustment_documents.count(), 2)

    def test_11_ordering_is_newest_first(self):
        company = make_company()
        older = make_adjustment_document(company=company)
        newer = make_adjustment_document(company=company)

        results = list(AdjustmentDocument.objects.filter(company=company))
        self.assertEqual(results[0].pk, newer.pk)
        self.assertEqual(results[1].pk, older.pk)

    def test_12_reversal_decimal_fields_accept_values(self):
        doc = make_adjustment_document(
            technician_wage_reversal=15_000,
            platform_fee_reversal=500,
            company_share_reversal=4_500,
        )
        doc.refresh_from_db()
        self.assertEqual(doc.technician_wage_reversal, 15_000)
        self.assertEqual(doc.platform_fee_reversal, 500)
        self.assertEqual(doc.company_share_reversal, 4_500)


def _make_bare_technician(company):
    """Local helper: create a Technician without pulling in payouts fixtures
    that would duplicate what test_task011a_fix2_ledger_idempotency.py already
    covers. Kept minimal and local to this file only."""
    from apps.accounts.models import CompanyUser, Technician, UserRole

    user = CompanyUser.objects.create_user(
        username=f"sprint1tech{_n()}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(company=company, user=user)


# ---------------------------------------------------------------------------
# No-side-effect guard
# ---------------------------------------------------------------------------

class NoSideEffectOnExistingModelsTest(TestCase):
    """
    Sanity check: creating rows in the four new models must never write to
    TechnicianLedgerEntry or CompanyPlatformFeeEntry. This guards against a
    future regression where a signal or default accidentally starts
    touching the immutable ledgers from model-level code.
    """

    def test_creating_all_four_models_does_not_touch_existing_ledgers(self):
        ledger_count_before = TechnicianLedgerEntry.objects.count()
        fee_count_before = CompanyPlatformFeeEntry.objects.count()

        company = make_company()
        invoice = make_invoice(company)
        payment = make_payment(company, invoice=invoice)
        make_escrow_record(company=company, payment=payment, invoice=invoice)
        batch = make_settlement_batch(company=company)
        make_settlement_item(company=company, batch=batch, invoice=invoice)
        make_adjustment_document(company=company, original_invoice=invoice)

        self.assertEqual(
            TechnicianLedgerEntry.objects.count(), ledger_count_before,
        )
        self.assertEqual(
            CompanyPlatformFeeEntry.objects.count(), fee_count_before,
        )
