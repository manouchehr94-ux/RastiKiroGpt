---
Title: ADR Index
Layer: Architecture Decision Records
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: 07_ADR/ folder contents
Source of Truth: ADR
Depends On: []
Related Documents: ADR-TEMPLATE.md
Reusable Across Projects: No
---

# Architecture Decision Records Index

ADRs are the source of truth for accepted architectural decisions.

**Rule:** Do not change code in a way that violates an accepted ADR without creating a new superseding ADR.

---

## Active ADRs

| ADR | Title | Status | Key Decision |
|---|---|---|---|
| [ADR-001](ADR-001-Rasti-Is-SaaS-Provider.md) | Rasti Is SaaS Provider | Accepted | Rasti is not a merchant; tenant companies sell services |
| [ADR-002](ADR-002-CompanyPaymentSettings.md) | CompanyPaymentSettings | Accepted | Payment mode and gateway activation is a separate model from financial policy |
| [ADR-003](ADR-003-Payment-Architecture.md) | Payment Architecture | Accepted | PSP verification required before marking PAID |
| [ADR-004](ADR-004-Ledger-Discipline.md) | Ledger Discipline | Accepted | Ledger entries are immutable; use reversing entries |
| [ADR-005](ADR-005-Technician-Service-Pricing.md) | Technician Service Pricing | Accepted | Wage calculation strategy |
| [ADR-006](ADR-006-Technician-Ledger-Statement-Architecture.md) | Technician Ledger & Statement | Accepted | Statement is a calculated view, not a stored document |
| [ADR-007](ADR-007-Financial-Event-Timeline.md) | Financial Event Timeline | Accepted | When financial events are created in the lifecycle |
| [ADR-008](ADR-008-Financial-Recovery-Policy.md) | Financial Recovery Policy | Accepted | How to handle NEEDS_RECONCILIATION payments |

---

## How to Read ADRs

Each ADR contains:
- **Context** — Why the decision was needed
- **Decision** — What was decided
- **Consequences** — What this means for the codebase
- **Status** — Accepted / Superseded / Deprecated

---

## Creating a New ADR

Use [ADR-TEMPLATE.md](ADR-TEMPLATE.md).

Trigger a new ADR when:
- A significant architectural choice is made
- An existing ADR is being reversed or modified
- A pattern is established that future developers must follow

---

## ADRs Most Relevant to AI Agents

| Task | Most Important ADR |
|---|---|
| Payment task | ADR-003, ADR-004, ADR-008 |
| Financial calculation | ADR-004 |
| Technician payout | ADR-005, ADR-006, ADR-007 |
| Multi-tenancy decision | ADR-001 |
| Payment mode | ADR-002 |
