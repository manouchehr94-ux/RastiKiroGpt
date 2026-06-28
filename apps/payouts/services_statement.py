"""
Payouts — Technician Statement Service.

Read-only projection of TechnicianLedgerEntry rows into a bank-statement-like
format for technicians and admins.

Contract (ADR-006 §2, §9):
  - No financial entries are created or modified here.
  - No amounts are recomputed; balance_after is read directly from each entry.
  - Internal source codes are translated to plain Persian descriptions.
  - Summary is computed exclusively from the filtered rows, not from raw ledger.
  - Output is deterministic: ordered by created_at ASC, then id ASC.
"""
from __future__ import annotations

import datetime
from typing import Optional

# Generic Persian labels for each source when the entry has no description.
# When an entry already carries a human-readable description (e.g., set by
# the posting service at write time), that description takes precedence.
_SOURCE_LABELS: dict[str, str] = {
    "technician_service_wage": "کارکرد سفارش",
    "online_gateway": "سهم تکنسین از فاکتور",
    "cash_from_customer": "دریافت نقدی از مشتری",
    "manual_payment": "پرداخت دستی فاکتور",
    "direct_gateway_settlement": "تسویه مستقیم شاپرک",
    "manual_settlement": "تسویه دستی توسط شرکت",
    "adjustment": "اصلاحیه",
    "refund": "برگشت وجه",
}


class TechnicianStatementService:
    """
    Converts immutable TechnicianLedgerEntry rows into a structured statement.

    Deterministic, stateless, and purely transformational (ADR-006 §9).
    """

    @staticmethod
    def build(
        technician,
        from_date: Optional[datetime.date] = None,
        to_date: Optional[datetime.date] = None,
    ) -> dict:
        """
        Build a full financial statement for a technician.

        Args:
            technician: Technician instance. Must have a .company and .user FK accessible.
            from_date: Inclusive start date filter (datetime.date). No filter if None.
            to_date: Inclusive end date filter (datetime.date). No filter if None.

        Returns:
            {
                "technician_id":   int,
                "technician_name": str,
                "from_date":       date | None,
                "to_date":         date | None,
                "rows": [
                    {
                        "date":         datetime,
                        "description":  str,
                        "credit":       int,   # amount_rial when CREDIT, else 0
                        "debit":        int,   # amount_rial when DEBIT, else 0
                        "balance_after": int,  # stored on ledger entry; not recomputed
                        "source":       str,
                        "order_id":     int | None,
                        "invoice_id":   int | None,
                        "payment_id":   int | None,
                    },
                    ...
                ],
                "summary": {
                    "total_credit":  int,  # sum of rows[*]["credit"]
                    "total_debit":   int,  # sum of rows[*]["debit"]
                    "final_balance": int,  # rows[-1]["balance_after"] or 0
                },
            }
        """
        from apps.payouts.models import TechnicianLedgerEntry

        qs = (
            TechnicianLedgerEntry.objects
            .filter(company=technician.company, technician=technician)
            .order_by("created_at", "id")
        )

        if from_date is not None:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date is not None:
            qs = qs.filter(created_at__date__lte=to_date)

        rows = []
        for entry in qs:
            is_credit = entry.entry_type == TechnicianLedgerEntry.EntryType.CREDIT
            rows.append({
                "date": entry.created_at,
                "description": TechnicianStatementService._describe(entry),
                "credit": entry.amount_rial if is_credit else 0,
                "debit": 0 if is_credit else entry.amount_rial,
                "balance_after": entry.balance_after,
                "source": entry.source,
                "order_id": entry.order_id,
                "invoice_id": entry.invoice_id,
                "payment_id": entry.payment_id,
            })

        # Summary is derived exclusively from the filtered row list.
        total_credit = sum(r["credit"] for r in rows)
        total_debit = sum(r["debit"] for r in rows)
        final_balance = rows[-1]["balance_after"] if rows else 0

        return {
            "technician_id": technician.pk,
            "technician_name": TechnicianStatementService._tech_name(technician),
            "from_date": from_date,
            "to_date": to_date,
            "rows": rows,
            "summary": {
                "total_credit": total_credit,
                "total_debit": total_debit,
                "final_balance": final_balance,
            },
        }

    @staticmethod
    def _describe(entry) -> str:
        """Return a human-readable description for one ledger entry."""
        if entry.description:
            return entry.description
        return _SOURCE_LABELS.get(entry.source, entry.source)

    @staticmethod
    def _tech_name(technician) -> str:
        """Resolve a display name for the technician."""
        user = getattr(technician, "user", None)
        if user is None:
            return str(technician.pk)
        full = user.get_full_name()
        return full if full else getattr(user, "username", str(technician.pk))
