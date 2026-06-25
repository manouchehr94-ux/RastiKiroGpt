"""
Invoice Cancellation Request — Service Layer.

Business rules enforced here:
  - Only DRAFT or ISSUED invoices may receive a cancellation request.
  - PAID and CANCELLED invoices are ineligible.
  - Only one PENDING request may exist per invoice (service-level check;
    DB partial unique index is the final race-safety guard).
  - Approval calls InvoiceCancelService.cancel() — the canonical path.
  - Approval is race-safe: invoice row is locked and re-checked before cancel.
  - PAID invoices raise ValueError on approve (never auto-cancel a paid invoice).
  - Rejection leaves the invoice status unchanged.
"""
from django.db import transaction
from django.utils import timezone

from .models import Invoice, InvoiceCancellationRequest


class InvoiceCancellationRequestService:

    @staticmethod
    @transaction.atomic
    def request(
        *,
        invoice: Invoice,
        requested_by,
        reason: str = "",
    ) -> InvoiceCancellationRequest:
        """
        Technician submits a cancellation request for a DRAFT or ISSUED invoice.

        Acquires a row-level lock on the invoice to prevent two concurrent
        technician requests from both passing the duplicate check.
        """
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)

        if invoice.status not in (Invoice.Status.DRAFT, Invoice.Status.ISSUED):
            raise ValueError(
                "درخواست لغو فقط برای فاکتورهای پیش‌نویس یا صادرشده امکان‌پذیر است."
            )

        already_pending = InvoiceCancellationRequest.objects.filter(
            invoice=invoice,
            status=InvoiceCancellationRequest.Status.PENDING,
        ).exists()
        if already_pending:
            raise ValueError(
                "یک درخواست لغو در حال بررسی برای این فاکتور وجود دارد."
            )

        return InvoiceCancellationRequest.objects.create(
            company=invoice.company,
            invoice=invoice,
            requested_by=requested_by,
            reason=reason or "",
            status=InvoiceCancellationRequest.Status.PENDING,
        )

    @staticmethod
    @transaction.atomic
    def approve(
        *,
        cancel_request: InvoiceCancellationRequest,
        reviewed_by,
        review_note: str = "",
    ) -> InvoiceCancellationRequest:
        """
        Admin/operator approves the cancellation request.

        Acquires locks on both the request row and the invoice row before acting.
        Re-checks that the request is still PENDING and the invoice is not PAID
        (the invoice could have been paid concurrently while the request was open).
        """
        # Lock request then invoice — consistent ordering prevents deadlock.
        cancel_request = InvoiceCancellationRequest.objects.select_for_update().get(
            pk=cancel_request.pk
        )
        invoice = Invoice.objects.select_for_update().get(pk=cancel_request.invoice_id)

        if cancel_request.status != InvoiceCancellationRequest.Status.PENDING:
            raise ValueError("فقط درخواست‌های در انتظار بررسی قابل تأیید هستند.")

        if invoice.status == Invoice.Status.PAID:
            raise ValueError(
                "فاکتور در این فاصله پرداخت شده است و قابل لغو نیست. "
                "لطفاً این درخواست را رد کنید."
            )

        # Cancellation must go through the canonical service, not a direct status write.
        from .services import InvoiceCancelService
        InvoiceCancelService.cancel(invoice=invoice)

        cancel_request.status = InvoiceCancellationRequest.Status.APPROVED
        cancel_request.reviewed_by = reviewed_by
        cancel_request.reviewed_at = timezone.now()
        cancel_request.review_note = review_note or ""
        cancel_request.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"]
        )
        return cancel_request

    @staticmethod
    @transaction.atomic
    def reject(
        *,
        cancel_request: InvoiceCancellationRequest,
        reviewed_by,
        review_note: str = "",
    ) -> InvoiceCancellationRequest:
        """
        Admin/operator rejects the cancellation request.

        The invoice status is preserved — no change to the invoice.
        """
        cancel_request = InvoiceCancellationRequest.objects.select_for_update().get(
            pk=cancel_request.pk
        )

        if cancel_request.status != InvoiceCancellationRequest.Status.PENDING:
            raise ValueError("فقط درخواست‌های در انتظار بررسی قابل رد شدن هستند.")

        cancel_request.status = InvoiceCancellationRequest.Status.REJECTED
        cancel_request.reviewed_by = reviewed_by
        cancel_request.reviewed_at = timezone.now()
        cancel_request.review_note = review_note or ""
        cancel_request.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"]
        )
        return cancel_request
