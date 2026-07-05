# 23 — مشخصات اصول مالی (Financial Principles Specification)

**Version:** v1.0 — Draft — Pending Clarification

**Purpose:**
This document defines the core financial principles that govern the
RastiSaas Financial Engine.

Every future financial feature must be evaluated against these principles
before implementation.

**Terminology mapping used throughout this document:**

| Domain term | Codebase term |
|---|---|
| Organization | Company (`apps/tenants/models.Company`) |
| Provider | Technician (`apps/accounts/models.Technician`) |
| Platform | RastiSaas platform owner (system-level, no dedicated model) |
| Customer | `apps/accounts/models.Customer` |

**Grounding:**
This document is derived from:

- `docs/13_Financial_Core/05_GAP_ANALYSIS.md`
- `docs/13_Financial_Core/target_architecture/04_DOMAIN_MODEL.md`
- `docs/13_Financial_Core/target_architecture/13_SETTLEMENT_NETTING_ENGINE.md`
- `docs/13_Financial_Core/target_architecture/19_DATA_MODEL.md`

No new business rule is invented here.
Every principle traces back to R01–R56 or to a documented Open Issue.

---

## Table of Contents

1. Money Movement vs Money Meaning
2. Legal Money Ownership
3. Platform as Escrow Holder, not Seller of Record
4. Organization as Invoice Issuer
5. Provider as Payable Recipient
6. Immutable Ledger
7. Revenue Recognition
8. Settlement Netting
9. Forward-only Policy Changes
10. Financial Auditability
11. Idempotency
12. Reconciliation
13. Correction through Reversal, not Mutation
14. Tenant Isolation
15. Event-driven Financial Transitions


---

## 1. Money Movement vs Money Meaning

### Principle Statement

The physical movement of money and the legal meaning of money are
two separate concerns.

A `Payment` record proves that money moved.

It does not, by itself, determine who owns that money,
who is entitled to it, or how it should be distributed.

### Why It Matters

Conflating "money moved" with "money is mine" causes systems to:

- Recognize revenue too early.
- Miss commission obligations.
- Lose the ability to reverse a transaction cleanly.

Separating the two concerns allows the engine to freeze a payment event
(`Payment.status = PAID`) independently from the financial interpretation
of that event (ledger entries, escrow state, settlement shares).

### Existing Implementation Mapping

- `apps/payments/models.py` — `Payment` records only the transaction fact:
  `status`, `amount`, `gateway`, `tracking_code`.
- `apps/payouts/models.py` — `TechnicianLedgerEntry` and
  `CompanyPlatformFeeEntry` record the *meaning* of that payment
  (who is owed what).
- `apps/invoices/services_settlement.py` — `InvoiceSettlementService.settle()`
  is the explicit translation step between "payment happened"
  and "here is who gets what."

### Required Future Extension

- `EscrowRecord` (target, not yet implemented) must formalize the
  ownership state between "money moved" and "money was distributed."
  See `04_DOMAIN_MODEL.md` §9.

### Related Business Rules

R01, R02, R05, R09, R37, R45.

### Related Open Issues

None directly. `EscrowRecord` design supports future OI-06/OI-07 work.


---

## 2. Legal Money Ownership

### Principle Statement

At every point in time, exactly one Financial Party
(Platform, Organization, or Provider) must be identifiable
as the current legal owner of a given amount of money,
even while another party physically holds it.

### Why It Matters

Physical custody and legal ownership are not the same thing.

The Platform may physically hold customer funds in its bank account
while legally owing that money to the Organization and Provider.

Without this principle, financial reporting cannot answer
"how much of our bank balance is actually ours?"

### Existing Implementation Mapping

- `apps/payments/models.py`, `PaymentGateway.OwnerType` —
  distinguishes `platform`-owned gateways from `company`-owned gateways.
- `apps/payouts/services_split.py` —
  `PaymentSplitDecisionService.compute()` calculates
  `company_deposit_amount`, `technician_direct_amount`,
  and `platform_fee_amount` as three distinct legal claims
  on the same physical payment.
