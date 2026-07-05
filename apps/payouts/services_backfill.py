"""
Payouts — Financial Backfill Service.

FinancialBackfillService retries ledger/fee writes that failed during
InvoiceMarkPaidService.mark_paid(). Each task is processed in its own
transaction so one failure does not affect the others.

Usage:
    FinancialBackfillService.create_task(...)    # called from mark_paid on failure
    FinancialBackfillService.process_pending()   # run via management command or cron
"""
import logging

from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class FinancialBackfillService:

    @staticmethod
    @transaction.atomic
    def create_task(
        *,
        company,
        task_type: str,
        invoice=None,
        payment=None,
        error_message: str = "",
        metadata: dict | None = None,
    ):
        """
        Create a PENDING backfill task, or return the existing active one.

        At most one PENDING or PROCESSING task may exist per
        (company, task_type, invoice) combination. The select_for_update()
        serializes concurrent callers so no duplicate is ever inserted.

        Returns (task, created: bool).
        """
        from .models import FinancialBackfillTask

        existing = (
            FinancialBackfillTask.objects.select_for_update()
            .filter(
                company=company,
                task_type=task_type,
                invoice=invoice,
                status__in=[
                    FinancialBackfillTask.Status.PENDING,
                    FinancialBackfillTask.Status.PROCESSING,
                ],
            )
            .first()
        )
        if existing:
            return existing, False

        task = FinancialBackfillTask.objects.create(
            company=company,
            task_type=task_type,
            invoice=invoice,
            payment=payment,
            status=FinancialBackfillTask.Status.PENDING,
            error_message=error_message[:1000] if error_message else "",
            metadata=metadata or {},
        )
        return task, True

    @staticmethod
    def process_pending(*, limit: int = 100) -> dict:
        """
        Process up to `limit` PENDING backfill tasks.

        Each task runs in its own transaction. A failure on one task
        does not roll back others.

        Returns {"resolved": int, "failed": int, "skipped": int}.
        """
        from .models import FinancialBackfillTask

        task_ids = list(
            FinancialBackfillTask.objects.filter(
                status=FinancialBackfillTask.Status.PENDING,
            )
            .order_by("created_at")
            .values_list("id", flat=True)[:limit]
        )

        resolved = 0
        failed = 0
        skipped = 0

        for task_id in task_ids:
            result = FinancialBackfillService._process_one(task_id)
            if result == "resolved":
                resolved += 1
            elif result == "failed":
                failed += 1
            else:
                skipped += 1

        return {"resolved": resolved, "failed": failed, "skipped": skipped}

    @staticmethod
    def _process_one(task_id: int) -> str:
        """
        Process a single task.

        Phase 1: open a transaction, lock the row, dispatch the retry.
          - On success: mark RESOLVED in the same transaction.
          - On failure: the transaction rolls back (no state change in DB).

        Phase 2 (failure only): open a fresh transaction to record the failure
        (increment attempts, store error_message).

        Returns "resolved", "failed", or "skipped".
        """
        from .models import FinancialBackfillTask

        try:
            with transaction.atomic():
                try:
                    task = FinancialBackfillTask.objects.select_for_update().get(
                        pk=task_id,
                        status=FinancialBackfillTask.Status.PENDING,
                    )
                except FinancialBackfillTask.DoesNotExist:
                    return "skipped"

                task.status = FinancialBackfillTask.Status.PROCESSING
                task.last_attempt_at = timezone.now()
                task.attempts += 1
                task.save(
                    update_fields=["status", "last_attempt_at", "attempts", "updated_at"]
                )

                FinancialBackfillService._dispatch(task)

                task.status = FinancialBackfillTask.Status.RESOLVED
                task.resolved_at = timezone.now()
                task.error_message = ""
                task.save(
                    update_fields=["status", "resolved_at", "error_message", "updated_at"]
                )
                return "resolved"

        except Exception as exc:
            logger.critical(
                "FinancialBackfillService: task #%s failed: %s",
                task_id,
                exc,
                exc_info=True,
            )
            # Phase 2: record the failure. The phase-1 transaction was rolled
            # back, so the DB row is still PENDING with its original attempt count.
            try:
                with transaction.atomic():
                    from .models import FinancialBackfillTask as _FBT  # re-import after rollback
                    _FBT.objects.filter(pk=task_id).update(
                        status=_FBT.Status.PENDING,
                        error_message=str(exc)[:1000],
                        last_attempt_at=timezone.now(),
                        attempts=models.F("attempts") + 1,
                        updated_at=timezone.now(),
                    )
            except Exception as update_exc:
                logger.error(
                    "FinancialBackfillService: could not record failure for task #%s: %s",
                    task_id,
                    update_exc,
                )
            return "failed"

    @staticmethod
    def _dispatch(task) -> None:
        """Route the task to the correct retry handler."""
        from .models import FinancialBackfillTask

        if task.task_type == FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER:
            _retry_technician_ledger(task)
        elif task.task_type == FinancialBackfillTask.TaskType.PLATFORM_FEE:
            _retry_platform_fee(task)
        elif task.task_type == FinancialBackfillTask.TaskType.PAYMENT_SPLIT_SNAPSHOT:
            _retry_payment_split_snapshot(task)
        elif task.task_type == FinancialBackfillTask.TaskType.DIRECT_GATEWAY_SETTLEMENT:
            _retry_direct_gateway_settlement(task)
        elif task.task_type == "escrow_record":
            # Sprint 3 — Escrow Integration. Uses a raw string task_type,
            # following the same precedent already established by
            # InvoiceMarkPaidService.mark_paid() for "technician_ledger" and
            # "platform_fee" (both of which also predate their own enum
            # members being required at the FinancialBackfillTask.TaskType
            # level for the dispatcher to work — TextChoices does not
            # enforce membership at the Python/DB level, only in forms).
            # Adding a real TaskType.ESCROW_RECORD choice would be a purely
            # cosmetic migration; deferred to avoid an unnecessary migration
            # in this additive-only sprint.
            _retry_escrow_record(task)
        else:
            raise ValueError(f"Unknown task_type: {task.task_type!r}")


