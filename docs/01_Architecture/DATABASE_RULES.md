# Database Rules

## General

- Prefer additive migrations.
- Never delete production financial data.
- Use `PROTECT` or soft-delete for financial ownership.
- Add indexes for frequent dashboard/report filters.
- Avoid nullable chaos unless needed for migration safety.

## Money

- Use `DecimalField`.
- Iranian Rial: `decimal_places=0`.
- No float conversion.

## Financial records

Ledger entries, payments, invoices, settlement snapshots must be append-only or immutable after finalization.
