# 26 — مشخصات موتور بازپرداخت و برگشت (Refund & Reversal Engine Specification)

**Version:** v1.0 — Draft — Pending Clarification

**Purpose:**
This document defines the target architecture for refunds,
reversals, and financial corrections in the RastiSaas Financial
Engine.

**Status: Not yet implemented.** No `RefundService` exists in the
codebase today. `TechnicianLedgerEntry.Source.REFUND` is defined
as an enum value but has zero producers. This entire document
describes target design, grounded in existing patterns already
proven elsewhere in the codebase (idempotent ledger writes,
immutable entries, backfill-based recovery).

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
- `docs/13_Financial_Core/target_architecture/24_MONEY_LIFECYCLE_SPECIFICATION.md`
- `docs/13_Financial_Core/target_architecture/25_FINANCIAL_STATE_MACHINE_SPECIFICATION.md`

**This document does not resolve any Open Issue.**
Every place where a Product Owner decision is required is marked
explicitly with `[OPEN-ISSUE: OI-xx]`.

---

## Table of Contents

1. Correction Type Taxonomy
2. AdjustmentDocument Lifecycle
3. Ledger Reversal Rules
4. Escrow Reversal Rules
5. Platform Commission Reversal Rules
6. Provider Wage Reversal Rules
7. Organization Share Reversal Rules
8. Customer Balance Impact
9. Refund Before Settlement
10. Refund After Settlement
11. Refund When Provider Already Received Direct Split
12. Refund When Organization Already Received Settlement
13. Refund When Platform Commission Was Already Recognized
14. Settlement Impact
15. Required Events
16. Required Permissions
17. Required Audit Trail
18. Idempotency Rules
19. Reporting Impact
20. Open Issues Register (this document)


---

## 1. Correction Type Taxonomy

The Financial Engine must clearly separate the following correction
types. They are not interchangeable, and mixing them causes
irreversible ambiguity in the ledger.

### Full Refund

Reverses 100% of the original invoice amount back to the Customer.
Every downstream party (Platform, Organization, Provider) has
their share of that invoice fully reversed.

[OPEN-ISSUE: OI-07] — the precise trigger conditions and customer
communication requirements for a Full Refund are not yet defined
by the Product Owner.

### Partial Refund

Reverses a portion of the original invoice amount, less than the
full `total_amount`. Requires a proportionality rule to determine
how the partial amount is distributed across Platform, Organization,
and Provider reversals.

[OPEN-ISSUE: OI-07] — the proportionality formula for Partial
Refund (pro-rata vs line-item-specific vs manual allocation) is
not yet defined.

### Credit Note

Does not return money to the Customer directly. Instead, creates
a credit balance the Customer can apply against a **future**
invoice. Requires `CustomerFinancialAccount`
(target, not yet designed — blocked on
[OPEN-ISSUE: OI-05]).

### Debit Note

The inverse of a Credit Note — records that the Customer owes
additional money beyond the original invoice (for example,
a service that ran over its originally quoted amount).
Also requires `CustomerFinancialAccount`.

### Manual Adjustment

A catch-all correction type for cases that do not fit the above,
used when an authorized Admin needs to correct a clerical or
calculation error without it being framed as a "refund"
(e.g., correcting a wage-percentage misapplication after the
fact). Closest existing precedent:
`TechnicianLedgerService.record_manual_settlement()` with
`direction=ADJUSTMENT_CREDIT` or `ADJUSTMENT_DEBIT`.

### Customer Overpayment

The Customer paid more than `invoice.total_amount`. Distinct from
a refund because no error occurred in the invoice itself — the
excess amount requires a decision on disposition (return, credit,
or wallet).

[OPEN-ISSUE: OI-06] — disposition of Customer overpayment
(refund the excess, credit balance, or wallet) is not yet decided.

### Customer Underpayment Attempt

