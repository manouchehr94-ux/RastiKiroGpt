"""
Payouts — Escrow Record Service (Sprint 2 — Financial Foundation Services).

Provides safe, idempotent state-machine operations for EscrowRecord per the
approved specification:
  docs/13_Financial_Core/target_architecture/25_FINANCIAL_STATE_MACHINE_SPECIFICATION.md §3
  docs/13_Financial_Core/target_architecture/24_MONEY_LIFECYCLE_SPECIFICATION.md

This service is NOT wired into any payment, invoice, or payout flow yet.
No signal, view, API, or background job calls it. It does not emit any
event or notification. It exists so that a future EscrowService
integration point (Sprint 3+) has a stable, tested API to build on.

Do NOT call this service from apps/payments/services.py,
apps/invoices/services.py, or apps/payouts/services.py in this sprint.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone


class EscrowTransitionError(ValueError):
    """Raised when an EscrowRecord state transition is not allowed."""


class EscrowRecordService:
    """
    Lifecycle operations for EscrowRecord.

    State machine (Document 25 §3):
        HELD -> RESERVED -> DISTRIBUTED -> PENDING_SETTLEMENT -> SETTLED -> CLOSED
        HELD / RESERVED / DISTRIBUTED -> CLOSED   (refund before settlement)

    No method here emits any event, signal, or notification. No method here
    is called by any existing production code path in this sprint.
    """

    @staticmethod
    def is_eligible_for_escrow(payment) -> bool:
        """
        Return True only if this payment should ever have an EscrowRecord.

        Per 24_MONEY_LIFECYCLE_SPECIFICATION.md §3 (cash) and §4
        (card-to-card): only online payments through a platform-owned
        gateway create escrow. Cash, manual, and company-owned-gateway
        payments are never eligible.
        """
        from apps.payments.models import PaymentGateway

        gateway = getattr(payment, "gateway", None)
        if gateway is None:
            return False
        return gateway.owner_type == PaymentGateway.OwnerType.PLATFORM

    @staticmethod
    @transaction.atomic
    def create_for_payment(payment, invoice=None):
        """
        Create (or return the existing) EscrowRecord for a Payment.

        Idempotent: at most one EscrowRecord may exist per Payment
        (enforced by the model's OneToOneField on `payment`). Calling this
        twice for the same payment returns the same row, never a duplicate.

        Returns None if the payment is not eligible for escrow (cash,
        card-to-card, manual, or company-owned-gateway payments) per
        is_eligible_for_escrow().
        """
        from .models import EscrowRecord

        existing = EscrowRecord.objects.filter(payment=payment).first()
        if existing is not None:
            return existing

        if not EscrowRecordService.is_eligible_for_escrow(payment):
            return None

        resolved_invoice = invoice if invoice is not None else getattr(payment, "invoice", None)
        amount_rial = int(payment.amount)

        return EscrowRecord.objects.create(
            company=payment.company,
            payment=payment,
            invoice=resolved_invoice,
            amount_rial=amount_rial,
        )

    @staticmethod
    @transaction.atomic
    def reserve_for_invoice(escrow_record, invoice):
        """
        HELD -> RESERVED.

        Links the escrow to a specific invoice and marks it reserved.
        Raises EscrowTransitionError if escrow_record.status is not HELD.
        """
        from .models import EscrowRecord

        locked = EscrowRecord.objects.select_for_update().get(pk=escrow_record.pk)

        if locked.status != EscrowRecord.Status.HELD:
            raise EscrowTransitionError(
                f"EscrowRecord #{locked.pk}: cannot reserve from status "
                f"'{locked.status}'. Must be HELD."
            )

        locked.invoice = invoice
        locked.status = EscrowRecord.Status.RESERVED
        locked.save(update_fields=["invoice", "status", "updated_at"])
        return locked

    @staticmethod
    @transaction.atomic
    def mark_distributed(
        escrow_record,
        *,
        platform_commission_rial: int,
        organization_share_rial: int,
        provider_share_rial: int,
    ):
        """
        RESERVED -> DISTRIBUTED.

        Enforces the amount-consistency invariant documented in
        04_DOMAIN_MODEL.md §9:
            platform_commission_rial + organization_share_rial
            + provider_share_rial == amount_rial

        Raises ValueError on a mismatch (no state change occurs) and
        EscrowTransitionError if escrow_record.status is not RESERVED.
        """
        from .models import EscrowRecord

        locked = EscrowRecord.objects.select_for_update().get(pk=escrow_record.pk)

        if locked.status != EscrowRecord.Status.RESERVED:
            raise EscrowTransitionError(
                f"EscrowRecord #{locked.pk}: cannot distribute from status "
                f"'{locked.status}'. Must be RESERVED."
            )

        platform_commission_rial = int(platform_commission_rial)
        organization_share_rial = int(organization_share_rial)
        provider_share_rial = int(provider_share_rial)
        total = platform_commission_rial + organization_share_rial + provider_share_rial

        if total != locked.amount_rial:
            raise ValueError(
                f"EscrowRecord #{locked.pk}: platform_commission_rial + "
                f"organization_share_rial + provider_share_rial ({total}) must "
                f"equal amount_rial ({locked.amount_rial})."
            )

        locked.platform_commission_rial = platform_commission_rial
        locked.organization_share_rial = organization_share_rial
        locked.provider_share_rial = provider_share_rial
        locked.status = EscrowRecord.Status.DISTRIBUTED
        locked.distributed_at = timezone.now()
        locked.save(update_fields=[
            "platform_commission_rial",
            "organization_share_rial",
            "provider_share_rial",
            "status",
            "distributed_at",
            "updated_at",
        ])
        return locked

    @staticmethod
    @transaction.atomic
    def mark_pending_settlement(escrow_record, settlement_batch):
        """
        DISTRIBUTED -> PENDING_SETTLEMENT.

        Links the escrow to a SettlementBatch. Raises EscrowTransitionError
        if escrow_record.status is not DISTRIBUTED.
        """
        from .models import EscrowRecord

        locked = EscrowRecord.objects.select_for_update().get(pk=escrow_record.pk)

        if locked.status != EscrowRecord.Status.DISTRIBUTED:
            raise EscrowTransitionError(
                f"EscrowRecord #{locked.pk}: cannot mark pending settlement "
                f"from status '{locked.status}'. Must be DISTRIBUTED."
            )

        locked.settlement_batch = settlement_batch
        locked.status = EscrowRecord.Status.PENDING_SETTLEMENT
        locked.save(update_fields=["settlement_batch", "status", "updated_at"])
        return locked

    @staticmethod
    @transaction.atomic
    def mark_settled(escrow_record, settlement_batch=None):
        """
        PENDING_SETTLEMENT -> SETTLED.

        settlement_batch is optional; if provided it overwrites the linked
        batch (normally already set by mark_pending_settlement). Raises
        EscrowTransitionError if escrow_record.status is not
        PENDING_SETTLEMENT.
        """
        from .models import EscrowRecord

        locked = EscrowRecord.objects.select_for_update().get(pk=escrow_record.pk)

        if locked.status != EscrowRecord.Status.PENDING_SETTLEMENT:
            raise EscrowTransitionError(
                f"EscrowRecord #{locked.pk}: cannot mark settled from status "
                f"'{locked.status}'. Must be PENDING_SETTLEMENT."
            )

        if settlement_batch is not None:
            locked.settlement_batch = settlement_batch
        locked.status = EscrowRecord.Status.SETTLED
        locked.settled_at = timezone.now()
        locked.save(update_fields=[
            "settlement_batch", "status", "settled_at", "updated_at",
        ])
        return locked

    @staticmethod
    @transaction.atomic
    def close(escrow_record, reason=None):
        """
        -> CLOSED. Terminal.

        Allowed from HELD, RESERVED, DISTRIBUTED (refund before settlement,
        per 24_MONEY_LIFECYCLE_SPECIFICATION.md §8) or from SETTLED (normal
        closure). Never allowed from PENDING_SETTLEMENT (must resolve to
        SETTLED first) or from an already-CLOSED record.

        `reason` is accepted for forward compatibility with a future audit
        trail, but is NOT persisted in Sprint 2: EscrowRecord has no
        `closed_reason` field (adding one would be a schema change, out of
        scope for this sprint).
        """
        from .models import EscrowRecord

        locked = EscrowRecord.objects.select_for_update().get(pk=escrow_record.pk)

        allowed_from = {
            EscrowRecord.Status.HELD,
            EscrowRecord.Status.RESERVED,
            EscrowRecord.Status.DISTRIBUTED,
            EscrowRecord.Status.SETTLED,
        }
        if locked.status not in allowed_from:
            raise EscrowTransitionError(
                f"EscrowRecord #{locked.pk}: cannot close from status "
                f"'{locked.status}'."
            )

        locked.status = EscrowRecord.Status.CLOSED
        locked.closed_at = timezone.now()
        locked.save(update_fields=["status", "closed_at", "updated_at"])
        return locked