- `apps/invoices/models.py` — `settled_technician_wage` and
  `settled_company_share` freeze the legal split at PAID time.

### Required Future Extension

- `EscrowRecord` model (target) must explicitly track:
  `platform_commission_rial`, `organization_share_rial`,
  `provider_share_rial` as separate, queryable fields.
  See `19_DATA_MODEL.md` — EscrowRecord.
- Currently the Platform cannot query
  "total funds legally owed to others" as a single number.

### Related Business Rules

R01, R05, R09, R21, R37, R45.

### Related Open Issues

[OPEN-ISSUE: OI-05] — customer-side ownership (creditor/debtor) is undefined.

[OPEN-ISSUE: OI-06] — ownership state during overpayment is undefined.


---

## 3. Platform as Escrow Holder, not Seller of Record

### Principle Statement

The Platform never acts as the seller of the underlying service.

The Platform is a temporary custodian of customer funds
until those funds are distributed to the Organization and Provider.

The only revenue the Platform is entitled to keep
is its commission (`CompanyPlatformFeeEntry` DEBIT amount).

### Why It Matters

If the Platform were treated as the seller of record,
it would be legally and tax-wise responsible for the full
transaction amount, not just its commission.

This principle protects the Organization's status as the
actual merchant of record for the customer.

### Existing Implementation Mapping

- `apps/invoices/models.py` — `Invoice.company` is mandatory;
  every invoice is issued by an Organization, never by the Platform.
- `apps/payouts/models.py` — `CompanyPlatformFeeEntry` records
  only commission amounts, never the full transaction amount.
- `apps/billing/models.py` — `BillingRecord` is a fully separate
  model for Platform-to-SaaS-subscription billing,
  confirming the Platform's revenue is structurally isolated
  from customer transaction revenue.

### Required Future Extension

- `EscrowRecord.status` lifecycle (`held → reserved → distributed →
  pending_settlement → settled → closed`) must make the custodial
  role explicit and queryable.
  See `04_DOMAIN_MODEL.md` §9.

### Related Business Rules

R01, R02, R03, R04, R05.

### Related Open Issues

None directly.


---

## 4. Organization as Invoice Issuer

### Principle Statement

The Organization is always the legal issuer of the customer-facing invoice.

The Provider (Technician) never issues an invoice in their own name.

### Why It Matters

Customers must have a single, consistent legal counterparty
for tax receipts, disputes, and refunds — the Organization.

Provider identity is operationally useful (assignment, wage calculation)
but must never surface as the invoice issuer.

### Existing Implementation Mapping

- `apps/invoices/models.py`, line 21 — `Invoice.company`
  is a mandatory field via `CompanyOwnedModel`.
- `apps/invoices/models.py`, line 90 — `technician_name_snapshot`
  and `technician_phone_snapshot` are supplementary display fields only.
- `apps/invoices/models.py`, line 181 — `footer_text` default text
  explicitly states the service provider (Organization) bears
  responsibility for the invoice.
- `apps/invoices/services.py`, line 131 —
  `InvoiceCreateService.create()` requires a `company` parameter;
  there is no code path to create an invoice without one.

### Required Future Extension

None. This principle is fully satisfied by the existing implementation.

### Related Business Rules

R02, R03, R04.

### Related Open Issues

None.

---

## 5. Provider as Payable Recipient

### Principle Statement

The Provider (Technician) is a payee, not a party to the customer contract.

The Provider's financial relationship exists only with the Organization,
represented by `TechnicianLedgerEntry`,
never directly with the Customer.

### Why It Matters

This keeps the customer-facing contract simple (Customer ↔ Organization)
while allowing the Organization to manage arbitrarily complex
internal wage-sharing arrangements with Providers.

It also means a Provider's compensation is never contingent
on the Customer's payment method choice
(cash vs online vs card-to-card).

### Existing Implementation Mapping