The Customer attempted to pay less than `invoice.total_amount`.
This is **not** a correction type requiring `AdjustmentDocument` —
it is already fully blocked by existing code
(R47, `05_GAP_ANALYSIS.md`):
`PaymentVerifyService.verify()` routes amount mismatches to
`NEEDS_RECONCILIATION` rather than accepting a partial payment
as `PAID`. No further design is required here; it is documented
for completeness of the taxonomy only.


---

## 2. AdjustmentDocument Lifecycle

The full state machine for `AdjustmentDocument` is defined in
`25_FINANCIAL_STATE_MACHINE_SPECIFICATION.md` §6. This section
adds refund-specific detail on top of that state machine.

### Document Type Field

Every `AdjustmentDocument` carries a `document_type` from
Section 1 of this document:
`full_refund`, `partial_refund`, `credit_note`, `debit_note`,
`manual_adjustment` — matching the choices already sketched in
`19_DATA_MODEL.md`.

### Creation Step

An `AdjustmentDocument` is created in `DRAFT` status referencing
`original_invoice` (which must be `PAID`) and a required `reason`.
At creation time, the system should compute — but not yet apply —
the proposed reversal amounts:

- `technician_wage_reversal`
- `platform_fee_reversal`
- `company_share_reversal`

These are computed fields shown to the approver before approval,
never applied until the document reaches `APPLIED`.

### Approval Step

Moves `DRAFT → PENDING_APPROVAL → APPROVED`.

[OPEN-ISSUE: OI-08] — whether this requires a single approver or
a two-step (maker-checker) approval workflow is undecided by the
Product Owner. This document assumes single-approver by default,
consistent with existing `record_manual_settlement()` behavior,
but flags this explicitly as unresolved.

### Application Step

Moves `APPROVED → APPLIED`. This is the only step that creates
new ledger entries. It must be atomic: either all required
reversal entries are created successfully, or none are, with
partial failures recovered via `FinancialBackfillTask`
(see `25_FINANCIAL_STATE_MACHINE_SPECIFICATION.md` §6,
Failure Handling).

### Rejection Step

Moves `PENDING_APPROVAL → REJECTED`. No ledger effect. Terminal.

### Cancellation Step

Moves `DRAFT → CANCELLED`. No ledger effect. Terminal.
Available only before submission for approval.


---

## 3. Ledger Reversal Rules

These rules govern how `TechnicianLedgerEntry` and
`CompanyPlatformFeeEntry` are reversed. They are direct
applications of Principle 6 (Immutable Ledger) and Principle 13
(Correction through Reversal, not Mutation) from
`23_FINANCIAL_PRINCIPLES_SPECIFICATION.md`.

### Rule 3.1 — Never Edit, Always Create

No refund or adjustment may ever call `.save()` on an existing
`TechnicianLedgerEntry` or `CompanyPlatformFeeEntry` row with
changed `amount_rial` or `balance_after`. This is already
enforced at the model level and must never be bypassed.

### Rule 3.2 — Reversal Direction Mirrors Original

If the original entry was a CREDIT, the reversal is a DEBIT of
the same amount (or the applicable partial amount), and vice
versa. This preserves the property that
`get_balance()` (SUM of credits minus SUM of debits) always
reflects the true net position after reversal.

### Rule 3.3 — Reversal Source is `refund` or `adjustment`

Reversal entries must use
`TechnicianLedgerEntry.Source.REFUND` or
`TechnicianLedgerEntry.Source.ADJUSTMENT`
(both already defined in `apps/payouts/models.py`),
never reuse the original entry's source
(e.g. `online_gateway`), so that reporting can distinguish
original transactions from corrections.

### Rule 3.4 — Reversal Amount is Read from AdjustmentDocument

Consistent with the Authoritative Source Rule
(ADR-006 §7, referenced in `04_DOMAIN_MODEL.md`), the reversal
entry's amount must be read from
`AdjustmentDocument.technician_wage_reversal` or
`.platform_fee_reversal`, never recomputed independently at
application time and never derived by reading the original
ledger entry's `amount_rial`.

### Rule 3.5 — Metadata Links Back to the AdjustmentDocument

