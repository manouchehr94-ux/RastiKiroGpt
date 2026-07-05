# 00 — Financial Operations Engine — Module Overview

**Version:** v1.0 — Draft — Pending Clarification
**Project:** RastiSaas — Multi-Tenant Service Dispatch Platform

---

## Module Boundary

The Financial Operations Engine begins at **Invoice creation** (or service reservation) and ends after **final Settlement** and publication of financial events.

### Entry Points
- Order reaches DONE status → Invoice creation triggered
- Admin manually creates standalone invoice
- Customer initiates payment

### Exit Points
- Settlement batch completed → funds transferred to Organization/Provider
- Financial event published (e.g., `settlement_completed`, `refund_issued`)
- Financial report generated

---

## What This Module Covers

| Subsystem | Scope |
|---|---|
| Invoice Engine | Creation, editing, issuance, line item management, immutability after payment |
| Payment Collection Engine | Online (PSP), Cash, Card-to-Card — all collection models (A/B/C) |
| Commission Allocation Engine | Category subtotals → wage calculation → discount allocation → net shares |
| Platform Escrow Engine | Ownership lifecycle tracking from customer_paid to settled |
| Financial Ledger Engine | Append-only immutable records for all financial movements |
| Settlement & Netting Engine | Two-layer: Platform↔Organization and Organization↔Provider |
| Financial Policy Engine | Organization-specific configurable rules for all calculations |
| Refund & Adjustment Engine | Full/partial refunds, credit notes, customer adjustments |
| IBAN Management Engine | Organization and Provider bank account verification workflows |
| Referral Engine | Future extension point (not implemented in current version) |
| Financial Event System | Domain events for all state transitions |
| Reporting Engine | Mandatory reports (R53-R56) + KPI dashboard |

---

## What This Module Does NOT Cover

- SaaS subscription billing (Company → Platform) → `apps/billing/`
- Order lifecycle management → `apps/orders/`
- Customer identity management → `apps/accounts/`
- SMS/notification delivery → `apps/notifications/`, `apps/sms/`

---

## Relationship to Existing Implementation

This target architecture is **grounded in the existing code audit** (see `docs/13_Financial_Core/01_EXISTING_ARCHITECTURE.md` through `11_EXECUTIVE_SUMMARY.md`).

**Audit findings:**
- 30 of 56 business rules are already fully implemented
- 12 are partially implemented
- 8 are missing and require new development
- 0 are incorrectly implemented

The target architecture **extends** the existing implementation rather than replacing it. All existing models, services, and patterns identified in `06_REUSE_ANALYSIS.md` are preserved.

---

## Document Organization

| # | Document | Content |
|---|---|---|
| 00 | This file | Module overview |
| 01 | EXECUTIVE_SUMMARY | Five key financial questions answered |
| 02 | ARCHITECTURAL_PRINCIPLES | P01–P10 with RastiSaas examples |
| 03 | BUSINESS_RULES | R01–R56 complete documentation |
| 04 | DOMAIN_MODEL | All financial domain models |
| 05 | MONEY_OWNERSHIP_LIFECYCLE | State machine with real events |
| 06 | INVOICE_LINE_ENGINE | Line model + calculation examples |
| 07 | COMMISSION_ALLOCATION_ENGINE | Formulas + discount handling |
| 08 | PAYMENT_COLLECTION_ENGINE | Online, Cash, Card-to-Card |
| 09 | ESCROW_ENGINE | Platform escrow model |
| 10 | FINANCIAL_POLICY_ENGINE | Configurable policies |
| 11 | ORGANIZATION_PROVIDER_IBAN_ENGINE | IBAN verification workflows |
| 12 | LEDGER_ENGINE | Immutable ledger architecture |
| 13 | SETTLEMENT_NETTING_ENGINE | Two-level net settlement |
| 14 | REFUND_ADJUSTMENT_ENGINE | Refund and adjustment architecture |
| 15 | REFERRAL_VISITOR_ENGINE | Future extension point |
| 16 | FINANCIAL_EVENT_CATALOG | Complete event catalog |
| 17 | PERMISSION_MATRIX | Role-based access control |
| 18 | REPORTING_REQUIREMENTS | Mandatory reports + KPIs |
| 19 | DATA_MODEL | Database schema proposals |
| 20 | TEST_SCENARIOS | Happy path + edge cases |
| 21 | OPEN_ISSUES_REGISTER | OI-01 through OI-10 |
| 22 | FREEZE_CHECKLIST | Readiness assessment |
| — | VERSION | Version and freeze status |