- `apps/payouts/models.py`, line 16 — `TechnicianLedgerEntry`
  links `company` and `technician`, never `customer`.
- `apps/invoices/services_wage.py` —
  wage is calculated from `invoice.settled_technician_wage`,
  which is derived from the invoice's own line items,
  not from how the customer chose to pay.
- ADR-006 §4 (referenced in `05_GAP_ANALYSIS.md`) —
  confirms Provider compensation is independent of
  customer payment behaviour.

### Required Future Extension

None for the core principle.

`EscrowRecord.provider_share_rial` (target) will make the
Provider's legal claim on escrowed funds explicit
before settlement occurs.

### Related Business Rules

R16, R17, R20, R21, R27, R37.

### Related Open Issues

[OPEN-ISSUE: OI-04] — exact formula for Provider debt to
Organization (e.g. after collecting cash) is not yet
formally documented as a business rule, only inferred from code.


---

## 6. Immutable Ledger

### Principle Statement

Once a financial ledger entry is created, it can never be edited
or deleted.

Every correction must be represented as a new, separate entry,
never as a mutation of history.

### Why It Matters

Financial history must be reconstructable at any point in time.

If entries could be edited, past reports would silently
become invalid, and audits would become impossible to trust.

### Existing Implementation Mapping

- `apps/payouts/models.py`, line 108 —
  `TechnicianLedgerEntry.delete()` unconditionally raises
  `PermissionError`.
- `apps/payouts/models.py`, line 267 —
  `CompanyPlatformFeeEntry.delete()` — identical enforcement.
- `apps/payouts/models.py` —
  `save()` on both models blocks any change to
  `amount_rial` or `balance_after` once a row has a primary key.
- `apps/invoices/models.py`, line 255 —
  `Invoice.recalculate_totals()` raises `ValueError` if the
  invoice status is already `PAID`.

### Required Future Extension

- `AdjustmentDocument` (target) must be the only sanctioned mechanism
  for correcting a PAID invoice's financial outcome —
  by creating new reversal ledger entries,
  never by touching the original entries.
  See `26_REFUND_REVERSAL_ENGINE_SPECIFICATION.md`.

### Related Business Rules

R51, R52.

### Related Open Issues

[OPEN-ISSUE: OI-07] — refund/reversal document types are not
yet finalized by the Product Owner.

---

## 7. Revenue Recognition

### Principle Statement

The Platform recognizes revenue only at the moment its commission
is calculated and recorded as a `CompanyPlatformFeeEntry` DEBIT.

Money that passes through the Platform but is not commission
is never recognized as Platform revenue, regardless of how long
it is physically held.

### Why It Matters

Without this principle, gross payment volume could be mistaken
for Platform revenue, causing serious accounting and tax errors.

### Existing Implementation Mapping

- `apps/payouts/services_platform_fee.py`, line 150 —
  `PlatformFeeService.record_invoice_fee()` is the only code path
  that creates Platform-recognized revenue,
  and it is gated by four explicit conditions (ADR-003).
- `apps/payouts/services_platform_fee.py`, line 180 —
  `amount = int(Decimal(str(invoice.total_amount)) * fee_pct / 100)` —
  commission is a percentage of total invoice amount,
  never the full amount.

### Required Future Extension

- When `SettlementBatch` (target) executes a
  Platform-to-Organization transfer, the corresponding
  `CompanyPlatformFeeEntry` CREDIT confirms that the commission
  portion was the only amount retained. See
  `13_SETTLEMENT_NETTING_ENGINE.md` — Reporting Impact.

### Related Business Rules

R05, R09, R10, R38.

### Related Open Issues

None directly.


---

## 8. Settlement Netting

### Principle Statement

Settlement between two Financial Parties should aggregate
all outstanding obligations over a period into a single net transfer,
rather than executing one transfer per invoice.

### Why It Matters

Netting reduces the number of bank transactions,
reduces transaction fees, and simplifies reconciliation.