The reversal entry's `metadata` JSONField must include the
`AdjustmentDocument.id`, enabling full traceability from any
ledger row back to the correction that produced it.


---

## 4. Escrow Reversal Rules

These rules apply only when `EscrowRecord` (target) exists for
the affected payment — i.e. online payments through a
platform-owned gateway. Cash and card-to-card payments never
create an `EscrowRecord` (per `24_MONEY_LIFECYCLE_SPECIFICATION.md`
§3–4) and are therefore unaffected by this section.

### Rule 4.1 — Original EscrowRecord is Never Reopened

If `EscrowRecord.status` is already `SETTLED` or `CLOSED`, a
refund must never transition that same record backward to an
earlier state. The original record remains untouched, consistent
with Principle 6.

### Rule 4.2 — Refund Before Settlement Closes the Original Record

If `EscrowRecord.status` is `HELD`, `RESERVED`, or `DISTRIBUTED`
(i.e. before `SettlementBatch` execution), applying the
`AdjustmentDocument` transitions the `EscrowRecord` directly to
`CLOSED`, skipping `PENDING_SETTLEMENT` and `SETTLED` entirely —
because no external transfer to Organization/Provider ever
occurred for that money.

### Rule 4.3 — Refund After Settlement Requires a New Record

If `EscrowRecord.status` is `SETTLED` or `CLOSED`, the refund
cannot reuse or reopen that record. A new tracking mechanism is
required.

[OPEN-ISSUE: OI-07] — whether this new tracking mechanism is a
second `EscrowRecord` in a `REFUNDED` sub-state, or a dedicated
field on `AdjustmentDocument` itself, is not yet decided by the
Product Owner. This document identifies the gap but does not
resolve it.

### Rule 4.4 — Amount Breakdown Must Still Sum Correctly

Whatever reversal tracking mechanism is chosen, the invariant
`platform_commission_rial + organization_share_rial +
provider_share_rial = amount_rial` (defined for the original
`EscrowRecord` in `19_DATA_MODEL.md`) must hold for the reversal
amounts as well, scoped to whatever portion is being refunded
(full or partial).


---

## 5. Platform Commission Reversal Rules

### Rule 5.1 — Reversal Only If Commission Was Actually Recognized

A `CompanyPlatformFeeEntry` CREDIT reversal is only created if a
corresponding DEBIT entry exists for the original invoice
(i.e. the 4-condition ADR-003 gate previously passed). If the
Platform never recognized commission on this invoice (e.g. it
was a cash payment with no commission), no commission reversal
is needed or created.

### Rule 5.2 — Reversal Amount Is Proportional for Partial Refunds

For a Partial Refund, the commission reversal amount is:

```
commission_reversal = original_commission_debit
                       × (refund_amount / invoice.total_amount)
```

[OPEN-ISSUE: OI-07] — whether this strict proportionality formula
is the Product Owner's intended rule, or whether commission
should be reversed in full regardless of refund percentage (to
avoid the Platform "keeping" a share of a partially-refunded
transaction), is not yet decided.

### Rule 5.3 — Reversal Before vs After Settlement (Layer 1)

If the commission DEBIT has not yet been included in a completed
`SettlementBatch` (Layer 1), the reversal simply creates an
offsetting CREDIT — no bank-level transfer has occurred, so no
money physically moves.

If the commission was already included in a `COMPLETED`
`SettlementBatch`, see Section 13 (Refund When Platform
Commission Was Already Recognized) for the more complex case
where money must be recovered from a batch that already executed.


---

## 6. Provider Wage Reversal Rules

### Rule 6.1 — Reversal Amount Read from AdjustmentDocument

Per Rule 3.4, the `TechnicianLedgerEntry` DEBIT reversal amount
is read from `AdjustmentDocument.technician_wage_reversal`,
which itself was computed from `invoice.settled_technician_wage`
at the time the `AdjustmentDocument` was drafted — never
recomputed from current wage percentages, consistent with
Principle 9 (Forward-only Policy Changes).

