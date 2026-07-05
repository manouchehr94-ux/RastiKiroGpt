# 04 — مدل دامنه مالی (Financial Domain Model)

**Version:** v1.0 — Draft — Pending Clarification
**مبنا:** یافته‌های ممیزی `03_MODEL_ANALYSIS.md`

---

## 1. Invoice

### Purpose
سند مالی رسمی صادره برای مشتری. واحد اصلی تسویه در سراسر سیستم (R45).


### Ownership
Organization (Company) — فاکتور به نام شرکت صادر می‌شود (R03).

### Relationships
- `company` → `tenants.Company` (CompanyOwnedModel) — mandatory
- `order` → `orders.Order` (FK, nullable) — standalone drafts allowed
- `customer` → `accounts.Customer` (FK, nullable)
- `created_by` → AUTH_USER_MODEL (FK, nullable)
- `items` ← `InvoiceItem[]` (reverse FK, CASCADE)
- `payments` ← `Payment[]` (reverse FK, SET_NULL)
- `ledger_entries` ← `TechnicianLedgerEntry[]` (reverse FK)
- `platform_fee_entries` ← `CompanyPlatformFeeEntry[]` (reverse FK)
- `split_snapshots` ← `PaymentSplitSnapshot[]` (reverse FK)
- `backfill_tasks` ← `FinancialBackfillTask[]` (reverse FK)
- `cancellation_requests` ← `InvoiceCancellationRequest[]` (reverse FK)

### Lifecycle
```
DRAFT → ISSUED → PAID
DRAFT → CANCELLED
ISSUED → CANCELLED (via CancellationRequest approval)
```

### State Transitions
| From | To | Trigger | Service |
|---|---|---|---|
| — | DRAFT | Admin/technician creates | `InvoiceCreateService.create()` |
| DRAFT | ISSUED | Admin/technician issues | `InvoiceIssueService.issue()` |
| ISSUED | PAID | Customer pays | `InvoiceMarkPaidService.mark_paid()` |
| DRAFT/ISSUED | CANCELLED | Admin cancels / CancellationRequest approved | `InvoiceCancelService.cancel()` |

### Invariants
- `total_amount > 0` before ISSUED (enforced by `InvoiceIssueService`)
- One active (DRAFT/ISSUED) invoice per order (DB constraint `unique_active_invoice_per_order`)
- PAID invoices are immutable (recalculate_totals raises ValueError)
- `settled_*` fields are NULL until PAID, then permanently frozen
- `invoice_number` unique per company (DB constraint)

### Existing Implementation
`apps/invoices/models.py`, line 21 — `Invoice`. Fully implemented with 17 `settled_*` fields.

### Required Extension
None for the model itself. New RowType choices for `InvoiceItem` (R23).

### Open Issue Impact
- OI-06: Overpayment handling may require new field or relationship to `AdjustmentDocument`
- OI-07: Refund may link `AdjustmentDocument.original_invoice` back to this model

---

## 2. InvoiceItem

### Purpose
ردیف فاکتور. قیمت‌ها اینجا زندگی می‌کنند (نه روی Order).

### Ownership
Organization (via Invoice.company).

### Relationships
- `invoice` → `Invoice` (FK, CASCADE)
- `company` (inherited from CompanyOwnedModel)

### Lifecycle
Created → may be deleted/recreated during DRAFT edits → frozen at PAID time.

### State Transitions
No explicit status. Immutability inherited from parent Invoice status.

### Invariants
- `total_price = max(0, quantity * unit_price - discount_amount)` (computed on save)
- Cannot be modified when Invoice is PAID

### Existing Implementation
`apps/invoices/models.py`, line 298 — `InvoiceItem`. RowType: service/goods/travel.

### Required Extension
Add RowType choices: `ADDITIONAL_DISCOUNT`, `LOYALTY_DISCOUNT` (R23).

### Open Issue Impact
- OI-02: Transportation modeling — currently a line type; may become dedicated field.


---

## 3. Payment (PaymentTransaction)

### Purpose
رکورد تراکنش پرداخت. اثبات حرکت فیزیکی پول (P01: جدا از معنای مالکیت).

### Ownership
Organization (Company).