Example: 10 invoices of 10,000,000 Rial each should produce
one 100,000,000 Rial transfer (minus fees),
not ten separate transfers.

### Existing Implementation Mapping

- Layer 2 (Organization ↔ Provider) already nets implicitly:
  `apps/payouts/services.py`, `TechnicianLedgerService.get_balance()`
  sums all credits and debits into one running balance.
- Layer 1 (Platform ↔ Organization) has no netting today —
  each `CompanyPlatformFeeEntry` is tracked individually,
  and there is no batch settlement mechanism.

### Required Future Extension

- `SettlementBatch` and `SettlementItem` (target models) —
  see `19_DATA_MODEL.md` and `13_SETTLEMENT_NETTING_ENGINE.md`
  for the complete net position formula and batch algorithm.

### Related Business Rules

R41, R42, R43, R44, R45, R55.

### Related Open Issues

[OPEN-ISSUE: OI-08] — whether settlement batch execution
requires a two-step approval workflow is undecided.

---

## 9. Forward-only Policy Changes

### Principle Statement

A change to a financial policy (commission rate, discount policy,
wage percentage) must never alter the financial outcome of
an invoice that was already issued or paid before the change.

### Why It Matters

Retroactive policy changes would make historical financial
records unreliable and would break the Immutable Ledger principle
by implication (past entries would no longer match current policy).

### Existing Implementation Mapping

- `apps/invoices/services_wage.py`, line 231 —
  `snapshot_wage_percentages_on_invoice()` freezes wage percentages
  onto the invoice at ISSUE time.
- `apps/invoices/services_settlement.py`, line 22 —
  `InvoiceSettlementService.settle()` reads the current policy
  only once, at PAID time, and freezes the result into
  `settled_*` fields permanently.
- `apps/payouts/services_order_wages.py`, line 65 —
  `TechnicianWagePostingService` reads
  `TechnicianServiceRate.fixed_wage_rial` at order-completion time
  and snapshots it into ledger entry metadata (ADR-005).

### Required Future Extension

None. This principle is already fully and correctly implemented
across every policy-driven calculation in the codebase.

### Related Business Rules

R49.

### Related Open Issues

None.


---

## 10. Financial Auditability

### Principle Statement

Every financial fact must be traceable to:

- the business event that caused it,
- the user or system process that recorded it,
- the exact timestamp it was recorded.

### Why It Matters

Auditability is what allows a dispute, a tax review,
or an incident investigation to be resolved with evidence
rather than guesswork.

### Existing Implementation Mapping

- `apps/payouts/models.py` —
  every `TechnicianLedgerEntry` and `CompanyPlatformFeeEntry`
  carries `created_by`, `created_at`, `idempotency_key`,
  and a `metadata` JSONField snapshot of the triggering event.
- `apps/tenants/models.py` —
  `CompanyMerchantProfile.reviewed_by` and `reviewed_at`
  record who approved KYC/IBAN changes.

### Required Future Extension

- No independent audit log exists today for changes to
  `CompanyFinancialPolicy` or `CompanyPaymentSettings` themselves
  (as opposed to the ledger entries they produce).
- Recommended: install `django-auditlog` or an equivalent
  change-tracking mechanism for these two policy models.

### Related Business Rules

R48, R50.

### Related Open Issues

None directly, though [OPEN-ISSUE: OI-08] (approval workflow)
would depend on this principle being extended first.

---

## 11. Idempotency

### Principle Statement

Any financial write operation must be safe to execute more than once
without creating duplicate financial effects.

### Why It Matters

Payment gateway callbacks, retried background jobs,
and network failures can all cause the same financial event
to be processed more than once.

Without idempotency, this would silently double-credit or
double-charge a Financial Party.

### Existing Implementation Mapping

- `apps/payouts/models.py` —
  `idempotency_key` is a globally unique, DB-enforced field on
  both `TechnicianLedgerEntry` and `CompanyPlatformFeeEntry`.
