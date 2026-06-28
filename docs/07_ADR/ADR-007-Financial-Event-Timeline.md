# ADR-007 — Financial Event Timeline

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Platform Team  
**Supersedes:** —  
**Superseded by:** —  
**Related:** ADR-004, ADR-005, ADR-006, ADR-008

---

## Context

The financial core now covers multiple overlapping event streams: order completion,
invoice payment, gateway settlement, and technician statement projection. Each stream
produces ledger entries from an authoritative source, and the ordering of these events
has non-obvious dependencies.

Before adding new financial features, the complete event lifecycle must be recorded so
that every future implementer knows the authoritative source for each write, the
required ordering, and the failure modes.

---

## Decision

The canonical financial event sequence is defined below. Every implementation task
involving ledger entries or financial state must be traced to this timeline.

---

## Complete Financial Event Timeline

```
ORDER COMPLETED
      │
      ▼
1. Technician Wage Posting
      │
      ▼
2. Invoice Issued
      │
      ▼
3. Invoice Paid  ──────────────────────────────────────┐
      │                                                 │
      ▼                                                 │
4. InvoiceSettlementService.settle()                    │
   (freezes settled_* fields on invoice)               │
      │                                                 │
      ▼                                                 │
5. TechnicianLedgerService.create_invoice_entries()    │
   (CREDIT: online_gateway / cash / manual_payment)    │
      │                                                 │
      ▼                                                 │
6. PlatformFeeService.record_invoice_fee()             │
   (DEBIT: company owes platform)                      │
      │                                                 │
      ▼                                                 │
7. PaymentSplitDecisionService.create_snapshot()       │
   (immutable split decision audit record)             │
      │                                                 │
      ▼                                                 │
8. TechnicianDirectSettlementService.post_for_payment()│
   (DEBIT: direct_gateway_settlement, if applicable)   │
      │                                                 │
      ▼                                                 │
9. Technician Statement (read-only projection)         │
      │                                                 │
      ▼                                                 │
10. Export / Print / Gateway Reconciliation ◄──────────┘
```

---

## Event Detail

### Event 1 — Technician Wage Posting

**Trigger:** `OrderCompleteService.complete()` marks order as DONE.

**Service:** `TechnicianWagePostingService.post_for_order()`  
**Ledger entry produced:** CREDIT `technician_service_wage`  
**Authoritative source:** `OrderItemValue.value_number × TechnicianServiceRate.fixed_wage_rial`  
**Snapshot point:** The rate is read at completion time and frozen in `metadata.items[].fixed_wage_rial`. Subsequent rate changes never affect this entry.  
**Idempotency key:** `technician_service_wage:order:{order.id}`  
**Failure mode:** Warning logged; missing rate does not fail order completion. Entry is omitted for items with no active rate.  
**ADR:** ADR-005, ADR-006 §4

---

### Events 2–3 — Invoice Issued → Invoice Paid

**Trigger:** Customer pays online, cash, or manually.  
**State transitions:** DRAFT → ISSUED → PAID  
**Service:** `InvoiceMarkPaidService.mark_paid()`  
**This event triggers events 4–8.**

---

### Event 4 — Invoice Settlement Freeze

**Service:** `InvoiceSettlementService.settle()`  
**What it does:** Freezes `settled_technician_wage`, `settled_platform_fee`, `settled_payment_method`, `settled_at` on the invoice. These fields are immutable after this point.  
**Authoritative source for downstream events:** `invoice.settled_technician_wage` is the canonical amount for all CREDIT entries in Event 5.  
**Key rule:** Customer discounts reduce company revenue, not technician earnings (ADR-006 §5).

---

### Event 5 — Technician Invoice Credit

**Service:** `TechnicianLedgerService.create_invoice_entries()`  
**Ledger entry produced:** CREDIT (`online_gateway` / `cash_from_customer` / `manual_payment`)  
**Authoritative source:** `invoice.settled_technician_wage` — frozen by Event 4.  
**Idempotency key:** `invoice:{invoice.id}:technician_credit`  
**Additional entry (cash collected by technician):** DEBIT `cash_from_customer` with key `invoice:{invoice.id}:cash_received_by_technician`  
**Failure mode:** Exception caught by `mark_paid()`; `FinancialBackfillTask(TECHNICIAN_LEDGER)` created.  
**ADR:** ADR-004, ADR-006 §7

---

### Event 6 — Platform Fee Recording

**Service:** `PlatformFeeService.record_invoice_fee()`  
**Ledger entry produced:** DEBIT on `CompanyPlatformFeeEntry`  
**Authoritative source:** `company.financial_policy.platform_fee_percent` × `invoice.total_amount`  
**Idempotency key:** `platform_fee:invoice:{invoice.id}`  
**Failure mode:** `PlatformFeeRecordingFailed` raised; `FinancialBackfillTask(PLATFORM_FEE)` created.

---

### Event 7 — Payment Split Snapshot

