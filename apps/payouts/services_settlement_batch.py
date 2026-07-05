"""
Payouts — Settlement Batch & Item Services (Sprint 2 — Financial Foundation
Services).

Provides safe, idempotent lifecycle operations for SettlementBatch and
SettlementItem per the approved specification:
  docs/13_Financial_Core/target_architecture/25_FINANCIAL_STATE_MACHINE_SPECIFICATION.md §4, §5
  docs/13_Financial_Core/target_architecture/13_SETTLEMENT_NETTING_ENGINE.md

This module manages batch/item LIFECYCLE only. It does not:
  - execute any bank transfer,
  - calculate real net-position amounts,
  - automatically select eligible invoices or ledger entries,
  - emit any event, signal, or notification.

No production code path (payment flow, invoice flow, payout flow) calls
these services yet. They exist so a future SettlementCalculationService /
SettlementExecutionService (Sprint 3+) has a stable, tested API to build on.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone


class SettlementBatchTransitionError(ValueError):
    """Raised when a SettlementBatch state transition is not allowed."""


class SettlementItemNotAllowedError(ValueError):
    """Raised when adding a SettlementItem to a non-CALCULATING batch."""


class SettlementBatchService:
    """
    Lifecycle operations for SettlementBatch.

    State machine (Document 25 §4):
        CALCULATING -> READY -> EXECUTING -> COMPLETED
        EXECUTING -> FAILED
    """

    @staticmethod
    @transaction.atomic
    def create_batch(company, level, period_start, period_end, created_by=None):
        """
        Create a new SettlementBatch in CALCULATING status.

        This method performs NO eligibility scan, NO net-position
        calculation, and creates NO SettlementItem rows. It only opens a
        new batch shell for a period. Populating items is the caller's
        responsibility via SettlementItemService, and remains manual in
        this sprint (no automatic invoice/ledger selection exists yet).
        """
        from .models import SettlementBatch

        return SettlementBatch.objects.create(
            company=company,
            level=level,
            period_start=period_start,
            period_end=period_end,
            created_by=created_by,
        )

    @staticmethod
    @transaction.atomic
    def mark_ready(batch):
        """
        CALCULATING -> READY.

        Raises SettlementBatchTransitionError if batch.status is not
        CALCULATING. Does not validate or recompute item totals in this
        sprint — that belongs to the future SettlementCalculationService.
        """
        from .models import SettlementBatch

        locked = SettlementBatch.objects.select_for_update().get(pk=batch.pk)

        if locked.status != SettlementBatch.Status.CALCULATING:
            raise SettlementBatchTransitionError(
                f"SettlementBatch #{locked.pk}: cannot mark ready from status "
                f"'{locked.status}'. Must be CALCULATING."
            )

        locked.status = SettlementBatch.Status.READY
        locked.save(update_fields=["status", "updated_at"])
        return locked

    @staticmethod
    @transaction.atomic
    def mark_executing(batch):
        """
        READY -> EXECUTING.

        Raises SettlementBatchTransitionError if batch.status is not
        READY. Does not perform any bank transfer.
        """
        from .models import SettlementBatch

        locked = SettlementBatch.objects.select_for_update().get(pk=batch.pk)

        if locked.status != SettlementBatch.Status.READY:
            raise SettlementBatchTransitionError(
                f"SettlementBatch #{locked.pk}: cannot mark executing from "
                f"status '{locked.status}'. Must be READY."
            )

        locked.status = SettlementBatch.Status.EXECUTING
        locked.save(update_fields=["status", "updated_at"])
        return locked

    @staticmethod
    @transaction.atomic
    def mark_completed(batch, bank_reference=None):
        """
        EXECUTING -> COMPLETED. Terminal.

        Raises SettlementBatchTransitionError if batch.status is not
        EXECUTING. Does not create any ledger CREDIT/DEBIT entries in this
        sprint (per Document 25 §4 Postconditions, that belongs to a
        future SettlementExecutionService).
        """
        from .models import SettlementBatch

        locked = SettlementBatch.objects.select_for_update().get(pk=batch.pk)

        if locked.status != SettlementBatch.Status.EXECUTING:
            raise SettlementBatchTransitionError(
                f"SettlementBatch #{locked.pk}: cannot mark completed from "
                f"status '{locked.status}'. Must be EXECUTING."
            )

        locked.status = SettlementBatch.Status.COMPLETED
        locked.executed_at = timezone.now()
        if bank_reference is not None:
            locked.bank_reference = bank_reference
        locked.save(update_fields=[
            "status", "executed_at", "bank_reference", "updated_at",
        ])
        return locked

    @staticmethod
    @transaction.atomic
    def mark_failed(batch, failure_reason):
        """
        EXECUTING -> FAILED. Terminal.

        `failure_reason` is required (per Document 25 §4 Postconditions:
        "FAILED: failure_reason set"). Raises SettlementBatchTransitionError
        if batch.status is not EXECUTING, or ValueError if failure_reason
        is empty.
        """
        from .models import SettlementBatch

        if not failure_reason:
            raise ValueError("failure_reason is required when marking a batch FAILED.")

        locked = SettlementBatch.objects.select_for_update().get(pk=batch.pk)

        if locked.status != SettlementBatch.Status.EXECUTING:
            raise SettlementBatchTransitionError(
                f"SettlementBatch #{locked.pk}: cannot mark failed from status "
                f"'{locked.status}'. Must be EXECUTING."
            )

        locked.status = SettlementBatch.Status.FAILED
        locked.failure_reason = failure_reason
        locked.save(update_fields=["status", "failure_reason", "updated_at"])
        return locked

    @staticmethod
    def is_terminal(batch) -> bool:
        """
        Return True if batch.status is COMPLETED or FAILED — i.e. no further
        transition is allowed (Document 25 §4 Forbidden Transitions).
        """
        from .models import SettlementBatch

        return batch.status in (
            SettlementBatch.Status.COMPLETED,
            SettlementBatch.Status.FAILED,
        )


class SettlementItemService:
    """
    Item-attachment operations for SettlementItem.

    Per Document 25 §5, a SettlementItem has no independent status — its
    effective state is derived entirely from its parent batch. Items may
    only be added while the parent batch is CALCULATING (the "Provisional"
    state); once the batch leaves CALCULATING, its item set is finalized.
    """

    @staticmethod
    def _assert_batch_is_calculating(batch) -> None:
        from .models import SettlementBatch

        if batch.status != SettlementBatch.Status.CALCULATING:
            raise SettlementItemNotAllowedError(
                f"SettlementBatch #{batch.pk}: cannot add items while status "
                f"is '{batch.status}'. Items may only be added while "
                f"CALCULATING."
            )

    @staticmethod
    @transaction.atomic
    def add_invoice_item(batch, invoice, amount_rial, description=""):
        """
        Attach an invoice-based SettlementItem to a CALCULATING batch.

        `amount_rial` is a signed contribution to the batch net position
        (per SettlementItem.amount_rial help_text) — negative values are
        valid and preserved as-is.

        Raises SettlementItemNotAllowedError if batch.status is not
        CALCULATING.
        """
        from .models import SettlementBatch, SettlementItem

        locked_batch = SettlementBatch.objects.select_for_update().get(pk=batch.pk)
        SettlementItemService._assert_batch_is_calculating(locked_batch)

        return SettlementItem.objects.create(
            company=locked_batch.company,
            batch=locked_batch,
            invoice=invoice,
            amount_rial=int(amount_rial),
            description=description,
        )

    @staticmethod
    @transaction.atomic
    def add_ledger_item(batch, ledger_entry, amount_rial, description=""):
        """
        Attach a TechnicianLedgerEntry-based SettlementItem to a
        CALCULATING batch (Layer 2: Organization <-> Provider).

        Does NOT read or write TechnicianLedgerEntry itself — it only
        stores a reference and the signed contribution amount. No ledger
        entry is created, modified, or inspected for correctness here.

        Raises SettlementItemNotAllowedError if batch.status is not
        CALCULATING.
        """
        from .models import SettlementBatch, SettlementItem

        locked_batch = SettlementBatch.objects.select_for_update().get(pk=batch.pk)
        SettlementItemService._assert_batch_is_calculating(locked_batch)

        return SettlementItem.objects.create(
            company=locked_batch.company,
            batch=locked_batch,
            ledger_entry=ledger_entry,
            amount_rial=int(amount_rial),
            description=description,
        )

    @staticmethod
    @transaction.atomic
    def add_platform_fee_item(batch, platform_fee_entry, amount_rial, description=""):
        """
        Attach a CompanyPlatformFeeEntry-based SettlementItem to a
        CALCULATING batch (Layer 1: Platform <-> Organization).

        Does NOT read or write CompanyPlatformFeeEntry itself — it only
        stores a reference and the signed contribution amount.

        Raises SettlementItemNotAllowedError if batch.status is not
        CALCULATING.
        """
        from .models import SettlementBatch, SettlementItem

        locked_batch = SettlementBatch.objects.select_for_update().get(pk=batch.pk)
        SettlementItemService._assert_batch_is_calculating(locked_batch)

        return SettlementItem.objects.create(
            company=locked_batch.company,
            batch=locked_batch,
            platform_fee_entry=platform_fee_entry,
            amount_rial=int(amount_rial),
            description=description,
        )
