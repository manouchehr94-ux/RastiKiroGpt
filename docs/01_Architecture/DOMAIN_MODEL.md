# Domain Model — Rasti Service

**Version:** RDOS v1.0 Stable

This document describes the core domain objects and how they relate.

---

## Domain Hierarchy

```text
Platform
└── Company
    ├── Company Users
    ├── Customers
    ├── Technicians
    ├── Orders
    │   └── Invoices
    │       └── Payments
    ├── Payment Gateways
    ├── Financial Policies
    ├── Payment Settings
    ├── Ledger Entries
    ├── SMS / Notifications
    └── Reports
```

---

## Company

The tenant boundary. All operational and financial data must be scoped to a company.

Rules:

- Never query tenant data without `company` filter.
- Never hard-delete a company with financial records.
- Company-specific settings must not leak across tenants.

---

## Order

The operational heart of the system.

Rules:

- Belongs to one company.
- Has one customer.
- May have one technician.
- Has a status from the approved Persian lifecycle.
- May have at most one active invoice.

See: `docs/03_Business/ORDER_RULES.md`.

---

## Invoice

The financial document for an order/service.

Rules:

- Belongs to one company.
- Must show tenant company and issuing user/technician.
- `PAID` is terminal except future formal reversal/refund flows.
- Settlement snapshots are immutable after `settled_at`.

See: `docs/03_Business/INVOICE_RULES.md`.

---

## Payment

Represents an online or recorded payment process.

Rules:

- Belongs to one company.
- Callback is never trusted alone.
- Provider verify is required.
- Ambiguous outcomes go to `NEEDS_RECONCILIATION`.

See: `docs/03_Business/PAYMENT_RULES.md`.

---

## PaymentGateway

The target canonical gateway model.

Rules:

- Must identify `owner_type`: `company` or `platform`.
- Company-owned gateway means tenant company owns the PSP relationship.
- Platform-owned gateway means Rasti Service/facilitator owns the PSP relationship.
- Platform commission may only be created for platform-owned gateway payments when all commission conditions are true.

Legacy/transitional gateway models:

- `apps.platform_core.models.CompanyPaymentGatewaySetting`
- `apps.platform_core.models.PlatformPaymentGatewaySetting`

Do not add new payment-flow logic to those legacy models. They may only be read during migration/consolidation tasks.

---

## CompanyPaymentSettings

Source of truth for online payment activation and mode.

Owns:

- payment mode
- activation status
- activated_by
- activated_at
- deactivation metadata

Only platform owner may activate or deactivate payment mode.

---

## CompanyFinancialPolicy

Source of truth for financial policies.

Owns:

- payout strategy
- platform fee percent
- discount absorption policies
- split/wage policy references

Does not own payment activation or gateway credentials.

---

## Ledger Entries

Existing ledgers:

- `TechnicianLedgerEntry`
- `CompanyPlatformFeeEntry`

Rules:

- Immutable.
- Idempotent.
- Company-scoped.
- Corrections are new entries, not edits.

See: `docs/07_ADR/ADR-004-Ledger-Discipline.md`.