### Rule 6.2 — Distinguish Direct-Split from Ledger-Held Wage

The reversal logic must check whether the original wage was paid
via direct PSP split (`PaymentSplitSnapshot.should_split_with_technician
= True`) or held on the ledger for later settlement. These two
cases require fundamentally different reversal mechanics:

- **Ledger-held case:** create a `TechnicianLedgerEntry` DEBIT
  with `source=refund`. This simply reduces the Provider's
  outstanding balance — no external money movement is required
  because the Provider never received a direct transfer.
- **Direct-split case:** see Section 11
  (Refund When Provider Already Received Direct Split) —
  the Provider has already been paid externally by the PSP,
  and recovering that amount is a materially different problem.

### Rule 6.3 — Partial Refund Wage Proportionality

For Partial Refund, the wage reversal amount follows the same
proportional formula pattern as Section 5, applied to
`settled_technician_wage` instead of the commission amount.

[OPEN-ISSUE: OI-07] — as with commission, whether proportional
reversal is correct, or whether a different allocation is
intended (e.g. line-item-specific refunds reversing only the
wage tied to the specific refunded line items), is undecided.


---

## 7. Organization Share Reversal Rules

### Rule 7.1 — No Dedicated Ledger for Organization Share Today

Unlike Provider wage and Platform commission, the Organization's
share (`invoice.settled_company_share`) has no dedicated ledger
model today — it is implicitly "whatever remains" after commission
and wage are accounted for. A refund reversal for the Organization
share therefore has no existing ledger table to write to.

[OPEN-ISSUE: OI-07] — whether a dedicated
`OrganizationLedgerEntry` model (symmetric to
`TechnicianLedgerEntry`) should be introduced as part of the
refund engine, or whether the Organization share reversal should
instead be handled purely through the `SettlementBatch` net
position calculation, is not yet decided by the Product Owner.
This document flags the gap without proposing a specific model.

### Rule 7.2 — Reversal Must Still Be Computed and Recorded

Even without a dedicated ledger, `AdjustmentDocument.
company_share_reversal` must still be computed and stored on the
`AdjustmentDocument` itself, so that the amount is available for:

- Reporting (Section 19 of this document).
- Inclusion in the next `SettlementBatch` net position calculation
  as a negative contribution, per Rule 14.1.

### Rule 7.3 — Consistency Check

At application time, the three reversal amounts must satisfy:

```
technician_wage_reversal + platform_fee_reversal
    + company_share_reversal == refund_amount_rial
```

This mirrors the same consistency check already performed at
original settlement time in
`InvoiceSettlementService.settle()`
(`13_SETTLEMENT_NETTING_ENGINE.md` references this as a
non-blocking sanity guard for future regressions — the refund
engine should apply the same guard).


---

## 8. Customer Balance Impact

### Current State

No `CustomerFinancialAccount` or equivalent wallet/balance model
exists in the codebase today (`05_GAP_ANALYSIS.md` R46 — MISSING).
`apps/accounts/models.Customer` has no balance-related fields.

### Impact by Correction Type

| Correction type | Customer balance impact |
|---|---|
| Full Refund | Money returned via original payment method; no residual balance |
| Partial Refund | Money returned via original payment method; no residual balance |
| Credit Note | Customer becomes a creditor — requires `CustomerFinancialAccount` |
| Debit Note | Customer becomes a debtor — requires `CustomerFinancialAccount` |
| Manual Adjustment | Depends on nature; may or may not touch customer balance |
| Overpayment | Undecided — see OI-06 |

[OPEN-ISSUE: OI-05] — the complete list of scenarios under which
a Customer becomes a creditor or debtor is not yet defined by the
Product Owner. This document cannot design
`CustomerFinancialAccount` without that list, per the instruction
not to invent Product Owner decisions.

[OPEN-ISSUE: OI-06] — Customer overpayment disposition
(refund the excess, credit balance, or wallet) directly determines
whether Credit Note functionality must exist before or after
Full/Partial Refund functionality is built.

