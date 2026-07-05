# 24 — مشخصات چرخه عمر پول (Money Lifecycle Specification)

**Version:** v1.0 — Draft — Pending Clarification

**Purpose:**
This document defines the complete lifecycle of money as it flows
through the RastiSaas Financial Engine, from the moment a Customer
intends to pay to the moment the transaction is financially closed.

**Terminology mapping used throughout this document:**

| Domain term | Codebase term |
|---|---|
| Organization | Company (`apps/tenants/models.Company`) |
| Provider | Technician (`apps/accounts/models.Technician`) |
| Platform | RastiSaas platform owner (system-level) |
| Customer | `apps/accounts/models.Customer` |

**Grounding:**
This document is derived from:

- `docs/13_Financial_Core/05_GAP_ANALYSIS.md`
- `docs/13_Financial_Core/target_architecture/04_DOMAIN_MODEL.md`
- `docs/13_Financial_Core/target_architecture/13_SETTLEMENT_NETTING_ENGINE.md`
- `docs/13_Financial_Core/target_architecture/19_DATA_MODEL.md`
- `docs/13_Financial_Core/target_architecture/23_FINANCIAL_PRINCIPLES_SPECIFICATION.md`

No new business rule is invented here.
Where the Financial Engine target model (`EscrowRecord`, `SettlementBatch`)
is referenced, it is explicitly marked as **(target)**.

---

## Table of Contents

1. Canonical Lifecycle States
2. Flow: Online Payment through Platform Gateway
3. Flow: Cash Payment
4. Flow: Card-to-Card Payment
5. Flow: Direct Provider Split
6. Flow: Failed Payment
7. Flow: Amount Mismatch
8. Flow: Refund Before Settlement
9. Flow: Refund After Settlement


---

## 1. Canonical Lifecycle States

The table below defines the 15 canonical states money passes through
in the primary (online, platform-gateway, no-split) path.

Not every flow visits every state — see the flow-specific sections
below for variants.

### State 1 — Customer Intends to Pay

| Field | Value |
|---|---|
| Owner of money | Customer |
| Physical holder of money | Customer (not yet transferred) |
| Ledger impact | None |
| Escrow impact | None |
| Settlement impact | None |
| Events emitted | None (pre-transaction, UI-level only) |
| Failure modes | Customer abandons before starting payment |

**Existing implementation:** No dedicated model state; this is the
customer's mental/UI state before `PaymentStartService.start()`
is called.

---

### State 2 — Payment Initiated

| Field | Value |
|---|---|
| Owner of money | Customer |
| Physical holder of money | Customer |
| Ledger impact | None |
| Escrow impact | None |
| Settlement impact | None |
| Events emitted | `PAYMENT_STARTED` (existing) |
| Failure modes | Gateway rejects initiation → `Payment.status = FAILED` |

**Existing implementation:** `apps/payments/services.py`,
`PaymentStartService.start()` creates `Payment(status=INITIATED)`,
then attempts to obtain a redirect URL from the gateway provider.

---

### State 3 — Payment Pending

| Field | Value |
|---|---|
| Owner of money | Customer |
| Physical holder of money | Payment Service Provider (PSP), in transit |
| Ledger impact | None |
| Escrow impact | None |
| Settlement impact | None |
| Events emitted | None (waiting for gateway callback) |
| Failure modes | Expires after 30 minutes → `NEEDS_RECONCILIATION` |

**Existing implementation:** `apps/payments/models.py`,
`Payment.status = PENDING` after successful gateway redirect.
`PAYMENT_EXPIRATION_MINUTES` (default 30) governs the expiry window.


---

### State 4 — Payment Verified

| Field | Value |
|---|---|
| Owner of money | Transitioning from Customer to Platform |
| Physical holder of money | Platform bank account (if platform gateway) |
| Ledger impact | None yet (ledger writes happen in later states) |
| Escrow impact | None yet — triggers Escrow creation next |
| Settlement impact | None |
| Events emitted | `PAYMENT_SUCCESS_CUSTOMER`, `PAYMENT_SUCCESS_ADMIN`, `PAYMENT_SUCCESS_OPERATOR` |
| Failure modes | Amount tampering detected → `NEEDS_RECONCILIATION` instead |