def _retry_technician_ledger(task) -> None:
    from apps.payouts.services import TechnicianLedgerService

    if task.invoice is None:
        raise ValueError(
            f"BackfillTask #{task.pk} (technician_ledger): invoice FK is None."
        )
    # create_invoice_entries is idempotent — skips entries that already exist
    TechnicianLedgerService.create_invoice_entries(task.invoice, payment=task.payment)


def _retry_platform_fee(task) -> None:
    from .services_platform_fee import PlatformFeeService

    if task.invoice is None:
        raise ValueError(
            f"BackfillTask #{task.pk} (platform_fee): invoice FK is None."
        )
    # record_invoice_fee is idempotent — skips if entry already exists.
    # Raises PlatformFeeRecordingFailed if the write fails again.
    PlatformFeeService.record_invoice_fee(task.invoice, payment=task.payment)


def _retry_payment_split_snapshot(task) -> None:
    from .services_split import PaymentSplitDecisionService

    if task.payment is None:
        raise ValueError(
            f"BackfillTask #{task.pk} (payment_split_snapshot): payment FK is None."
        )
    payment = task.payment
    invoice = getattr(payment, "invoice", None)
    if invoice is None:
        raise ValueError(
            f"BackfillTask #{task.pk} (payment_split_snapshot): payment has no invoice."
        )
    # Reload the invoice to pick up any settled_* fields written by mark_paid.
    fresh_invoice = invoice.__class__.objects.get(pk=invoice.pk)
    # create_snapshot is idempotent — returns existing snapshot if already present.
    PaymentSplitDecisionService.create_snapshot(payment, fresh_invoice)


def _retry_escrow_record(task) -> None:
    from apps.invoices.services import reserve_and_distribute_escrow_for_invoice
    from apps.payouts.services_escrow import EscrowRecordService

    if task.invoice is None:
        raise ValueError(
            f"BackfillTask #{task.pk} (escrow_record): invoice FK is None."
        )
    if task.payment is None:
        raise ValueError(
            f"BackfillTask #{task.pk} (escrow_record): payment FK is None."
        )

    # Cover both possible failure points with one idempotent retry:
    #   1. EscrowRecordService.create_for_payment() may have failed at
    #      payment-verification time (no EscrowRecord exists yet at all).
    #   2. reserve_and_distribute_escrow_for_invoice() may have failed at
    #      mark_paid() time (EscrowRecord exists but is still HELD or
    #      RESERVED, never reached DISTRIBUTED).
    # create_for_payment is idempotent — returns the existing record (or
    # None for an ineligible payment) rather than duplicating.
    EscrowRecordService.create_for_payment(task.payment, invoice=task.invoice)
    reserve_and_distribute_escrow_for_invoice(invoice=task.invoice, payment=task.payment)


def _retry_direct_gateway_settlement(task) -> None:
    from .models import PaymentSplitSnapshot
    from .services_split import PaymentSplitDecisionService
    from .services_direct_settlement import TechnicianDirectSettlementService

    if task.payment is None:
        raise ValueError(
            f"BackfillTask #{task.pk} (direct_gateway_settlement): payment FK is None."
        )
    payment = task.payment

    # Ensure the split snapshot exists before attempting to post the DEBIT.
    # It may be missing if PaymentSplitDecisionService.create_snapshot() also failed.
    snapshot = PaymentSplitSnapshot.objects.filter(payment=payment).first()
    if snapshot is None:
        invoice = getattr(payment, "invoice", None)
        if invoice is None:
            raise ValueError(
                f"BackfillTask #{task.pk} (direct_gateway_settlement): "
                "payment has no invoice; cannot create missing split snapshot."
            )
        fresh_invoice = invoice.__class__.objects.get(pk=invoice.pk)
        PaymentSplitDecisionService.create_snapshot(payment, fresh_invoice)

    # post_for_payment is idempotent via idempotency_key.
    # Returns [] gracefully when conditions are not met (e.g. should_split=False).
    TechnicianDirectSettlementService.post_for_payment(payment)