### Relationships
- `invoice` → `Invoice` (FK, SET_NULL, nullable)
- `gateway` → `PaymentGateway` (FK, SET_NULL, nullable)
- `company` (CompanyOwnedModel)
- `attempts` ← `PaymentAttempt[]` (reverse FK, CASCADE)
- `split_snapshot` ← `PaymentSplitSnapshot` (OneToOne reverse)
- `ledger_entries` ← `TechnicianLedgerEntry[]` (reverse FK)
- `platform_fee_entries` ← `CompanyPlatformFeeEntry[]` (reverse FK)

### Lifecycle
```
INITIATED → PENDING → PAID
INITIATED → PENDING → FAILED
INITIATED → PENDING → NEEDS_RECONCILIATION
INITIATED → CANCELLED
```

### State Transitions
| From | To | Trigger |
|---|---|---|
| — | INITIATED | `PaymentStartService.start()` |
| INITIATED | PENDING | PSP returns redirect URL successfully |
| INITIATED | FAILED | PSP rejects initiation |
| PENDING | PAID | `PaymentVerifyService.verify()` confirms |
| PENDING | FAILED | PSP verification fails |
| PENDING | NEEDS_RECONCILIATION | Expired (>30min) or amount mismatch |
| INITIATED | CANCELLED | User abandons before PSP redirect |

### Invariants
- `amount` matches `invoice.total_amount` at creation (enforced in mark_paid)
- Only PENDING payments can be verified
- Already-PAID payments return idempotent success
- `select_for_update()` prevents concurrent verification

### Existing Implementation
`apps/payments/models.py`, line 60 — `Payment`. Fully implemented.

### Required Extension
None to the model. Gateway integration for refund API (target Sprint 6).

### Open Issue Impact
- OI-01: Split payment mechanics via PSP — `PaymentSplitSnapshot` is the decision record
- OI-06: Overpayment — amount mismatch already routes to NEEDS_RECONCILIATION

---

## 4. TechnicianLedgerEntry

### Purpose
دفترکل تغییرناپذیر تکنسین. ثبت تمام حقوق و تسویه‌ها. (P02, R51)

### Ownership
Organization (Company) + Provider (Technician).

### Relationships
- `company` (CompanyOwnedModel)
- `technician` → `accounts.Technician` (FK, PROTECT)
- `invoice` → `invoices.Invoice` (FK, SET_NULL, nullable)
- `payment` → `payments.Payment` (FK, SET_NULL, nullable)
- `order` → `orders.Order` (FK, SET_NULL, nullable)
- `created_by` → `accounts.CompanyUser` (FK, SET_NULL, nullable)

### Lifecycle
Created → immutable forever. No status transitions. No updates. No deletes.

### State Transitions
None — entries are born and live forever.

### Invariants
- `amount_rial` immutable after creation (model-level enforcement)
- `balance_after` immutable after creation (model-level enforcement)
- `delete()` always raises PermissionError
- `idempotency_key` globally unique (DB UNIQUE constraint)
- `get_balance()` = SUM(credits) - SUM(debits) — always recomputed, not cached

### Existing Implementation
`apps/payouts/models.py`, line 16 — `TechnicianLedgerEntry`. Fully implemented with 8 Source choices.

### Required Extension
None to model. New Source choices may be added in future (bonus, penalty).

### Open Issue Impact
None directly.

---

## 5. CompanyPlatformFeeEntry

### Purpose
دفترکل کارمزد پلتفرم هر شرکت. همان الگوی TechnicianLedgerEntry.

### Ownership
Organization (debtor) ↔ Platform (creditor).

### Relationships
- `company` (CompanyOwnedModel)
- `invoice` → `invoices.Invoice` (FK, SET_NULL, nullable)
- `payment` → `payments.Payment` (FK, SET_NULL, nullable)
- `created_by` → `accounts.CompanyUser` (FK, SET_NULL, nullable)

### Lifecycle
Created → immutable forever.

### Invariants
Same as TechnicianLedgerEntry: immutable amount, balance, no delete, unique idempotency_key.

### Existing Implementation
`apps/payouts/models.py`, line 189 — `CompanyPlatformFeeEntry`. Fully implemented.

### Required Extension
None. Future `SettlementBatch` will create CREDIT entries on this ledger.

### Open Issue Impact
None.

---

## 6. PaymentSplitSnapshot

### Purpose
رکورد تغییرناپذیر تصمیم تسهیم. مرجع authoritative برای `direct_gateway_settlement` DEBIT amount (ADR-006 §7).

### Ownership
Organization (Company).