**Existing implementation:** `apps/payments/services.py`,
`PaymentVerifyService.verify()` calls the PSP verify endpoint,
compares `verified_amount` to `payment.amount`, and only then
sets `Payment.status = PAID`.

---

### State 5 — Funds Held by Platform

| Field | Value |
|---|---|
| Owner of money | Split: Platform (commission) + Organization (share) + Provider (share) |
| Physical holder of money | Platform bank account |
| Ledger impact | None yet |
| Escrow impact | **(target)** `EscrowRecord` should be created here with `status=HELD` |
| Settlement impact | None |
| Events emitted | **(target)** `escrow_reserved` |
| Failure modes | None specific — this is a custodial, not transactional, state |

**Existing implementation:** Implicit only — the money is now
physically in the Platform's gateway account (`PaymentGateway.owner_type
= PLATFORM`), but no `EscrowRecord` model exists yet to represent
this state explicitly. See `04_DOMAIN_MODEL.md` §9 and
`05_GAP_ANALYSIS.md` R01.

---

### State 6 — Escrow Created (target)

| Field | Value |
|---|---|
| Owner of money | Split: Platform + Organization + Provider |
| Physical holder of money | Platform bank account |
| Ledger impact | None |
| Escrow impact | `EscrowRecord(status=HELD)` created, linked 1:1 to `Payment` |
| Settlement impact | None |
| Events emitted | **(target)** `escrow_reserved` |

**Failure modes:** Escrow creation failure must not block
`Payment.status=PAID`. Must recover via a backfill-style
mechanism, matching the existing `FinancialBackfillTask` pattern.

**Required future extension:** This entire state is new.
See `19_DATA_MODEL.md` — EscrowRecord.

---

### State 7 — Escrow Reserved for Invoice

| Field | Value |
|---|---|
| Owner of money | Split: Platform + Organization + Provider |
| Physical holder of money | Platform bank account |
| Ledger impact | None yet |
| Escrow impact | `EscrowRecord.status = RESERVED`, `EscrowRecord.invoice` set |
| Settlement impact | None |
| Events emitted | None new |
| Failure modes | None specific |

**Existing implementation today:** `Invoice.status` transitions to
`PAID` via `InvoiceMarkPaidService.mark_paid()`, which links
`payment.invoice` — this is the existing signal that would drive
the target `EscrowRecord.status = RESERVED` transition.


---

### State 8 — Invoice Marked Paid

| Field | Value |
|---|---|
| Owner of money | Split: Platform + Organization + Provider |
| Physical holder of money | Platform bank account |
| Ledger impact | Triggers `InvoiceSettlementService.settle()` — freezes `settled_*` fields |
| Escrow impact | **(target)** should trigger `EscrowRecord.status = RESERVED` |
| Settlement impact | None yet — settlement batch happens later |
| Events emitted | `INVOICE_PAID_CUSTOMER` (existing) |
| Failure modes | `ValueError` if invoice not `ISSUED`, or already settled |

**Existing implementation:** `apps/invoices/services.py`,
`InvoiceMarkPaidService.mark_paid()` — locks the invoice row,
validates payment amount matches invoice total, calls
`InvoiceSettlementService.settle()`, sets `Invoice.status = PAID`.

---

### State 9 — Commission Calculated

| Field | Value |
|---|---|
| Owner of money | Platform's share becomes fixed and recognized |
| Physical holder of money | Platform bank account |
| Ledger impact | `CompanyPlatformFeeEntry` DEBIT created (if 4-condition gate passes) |
| Escrow impact | **(target)** `EscrowRecord.platform_commission_rial` populated |
| Settlement impact | Feeds into future `SettlementBatch` net position calculation |
| Events emitted | **(target)** `commission_calculated` |
| Failure modes | `PlatformFeeRecordingFailed` → `FinancialBackfillTask(PLATFORM_FEE)` created |

**Existing implementation:** `apps/payouts/services_platform_fee.py`,
`PlatformFeeService.record_invoice_fee()`.

---

### State 10 — Provider Wage Calculated

| Field | Value |
|---|---|
| Owner of money | Provider's share becomes fixed and recognized |
| Physical holder of money | Platform bank account (unless direct split already occurred) |
| Ledger impact | `TechnicianLedgerEntry` CREDIT created |
| Escrow impact | **(target)** `EscrowRecord.provider_share_rial` populated |
| Settlement impact | Feeds into Layer 2 net position (Organization ↔ Provider) |
| Events emitted | **(target)** `provider_wage_posted` |
| Failure modes | Ledger write failure → `FinancialBackfillTask(TECHNICIAN_LEDGER)` created |

**Existing implementation:** `apps/payouts/services.py`,
`TechnicianLedgerService.create_invoice_entries()`.

---

### State 11 — Organization Share Calculated

| Field | Value |
|---|---|
| Owner of money | Organization's share becomes fixed and recognized |
| Physical holder of money | Platform bank account |
| Ledger impact | Implicit — `invoice.settled_company_share` is the authoritative amount |
| Escrow impact | **(target)** `EscrowRecord.organization_share_rial` populated; `status = DISTRIBUTED` |
| Settlement impact | Feeds into Layer 1 net position (Platform ↔ Organization) |
| Events emitted | None new — covered by `INVOICE_PAID_CUSTOMER` |
| Failure modes | None specific — this is a derived/computed value, not a separate write |

**Existing implementation:** `apps/invoices/services_settlement.py`,
`InvoiceSettlementService.settle()` writes
`invoice.settled_company_share` as part of the same atomic
settlement freeze.


---

### State 12 — Settlement Eligible

| Field | Value |
|---|---|
| Owner of money | Split: Platform + Organization + Provider |
| Physical holder of money | Platform bank account |
| Ledger impact | None new |
| Escrow impact | **(target)** `status = PENDING_SETTLEMENT` once `paid_at + delay_hours <= now()` |
| Settlement impact | Invoice becomes selectable by `SettlementCalculationService._find_eligible_invoices()` |
| Events emitted | None new |
| Failure modes | Excluded if pending `AdjustmentDocument` or `FinancialBackfillTask` exists |

**Required future extension:** Eligibility criteria fully specified
in `13_SETTLEMENT_NETTING_ENGINE.md` — Settlement Item Selection Rules.

---

### State 13 — Settlement Batch Created (target)

| Field | Value |
|---|---|
| Owner of money | Split: Platform + Organization + Provider |
| Physical holder of money | Platform bank account |
| Ledger impact | `SettlementItem` rows created, linked to `SettlementBatch` |
| Escrow impact | `EscrowRecord.settlement_batch` FK populated |
| Settlement impact | `SettlementBatch.status = CALCULATING → READY` |
| Events emitted | **(target)** `settlement_batch_created` |
| Failure modes | Batch calculation raises exception → transaction rolls back; no partial batch persists |

**Required future extension:** See `13_SETTLEMENT_NETTING_ENGINE.md` —
Batch Creation Algorithm.

---

### State 14 — Settlement Executed (target)

| Field | Value |
|---|---|
| Owner of money | Transitioning from Platform custody to Organization/Provider bank accounts |
| Physical holder of money | Organization or Provider bank account (post-transfer) |
| Ledger impact | `CompanyPlatformFeeEntry` CREDIT (Layer 1) or `TechnicianLedgerEntry` DEBIT (Layer 2) |
| Escrow impact | `EscrowRecord.status = SETTLED` |
| Settlement impact | `SettlementBatch.status = EXECUTING → COMPLETED` (or `FAILED`) |
| Events emitted | **(target)** `settlement_completed` or `settlement_failed` |
| Failure modes | Bank transfer fails → `SettlementBatch.status = FAILED`; items become re-eligible for the next batch |

**Required future extension:** See `13_SETTLEMENT_NETTING_ENGINE.md` —
Failure and Retry Handling.

---

### State 15 — Final Closed State

| Field | Value |
|---|---|
| Owner of money | Organization / Provider (fully realized) |
| Physical holder of money | Organization or Provider bank account |
| Ledger impact | None new — history is final and immutable |
| Escrow impact | `EscrowRecord.status = CLOSED` |
| Settlement impact | None new |
| Events emitted | None new |
| Failure modes | None — this state is terminal, absent a later refund (see §9) |

**Required future extension:** Closure condition
("no outstanding adjustments") must be defined precisely once
`AdjustmentDocument` exists — see
`26_REFUND_REVERSAL_ENGINE_SPECIFICATION.md`.


---

## 2. Flow: Online Payment through Platform Gateway

This is the canonical flow described state-by-state in Section 1.

### Path

```
State 1 → 2 → 3 → 4 → 5 → 6(target) → 7 → 8 → 9 → 10 → 11
→ 12 → 13(target) → 14(target) → 15
```

### Owner of Money at Each Major Milestone

| Milestone | Owner |
|---|---|
| Before payment | Customer |
| After PSP verification | Platform (custodial), split among 3 parties (legal) |
| After settlement batch executes | Organization / Provider (final) |

### Physical Holder of Money at Each Major Milestone

| Milestone | Physical holder |
|---|---|
| Before payment | Customer's own bank/wallet |
| After PSP verification | Platform's gateway bank account |
| After settlement batch executes | Organization's or Provider's bank account |

### Ledger Impact Summary

- `CompanyPlatformFeeEntry` DEBIT (commission owed) — at Invoice PAID.
- `TechnicianLedgerEntry` CREDIT (wage owed) — at Invoice PAID.
- `CompanyPlatformFeeEntry` CREDIT / `TechnicianLedgerEntry` DEBIT
  (settlement executed) — **(target)**, at batch completion.

### Escrow Impact Summary

- `EscrowRecord` created at PSP verification — **(target)**.
- Full lifecycle: `HELD → RESERVED → DISTRIBUTED →
  PENDING_SETTLEMENT → SETTLED → CLOSED` — **(target)**.

### Settlement Impact Summary

- Feeds Layer 1 (Platform ↔ Organization) net position.
- Feeds Layer 2 (Organization ↔ Provider) net position,
  unless a direct split already occurred (see Section 5).

### Events Emitted (chronological)

1. `PAYMENT_STARTED`
2. `PAYMENT_SUCCESS_CUSTOMER`, `PAYMENT_SUCCESS_ADMIN`,
   `PAYMENT_SUCCESS_OPERATOR`
3. `INVOICE_PAID_CUSTOMER`
4. **(target)** `escrow_reserved`
5. **(target)** `commission_calculated`
6. **(target)** `provider_wage_posted`
7. **(target)** `settlement_batch_created`
8. **(target)** `settlement_completed`

### Failure Modes

| Failure | Handling |
|---|---|
| PSP initiation fails | `Payment.status = FAILED` |
| Verification expires | `Payment.status = NEEDS_RECONCILIATION` |
| Amount mismatch | `Payment.status = NEEDS_RECONCILIATION` |
| Ledger write fails after PAID | `FinancialBackfillTask` created, invoice remains PAID |
| Settlement batch execution fails | `SettlementBatch.status = FAILED`, items re-eligible |


---

## 3. Flow: Cash Payment

### Path

```
State 1 → 8 → 9(skipped by default) → 10 → 11 → 12(N/A) → 15
```

Cash payments **skip** the Platform escrow states entirely (States 5–7),
because the money never physically enters the Platform's bank account.
This is R37: legal ownership of cash belongs to the Organization
immediately.

### Owner of Money

| Milestone | Owner |
|---|---|
| Before payment | Customer |
| Immediately after cash collection | Organization (R37) |
| After wage calculation | Organization (owes Provider) or Provider (if Provider physically holds the cash) |

### Physical Holder of Money

| Milestone | Physical holder |
|---|---|
| Before payment | Customer |
| Immediately after collection | Organization admin, or Provider (if Provider collected it directly) |

### Ledger Impact

- `TechnicianLedgerEntry` CREDIT (`source=cash_from_customer` or
  `manual_payment`) — always created.
- `TechnicianLedgerEntry` DEBIT (`source=cash_from_customer`,
  full invoice amount) — created **only** if payment metadata
  indicates the Provider personally collected the cash
  (`_payment_collected_by_technician()` in
  `apps/payouts/services.py`).

### Escrow Impact

None. No `EscrowRecord` is created for cash payments —
the money was never in Platform custody.

### Settlement Impact

- No Layer 1 (Platform ↔ Organization) impact by default
  (R38: no commission on cash payments unless explicitly enabled).
- Layer 2 (Organization ↔ Provider) impact only if the Provider
  physically holds cash that must later be reconciled with the
  Organization via `record_manual_settlement()`.

### Events Emitted

1. `INVOICE_PAID_CUSTOMER`

### Failure Modes

- Admin records wrong amount.
  Must be corrected via `AdjustmentDocument` (target) —
  see Document 26.
- Provider never remits collected cash.
  Tracked as negative balance via `get_balance()`.
  R53 mandates a liability report for this case.

### Related Open Issues

[OPEN-ISSUE: OI-04] — the exact formula for Provider debt after
cash collection is inferred from code but not formally
documented as a Product Owner decision.


---

## 4. Flow: Card-to-Card Payment

**Status: Not yet implemented.** See `05_GAP_ANALYSIS.md` R40 —
Card-to-Card is currently absent as an independent payment channel.
The flow below is the target design, not the current implementation.

### Path (target)

```
State 1 → 8 → 9(skipped by default) → 10 → 11 → 15
```

Structurally identical to the Cash flow (Section 3),
but tracked under a distinct channel identity so that reporting
can distinguish "cash in hand" from "card-to-card transfer,"
per R40.

### Owner of Money

| Milestone | Owner |
|---|---|
| Before payment | Customer |
| Immediately after transfer confirmation | Organization (R37 applies by analogy) |

### Physical Holder of Money

Organization's personal or business bank account
(not the Platform's gateway account).

### Ledger Impact (target)

Same as Cash flow, but `TechnicianLedgerEntry.source` and/or
`Payment.metadata.method` must record `card_to_card` distinctly
from `cash`, to satisfy R40.

### Escrow Impact

None — same reasoning as Cash flow.

### Settlement Impact

Same as Cash flow.

### Events Emitted (target)

Same as Cash flow.

### Failure Modes (target)

Same as Cash flow, plus:

- Transfer reference cannot be verified.
  A bank reference field before recording is recommended.
  This remains a UI/process decision, not yet specified.

### Required Future Extension

- Add `CARD_TO_CARD = "card_to_card"` to
  `PaymentGateway.GatewayType` choices, per `05_GAP_ANALYSIS.md` R40.
- No model or migration change is proposed by this document —
  this section only describes the target flow shape,
  consistent with `19_DATA_MODEL.md`'s existing recommendation.

### Related Open Issues

None directly, though card-to-card is referenced as a distinct
channel requirement in R40.


---

## 5. Flow: Direct Provider Split

This flow is a variant of the Online Payment flow (Section 2)
where the Provider's share is paid directly by the PSP
(Shaparak sub-merchant split), rather than being held by the
Platform and settled later.

### Path

```
State 1 → 2 → 3 → 4 → 5 → 6(target) → 7 → 8 → 9
→ 10(direct-split variant) → 11 → 12 → 13(target) → 14(target) → 15
```

### Preconditions (existing implementation)

- `CompanyFinancialPolicy.payout_strategy = SPLIT_WITH_TECHNICIAN`
- `Technician.shaba_verified = True`
- `Technician.sub_merchant_id` is set
- `Technician.settled_technician_wage > 0`
- `PaymentGateway.owner_type = PLATFORM`
  (company-owned gateways cannot execute PSP-level splits)

### Owner of Money

| Milestone | Owner |
|---|---|
| Before split executes | Platform (custodial) |
| After split executes | Provider (direct bank deposit from PSP) |

### Physical Holder of Money

PSP transfers the Provider's share directly to the Provider's
bank account, bypassing the Platform's own bank account for
that specific portion.

### Ledger Impact

- `TechnicianLedgerEntry` CREDIT (`source=online_gateway`) —
  same as the standard flow, recording that the Organization
  owed the Provider this amount.
- `TechnicianLedgerEntry` DEBIT (`source=direct_gateway_settlement`) —
  recording that the PSP already discharged this obligation
  directly. Amount is read from
  `PaymentSplitSnapshot.technician_direct_amount`,
  never recomputed (ADR-006 §7, §8).

### Escrow Impact (target)

`EscrowRecord.provider_share_rial` should reflect that this
portion was never actually held by the Platform, or should be
marked as `SETTLED` immediately rather than progressing through
`PENDING_SETTLEMENT`.

### Settlement Impact

This amount is **excluded** from future Layer 2 settlement batches,
since it was already paid directly by the PSP.

### Events Emitted

1. Same as Online Payment flow (Section 2), plus:
2. **(target)** `provider_settlement_received`
   (emitted immediately, not at batch time)

### Failure Modes

- `PaymentSplitSnapshot` creation fails.
  `FinancialBackfillTask(PAYMENT_SPLIT_SNAPSHOT)` is created.
- Direct settlement DEBIT fails.
  `FinancialBackfillTask(DIRECT_GATEWAY_SETTLEMENT)` is created.
  It recreates the snapshot first if missing (ADR-008).
- Gateway is company-owned, not platform-owned.
  Split is blocked; falls back to the standard
  Organization-held flow.

### Related Open Issues

[OPEN-ISSUE: OI-01] — whether the selected PSP (Shaparak) supports
real-time split payment in production is not yet confirmed.
The infrastructure (`PaymentSplitSnapshot`, `sub_merchant_id`)
is designed but not yet verified end-to-end against a live PSP.


---

## 6. Flow: Failed Payment

### Path

```
State 1 → 2 → (FAILED)
State 1 → 2 → 3 → (FAILED)
```

Failure can occur either at initiation (PSP rejects the request)
or during verification (PSP confirms failure).

### Owner of Money

Customer retains ownership at all times — no transfer occurred.

### Physical Holder of Money

Customer's own bank/wallet, unaffected.

### Ledger Impact

None. No ledger entry of any kind is created for a failed payment.

### Escrow Impact

None. No `EscrowRecord` is created.

### Settlement Impact

None.

### Events Emitted

1. `PAYMENT_FAILED_CUSTOMER`

### Failure Modes (this flow describes a failure mode itself)

| Scenario | Resulting state |
|---|---|
| PSP rejects initiation | `Payment.status = FAILED` immediately, no redirect occurs |
| PSP confirms failure at verification | `Payment.status = FAILED` |
| Customer abandons before redirect | `Payment.status = CANCELLED` (distinct from FAILED) |

### Existing Implementation

`apps/payments/services.py`, `PaymentStartService.start()` and
`PaymentVerifyService.verify()` — both set `Payment.status = FAILED`
on the corresponding failure path, and create a `PaymentAttempt`
record with `AttemptStatus.FAILED` for audit purposes.

Crucially, `Invoice.status` remains `ISSUED` — the customer may
retry payment on the same invoice.


---

## 7. Flow: Amount Mismatch

### Path

```
State 1 → 2 → 3 → 4(mismatch detected) → (NEEDS_RECONCILIATION)
```

### Owner of Money

Ambiguous by design — this is precisely why the state exists.
The money has left the Customer's control according to the PSP,
but the amount does not match what the Organization expects,
so no party is assigned definitive ownership until a human
resolves the discrepancy.

### Physical Holder of Money

Likely the PSP or Platform gateway account,
but this must be confirmed manually, not assumed.

### Ledger Impact

None automatically. No ledger entry is created while status is
`NEEDS_RECONCILIATION` — this is intentional, per Principle 12
(Reconciliation) in `23_FINANCIAL_PRINCIPLES_SPECIFICATION.md`.

### Escrow Impact

None automatically created. If `EscrowRecord` existed for this
payment (unlikely, since verification did not complete normally),
its resolution would depend on manual review outcome.

### Settlement Impact

None. This invoice cannot become eligible for settlement while
its payment remains in this state.

### Events Emitted

None automatically — `NEEDS_RECONCILIATION` is a "silence by
design" state to avoid asserting an incorrect financial fact.

**(target)** A `payment_needs_reconciliation` event to notify the
Platform Owner is a reasonable extension, referenced but not
implemented, matching the pattern of other target events in
`13_SETTLEMENT_NETTING_ENGINE.md`.

### Failure Modes (this flow describes a failure/ambiguity mode)

| Trigger | Resulting state |
|---|---|
| `verified_amount != payment.amount` | `Payment.status = NEEDS_RECONCILIATION` |
| Payment older than expiration window at verification time | `Payment.status = NEEDS_RECONCILIATION` |

### Resolution Path (existing, manual)

Per `docs/04_Business_Rules/PAYMENT_RULES.md`
(referenced in prior audit work), the Platform Owner reviews
ambiguous payments at `/owner-platform/payments/operations/`
and manually decides:

- Mark as PAID (if PSP confirms payment on manual check).
- Mark as FAILED (if PSP confirms failure).
- Initiate a refund (if a duplicate payment is found).

### Related Open Issues

[OPEN-ISSUE: OI-06] — Customer overpayment is a related but
distinct scenario; see Section 9 in this document and
`26_REFUND_REVERSAL_ENGINE_SPECIFICATION.md`.


---

## 8. Flow: Refund Before Settlement

**Status: Not yet implemented.** No `RefundService` exists in the
codebase today (`05_GAP_ANALYSIS.md` R46, OI-07).
This section describes the target flow only.

### Definition of "Before Settlement"

The Escrow is still in `HELD`, `RESERVED`, or `DISTRIBUTED` state
(target model) — i.e. no `SettlementBatch` has yet executed a
transfer for this invoice.

### Path (target)

```
State 4/5/6/7/8/9/10/11 (any of these) → Refund Requested
→ AdjustmentDocument created → AdjustmentDocument APPLIED
→ EscrowRecord marked CLOSED (with refund note, not SETTLED)
```

### Owner of Money

Reverts to Customer upon successful refund execution.

### Physical Holder of Money

Still the Platform's gateway account until the refund transfer
is executed back to the Customer's original payment method.

### Ledger Impact (target)

Because settlement has not yet occurred, this is the simplest
refund case:

- `TechnicianLedgerEntry` ADJUSTMENT (reverses the wage CREDIT
  created at Invoice PAID time).
- `CompanyPlatformFeeEntry` CREDIT (`source=refund`) reverses
  the commission DEBIT, since the Platform never actually
  transferred the commission out.

### Escrow Impact (target)

`EscrowRecord.status` moves directly to `CLOSED`,
skipping `PENDING_SETTLEMENT` and `SETTLED` entirely,
since no external transfer to Organization/Provider ever occurred.

### Settlement Impact

None — the invoice is removed from settlement eligibility
(excluded per the exclusion criteria already specified in
`13_SETTLEMENT_NETTING_ENGINE.md`: "Invoices with pending
AdjustmentDocument").

### Events Emitted (target)

1. `refund_requested`
2. `refund_approved`
3. `refund_issued`

### Failure Modes (target)

- Gateway refund API call fails.
  `AdjustmentDocument` stays in `APPROVED`, not `APPLIED`,
  until retried.
- Partial ledger reversal succeeds, the other half fails.
  Must reuse the atomic-transaction plus backfill-task
  pattern already used by `InvoiceMarkPaidService`.

### Related Open Issues

[OPEN-ISSUE: OI-07] — Full Refund, Partial Refund, and Manual
Adjustment definitions are not yet finalized by the Product Owner.
This flow assumes a Full Refund; Partial Refund proportionality
rules are undefined.

[OPEN-ISSUE: OI-05] — whether the Customer becomes a
creditor/debtor as a side effect of this flow is undefined.


---

## 9. Flow: Refund After Settlement

**Status: Not yet implemented.** This is the most complex refund
scenario and is explicitly flagged as blocking further design
in `26_REFUND_REVERSAL_ENGINE_SPECIFICATION.md`.

### Definition of "After Settlement"

`EscrowRecord.status = SETTLED` or `CLOSED` (target model) —
i.e. a `SettlementBatch` has already executed a bank transfer
to the Organization and/or a direct split has already paid
the Provider.

### Path (target)

```
State 15 (Final Closed) → Refund Requested
→ AdjustmentDocument created → AdjustmentDocument APPLIED
→ New reversal ledger entries created
→ New settlement obligation created for the NEXT settlement batch
```

### Owner of Money

This is the crux of the complexity: the money has already left
Platform custody. A refund at this stage does not "undo" a
transfer — it creates a **new financial obligation** for the
Organization (and possibly the Provider) to return funds,
typically netted against their **next** settlement.

### Physical Holder of Money

Already in the Organization's or Provider's bank account.
The Platform cannot claw back funds it no longer holds
without a new transfer request.

### Ledger Impact (target)

- `CompanyPlatformFeeEntry` DEBIT (`source=refund`) —
  if commission was already recognized as revenue, reversing it
  now creates a new debt from Organization to Platform,
  since Platform must fund the customer refund from its own
  pocket, then recover that amount from the Organization.
- `TechnicianLedgerEntry` DEBIT (`source=refund`) —
  if the Provider already received payment (direct split or
  settled wage), this creates a new debt from Provider to
  Organization.
- These are **new** entries dated at refund time, never
  modifications of the original PAID-time entries
  (Principle 6 and 13 in Document 23).

### Escrow Impact (target)

The original `EscrowRecord` remains `CLOSED` and untouched
(immutability). A **new** tracking record — either a new
`EscrowRecord` in a `REFUNDED` sub-state or a dedicated
refund-tracking relationship on `AdjustmentDocument` —
is required. This is unresolved; see Open Issues below.

### Settlement Impact (target)

The reversal amounts must be included as negative contributions
in the **next** `SettlementBatch` net position calculation for
the affected Organization/Provider, per the Net Position Formula
in `13_SETTLEMENT_NETTING_ENGINE.md`.

### Events Emitted (target)

1. `refund_requested`
2. `refund_approved`
3. `refund_issued`
4. **(target)** `settlement_adjustment_scheduled`
   (signals that the next batch will include a reversal)

### Failure Modes (target)

- Organization has no positive balance to net against.
  Needs either a direct reclaim transfer or a documented
  negative-balance carry-forward policy — undefined, see OI-07.
- Provider already spent the money and cannot repay.
  Needs Organization to absorb the loss or a dispute
  process — undefined.

### Related Open Issues

[OPEN-ISSUE: OI-07] — refund-after-settlement recovery mechanics
(net against next batch vs. direct reclaim) are not defined by
the Product Owner. This document does not resolve this issue;
it only identifies where the decision is required.

[OPEN-ISSUE: OI-05] — Customer creditor/debtor status after a
refund is issued is undefined.

[OPEN-ISSUE: OI-06] — interacts with this flow when the original
payment was already an overpayment case.
