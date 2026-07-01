---
Title: ADR — README
Layer: Architecture Decision Records
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: ADR
Reusable Across Projects: Partially
---

# 07 — Architecture Decision Records

ADRs capture important architectural decisions with their context and consequences.

---

## Index

See [ADR_INDEX.md](ADR_INDEX.md) for the complete list.

---

## ADR Files

| File | Decision |
|---|---|
| [ADR-001](ADR-001-Rasti-Is-SaaS-Provider.md) | Rasti is SaaS provider, not service merchant |
| [ADR-002](ADR-002-CompanyPaymentSettings.md) | Separate model for payment activation vs financial policy |
| [ADR-003](ADR-003-Payment-Architecture.md) | PSP verification required before PAID status |
| [ADR-004](ADR-004-Ledger-Discipline.md) | Immutable ledger entries |
| [ADR-005](ADR-005-Technician-Service-Pricing.md) | Technician wage calculation |
| [ADR-006](ADR-006-Technician-Ledger-Statement-Architecture.md) | Technician statement as calculated view |
| [ADR-007](ADR-007-Financial-Event-Timeline.md) | Financial event timing in order lifecycle |
| [ADR-008](ADR-008-Financial-Recovery-Policy.md) | Handling ambiguous payment outcomes |
| [ADR-TEMPLATE.md](ADR-TEMPLATE.md) | Template for new ADRs |
| [FINANCIAL_ARCHITECTURE_INDEX.md](FINANCIAL_ARCHITECTURE_INDEX.md) | Financial architecture summary |

---

## Reading Order

New to the project? Read [ADR_INDEX.md](ADR_INDEX.md) for the full list with one-line summaries.

The most critical ADRs for day-to-day work:
1. [ADR-004](ADR-004-Ledger-Discipline.md) — immutable ledger (financial code)
2. [ADR-003](ADR-003-Payment-Architecture.md) — PSP verification required (payment code)
3. [ADR-001](ADR-001-Rasti-Is-SaaS-Provider.md) — platform identity (all business logic)

---

## Related Documents

- [../04_Business_Rules/](../04_Business_Rules/) — business rules that implement ADR decisions
- [../03_Architecture/](../03_Architecture/) — architecture docs that explain ADR consequences
- [../11_Project_Knowledge/SOURCE_OF_TRUTH.md](../11_Project_Knowledge/SOURCE_OF_TRUTH.md) — ADR authority rules

---

## Maintenance Notes

To add a new ADR: copy [ADR-TEMPLATE.md](ADR-TEMPLATE.md), fill it in, update [ADR_INDEX.md](ADR_INDEX.md). ADRs are never deleted — only superseded by a newer ADR.

---

## Rule

ADRs are binding. A new ADR is needed to reverse or change an existing decision.

Do not change code in a way that contradicts an accepted ADR without creating a new superseding ADR first.