### Relationships
- `payment` → `Payment` (OneToOneField) — enforces one snapshot per payment
- `invoice` → `Invoice` (FK, nullable)
- `company` (CompanyOwnedModel)

### Lifecycle
Created once at payment verification → immutable forever.

### Invariants
- OneToOneField on `payment` — DB enforces uniqueness
- `create_snapshot()` is code-level idempotent (returns existing if present)
- `technician_direct_amount` is the sole authoritative source for DEBIT amount

### Existing Implementation
`apps/payouts/models.py`, line 137 — `PaymentSplitSnapshot`. Fully implemented.

### Required Extension
None.

### Open Issue Impact
- OI-01: If PSP supports real split, `technician_direct_amount` becomes the actual PSP-level settlement amount.


---

## 7. FinancialBackfillTask

### Purpose
ردیابی نوشتارهای مالی ناموفق برای retry خودکار (ADR-008).

### Ownership
Organization (Company).

### Relationships
- `company` (CompanyOwnedModel)
- `invoice` → `Invoice` (FK, SET_NULL, nullable)
- `payment` → `Payment` (FK, SET_NULL, nullable)

### Lifecycle
```
PENDING → PROCESSING → RESOLVED
PENDING → PROCESSING → (rollback) → PENDING (attempts++)
```

### State Transitions
| From | To | Trigger |
|---|---|---|
| — | PENDING | Financial write failure |
| PENDING | PROCESSING | `process_pending()` picks up task |
| PROCESSING | RESOLVED | Retry succeeds (same transaction) |
| PROCESSING | PENDING | Retry fails (rollback + increment) |

### Invariants
- At most one PENDING/PROCESSING task per (company, task_type, invoice) — enforced by `create_task()`
- Never deleted (ADR-008)
- Each task processed in its own transaction

### Existing Implementation
`apps/payouts/models.py`, line 296 — `FinancialBackfillTask`. Fully implemented.

### Required Extension
None. Consider alerting integration (notify platform owner when attempts > threshold).

### Open Issue Impact
None.

---

## 8. TechnicianServiceRate

### Purpose
نرخ ثابت ریالی اجرت تکنسین per countable order item (ADR-005).

### Ownership
Organization (Company) + Provider (Technician).

### Relationships
- `company` (CompanyOwnedModel)
- `technician` → `accounts.Technician` (FK, CASCADE)
- `item_definition` → `orders.OrderItemDefinition` (FK, CASCADE)

### Lifecycle
Created → active/deactivated → read at order completion → snapshot in metadata.

### Invariants
- UNIQUE (company, technician, item_definition) — DB constraint
- Only `kind=NUMBER` item definitions (enforced by `clean()`)
- Rate read at completion time, never retroactively applied (ADR-005)

### Existing Implementation
`apps/payouts/models.py`, line 367 — `TechnicianServiceRate`. Fully implemented.

### Required Extension
Phase 2 (ADR-005): `pricing_type`, `effective_from/to`, `created_by`, `notes`. All nullable/default —
backward-compatible.

### Open Issue Impact
None.

---

## 9. EscrowRecord (TARGET — NEW MODEL)

### Purpose
Explicit ownership tracking of customer funds held by Platform.
Materializes the Money Ownership Lifecycle (Section 3.2).

### Ownership
Platform (holds) on behalf of Organization + Provider.

### Relationships
- `company` (CompanyOwnedModel)
- `payment` → `Payment` (OneToOneField) — one escrow per online payment
- `invoice` → `Invoice` (FK)
- `settlement_batch` → `SettlementBatch` (FK, nullable) — linked when settled

### Lifecycle
```
HELD → RESERVED → ELIGIBLE → DISTRIBUTED → PENDING_SETTLEMENT → SETTLED → CLOSED
```

### State Transitions
| From | To | Trigger | Service |
|---|---|---|---|
| — | HELD | Payment verified (platform gateway) | PaymentVerifyService |
| HELD | RESERVED | Invoice marked PAID | InvoiceMarkPaidService |
| RESERVED | DISTRIBUTED | Settlement freeze written | InvoiceSettlementService |
| DISTRIBUTED | PENDING_SETTLEMENT | SettlementBatch created | SettlementCalculationService |
| PENDING_SETTLEMENT | SETTLED | Bank transfer confirmed | SettlementExecutionService |
| SETTLED | CLOSED | No outstanding adjustments | Periodic check |

