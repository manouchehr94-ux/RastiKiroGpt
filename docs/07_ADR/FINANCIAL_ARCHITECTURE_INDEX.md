# Financial Architecture Index

**Version:** RDOS v1.0 — Frozen  
**Date:** 2026-06-28  
**Status:** Authoritative reference for all financial implementation tasks

---

## Purpose

This index is the entry point for every task that touches financial data:
ledger entries, platform fees, payment splits, technician compensation, or
financial recovery. Read it before reading any service code.

---

## ADR Map

| ADR | Title | Owns |
|---|---|---|
| [ADR-004](ADR-004-Ledger-Discipline.md) | Ledger Discipline | Immutability rules, idempotency keys, balance convention |
| [ADR-005](ADR-005-Technician-Service-Pricing.md) | Technician Service Pricing | Wage rate model, `TechnicianServiceRate`, Phase 1 constraints |
| [ADR-006](ADR-006-Technician-Ledger-Statement-Architecture.md) | Technician Ledger Statement Architecture | Ledger-vs-statement separation, source mapping, discount rule, authoritative source per event |
| [ADR-007](ADR-007-Financial-Event-Timeline.md) | Financial Event Timeline | Complete event sequence, ordering dependencies, authoritative source table |
| [ADR-008](ADR-008-Financial-Recovery-Policy.md) | Financial Recovery Policy | Backfill task lifecycle, retry policy, manual intervention, deferred technical debt |

---

## Quick Reference: Which ADR Answers My Question?

| Question | ADR |
|---|---|
| Can I mutate a ledger entry after it is created? | ADR-004 |
| Which fields on `TechnicianLedgerEntry` are immutable? | ADR-004 |
| What is the idempotency key format for a ledger entry? | ADR-004, ADR-006 §8 |
| How is technician wage calculated per order item? | ADR-005 |
| What happens when a technician's rate changes after an order is complete? | ADR-005 |
| What is the difference between the ledger and the statement? | ADR-006 §1–2 |
| What is the authoritative source for a direct gateway settlement DEBIT? | ADR-006 §7, ADR-007 Event 8 |
| Can a customer discount reduce the technician's wage? | ADR-006 §5 |
| In what order do financial events run after a payment is verified? | ADR-007 |
| What happens when `TechnicianLedgerService.create_invoice_entries()` fails? | ADR-008 |
| How does `FinancialBackfillTask` ensure exactly-once retry? | ADR-008 |
| What is the deduplication key for a backfill task? | ADR-008 |
| Why is the Financial Account Lock deferred? | ADR-008 (Technical Debt §1) |
| When is manual intervention required? | ADR-008 |

---

## Financial Model Summary

```
TechnicianLedgerEntry   — immutable ledger; one row per business event
CompanyPlatformFeeEntry — immutable platform fee ledger
PaymentSplitSnapshot    — immutable split decision audit record
FinancialBackfillTask   — retry queue for failed financial writes
TechnicianServiceRate   — wage rate per technician per item definition
```

---

## Service Summary

```
TechnicianLedgerService         — all ledger writes (create_credit, create_debit)
PlatformFeeService              — platform fee writes
PaymentSplitDecisionService     — split snapshot creation
TechnicianDirectSettlementService — direct gateway settlement DEBIT
TechnicianWagePostingService    — order completion wage posting
TechnicianStatementService      — read-only statement projection
FinancialBackfillService        — retry queue processing
InvoiceMarkPaidService          — orchestrates events 4–6
PaymentVerifyService            — orchestrates events 7–8
```

---

## Invariants (Non-Negotiable)

These rules are non-negotiable in all future financial tasks:

1. **Ledger entries are immutable.** `amount_rial` and `balance_after` cannot be changed after creation. Delete is permanently disabled. Corrections use an ADJUSTMENT entry.

2. **Every ledger entry carries a deterministic idempotency key.** The key must be computable from business data alone, without reading other ledger entries.

3. **Amounts come from authoritative snapshots.** A ledger amount is never derived from another ledger entry. It is always read from the business event's snapshot (e.g., `invoice.settled_technician_wage`, `PaymentSplitSnapshot.technician_direct_amount`).

4. **The statement is read-only.** `TechnicianStatementService` never writes to the ledger. No financial write ever originates from statement or export logic.

5. **Backfill tasks deduplicate per `(company, task_type, invoice)`.** At most one PENDING or PROCESSING task exists for each combination.

6. **All financial writes are non-blocking on payment success.** If a ledger or fee write fails, the payment is still marked PAID and the failure is queued for retry.

---

## Freeze Declaration

The financial architecture described in ADR-004 through ADR-008 is **frozen** as of
RDOS v1.0.

New financial features must:
1. Trace their ledger entries to an authoritative source (ADR-006 §7).
2. Assign a new `FinancialBackfillTask.TaskType` value and register a handler in `_dispatch()`.
3. Add an idempotency key with format documented in the relevant ADR or task spec.
4. Pass regression against all existing financial tests before merge.

Changes to the core rules in ADR-004, ADR-006 §7, or this invariant list require a
new ADR and explicit sign-off.

---

## References

- `apps/payouts/models.py`
- `apps/payouts/services.py`
- `apps/payouts/services_backfill.py`
- `apps/payouts/services_direct_settlement.py`
- `apps/payouts/services_order_wages.py`
- `apps/payouts/services_platform_fee.py`
- `apps/payouts/services_split.py`
- `apps/payouts/services_statement.py`
- `apps/invoices/services.py`
- `apps/payments/services.py`
- `docs/03_Business/ACCOUNTING_RULES.md`