### Non-Design Statement

This document intentionally does **not** propose a
`CustomerFinancialAccount` schema, because doing so would require
inventing the very Product Owner decisions that OI-05 and OI-06
represent. Once those Open Issues are resolved, this section must
be revisited and expanded with a concrete data model.


---

## 9. Refund Before Settlement

**Scenario:** `EscrowRecord.status` is `HELD`, `RESERVED`, or
`DISTRIBUTED` (target) — no `SettlementBatch` has executed yet.

This is the simplest case. Full detail already given in
`24_MONEY_LIFECYCLE_SPECIFICATION.md` §8. Summary for this
document's context:

- Ledger reversal: straightforward CREDIT/DEBIT offsets, no
  external transfer has occurred yet for either commission or
  wage (unless a direct split already happened — see Section 11).
- Escrow reversal: Rule 4.2 applies — `EscrowRecord` closes
  directly without ever reaching `SETTLED`.
- Settlement impact: none — the invoice is simply excluded from
  future settlement eligibility (already specified as an
  exclusion criterion in
  `13_SETTLEMENT_NETTING_ENGINE.md`).

## 10. Refund After Settlement

**Scenario:** `EscrowRecord.status` is `SETTLED` or `CLOSED`
(target) — a `SettlementBatch` has already transferred funds to
the Organization, and/or a direct split already paid the
Provider.

This is the complex case, already introduced in
`24_MONEY_LIFECYCLE_SPECIFICATION.md` §9. This document adds the
reversal-mechanics detail:

- Ledger reversal: Rules 3.1–3.5 apply; new DEBIT/CREDIT entries
  are dated at refund time, never backdated to the original
  transaction.
- Escrow reversal: Rule 4.3 applies — a new tracking mechanism is
  required since the original record cannot be reopened.
- Settlement impact: Rule 14.1 — reversal amounts must be included
  as negative contributions in the **next** `SettlementBatch` net
  position calculation for the affected Organization/Provider.

[OPEN-ISSUE: OI-07] — the recovery mechanics
(net against next batch vs. direct reclaim transfer request) are
not defined by the Product Owner. See also Section 4, Rule 4.3.


---

## 11. Refund When Provider Already Received Direct Split

**Scenario:** `PaymentSplitSnapshot.should_split_with_technician
= True` — the PSP (Shaparak) already transferred the Provider's
share directly to the Provider's bank account, bypassing the
Platform entirely for that portion (per
`24_MONEY_LIFECYCLE_SPECIFICATION.md` §5).

### Why This Is Materially Different

In the Ledger-Held case (Rule 6.2), reversing the Provider's
wage CREDIT is sufficient — no money ever left the Platform's
custody for that portion. In the Direct-Split case, the Platform
has no money to reverse from; the Provider's bank account
already received the funds directly from the PSP.

### Required Reversal Mechanics (target)

- The `TechnicianLedgerEntry` DEBIT with
  `source=direct_gateway_settlement` (created at original
  payment time, per ADR-006 §8) is **not** itself reversible in
  isolation — reversing it alone would incorrectly suggest the
  Platform still owes the Provider that amount.
- Instead, a **new** DEBIT with `source=refund` must be created,
  representing a fresh claim: the Provider now owes the
  Organization (or Platform) this amount back, because the
  underlying service was refunded to the Customer after the
  Provider was already paid.
- This effectively creates Provider debt, to be recovered through
  the same manual settlement or future-wage-offset mechanisms
  already used for cash-collection debt
  (`record_manual_settlement()`), per Rule 6.2's Ledger-Held
  case, applied retroactively.

### Related Open Issues

[OPEN-ISSUE: OI-04] — the exact formula and recovery timeline for
Provider debt (originally scoped to cash-collection scenarios) may
need to be extended to cover this refund-driven debt scenario as
well; this is not yet confirmed by the Product Owner.

[OPEN-ISSUE: OI-07] — whether the Platform or the Organization is
responsible for pursuing recovery from the Provider in this
scenario is undecided.