- `apps/payouts/services.py` —
  `TechnicianLedgerService._write_entry()` checks for an existing
  entry with the same key before writing, inside a transaction,
  with a savepoint to recover from race conditions.
- `apps/payouts/models.py`, line 137 —
  `PaymentSplitSnapshot.payment` is a `OneToOneField`,
  making `create_snapshot()` naturally idempotent at the DB level.
- `apps/payouts/services_backfill.py` —
  `FinancialBackfillService` relies entirely on the idempotency
  of the underlying services it retries (ADR-008).

### Required Future Extension

- `SettlementBatch` creation (target) must define its own
  idempotency key strategy per (company, level, period) to avoid
  duplicate batches for the same period.
  See `13_SETTLEMENT_NETTING_ENGINE.md` — Idempotency Rules.

### Related Business Rules

R51 (supports immutability), implicitly required by R41–R45.

### Related Open Issues

None directly.


---

## 12. Reconciliation

### Principle Statement

The system must be able to detect and flag any mismatch between
the amount a Customer was verified as paying and the amount
the Organization's invoice expected, rather than silently
accepting an ambiguous outcome.

### Why It Matters

Payment gateways can return ambiguous, delayed, or tampered
responses. Silently trusting these responses risks financial loss
or fraud.

### Existing Implementation Mapping

- `apps/payments/services.py`, lines 287–288 —
  `PaymentVerifyService.verify()` compares `response.verified_amount`
  against `payment.amount`; on mismatch it sets
  `Payment.status = NEEDS_RECONCILIATION` rather than `PAID`.
- `apps/payments/services.py` —
  a payment older than the configured expiration window
  is also routed to `NEEDS_RECONCILIATION` instead of being
  silently verified.
- `apps/invoices/services.py`, line 361 —
  `InvoiceMarkPaidService.mark_paid()` raises `ValueError` if
  `payment.amount != invoice.total_amount`, blocking the mark-paid
  transition entirely.

### Required Future Extension

- There is currently no automated resolution workflow for
  `NEEDS_RECONCILIATION` payments; resolution is manual only.
- `EscrowRecord` (target) should expose reconciliation status
  in Platform Owner reporting.

### Related Business Rules

R47.

### Related Open Issues

[OPEN-ISSUE: OI-06] — customer overpayment handling is undecided,
which is a specific case of reconciliation.

---

## 13. Correction through Reversal, not Mutation

### Principle Statement

A financial mistake must always be corrected by creating a new,
opposite-direction ledger entry or adjustment document,
never by editing or deleting the original record.

### Why It Matters

This is the practical consequence of the Immutable Ledger principle
(Principle 6) applied specifically to error correction.

It guarantees that anyone reviewing the ledger can see both
the original mistake and its correction, preserving a complete
and honest history.

### Existing Implementation Mapping

- `apps/payouts/services.py`, line 232 —
  `TechnicianLedgerService.record_manual_settlement()` supports
  `ADJUSTMENT_CREDIT` and `ADJUSTMENT_DEBIT` directions,
  which create new entries rather than mutating old ones.
- `apps/payouts/models.py` —
  `TechnicianLedgerEntry.Source.ADJUSTMENT` and
  `TechnicianLedgerEntry.Source.REFUND` are already defined
  as ledger source types, though no `RefundService` exists yet
  to populate the `REFUND` source.

### Required Future Extension

- `AdjustmentDocument` (target model) must become the mandatory
  entry point for all PAID-invoice corrections, orchestrating
  the creation of the correct reversal ledger entries on
  `TechnicianLedgerEntry` and `CompanyPlatformFeeEntry`.
  Full detail in `26_REFUND_REVERSAL_ENGINE_SPECIFICATION.md`.

### Related Business Rules

R46, R51, R52.

### Related Open Issues

[OPEN-ISSUE: OI-05], [OPEN-ISSUE: OI-06], [OPEN-ISSUE: OI-07].


---

## 14. Tenant Isolation

### Principle Statement

