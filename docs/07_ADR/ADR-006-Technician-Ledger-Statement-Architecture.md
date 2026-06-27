# ADR-006 — Technician Ledger and Statement Architecture

**Status:** Accepted  
**Date:** 2026-06-27  
**Deciders:** Platform Team  
**Supersedes:** ADR-004 (extends, does not replace)  
**Superseded by:** —

---

## Context

As technician compensation grows more complex — order-item wages (TASK-010B), direct
Shaparak settlement (TASK-010C), cash collection, manual company payouts, and future
bonuses/penalties — two distinct needs have emerged:

1. **Internal bookkeeping**: an auditable, tamper-proof record of every financial event,
   suitable for reconciliation and compliance.
2. **Technician-facing output**: a readable bank-statement-like view the technician uses
   to verify their earnings and know their current balance.

These two needs must be served by different layers. Conflating the raw ledger with the
technician-facing view causes coupling that blocks both correct accounting and clean UI.

---

## Decision

### 1. TechnicianLedgerEntry is the internal immutable ledger

`TechnicianLedgerEntry` (in `apps/payouts/models.py`) is the system of record for all
technician financial events. Its rules (from ADR-004) are non-negotiable:

- Entries are **immutable** after creation: `amount_rial` and `balance_after` cannot be
  changed. `delete()` is permanently disabled. Errors are corrected with a new
  `ADJUSTMENT` CREDIT or DEBIT entry — never by mutating existing rows.
- Every entry carries a deterministic **idempotency key** so replayed callbacks or
  management command retries never produce duplicate rows.
- **balance_after** stores the technician's running balance immediately after each entry.
  Positive = company still owes the technician. Negative = technician owes the company.
- Both sides of every cash movement are recorded atomically within `@transaction.atomic`.

**This table is not exposed raw to technicians.** It contains internal codes, FK IDs, and
field names that are not meaningful to a technician.

---

### 2. Technician-facing statement is a view, not the ledger table

The statement shown to a technician is a **computed view** generated from ledger rows.
It will be produced by a future `TechnicianStatementService` that selects, sorts, and
translates ledger rows into human-readable line items.

The service is not implemented yet (out of scope until TASK-010D or later). When built it
will live in `apps/payouts/services_statement.py`.

The statement is **read-only**. No financial write ever originates from statement logic.

---

### 3. Statement format — what the technician sees

The technician statement resembles a bank statement: description, debit column, credit
column, and running balance. Column headers in Persian:

```
شرح                              | بدهکار | بستانکار | مانده
-----------------------------------------------------------------
کارکرد سفارش ۱۲۳                 |        | ۲٬۰۰۰   | ۲٬۰۰۰
فاکتور شماره ۲۴، سهم تکنسین      |        | ۳٬۵۰۰   | ۵٬۵۰۰
مشتری نقدی پرداخت کرد            | ۵٬۰۰۰  |          |   ۵۰۰
شرکت کارت‌به‌کارت کرد            |   ۵۰۰  |          |     ۰
```

**Mapping of ledger Source → statement description:**