---

## 12. Refund When Organization Already Received Settlement

**Scenario:** A `SettlementBatch(level=PLATFORM_TO_ORG)` has
already reached `COMPLETED` status (target), meaning the Platform
has already transferred the Organization's net share to the
Organization's bank account.

### Required Reversal Mechanics (target)

- The Platform cannot claw back funds it no longer holds without
  initiating a new transfer request.
- Per Rule 14.1, the reversal amount
  (`company_share_reversal` + any commission portion the
  Organization is expected to help fund) becomes a **negative
  contribution** to the next `SettlementBatch` net position
  calculation for that Organization.
- If the Organization's next settlement period has insufficient
  positive balance to absorb the reversal, a shortfall exists.

[OPEN-ISSUE: OI-07] — how a shortfall is handled (carried forward
to the following period, direct reclaim invoice sent to the
Organization, or another mechanism) is not defined by the Product
Owner. This document identifies the gap without resolving it.

### Interaction with Platform Commission

If the Platform already recognized commission on this invoice
(Section 13) and that commission was itself already transferred
in a completed batch, the reversal chain becomes: Platform must
first recover commission from itself (an accounting entry, not a
real bank transfer, since Platform never sends commission
anywhere), then separately recover the Organization's share via
the next batch's net position, as described above.


---

## 13. Refund When Platform Commission Was Already Recognized

**Scenario:** `CompanyPlatformFeeEntry` DEBIT was already created
for this invoice (Rule 5.1's precondition was satisfied at
original payment time), meaning the Platform has already
recognized this commission as revenue per Principle 7
(Revenue Recognition, Document 23).

### Required Reversal Mechanics (target)

- A `CompanyPlatformFeeEntry` CREDIT with `source=refund` must be
  created, reducing the Organization's outstanding commission
  balance (or, if already settled via a completed
  `SettlementBatch`, becoming a negative contribution to the
  Organization's next Layer 1 net position — same mechanism as
  Section 12).
- This CREDIT amount follows the proportionality rule in
  Rule 5.2 for Partial Refunds, or the full original DEBIT amount
  for Full Refunds.
- Because the Platform never physically "returns" commission
  money anywhere (it is a percentage the Platform itself has
  already effectively pocketed by not forwarding it), this
  reversal is purely an internal accounting correction —
  it does not, by itself, trigger any bank transfer. It only
  changes the net amount the Platform owes the Organization
  in the next settlement cycle.

### Revenue Recognition Consequence

This reversal means the Platform's previously-recognized revenue
for this invoice is retroactively reduced. Financial reporting
(Section 19 of this document, and R54 in
`05_GAP_ANALYSIS.md`) must reflect this as a distinct
"refunded commission" line item, not silently netted away,
so that historical revenue reports remain explainable
(Principle 10, Financial Auditability).

### Related Open Issues

[OPEN-ISSUE: OI-07] — whether commission reversal timing must be
synchronized with the Customer-facing refund timing, or can lag
until the next settlement cycle, is not decided by the Product
Owner.


---

## 14. Settlement Impact

### Rule 14.1 — Reversals Feed the Next Batch's Net Position

For any refund that occurs after settlement has already
completed, the reversal amounts must be added as **negative**
contributions to the Net Position Formula already defined in
`13_SETTLEMENT_NETTING_ENGINE.md`:

```
NET_POSITION_L1(company, period) =
    Σ(invoice.total_amount)
  − Σ(CompanyPlatformFeeEntry.amount_rial WHERE entry_type=DEBIT)
  − Σ(PaymentSplitSnapshot.technician_direct_amount)
  − Σ(refund reversals applicable to this period)   ← new term
```

### Rule 14.2 — Refunds Before Settlement Simply Exclude the Invoice

For any refund that occurs before settlement, no net position
adjustment is needed — the invoice is simply excluded from the
eligible-invoices query entirely
(already specified as an exclusion criterion for pending
`AdjustmentDocument` in
`13_SETTLEMENT_NETTING_ENGINE.md` — Settlement Item Selection
Rules).

