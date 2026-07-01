---
Title: Payout and Ledger Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/payouts/models.py, apps/payouts/services.py
Source of Truth: Code + ADR
Depends On: []
Related Documents: ../07_ADR/ADR-004-Ledger-Discipline.md, ../07_ADR/ADR-005-Technician-Service-Pricing.md, ../07_ADR/ADR-006-Technician-Ledger-Statement-Architecture.md
Reusable Across Projects: No
---

# Payout and Ledger Business Rules

---

## Technician Ledger

The technician ledger (`TechnicianLedgerEntry`) is the immutable financial record of all money owed to or paid to a technician.

### Immutability Rule

**Ledger entries are never edited.**

To correct an error:
1. Create a new reversing entry (negative amount)
2. Create a new correct entry
3. Both entries remain in the ledger permanently

This ensures the full financial history is always auditable.

### Ledger Entry Types

Needs Verification — inspect `apps/payouts/models.py` for current entry type choices.

Common types expected:
- Wage credit (when invoice is paid)
- Settlement debit (when technician is paid out)
- Reversal credit/debit

---

## Technician Statement

The technician statement is a calculated view (not a stored document) of:
- All ledger entries for a period
- Running balance
- Settlement history

Accessed at: `/<code>/admin/technicians/<id>/statement/`

PDF export: `/<code>/admin/technicians/<id>/statement/pdf/` — Needs Verification (button existence on statement page)

---

## Settlement

Settlement = paying the technician what is owed.

Settlement rules (from ADR-006):
1. Calculate owed amount from ledger
2. Admin records settlement at `/<code>/admin/technicians/<id>/statement/`
3. Settlement creates a debit ledger entry
4. Uses `select_for_update()` to prevent race conditions

---

## Platform Commission Ledger

`CompanyPlatformFeeEntry` — records platform commission per verified payment.

Same immutability rules apply as technician ledger.

---

## Financial Policies

`CompanyFinancialPolicy` controls:
- Technician wage strategy (fixed vs. percentage)
- Platform fee percentage
- Discount absorption policy (who absorbs discounts — company or technician)

`CompanyPaymentSettings` controls:
- Payment mode (disabled / company_gateway / platform_gateway)
- Gateway activation status

These are two separate models. Do not confuse them.

---

## Financial Verification (Platform Level)

Platform Owner can verify technician financial history across all companies at:
`/owner-platform/technician-financial-verifications/`

Note: This page is NOT linked in the platform owner sidebar (orphan page). Must navigate to directly.