| Source                        | Example description (Persian)                             |
|-------------------------------|-----------------------------------------------------------|
| `technician_service_wage`     | کارکرد سفارش #N                                           |
| `online_gateway`              | فاکتور شماره N، سهم تکنسین (پرداخت آنلاین)               |
| `cash_from_customer`          | مشتری نقدی پرداخت کرد (سفارش #N)                         |
| `manual_payment`              | پرداخت دستی فاکتور N                                       |
| `direct_gateway_settlement`   | تسویه مستقیم شاپرک سفارش #N                               |
| `manual_settlement`           | تسویه دستی توسط شرکت                                      |
| `adjustment`                  | تعدیل حساب                                                |
| `refund`                      | برگشت وجه                                                  |

Statement rows are ordered chronologically (oldest first). `balance_after` from the ledger
row is displayed as `مانده` without recomputing.

---

### 4. Technician compensation is independent of customer payment behaviour

Technician earnings are calculated from two independent sources:

- **Order-item wages** (`technician_service_wage`): determined by item quantities and the
  technician's `TechnicianServiceRate` at the moment the order is marked DONE. These are
  unaffected by how the customer pays.
- **Invoice share** (`online_gateway`, `cash_from_customer`, `manual_payment`): determined
  by `invoice.settled_technician_wage`, which is frozen at invoice settlement time via
  `InvoiceSettlementService.settle()`.

Neither source is reduced by:

- Customer discounts (e.g., customer-club discount codes)
- Payment method chosen by the customer
- Customer late payment or partial payment

---

### 5. Customer club discounts are absorbed by the company

When a customer applies a discount code, the discount reduces the invoice amount received
by the company. The technician's compensation is calculated **before** the discount is
applied to determine what the company owes the technician.

> **Rule**: Customer discounts reduce company revenue, not technician earnings.
> This rule holds in Phase 1. A future explicit company policy (not yet designed) would be
> required to override it.

This means `invoice.settled_technician_wage` must be computed on the **pre-discount
service value** or the technician's contractual percentage of the gross invoice — not the
discounted amount paid by the customer. Implementation of this rule is enforced in
`InvoiceSettlementService.settle()`.

---

### 6. Source, type, and metadata support future reporting

Every `TechnicianLedgerEntry` carries:

- `entry_type`: `credit` or `debit`
- `source`: one of the `Source` choices (see Section 3 table above)
- `metadata`: JSONField with a versioned payload (`metadata_version: 1`)
- FKs to `order`, `invoice`, `payment` where applicable

This structure makes future reports possible by filtering on `source` and joining on FK
fields without parsing description strings. The `metadata` field captures the snapshot
values used at posting time (e.g., quantities, rates, amounts) so reports remain
accurate even when the underlying master data changes.

**Mandatory metadata fields** (as of metadata_version 1):

```json
{
  "metadata_version": 1,
  "posting_type": "<matches source value>",
  "technician_id": 42,
  "<other context fields as required by the source>"
}
```

---

### 7. TASK-010C direct Shaparak settlement — DEBIT rule

When `PaymentSplitSnapshot.should_split_with_technician == True` after a successful online
payment verification, the PSP (Shaparak) has wired money **directly** to the technician's
bank account. The company has already posted a CREDIT for the technician's invoice share
(source: `online_gateway`). To record that the obligation has been discharged by the PSP:

- A **DEBIT** entry must be created with `source = direct_gateway_settlement`.
- The DEBIT amount must equal `PaymentSplitSnapshot.technician_direct_amount` — the exact
  amount the PSP settled, as recorded in the snapshot. This is NOT recomputed from the
  invoice or the order; it is read from the frozen snapshot.
- This DEBIT is posted only when `payment.gateway.owner_type == PLATFORM`. Company-owned
  gateways cannot physically execute PSP-level splits.
- Idempotency key: `direct_gateway_settlement:payment:{payment.id}`.
- The DEBIT is non-fatal: if it fails, the payment is still marked PAID. A log at
  CRITICAL level is emitted and manual recovery is required.

The DEBIT is conceptually the bookkeeping mirror of the CREDIT: the company acknowledged
it owed the technician (CREDIT), then recorded that Shaparak paid it on the company's
behalf (DEBIT), leaving the technician's net claim against the company reduced by the
settled amount.

---

### 8. Internal accounting stays strict; technician view stays simple

The internal `TechnicianLedgerEntry` table enforces financial discipline:

- Every rial is accounted for with a source.
- No entry is ever deleted or mutated.
- Balance is always recomputable from the ordered sequence of entries.
- All writes are under `select_for_update` to prevent concurrent balance corruption.

The technician-facing statement deliberately hides this complexity:

- Internal source codes are translated to plain Persian descriptions.
- FK IDs are replaced with human-readable identifiers (order title, invoice number).
- Balance is shown as a single number — no explanation of how it was computed.
- Filtering and grouping (by date range, by source) will be provided in future UI.

This separation is intentional: it allows the accounting model to evolve (new sources, new
entry types, reconciliation adjustments) without requiring changes to the statement UI.

---

### 9. Future additions (approved, not yet scheduled)

The following capabilities are planned but not implemented:

| Capability | Description | Depends on |
|---|---|---|
| `TechnicianStatementService` | Translates ledger rows to statement line items | TASK-010D or later |
| Printable statement | PDF or printable HTML view of the statement | `TechnicianStatementService` |
| Grouped reports by source | "Total order-item wages this month" etc. | `TechnicianStatementService` |
| Technician portal page | Technician can view their own balance and statement | Statement service + auth |
| Bonus/penalty entries | New sources: `bonus`, `penalty` | New `Source` choices + policy |
| Technician payment to company | Technician repays a debt (e.g., advance) | New `Source` choice |
| Company advance to technician | Direct rial transfer as an advance on wages | New `Source` choice |

When `TechnicianStatementService` is built, it must read only from `TechnicianLedgerEntry`
and must not write any financial entries. It must be a pure read-only projection.

---

## Consequences

### Positive

- **Ledger stays tamper-proof.** No statement logic can accidentally write to the ledger.
- **Statement can change independently.** The description format, grouping, and filtering
  of the statement can be updated without touching the financial model.
- **Discount logic is unambiguous.** Technician pay is never silently reduced by customer
  discounts without an explicit company policy.
- **Metadata enables analytics.** Future reporting can filter by source and join on FKs
  without parsing text fields.

### Negative / Trade-offs

- **Separation requires an extra service.** `TechnicianStatementService` must be built
  before technicians can view their statement. Until then, admins can query the ledger
  directly from the admin panel.
- **Two CREDITs per online payment with split.** For a SPLIT_WITH_TECHNICIAN online
  payment, the ledger has: CREDIT (`technician_service_wage`) + CREDIT (`online_gateway`)
  + DEBIT (`direct_gateway_settlement`). The statement must group or annotate these clearly
  or technicians will be confused by the extra rows.
- **`metadata_version` must be incremented on schema changes.** Any change to the metadata
  payload requires bumping `metadata_version` and updating all readers of the metadata.

---

## References

- `apps/payouts/models.py` — `TechnicianLedgerEntry`, `PaymentSplitSnapshot`
- `apps/payouts/services.py` — `TechnicianLedgerService`
- `apps/payouts/services_order_wages.py` — TASK-010B wage posting
- `apps/payouts/services_split.py` — `PaymentSplitDecisionService`
- `apps/invoices/services.py` — `InvoiceMarkPaidService`, `InvoiceSettlementService`
- `docs/07_ADR/ADR-004-Ledger-Discipline.md` — immutability and idempotency rules
- `docs/07_ADR/ADR-005-Technician-Service-Pricing.md` — wage rate model
- `docs/03_Business/ACCOUNTING_RULES.md` — ledger V1 rules
- TASK-010B — order-completion wage posting (committed `12e0ee8`)
- TASK-010C — direct Shaparak settlement DEBIT (planned)
- TASK-010C-0 — architecture audit (this ADR is its output)