### Rule 14.3 — SettlementItem Traceability

If a refund's reversal is included in a `SettlementBatch`'s net
position, a corresponding `SettlementItem` should reference the
`AdjustmentDocument` (not just the original `Invoice`), so the
batch's audit trail clearly shows which items are original
invoices and which are refund reversals.

[OPEN-ISSUE: OI-07] — whether `SettlementItem` needs a new FK
to `AdjustmentDocument`, or whether the existing `invoice` FK is
sufficient (relying on `AdjustmentDocument.original_invoice` for
the join), is a data-modeling decision not yet made, pending
resolution of the broader refund-after-settlement design.

---

## 15. Required Events

| Event | Trigger |
|---|---|
| `refund_requested` | `AdjustmentDocument` moves to `PENDING_APPROVAL` |
| `refund_approved` | `AdjustmentDocument` moves to `APPROVED` |
| `refund_issued` | `AdjustmentDocument` moves to `APPLIED` |
| `refund_rejected` | `AdjustmentDocument` moves to `REJECTED` (internal notification, low severity) |
| `settlement_adjustment_scheduled` | Reversal is queued for inclusion in the next `SettlementBatch` (Rule 14.1) |

These extend the existing event catalog
(`apps/notifications/event_catalog.py`) using the same pattern
as `INVOICE_PAID_CUSTOMER` and `PAYMENT_SUCCESS_CUSTOMER` —
no new event delivery mechanism is required.


---

## 16. Required Permissions

Following the existing pattern of
`@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")`
already used for settlement views
(`apps/payouts/views.py`), and R48
(only Admin/Operators with appropriate permissions may modify
financial policies):

| Action | Minimum required role |
|---|---|
| Create `AdjustmentDocument` (DRAFT) | `COMPANY_ADMIN` or `COMPANY_STAFF` |
| Approve `AdjustmentDocument` | `COMPANY_ADMIN` (proposed; see OI-08) |
| Apply (execute) `AdjustmentDocument` | System-triggered upon approval; no separate human action |
| View refund history / reports | `COMPANY_ADMIN`, `COMPANY_STAFF`, `PLATFORM_OWNER` |
| Resolve refund-after-settlement shortfalls | `PLATFORM_OWNER` only (cross-tenant financial exposure) |

[OPEN-ISSUE: OI-08] — whether Approval requires a role distinct
from Creation (maker-checker separation of duties) is not decided
by the Product Owner. The table above reflects the minimum
existing role vocabulary and should not be read as a final
decision.

---

## 17. Required Audit Trail

Per Principle 10 (Financial Auditability) and R50
(every financial modification must be fully recorded in an audit
log):

- `AdjustmentDocument.created_by` and `created_at` — who drafted
  the correction and when.
- `AdjustmentDocument.approved_by` and `approved_at` — who
  approved it and when.
- `AdjustmentDocument.reason` — mandatory, non-empty justification.
- Every reversal ledger entry's `metadata` field must reference
  `AdjustmentDocument.id` (Rule 3.5).
- `AdjustmentDocument.applied_at` — exact timestamp reversal
  entries were created.

This reuses the existing audit pattern already present on
`CompanyMerchantProfile` (`reviewed_by`, `reviewed_at`,
`review_note`) rather than introducing a new audit mechanism.


---

## 18. Idempotency Rules

Consistent with Principle 11 (Idempotency, Document 23) and the
existing pattern of `idempotency_key` on
`TechnicianLedgerEntry` and `CompanyPlatformFeeEntry`:

### Rule 18.1 — Application Idempotency Key

`adjustment:{document_id}:apply` — checked before creating any
reversal ledger entry, guarding against double-application if
the applying service is retried after a partial failure.

### Rule 18.2 — Per-Entry Idempotency Keys

Each reversal entry created during application must have its own
deterministic key, following the existing naming convention:

- `adjustment:{document_id}:technician_wage_reversal`
- `adjustment:{document_id}:platform_fee_reversal`

### Rule 18.3 — Retry Handlers Never Pre-Check

Consistent with ADR-008's binding rule (referenced in
`25_FINANCIAL_STATE_MACHINE_SPECIFICATION.md` §6), a retry
handler for a failed adjustment application must call the
underlying reversal-writing service unconditionally and rely
entirely on the service's own idempotency check —
never pre-checking "has this already been done?" at the handler
level.

### Rule 18.4 — At Most One Active Adjustment Per Invoice Per Type

To avoid ambiguity, at most one `AdjustmentDocument` in
`DRAFT`, `PENDING_APPROVAL`, or `APPROVED` status should exist per
`(original_invoice, document_type)` combination — mirroring the
existing pattern for `InvoiceCancellationRequest`
(only one PENDING request per invoice, enforced by a partial
unique index).

[OPEN-ISSUE: OI-07] — whether multiple **different** correction
types can be simultaneously active on the same invoice (e.g. a
Partial Refund and a separate Debit Note) is not decided by the
Product Owner.


---

## 19. Reporting Impact

### Platform Commission Report (R54)

Must show refunded commission as a distinct line item
(per Section 13), never silently netted into the gross commission
total, so the report remains explainable.

### Provider Liability Report (R53)

Must reflect new Provider debt created by Section 11's
direct-split reversal scenario, alongside the existing
cash-collection debt scenario already covered by this report
per `05_GAP_ANALYSIS.md` R53.

### Settlement Status Report (R55)

Must distinguish `SettlementItem` rows originating from original
invoices versus those originating from refund reversals
(Rule 14.3), once that data-modeling decision is resolved.

### New Report Requirement: Refund History Report

Not previously specified in R53–R56. This document proposes a
new mandatory report:

| Field | Source |
|---|---|
| Adjustment # | `AdjustmentDocument.id` |
| Original Invoice | `AdjustmentDocument.original_invoice` |
| Type | `AdjustmentDocument.document_type` |
| Amount | `AdjustmentDocument.amount_rial` |
| Status | `AdjustmentDocument.status` |
| Reason | `AdjustmentDocument.reason` |
| Created By / Approved By | audit fields |

[OPEN-ISSUE: OI-09] — whether this Refund History Report is part
of the "most comprehensive financial reporting possible" KPI
catalog the Product Owner has requested is not yet confirmed,
since the KPI catalog itself remains undefined.


---

## 20. Open Issues Register (this document)

The table below consolidates every Open Issue referenced in this
document. None of these issues are resolved here — each entry
states the exact question that remains for the Product Owner.

**[OPEN-ISSUE: OI-04]**
Does the Provider debt formula, originally scoped to cash
collection, extend to refund-driven direct-split recovery?
See Section 11.

**[OPEN-ISSUE: OI-05]**
What is the complete list of scenarios where a Customer becomes
a creditor or debtor? See Section 8.

**[OPEN-ISSUE: OI-06]**
How should Customer overpayment be resolved: refund, credit,
or wallet? See Section 1 and Section 8.

**[OPEN-ISSUE: OI-07]**
What are the Full/Partial Refund definitions, proportionality
formulas, shortfall handling rules, and reversal-tracking data
model? See Sections 1, 3 through 7, 9 through 14, and 18.

**[OPEN-ISSUE: OI-08]**
Does adjustment approval require a two-step, maker-checker
workflow? See Section 2 and Section 16.

**[OPEN-ISSUE: OI-09]**
Is the proposed Refund History Report part of the Platform's
KPI catalog? See Section 19.

### Explicit Non-Resolution Statement

This document identifies exactly where each Open Issue blocks a
specific design decision. It does not propose a default behavior
for any of them beyond what is already explicitly implemented in
the existing codebase (e.g. R47's existing block on underpayment).
Any design choice not already backed by existing code or a Locked
Business Rule (R01–R56) is marked as pending Product Owner input.
