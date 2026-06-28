# Architecture Index — Where to Find the Truth

**Version:** RDOS v1.0 Stable

Use this index before every implementation task. It tells you which documents are authoritative for each topic.

---

## Source-of-Truth Matrix

| Topic | Primary source | Secondary source |
|---|---|---|
| SaaS identity and liability | `07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md` | `03_Business/CUSTOMER_RULES.md` |
| Company payment mode | `07_ADR/ADR-002-CompanyPaymentSettings.md` | `03_Business/PAYMENT_RULES.md` |
| Gateway ownership | `07_ADR/ADR-003-Payment-Architecture.md` | `01_Architecture/PAYMENT_ARCHITECTURE.md` |
| Platform commission | `03_Business/PAYMENT_RULES.md` | `SKILL.md` |
| Ledger immutability | `07_ADR/ADR-004-Ledger-Discipline.md` | `03_Business/ACCOUNTING_RULES.md` |
| Technician wage rates | `07_ADR/ADR-005-Technician-Service-Pricing.md` | `03_Business/ACCOUNTING_RULES.md` |
| Ledger vs statement separation | `07_ADR/ADR-006-Technician-Ledger-Statement-Architecture.md` | `apps/payouts/services_statement.py` |
| Financial event ordering | `07_ADR/ADR-007-Financial-Event-Timeline.md` | `07_ADR/FINANCIAL_ARCHITECTURE_INDEX.md` |
| Financial recovery and backfill | `07_ADR/ADR-008-Financial-Recovery-Policy.md` | `apps/payouts/services_backfill.py` |
| Orders | `03_Business/ORDER_RULES.md` | `01_Architecture/DOMAIN_MODEL.md` |
| Invoices | `03_Business/INVOICE_RULES.md` | `01_Architecture/DOMAIN_MODEL.md` |
| Multi-tenancy | `01_Architecture/MULTI_TENANT.md` | `01_Architecture/DATABASE_RULES.md` |
| Permissions | `01_Architecture/PERMISSIONS.md` | domain business rules |
| Testing | `04_Testing/TEST_STRATEGY.md` | `02_Development_System/TEST_CHECKLIST.md` |
| Migration safety | `01_Architecture/DATABASE_RULES.md` | `02_Development_System/MIGRATION_CHECKLIST.md` |
| Claude behaviour | `02_Development_System/CLAUDE_BEHAVIOR.md` | `02_Development_System/MASTER_PROMPT.md` |
| Release | `05_Deployment/RELEASE_PROCESS.md` | `05_Deployment/ROLLBACK.md` |

---

## Documents to Read by Task Type

### Order task
Read:
- `03_Business/ORDER_RULES.md`
- `01_Architecture/MULTI_TENANT.md`
- `01_Architecture/SERVICE_LAYER.md`
- related order models/services/tests

### Invoice task
Read:
- `03_Business/INVOICE_RULES.md`
- `03_Business/ORDER_RULES.md`
- `01_Architecture/DATABASE_RULES.md`
- related invoice models/services/tests

### Payment task
Read:
- `07_ADR/ADR-002-CompanyPaymentSettings.md`
- `07_ADR/ADR-003-Payment-Architecture.md`
- `03_Business/PAYMENT_RULES.md`
- `03_Business/INVOICE_RULES.md`
- related payment, invoice, payout models/services/tests

### Ledger or accounting task
Read:
- `07_ADR/FINANCIAL_ARCHITECTURE_INDEX.md` ← start here
- `07_ADR/ADR-004-Ledger-Discipline.md`
- `07_ADR/ADR-006-Technician-Ledger-Statement-Architecture.md`
- `07_ADR/ADR-007-Financial-Event-Timeline.md`
- `07_ADR/ADR-008-Financial-Recovery-Policy.md`
- `03_Business/ACCOUNTING_RULES.md`
- related payout models/services/tests

### Financial recovery or backfill task
Read:
- `07_ADR/ADR-008-Financial-Recovery-Policy.md`
- `07_ADR/ADR-007-Financial-Event-Timeline.md`
- `apps/payouts/services_backfill.py`
- `apps/payouts/models.py` (FinancialBackfillTask)

### SMS or notification task
Read:
- `03_Business/SMS_RULES.md`
- `03_Business/NOTIFICATION_RULES.md`
- `01_Architecture/MULTI_TENANT.md`

### Permission or security task
Read:
- `01_Architecture/PERMISSIONS.md`
- `01_Architecture/SECURITY_RULES.md`
- relevant business rules

---

## Legacy Warning

The following gateway models are legacy/transitional and must not receive new payment-flow logic:

- `apps.platform_core.models.CompanyPaymentGatewaySetting`
- `apps.platform_core.models.PlatformPaymentGatewaySetting`

The target canonical model is `apps.payments.models.PaymentGateway`.

---

## Freeze Rule

If a requested change contradicts this index, stop and ask whether an ADR update is required.
