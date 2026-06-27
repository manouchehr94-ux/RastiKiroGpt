"""
Payouts — Direct Gateway Settlement Service.

When PaymentSplitSnapshot.should_split_with_technician is True after a successful
online payment, Shaparak has already wired the technician's share directly to their
bank account.  This service records that event as an immutable DEBIT entry on the
technician's ledger.

Amount source: PaymentSplitSnapshot.technician_direct_amount — the authoritative
frozen business-event snapshot.  Must NOT be derived from any prior
TechnicianLedgerEntry (ADR-006 §7).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class TechnicianDirectSettlementService:
    """
    Posts a single DIRECT_GATEWAY_SETTLEMENT DEBIT when Shaparak settles directly
    to the technician's bank account.
    """

    @staticmethod
    def post_for_payment(payment) -> list:
        """
        Evaluate PaymentSplitSnapshot and post a DEBIT if all applicability
        conditions are met (ADR-006 §8).

        Applicability conditions (all must be true):
          1. PaymentSplitSnapshot exists for this payment.
          2. snapshot.should_split_with_technician is True.
          3. snapshot.technician_direct_amount > 0.
          4. payment.gateway.owner_type == PLATFORM.
          5. payment.invoice is not None.
          6. payment.invoice.order is not None.
          7. order.technician is not None.
          8. payment.company == order.company.
          9. technician.company == payment.company.

        Returns:
            []      — conditions not met; no entry created.
            [entry] — one DEBIT TechnicianLedgerEntry created (or idempotency hit → []).
        """
        from apps.payouts.models import PaymentSplitSnapshot, TechnicianLedgerEntry
        from apps.payments.models import PaymentGateway
        from apps.payouts.services import TechnicianLedgerService

        # 1. Snapshot must exist
        snapshot = PaymentSplitSnapshot.objects.filter(payment=payment).first()
        if snapshot is None:
            return []

        # 2. Split must have been executed
        if not snapshot.should_split_with_technician:
            return []

        # 3. Amount must be positive
        direct_amount = int(snapshot.technician_direct_amount)
        if direct_amount <= 0:
            return []

        # 4. Only platform-owned gateways physically execute PSP-level splits
        gateway = getattr(payment, "gateway", None)
        if gateway is None or gateway.owner_type != PaymentGateway.OwnerType.PLATFORM:
            return []

        # 5. Payment must have an invoice
        invoice = getattr(payment, "invoice", None)
        if invoice is None:
            return []

        # 6. Invoice must have an order
        order = getattr(invoice, "order", None)
        if order is None:
            return []

        # 7. Order must have a technician
        technician = getattr(order, "technician", None)
        if technician is None:
            return []

        # 8. Payment and order must belong to the same company
        if payment.company_id != order.company_id:
            logger.warning(
                "TechnicianDirectSettlementService: company mismatch — "
                "payment.company_id=%s order.company_id=%s; skipping DEBIT",
                payment.company_id, order.company_id,
            )
            return []

        # 9. Technician must belong to the payment's company
        if technician.company_id != payment.company_id:
            logger.warning(
                "TechnicianDirectSettlementService: technician company mismatch — "
                "technician.company_id=%s payment.company_id=%s; skipping DEBIT",
                technician.company_id, payment.company_id,
            )
            return []

        idempotency_key = f"direct_gateway_settlement:payment:{payment.id}"

        metadata = {
            "metadata_version": 1,
            "posting_type": "direct_gateway_settlement",
            "payment_id": payment.id,
            "invoice_id": invoice.id,
            "order_id": order.id,
            "technician_id": technician.id,
            "technician_direct_amount": direct_amount,
            "should_split_with_technician": snapshot.should_split_with_technician,
            "payout_strategy_snapshot": snapshot.payout_strategy_snapshot,
            "technician_verified_snapshot": snapshot.technician_verified_snapshot,
            "technician_sub_merchant_id_snapshot": snapshot.technician_sub_merchant_id_snapshot,
        }

        entry = TechnicianLedgerService.create_debit(
            company=payment.company,
            technician=technician,
            source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
            amount_rial=direct_amount,
            idempotency_key=idempotency_key,
            order=order,
            invoice=invoice,
            payment=payment,
            description=f"تسویه مستقیم شاپرک سفارش #{order.id}",
            metadata=metadata,
        )

        return [entry] if entry is not None else []