**Service:** `PaymentSplitDecisionService.create_snapshot()`  
**What it produces:** `PaymentSplitSnapshot` — immutable audit record of the split routing decision.  
**Authoritative source:** Payout strategy settings at payment time, technician verification status, sub-merchant ID.  
**Idempotency:** `PaymentSplitSnapshot.payment` is a `OneToOneField` (DB-enforced uniqueness). `create_snapshot()` is code-level idempotent: returns existing snapshot if already present.  
**This record is the authoritative source for Event 8.**  
**Failure mode:** Exception caught by `verify()`; `FinancialBackfillTask(PAYMENT_SPLIT_SNAPSHOT)` created.

---

### Event 8 — Direct Gateway Settlement DEBIT

**Service:** `TechnicianDirectSettlementService.post_for_payment()`  
**Trigger:** `PaymentSplitSnapshot.should_split_with_technician == True` and gateway `owner_type == PLATFORM`.  
**Ledger entry produced:** DEBIT `direct_gateway_settlement`  
**Authoritative source:** `PaymentSplitSnapshot.technician_direct_amount` — the exact rial amount the PSP settled to the technician's bank account, as recorded in the snapshot. Never re-read from invoice or order.  
**Idempotency key:** `direct_gateway_settlement:payment:{payment.id}`  
**Failure mode:** Exception caught by `verify()`; `FinancialBackfillTask(DIRECT_GATEWAY_SETTLEMENT)` created.  
**ADR:** ADR-006 §7, §8

---

### Event 9 — Technician Statement Projection

**Service:** `TechnicianStatementService.build()`  
**Nature:** Pure read-only projection. No writes. No financial decisions.  
**Source:** `TechnicianLedgerEntry` rows, ordered chronologically.  
**`balance_after`:** Displayed directly from the stored row; not recomputed.  
**`get_balance()`:** Always recomputed from `SUM(credits) - SUM(debits)` — authoritative.  
**ADR:** ADR-006 §2, §9

---

### Event 10 — Export / Print / Reconciliation

**Views:** `technician_statement_export` (CSV), `technician_statement_pdf` (WeasyPrint), `gateway_reconciliation`  
**Nature:** Read-only. No financial writes originate from any of these views.  
**CSV encoding:** UTF-8 BOM for Persian Excel compatibility.

---

## The Authoritative Source Rule (ADR-006 §7, restated here for clarity)

Every ledger entry records one business event. The amount posted must come from the
**authoritative snapshot of that event** — never from a previously created ledger entry.

| Business event | Authoritative source |
|---|---|
| Order marked DONE | `OrderItemValue.value_number × TechnicianServiceRate.fixed_wage_rial` (at completion time) |
| Invoice paid | `invoice.settled_technician_wage` (frozen by `InvoiceSettlementService.settle()`) |
| Gateway split executed | `PaymentSplitSnapshot.technician_direct_amount` |
| Manual settlement | Amount set by authorised admin at time of settlement |

**Anti-pattern (forbidden):**
```python
# WRONG — reading a prior ledger entry to determine a new amount
prior = TechnicianLedgerEntry.objects.get(source="online_gateway", invoice=inv)
debit_amount = prior.amount_rial  # ← never do this
```

---

## Ordering Dependencies

```
Event 1 (wage posting)          independent of events 4–8
Event 4 (settlement freeze)     MUST happen before events 5, 6, 7, 8
Event 7 (split snapshot)        MUST exist before event 8 (settlement reads it)
Events 9, 10                    always after event 5 (otherwise statement is incomplete)
```

Events 5, 6, 7, 8 all run inside or immediately after `InvoiceMarkPaidService.mark_paid()`.
Events 7 and 8 run inside `PaymentVerifyService.verify()`.
All failures in events 5–8 produce a `FinancialBackfillTask` — see ADR-008.

---

## Consequences

### Positive

- Every developer can identify the authoritative source for any amount before writing code.
- The timeline makes it obvious why snapshot → debit ordering matters.
- New financial events can be inserted at the correct point without rewriting existing flows.

### Negative / Trade-offs

- Events 5–8 run inside a single HTTP request (`PaymentVerifyService.verify()`). A slow
  direct-settlement service call adds latency to the payment callback response. Accepted
  for V1; a future background-job model would decouple this.
- Event 1 (wage posting) and events 5–8 (invoice payment) are financially independent but
  produce correlated ledger entries. The statement must group or annotate them clearly.

---

## References

- `apps/payouts/services.py` — `TechnicianLedgerService`
- `apps/payouts/services_order_wages.py` — `TechnicianWagePostingService`
- `apps/payouts/services_direct_settlement.py` — `TechnicianDirectSettlementService`
- `apps/payouts/services_split.py` — `PaymentSplitDecisionService`
- `apps/payouts/services_statement.py` — `TechnicianStatementService`
- `apps/invoices/services.py` — `InvoiceMarkPaidService`, `InvoiceSettlementService`
- `apps/payments/services.py` — `PaymentVerifyService`
- `apps/payouts/views.py` — export, print, statement views
- `apps/payouts/views_split_snapshots.py` — `gateway_reconciliation`
- `docs/07_ADR/ADR-004-Ledger-Discipline.md`
- `docs/07_ADR/ADR-005-Technician-Service-Pricing.md`
- `docs/07_ADR/ADR-006-Technician-Ledger-Statement-Architecture.md`
- `docs/07_ADR/ADR-008-Financial-Recovery-Policy.md`