### Invariants
- Only created for online payments with platform-owned gateway (not cash)
- OneToOneField on payment prevents duplicates
- Amount breakdown: `platform_commission + organization_share + provider_share = amount_rial`
- No status can be skipped

### Existing Implementation
None — target new model.

### Required Extension
New model. New migration (CREATE TABLE — zero downtime).

### Open Issue Impact
- OI-06: Overpayment handling may require special escrow state
- OI-07: Refund may require escrow state reversal (SETTLED → REFUNDED)

---

## 10. SettlementBatch (TARGET — NEW MODEL)

### Purpose
Batch of invoices settled together in one bank transfer (Net Position Settlement, Section 3.6).

### Ownership
Organization (Company) — scoped to one company per batch.

### Relationships
- `company` (CompanyOwnedModel)
- `items` ← `SettlementItem[]` (reverse FK)
- `created_by` → `accounts.CompanyUser` (FK, nullable)

### Lifecycle
```
CALCULATING → READY → EXECUTING → COMPLETED
CALCULATING → READY → EXECUTING → FAILED
```

### State Transitions
| From | To | Trigger |
|---|---|---|
| — | CALCULATING | `process_settlements` command starts period |
| CALCULATING | READY | Net position computed, items aggregated |
| READY | EXECUTING | Auto-approved (R44) or manual trigger |
| EXECUTING | COMPLETED | Bank transfer confirmed |
| EXECUTING | FAILED | Bank transfer failed |

### Invariants
- `net_amount_rial` = total_credits - total_debits for the period
- `level` distinguishes Platform↔Org vs Org↔Provider
- `period_start` < `period_end`
- Items in a batch cannot belong to another batch

### Existing Implementation
None — grep confirmed zero results for `SettlementBatch`.

### Required Extension
New model. New migration (CREATE TABLE — zero downtime).

### Open Issue Impact
- OI-08: May require `PENDING_APPROVAL` status if two-step approval decided

---

## 11. SettlementItem (TARGET — NEW MODEL)

### Purpose
Individual invoice included in a settlement batch.

### Ownership
Organization (via batch).

### Relationships
- `batch` → `SettlementBatch` (FK, CASCADE)
- `invoice` → `Invoice` (FK)
- `company` (CompanyOwnedModel)

### Lifecycle
Created with batch → immutable.

### Invariants
- Each invoice appears in at most one batch (enforced by service logic, not DB constraint —
  some invoices may be excluded from batching).

### Existing Implementation
None.

---

## 12. AdjustmentDocument (TARGET — NEW MODEL)

### Purpose
Formal correction document for PAID invoices (Credit Note, Debit Note, Refund).
Satisfies R52 (corrections via separate documents).

### Ownership
Organization (Company).

### Relationships
- `company` (CompanyOwnedModel)
- `original_invoice` → `Invoice` (FK)
- `created_by` → `accounts.CompanyUser` (FK)
- `approved_by` → `accounts.CompanyUser` (FK, nullable)
- `technician_ledger_entry` → `TechnicianLedgerEntry` (FK, nullable) — created on apply
- `platform_fee_entry` → `CompanyPlatformFeeEntry` (FK, nullable) — created on apply

### Lifecycle
```
DRAFT → PENDING_APPROVAL → APPROVED → APPLIED
DRAFT → CANCELLED
PENDING_APPROVAL → REJECTED
```

### State Transitions
| From | To | Trigger |
|---|---|---|
| — | DRAFT | Admin creates |
| DRAFT | PENDING_APPROVAL | Admin submits |
| PENDING_APPROVAL | APPROVED | Approver approves |
| APPROVED | APPLIED | System executes ledger reversals |
| DRAFT | CANCELLED | Admin cancels |
| PENDING_APPROVAL | REJECTED | Approver rejects |

### Invariants
- Original invoice must be PAID (you don't adjust unpaid invoices — cancel them instead)
- `amount_rial` ≤ `original_invoice.total_amount` (for partial refunds)
- Once APPLIED, technician_ledger_entry and platform_fee_entry FKs are populated

### Existing Implementation
None.

### Required Extension
New model + new service (`RefundExecutionService`).

### Open Issue Impact
- OI-05: Defines when customer becomes creditor/debtor
- OI-06: Overpayment may be handled as AdjustmentDocument(type=CREDIT_NOTE)
- OI-07: **BLOCKING** — Full/Partial Refund definitions needed before implementation
