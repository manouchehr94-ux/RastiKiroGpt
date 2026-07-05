"""
Payouts — Adjustment Document Service (Sprint 2 — Financial Foundation
Services).

Provides safe, idempotent lifecycle operations for AdjustmentDocument per
the approved specification:
  docs/13_Financial_Core/target_architecture/25_FINANCIAL_STATE_MACHINE_SPECIFICATION.md §6
  docs/13_Financial_Core/target_architecture/26_REFUND_REVERSAL_ENGINE_SPECIFICATION.md

This service manages document LIFECYCLE only. It does not:
  - create reversal ledger entries (TechnicianLedgerEntry / CompanyPlatformFeeEntry),
  - call any refund gateway API,
  - change any customer balance,
  - emit any event, signal, or notification.

[OPEN-ISSUE: OI-05], [OPEN-ISSUE: OI-06], [OPEN-ISSUE: OI-07],
[OPEN-ISSUE: OI-08] — the full refund/reversal execution semantics remain
unresolved by the Product Owner (see Document 26). This service does not
resolve any of them; mark_applied() only records that a document has
reached its terminal APPLIED state, matching the state machine contract.
Actually creating and linking reversal ledger entries is explicitly
deferred to a future RefundExecutionService (Sprint 3+, blocked on OI-07).

No production code path (payment flow, invoice flow, payout flow) calls
this service yet.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.invoices.models import Invoice

from .exceptions import AdjustmentTransitionError
from .models import AdjustmentDocument

# Re-exported for backward compatibility: existing call sites and tests that
# do `from apps.payouts.services_adjustment import AdjustmentTransitionError`
# must keep working unchanged. The canonical definition now lives in
# apps/payouts/exceptions.py as part of the shared FinancialError
# hierarchy.
__all__ = ["AdjustmentDocumentService", "AdjustmentTransitionError"]


class AdjustmentDocumentService:
    """
    Lifecycle operations for AdjustmentDocument.

    State machine (Document 25 §6):
        DRAFT -> PENDING_APPROVAL -> APPROVED -> APPLIED
        DRAFT -> CANCELLED
        PENDING_APPROVAL -> REJECTED
    """

    @staticmethod
    def _refund_document_types():
        return {
            AdjustmentDocument.DocumentType.FULL_REFUND,
            AdjustmentDocument.DocumentType.PARTIAL_REFUND,
        }

    @staticmethod
    @transaction.atomic
    def create_draft(company, original_invoice, document_type, amount_rial, reason, created_by=None):
        """
        Create a new AdjustmentDocument in DRAFT status.

        Validation (per Document 25 §6 Preconditions and Sprint 2 scope):
          - original_invoice.status must be PAID.
          - amount_rial must be a positive integer.
          - amount_rial must not exceed original_invoice.total_amount for
            FULL_REFUND / PARTIAL_REFUND document types.
          - reason must be a non-empty string (mandatory justification,
            per R50).

        Raises ValueError if any precondition fails. No reversal ledger
        entry is created. No customer balance is touched.
        """
        if original_invoice.status != Invoice.Status.PAID:
            raise ValueError(
                f"AdjustmentDocument can only be created for a PAID invoice "
                f"(invoice #{original_invoice.pk} is '{original_invoice.status}')."
            )

        amount_rial = int(amount_rial)
        if amount_rial <= 0:
            raise ValueError("amount_rial must be a positive integer.")

        if document_type in AdjustmentDocumentService._refund_document_types():
            if amount_rial > int(original_invoice.total_amount):
                raise ValueError(
                    f"amount_rial ({amount_rial}) must not exceed "
                    f"original_invoice.total_amount "
                    f"({int(original_invoice.total_amount)}) for refund-type "
                    f"documents."
                )

        if not reason or not str(reason).strip():
            raise ValueError("reason is required and must not be empty.")

        return AdjustmentDocument.objects.create(
            company=company,
            original_invoice=original_invoice,
            document_type=document_type,
            amount_rial=amount_rial,
            reason=reason,
            created_by=created_by,
        )

    @staticmethod
    @transaction.atomic
    def submit_for_approval(document):
        """
        DRAFT -> PENDING_APPROVAL.

        Raises AdjustmentTransitionError if document.status is not DRAFT.
        """
        locked = AdjustmentDocument.objects.select_for_update().get(pk=document.pk)

        if locked.status != AdjustmentDocument.Status.DRAFT:
            raise AdjustmentTransitionError(
                f"AdjustmentDocument #{locked.pk}: cannot submit for approval "
                f"from status '{locked.status}'. Must be DRAFT."
            )

        locked.status = AdjustmentDocument.Status.PENDING_APPROVAL
        locked.save(update_fields=["status", "updated_at"])
        return locked

    @staticmethod
    @transaction.atomic
    def approve(document, approved_by):
        """
        PENDING_APPROVAL -> APPROVED.

        Raises AdjustmentTransitionError if document.status is not
        PENDING_APPROVAL. Does not create any reversal ledger entry —
        only records the approval decision itself.

        [OPEN-ISSUE: OI-08] — whether a second, distinct approval step is
        additionally required for certain adjustment types is not decided.
        This method implements single-step approval only.
        """
        locked = AdjustmentDocument.objects.select_for_update().get(pk=document.pk)

        if locked.status != AdjustmentDocument.Status.PENDING_APPROVAL:
            raise AdjustmentTransitionError(
                f"AdjustmentDocument #{locked.pk}: cannot approve from status "
                f"'{locked.status}'. Must be PENDING_APPROVAL."
            )

        locked.status = AdjustmentDocument.Status.APPROVED
        locked.approved_by = approved_by
        locked.approved_at = timezone.now()
        locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return locked

    @staticmethod
    @transaction.atomic
    def reject(document, rejected_by=None, reason=None):
        """
        PENDING_APPROVAL -> REJECTED. Terminal.

        `rejected_by` and `reason` are accepted for forward compatibility
        with a future audit trail, but are NOT persisted in Sprint 2:
        AdjustmentDocument has no `rejected_by` or `rejection_reason`
        field (adding one would be a schema change, out of scope for this
        sprint).

        Raises AdjustmentTransitionError if document.status is not
        PENDING_APPROVAL.
        """
        locked = AdjustmentDocument.objects.select_for_update().get(pk=document.pk)

        if locked.status != AdjustmentDocument.Status.PENDING_APPROVAL:
            raise AdjustmentTransitionError(
                f"AdjustmentDocument #{locked.pk}: cannot reject from status "
                f"'{locked.status}'. Must be PENDING_APPROVAL."
            )

        locked.status = AdjustmentDocument.Status.REJECTED
        locked.save(update_fields=["status", "updated_at"])
        return locked

    @staticmethod
    @transaction.atomic
    def cancel(document, reason=None):
        """
        DRAFT -> CANCELLED. Terminal.

        `reason` is accepted for forward compatibility with a future audit
        trail, but is NOT persisted in Sprint 2 (see reject() docstring
        for the same reasoning).

        Raises AdjustmentTransitionError if document.status is not DRAFT.
        """
        locked = AdjustmentDocument.objects.select_for_update().get(pk=document.pk)

        if locked.status != AdjustmentDocument.Status.DRAFT:
            raise AdjustmentTransitionError(
                f"AdjustmentDocument #{locked.pk}: cannot cancel from status "
                f"'{locked.status}'. Must be DRAFT."
            )

        locked.status = AdjustmentDocument.Status.CANCELLED
        locked.save(update_fields=["status", "updated_at"])
        return locked

    @staticmethod
    @transaction.atomic
    def mark_applied(document):
        """
        APPROVED -> APPLIED. Terminal.

        This method ONLY records that the document has reached its
        terminal APPLIED state and sets `applied_at`. It deliberately does
        NOT:
          - create any TechnicianLedgerEntry or CompanyPlatformFeeEntry
            reversal,
          - populate `technician_ledger_entry` / `platform_fee_entry` FKs
            (those remain None unless the caller sets them explicitly
            before calling this method),
          - call any refund gateway API,
          - change any customer balance,
          - emit any event.

        Actually executing reversals is the responsibility of a future
        RefundExecutionService (Sprint 3+, blocked on
        [OPEN-ISSUE: OI-07]). Raises AdjustmentTransitionError if
        document.status is not APPROVED.
        """
        locked = AdjustmentDocument.objects.select_for_update().get(pk=document.pk)

        if locked.status != AdjustmentDocument.Status.APPROVED:
            raise AdjustmentTransitionError(
                f"AdjustmentDocument #{locked.pk}: cannot mark applied from "
                f"status '{locked.status}'. Must be APPROVED."
            )

        locked.status = AdjustmentDocument.Status.APPLIED
        locked.applied_at = timezone.now()
        locked.save(update_fields=["status", "applied_at", "updated_at"])
        return locked