No financial query, calculation, or record may ever cross
Organization (tenant) boundaries.

Every financial model must be scoped to exactly one Organization.

### Why It Matters

RastiSaas is a multi-tenant platform. A single leaked query
without a company filter could expose one Organization's
financial data to another, which is both a security incident
and a potential legal liability.

### Existing Implementation Mapping

- `apps/common/models.py` —
  `CompanyOwnedModel` is the base class inherited by every
  financial model: `Invoice`, `InvoiceItem`, `Payment`,
  `PaymentGateway`, `TechnicianLedgerEntry`,
  `CompanyPlatformFeeEntry`, `PaymentSplitSnapshot`,
  `FinancialBackfillTask`, `TechnicianServiceRate`.
- `apps/invoices/selectors.py`, `apps/payments/selectors.py` —
  every selector method takes `company` as a required parameter
  and filters on it.

### Required Future Extension

- All target models (`EscrowRecord`, `SettlementBatch`,
  `SettlementItem`, `AdjustmentDocument`) must also inherit
  `CompanyOwnedModel`, as already specified in
  `19_DATA_MODEL.md`.

### Related Business Rules

R06, R07, R08. Implicit precondition for all rules R01–R56.

### Related Open Issues

None.

---

## 15. Event-driven Financial Transitions

### Principle Statement

Every meaningful financial state transition should be capable of
emitting a domain event, so that downstream consumers
(notifications, reporting, future integrations) can react
without being tightly coupled to the originating service.

### Why It Matters

Coupling every future feature directly to
`InvoiceMarkPaidService` or `PaymentVerifyService` would make
the codebase increasingly fragile.

An event-driven approach lets new consumers subscribe to
existing financial facts without modifying the services that
produce them.

### Existing Implementation Mapping

- `apps/notifications/event_catalog.py` —
  defines financial-adjacent events such as
  `INVOICE_PAID_CUSTOMER`, `PAYMENT_SUCCESS_CUSTOMER`,
  `PAYMENT_SUCCESS_ADMIN`, `PAYMENT_FAILED_CUSTOMER`.
- These events are triggered via Django signals on model changes,
  decoupling notification delivery from the financial services
  themselves.

### Required Future Extension

- New event keys are needed for settlement and escrow transitions:
  `settlement_batch_created`, `settlement_completed`,
  `settlement_failed`, `provider_settlement_received`
  (already specified in `13_SETTLEMENT_NETTING_ENGINE.md` —
  Events Emitted).
- Refund/reversal events (`refund_issued`, `adjustment_applied`)
  are required once `AdjustmentDocument` is implemented.
  See `26_REFUND_REVERSAL_ENGINE_SPECIFICATION.md`.

### Related Business Rules

R50 (supports auditability via events).

### Related Open Issues

None directly.

---

## Summary Table

| # | Principle | Status Today |
|---|---|---|
| 1 | Money Movement vs Money Meaning | 🟡 Partial — EscrowRecord missing |
| 2 | Legal Money Ownership | 🟡 Partial — no explicit escrow tracking |
| 3 | Platform as Escrow Holder | ✅ Implemented |
| 4 | Organization as Invoice Issuer | ✅ Implemented |
| 5 | Provider as Payable Recipient | ✅ Implemented |
| 6 | Immutable Ledger | ✅ Implemented |
| 7 | Revenue Recognition | ✅ Implemented |
| 8 | Settlement Netting | 🟡 Partial — Layer 1 batch missing |
| 9 | Forward-only Policy Changes | ✅ Implemented |
| 10 | Financial Auditability | 🟡 Partial — no policy-change audit log |
| 11 | Idempotency | ✅ Implemented |
| 12 | Reconciliation | 🟡 Partial — manual resolution only |
| 13 | Correction through Reversal | ❌ Missing — no AdjustmentDocument |
| 14 | Tenant Isolation | ✅ Implemented |
| 15 | Event-driven Financial Transitions | 🟡 Partial — settlement/refund events missing |
