---
Title: AI Reading Order by Task Type
Layer: AI Operating System
Audience: AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# AI Reading Order

Ordered reading lists by task type.
Read in the order listed — earlier docs provide context for later ones.

---

## Documentation-Only Task

1. [../README.md](../README.md)
2. [../DOCS_INDEX.md](../DOCS_INDEX.md)
3. [../DOCUMENTATION_STATUS.md](../DOCUMENTATION_STATUS.md)
4. The specific folder for the topic being documented

---

## Order Task

1. [../00_Project/GLOSSARY.md](../00_Project/GLOSSARY.md) — "Order" definition
2. [../04_Business_Rules/ORDER_RULES.md](../04_Business_Rules/ORDER_RULES.md)
3. [../05_Workflows/ORDER_LIFECYCLE.md](../05_Workflows/ORDER_LIFECYCLE.md)
4. [../05_Workflows/OPERATOR_REVIEW_FLOW.md](../05_Workflows/OPERATOR_REVIEW_FLOW.md)
5. [../05_Workflows/TECHNICIAN_FLOW.md](../05_Workflows/TECHNICIAN_FLOW.md)
6. [../05_Workflows/CANCELLATION_FLOW.md](../05_Workflows/CANCELLATION_FLOW.md)
7. Inspect code only if changing: `apps/orders/`, `apps/tenants/services.py`

---

## Invoice Task

1. [../00_Project/GLOSSARY.md](../00_Project/GLOSSARY.md) — "Invoice" definition
2. [../04_Business_Rules/INVOICE_RULES.md](../04_Business_Rules/INVOICE_RULES.md)
3. [../05_Workflows/INVOICE_PAYMENT_FLOW.md](../05_Workflows/INVOICE_PAYMENT_FLOW.md)
4. Inspect code only if changing: `apps/invoices/`

---

## Payment Task

1. [../00_Project/GLOSSARY.md](../00_Project/GLOSSARY.md) — "Payment", "PaymentGateway" definitions
2. [../00_Project/TERMINOLOGY.md](../00_Project/TERMINOLOGY.md) — `payment_mode`, `owner_type` naming rules
3. [../04_Business_Rules/PAYMENT_RULES.md](../04_Business_Rules/PAYMENT_RULES.md)
4. [../07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md](../07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md)
5. [../07_ADR/ADR-002-CompanyPaymentSettings.md](../07_ADR/ADR-002-CompanyPaymentSettings.md)
6. [../07_ADR/ADR-003-Payment-Architecture.md](../07_ADR/ADR-003-Payment-Architecture.md)
7. [../07_ADR/ADR-004-Ledger-Discipline.md](../07_ADR/ADR-004-Ledger-Discipline.md)
8. [../07_ADR/ADR-008-Financial-Recovery-Policy.md](../07_ADR/ADR-008-Financial-Recovery-Policy.md)
9. Inspect code only if changing: `apps/payments/`

---

## Notification / SMS Task

1. [../04_Business_Rules/NOTIFICATION_RULES.md](../04_Business_Rules/NOTIFICATION_RULES.md)
2. [../04_Business_Rules/SMS_RULES.md](../04_Business_Rules/SMS_RULES.md)
3. [../05_Workflows/NOTIFICATION_FLOW.md](../05_Workflows/NOTIFICATION_FLOW.md)
4. Inspect code only if changing: `apps/notifications/`, `apps/sms/`

---

## Tenant / Security Task

1. [../03_Architecture/MULTI_TENANCY.md](../03_Architecture/MULTI_TENANCY.md)
2. [../03_Architecture/PERMISSIONS.md](../03_Architecture/PERMISSIONS.md)
3. [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md)
4. [../07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md](../07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md)
5. Inspect code only if changing: `apps/accounts/permissions.py`, `apps/tenants/middleware.py`

---

## UI / Template Task

1. [../08_Site_Map/02_ROLE_BASED_SITE_MAP.md](../08_Site_Map/02_ROLE_BASED_SITE_MAP.md)
2. [../08_Site_Map/05_TEMPLATE_MAP.md](../08_Site_Map/05_TEMPLATE_MAP.md)
3. [../03_Architecture/TEMPLATE_ARCHITECTURE.md](../03_Architecture/TEMPLATE_ARCHITECTURE.md)
4. Inspect code only if changing: `templates/base_dashboard.html`, relevant template

---

## Test Task

1. [../06_Quality_Assurance/TEST_STRATEGY.md](../06_Quality_Assurance/TEST_STRATEGY.md)
2. [../06_Quality_Assurance/REGRESSION_TEST_PLAN.md](../06_Quality_Assurance/REGRESSION_TEST_PLAN.md)
3. [../06_Quality_Assurance/AI_VERIFICATION_CHECKLIST.md](../06_Quality_Assurance/AI_VERIFICATION_CHECKLIST.md)
4. Inspect code only if changing: `apps/*/tests/`

---

## Deployment Task

1. [../09_Operations/ENVIRONMENTS.md](../09_Operations/ENVIRONMENTS.md)
2. [../09_Operations/DEPLOYMENT.md](../09_Operations/DEPLOYMENT.md)
3. [../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md](../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md)
4. Inspect code only if changing: `config/settings/`, `requirements*.txt`

---

## Architecture / Refactor Task

1. [../03_Architecture/SYSTEM_ARCHITECTURE.md](../03_Architecture/SYSTEM_ARCHITECTURE.md)
2. [../03_Architecture/DJANGO_APP_ARCHITECTURE.md](../03_Architecture/DJANGO_APP_ARCHITECTURE.md)
3. [../03_Architecture/SERVICE_LAYER.md](../03_Architecture/SERVICE_LAYER.md)
4. All relevant [../07_ADR/](../07_ADR/) files
5. Inspect code only after reading all relevant ADRs
