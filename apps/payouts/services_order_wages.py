"""
Payouts - Order Wage Posting Service.

Posts a single technician service wage CREDIT on order completion.
Called by OrderCompleteService.complete() after status transitions to DONE.
"""
from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class TechnicianWagePostingService:
    """
    Calculates and posts one TechnicianLedgerEntry CREDIT per completed order.

    Algorithm:
    - Skip silently if order has no assigned technician.
    - Collect OrderItemValues where kind=NUMBER and is_technician_wage_applicable=True.
    - For each with value_number > 0, look up the active TechnicianServiceRate.
    - Missing / inactive rate → log warning, record in missing_rate_items, skip.
    - total_wage = sum(quantity * fixed_wage_rial) across payable items.
    - If total_wage == 0 → return [] without writing any entry.
    - Otherwise create ONE CREDIT with idempotency_key=technician_service_wage:order:{id}.
    """

    @staticmethod
    def post_for_order(order) -> list:
        """
        Post technician service wage for a completed order.

        Returns:
            []      — no entry created (no technician, no eligible items, zero wage)
            [entry] — one CREDIT TechnicianLedgerEntry created (or idempotency hit)
        """
        from apps.payouts.models import TechnicianLedgerEntry, TechnicianServiceRate
        from apps.orders.models import OrderItemValue

        technician = getattr(order, "technician", None)
        if technician is None or not getattr(technician, "pk", None):
            return []

        company = order.company

        item_values = list(
            OrderItemValue.objects.filter(
                order=order,
                item__kind="number",
                item__is_technician_wage_applicable=True,
            ).select_related("item")
        )

        if not item_values:
            return []

        payable = []
        missing = []

        for value in item_values:
            qty = value.value_number
            if qty is None or qty <= Decimal("0"):
                continue

            item = value.item
            rate = TechnicianServiceRate.objects.filter(
                company=company,
                technician=technician,
                item_definition=item,
                is_active=True,
            ).first()

            if rate is None:
                logger.warning(
                    "TechnicianWagePostingService: no active rate for "
                    "order=%d technician=%d item_definition=%d (%s)",
                    order.id, technician.id, item.id, item.title,
                )
                missing.append({
                    "order_item_value_id": value.id,
                    "item_definition_id": item.id,
                    "item_title": item.title,
                    "quantity": str(qty),
                    "reason": "missing_active_technician_service_rate",
                })
                continue

            item_wage = int(qty * Decimal(rate.fixed_wage_rial))
            payable.append({
                "value": value,
                "item": item,
                "rate": rate,
                "item_wage": item_wage,
            })

        total_wage = sum(p["item_wage"] for p in payable)

        if total_wage <= 0:
            if missing:
                logger.warning(
                    "TechnicianWagePostingService: order=%d all wage-applicable items "
                    "have missing rates; no CREDIT posted. missing_item_ids=%r",
                    order.id, [m["item_definition_id"] for m in missing],
                )
            return []

        metadata = {
            "posting_type": "technician_service_wage",
            "order_id": order.id,
            "technician_id": technician.id,
            "completed_at": (
                order.completed_at.isoformat() if order.completed_at else None
            ),
            "items": [
                {
                    "order_item_value_id": p["value"].id,
                    "item_definition_id": p["item"].id,
                    "item_title": p["item"].title,
                    "quantity": str(p["value"].value_number),
                    "rate_id": p["rate"].id,
                    "fixed_wage_rial": p["rate"].fixed_wage_rial,
                    "computed_wage_rial": p["item_wage"],
                }
                for p in payable
            ],
            "missing_rate_items": missing,
            "total_wage_rial": total_wage,
        }

        idempotency_key = f"technician_service_wage:order:{order.id}"

        from apps.payouts.services import TechnicianLedgerService

        entry = TechnicianLedgerService.create_credit(
            company=company,
            technician=technician,
            source=TechnicianLedgerEntry.Source.TECHNICIAN_SERVICE_WAGE,
            amount_rial=total_wage,
            idempotency_key=idempotency_key,
            order=order,
            description=f"اجرت خدمت سفارش #{order.id}",
            metadata=metadata,
        )

        if entry is not None:
            return [entry]
        return []
