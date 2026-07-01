---
Title: Business Rules — README
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code + ADR
Reusable Across Projects: No
---

# 04 — Business Rules

Domain-specific business rules for each entity in the Rasti platform.

**Important:** Business rule documents describe the intended behavior. Always verify in code before implementing changes. If a rule conflicts with code, trust the code and mark the conflict.

---

## Files in This Folder

| File | Entity | Key Rules |
|---|---|---|
| [ORDER_RULES.md](ORDER_RULES.md) | Order | Status machine, creation paths, assignment |
| [INVOICE_RULES.md](INVOICE_RULES.md) | Invoice | Creation, payment, immutability of PAID |
| [PAYMENT_RULES.md](PAYMENT_RULES.md) | Payment | Verification, NEEDS_RECONCILIATION, commission |
| [TECHNICIAN_RULES.md](TECHNICIAN_RULES.md) | Technician | Assignment, completion, wage, SMS bug |
| [PAYOUT_RULES.md](PAYOUT_RULES.md) | Payout/Ledger | Immutability, settlement, statements |
| [CUSTOMER_RULES.md](CUSTOMER_RULES.md) | Customer | Access, dashboard status, API bug |
| [COMPANY_RULES.md](COMPANY_RULES.md) | Company | Registration, activation, billing stub |
| [NOTIFICATION_RULES.md](NOTIFICATION_RULES.md) | Notifications | Catalog, throttle, untriggered events |
| [SMS_RULES.md](SMS_RULES.md) | SMS | Credit, templates, technician SMS bug |

---

## Reading Order

Business rules are independent per entity. Read the one relevant to your task:
- Financial work → [PAYMENT_RULES.md](PAYMENT_RULES.md) + [PAYOUT_RULES.md](PAYOUT_RULES.md)
- Order work → [ORDER_RULES.md](ORDER_RULES.md)
- Notification work → [NOTIFICATION_RULES.md](NOTIFICATION_RULES.md) + [SMS_RULES.md](SMS_RULES.md)

---

## Related Documents

- [../07_ADR/](../07_ADR/) — architectural decisions that established these rules
- [../05_Workflows/](../05_Workflows/) — how these rules manifest in end-to-end flows
- [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md) — known bugs affecting business rules

---

## Maintenance Notes

When a business rule changes, update the relevant file here AND create or update an ADR if the change is architectural. Never update business rules without updating the corresponding tests.

---

## Cross-Reference with ADRs

| Business Rule | Relevant ADR |
|---|---|
| Platform is SaaS provider, not service seller | ADR-001 |
| CompanyPaymentSettings vs CompanyFinancialPolicy | ADR-002 |
| Payment gateway architecture | ADR-003 |
| Ledger immutability | ADR-004 |
| Technician service pricing | ADR-005 |
| Technician ledger and statement | ADR-006 |
| Financial event timeline | ADR-007 |
| Financial recovery policy | ADR-008 |
