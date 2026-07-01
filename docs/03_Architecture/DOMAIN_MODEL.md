---
Title: Domain Model
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/*/models.py (field names), 01_Architecture/DOMAIN_MODEL.md
Source of Truth: Code
Depends On: []
Related Documents: SYSTEM_ARCHITECTURE.md, DJANGO_APP_ARCHITECTURE.md, ../00_Project/GLOSSARY.md
Reusable Across Projects: No
---

# Domain Model — Rasti Service

Describes the core domain objects and their relationships.

---

## Domain Hierarchy

```
Platform (Rasti Service)
└── Company (Tenant)
    ├── Users (Company Admin, Staff, Technician, Customer)
    ├── Orders
    │   ├── ServiceRequest (pre-order, PENDING_REVIEW)
    │   └── Invoice
    │       └── Payment
    ├── Customers
    ├── Technicians
    │   └── TechnicianLedgerEntry (immutable)
    ├── PaymentGateway
    ├── CompanyPaymentSettings
    ├── CompanyFinancialPolicy
    │   └── CompanyPlatformFeeEntry (immutable)
    ├── SMS / Notifications
    │   ├── SMSMessage
    │   └── Notification
    └── Reports / Analytics
```

---

## Company

The tenant boundary. All operational and financial data is scoped to a company.

**Key rules:**
- Never query tenant data without `company=` filter
- Never hard-delete a company with financial records
- Company-specific settings must not leak across tenants
- Company is identified by `company_code` slug in the URL

**Model:** `apps/tenants/models.py` — `Company`

---

## Order

The operational heart of the system.

**Key rules:**
- Belongs to one company
- Has one customer
- May have at most one active technician
- Has a status from the Persian lifecycle (see [ORDER_RULES.md](../04_Business_Rules/ORDER_RULES.md))
- May have at most one active invoice (`DRAFT` or `ISSUED`)

**Model:** `apps/orders/models.py` — `Order`

---

## Invoice

The financial document for a completed service.

**Key rules:**
- Belongs to one company
- Must show tenant company and issuing user/technician
- `PAID` is terminal — invoice snapshot is immutable after payment
- Settlement amounts are frozen at the time of the payment

**Model:** `apps/invoices/models.py` — `Invoice`

---

## Payment

Represents an online or recorded payment process.

**Key rules:**
- Belongs to one company
- Callback alone is never trusted — PSP verification required
- Ambiguous outcomes go to `NEEDS_RECONCILIATION`
- Callbacks are idempotent (same reference = same outcome)

**Model:** `apps/payments/models.py` — `Payment`

---

## PaymentGateway

The canonical gateway model.

**Key rules:**
- Must identify `owner_type`: `company` or `platform`
- Company-owned: tenant company owns the PSP relationship
- Platform-owned: Rasti Service/facilitator owns the PSP relationship
- Platform commission may only be created for platform-owned gateway payments when all commission conditions are met

**Legacy/transitional models (READ ONLY — do not add new logic to these):**
- `apps.platform_core.models.CompanyPaymentGatewaySetting`
- `apps.platform_core.models.PlatformPaymentGatewaySetting`

Use `apps.payments.models.PaymentGateway` for all new payment-flow logic.

**Model:** `apps/payments/models.py` — `PaymentGateway`

---

## CompanyPaymentSettings

Source of truth for online payment activation and mode.

**Owns:**
- `payment_mode` — `disabled`, `company_gateway`, `platform_gateway`
- Activation status (`is_activated`)
- `activated_by`, `activated_at`
- Deactivation metadata

Only the Platform Owner may activate or deactivate payment mode.

**Model:** `apps/tenants/models.py` — `CompanyPaymentSettings`

---

## CompanyFinancialPolicy

Source of truth for financial policies.

**Owns:**
- Payout strategy
- Platform fee percent
- Discount absorption policies
- Split/wage policy references

**Does NOT own:** payment activation or gateway credentials.

**Model:** `apps/tenants/models.py` — `CompanyFinancialPolicy`

---

## Ledger Entries

Two immutable ledger types:

| Model | Purpose | App |
|---|---|---|
| `TechnicianLedgerEntry` | Wages owed to / paid to technician | `apps/payouts/models.py` |
| `CompanyPlatformFeeEntry` | Platform commission per payment | `apps/payouts/models.py` |

**Rules (both types):**
- Immutable — never edited
- Idempotent — same operation creates same entry
- Company-scoped
- Corrections are new reversing entries, never updates

See [../07_ADR/ADR-004-Ledger-Discipline.md](../07_ADR/ADR-004-Ledger-Discipline.md).

---

## Accounting Model (Current vs. Future)

**Current (V1):**
- Single-entry ledger
- Immutable entries with idempotency keys
- Double-entry discipline (each credit has a corresponding debit)

**Future (planned, not yet implemented):**
- Customer wallet
- Company revenue ledger
- Platform revenue ledger
- Full double-entry accounting

`apps/billing/` is the planned home for the future accounting system — currently a stub.
