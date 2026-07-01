---
Title: Payment Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/payments/models.py, apps/payments/services.py, config/settings/base.py
Source of Truth: Code + ADR
Depends On: []
Related Documents: ../07_ADR/ADR-002-CompanyPaymentSettings.md, ../07_ADR/ADR-003-Payment-Architecture.md, ../07_ADR/ADR-004-Ledger-Discipline.md, ../07_ADR/ADR-008-Financial-Recovery-Policy.md
Reusable Across Projects: No
---

# Payment Business Rules

---

## Payment Status Values

| Code | Meaning |
|---|---|
| `INITIATED` | Payment request sent to PSP |
| `PENDING` | Awaiting PSP callback |
| `PAID` | PSP verification confirmed payment |
| `FAILED` | PSP returned failure |
| `CANCELLED` | Payment cancelled before PSP redirect |
| `NEEDS_RECONCILIATION` | Ambiguous outcome requiring manual review |

---

## The Payment Verification Rule

**A payment is only considered PAID after PSP verification — never on callback alone.**

Callback URL (`/<code>/payments/callback/`) is public and must not trust callback data without verification:
1. Receive callback
2. Call PSP verify endpoint with the transaction reference
3. Confirm amount matches
4. Only then set status to `PAID`

---

## NEEDS_RECONCILIATION Status

A payment enters `NEEDS_RECONCILIATION` when:
- Payment expires while PENDING
- PSP verification times out
- Provider returns ambiguous result
- Amount mismatch between callback and invoice

`NEEDS_RECONCILIATION` payments:
- Must NOT be auto-settled
- Must be reviewed by Platform Owner at `/owner-platform/payments/operations/`
- Must NOT be treated as PAID or FAILED without manual decision

---

## Payment Gateway Modes

Each company has a `CompanyPaymentSettings` record that determines payment behavior:

| Mode | Description |
|---|---|
| `disabled` | Online payment is disabled for this company |
| `company_gateway` | Company uses its own PSP arrangement |
| `platform_gateway` | Company uses platform's gateway (commission applies) |

Only the Platform Owner can change this mode.

---

## Platform Commission Rule

Platform commission (`CompanyPlatformFeeEntry`) is created **only** when ALL of these are true:
1. `CompanyPaymentSettings.payment_mode == "platform_gateway"`
2. `Payment.status == "PAID"`
3. `PaymentGateway.owner_type == "platform"`
4. `CompanyFinancialPolicy.platform_fee_percent > 0`

If any condition is false, no commission is created. This is non-negotiable (ADR-003).

---

## Ledger Immutability Rule

`TechnicianLedgerEntry` and `CompanyPlatformFeeEntry` are immutable. Once created:
- Never edit an existing ledger entry
- To reverse: create a new entry with negative amount (reversing entry)
- All financial history must be preserved for audit

See [../07_ADR/ADR-004-Ledger-Discipline.md](../07_ADR/ADR-004-Ledger-Discipline.md).

---

## Financial Calculation Rules

- All monetary values must use `Decimal`, never `float`
- All financial service methods must use `transaction.atomic`
- All financial operations susceptible to double-processing must use `select_for_update()`
- Idempotency keys must be used for payment initiation and commission creation

---

## Manual / Cash Payments

Company admins can record manual payments (cash, bank transfer):
- Recorded at `/<code>/admin/invoices/<id>/record-payment/`
- Does not go through PSP
- Directly marks invoice as `PAID`
- No platform commission is created

---

## KYC and Gateway Activation

- Companies must submit KYC before activating online payment
- Platform Owner reviews and approves KYC at `/owner-platform/merchant-profiles/`
- KYC approval does NOT automatically activate payment mode
- Platform Owner must separately activate payment mode after KYC approval
