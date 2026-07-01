---
Title: AI Agent Start Here
Layer: AI Operating System
Audience: AI
Status: Active
Last Verified: 2026-07-01
Verified Against: Full codebase audit 2026-06-30, Site Map 2026-07-01
Source of Truth: Code + ADR
Depends On: []
Related Documents: AI_CONTEXT_MAP.md, AI_CODE_CHANGE_RULES.md, AI_SAFE_CHANGE_PROTOCOL.md
Reusable Across Projects: No
---

# AI Agent Start Here

You are an AI agent working on the Rasti SaaS Django project.

Read this document before doing anything else.

---

## What this project is

Rasti is a **multi-tenant SaaS platform** for field-service dispatch companies in Iran.

- Django 5.1.3, Python 3.11.9, PostgreSQL, Tailwind CSS
- Multi-tenancy via URL: first URL segment = company code (`/<company_code>/`)
- 5 user roles: `PLATFORM_OWNER`, `COMPANY_ADMIN`, `COMPANY_STAFF`, `TECHNICIAN`, `CUSTOMER`
- Language: Persian UI, English code identifiers
- 238 URL patterns across 21 url files
- 199+ templates, 1242 tests

The platform is **production-ready with 5 unresolved critical bugs** (P0-1 through P0-5). See [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md).

---

## 5 Things You Must Know Before Changing Code

### 1. Multi-tenant isolation is non-negotiable

Every query on `Order`, `Invoice`, `Payment`, `Customer`, `Technician` must be scoped by `company`. Never do:
```python
Order.objects.get(id=order_id)   # FORBIDDEN
Invoice.objects.get(id=invoice_id)  # FORBIDDEN
```
Always scope by company:
```python
Order.objects.get(id=order_id, company=request.company)  # CORRECT
```

### 2. Business logic lives in services only

Views must be thin. All business decisions (status transitions, financial calculations, notification triggers) live in `services.py` files. Never add business logic to views.

### 3. Financial code requires extreme caution

All financial services must use `transaction.atomic`, `select_for_update()`, `Decimal` (never float), and idempotency keys. The ledger (`TechnicianLedgerEntry`) is immutable — never edit existing rows.

### 4. Permissions are enforced by decorators

- `@require_tenant_role("ROLE1", "ROLE2")` — checks auth + company membership + role
- `@require_platform_owner` — platform-level views only
- **P0-1**: `admin_operator_list` at `apps/tenants/views_admin.py:2125` is missing its decorator — this is a known critical bug

### 5. Persian UI labels must not change

Do not translate or modify any Persian-language user-visible strings unless the user explicitly requests it. These include order status labels, button text, and error messages.

---

## Reading Order by Task Type

### You are doing an ORDER task:
1. [../04_Business_Rules/ORDER_RULES.md](../04_Business_Rules/ORDER_RULES.md)
2. [../05_Workflows/ORDER_LIFECYCLE.md](../05_Workflows/ORDER_LIFECYCLE.md)
3. Then inspect (only if changing): `apps/orders/models.py`, `apps/orders/services.py`, `apps/tenants/services.py`

### You are doing a PAYMENT / INVOICE task:
1. [../04_Business_Rules/PAYMENT_RULES.md](../04_Business_Rules/PAYMENT_RULES.md)
2. [../04_Business_Rules/INVOICE_RULES.md](../04_Business_Rules/INVOICE_RULES.md)
3. [../07_ADR/ADR-003-Payment-Architecture.md](../07_ADR/ADR-003-Payment-Architecture.md)
4. [../07_ADR/ADR-004-Ledger-Discipline.md](../07_ADR/ADR-004-Ledger-Discipline.md)
5. Then inspect: `apps/payments/`, `apps/invoices/`, `apps/billing/`

### You are doing a TECHNICIAN / PAYOUT task:
1. [../04_Business_Rules/TECHNICIAN_RULES.md](../04_Business_Rules/TECHNICIAN_RULES.md)
2. [../04_Business_Rules/PAYOUT_RULES.md](../04_Business_Rules/PAYOUT_RULES.md)
3. [../07_ADR/ADR-006-Technician-Ledger-Statement-Architecture.md](../07_ADR/ADR-006-Technician-Ledger-Statement-Architecture.md)
4. Then inspect: `apps/payouts/`, `apps/technicians/`

### You are doing a SECURITY / PERMISSION task:
1. [../03_Architecture/PERMISSIONS.md](../03_Architecture/PERMISSIONS.md)
2. [../03_Architecture/MULTI_TENANCY.md](../03_Architecture/MULTI_TENANCY.md)
3. Then inspect: `apps/accounts/permissions.py`, `apps/tenants/middleware.py`

### You are doing a NOTIFICATION / SMS task:
1. [../04_Business_Rules/NOTIFICATION_RULES.md](../04_Business_Rules/NOTIFICATION_RULES.md)
2. [../04_Business_Rules/SMS_RULES.md](../04_Business_Rules/SMS_RULES.md)
3. Then inspect: `apps/notifications/`, `apps/sms/`

### You are doing a UI / TEMPLATE task:
1. [../08_Site_Map/02_ROLE_BASED_SITE_MAP.md](../08_Site_Map/02_ROLE_BASED_SITE_MAP.md)
2. [../08_Site_Map/05_TEMPLATE_MAP.md](../08_Site_Map/05_TEMPLATE_MAP.md)
3. Then inspect: `templates/base_dashboard.html`, relevant template folder

### You are doing a URL / ROUTING task:
1. [../08_Site_Map/01_URL_INVENTORY.md](../08_Site_Map/01_URL_INVENTORY.md)
2. Then inspect: `config/urls.py` + relevant `apps/*/urls*.py`

### You are doing an ARCHITECTURE task:
1. [../03_Architecture/SYSTEM_ARCHITECTURE.md](../03_Architecture/SYSTEM_ARCHITECTURE.md)
2. [../03_Architecture/DJANGO_APP_ARCHITECTURE.md](../03_Architecture/DJANGO_APP_ARCHITECTURE.md)
3. Read all relevant ADRs in [../07_ADR/](../07_ADR/)

---

## What AI Must Verify in Code (Cannot Trust Docs Alone)

| Situation | Must verify in code |
|---|---|
| Adding permission to a view | Read `apps/accounts/permissions.py` to confirm decorator signature |
| Changing order status | Read `apps/orders/models.py` — confirm all valid transitions |
| Changing financial calculation | Read `apps/*/services.py` + relevant ADR |
| Adding a URL | Read `config/urls.py` + relevant `apps/*/urls*.py` |
| Adding a template | Read `templates/base_dashboard.html` for layout context |
| Adding a model field | Read migration history — check for existing fields |
| Adding a notification event | Read `apps/notifications/catalog.py` for existing event keys |

Docs describe the intended design. Code is what actually runs. Always verify.

---

## What AI Must Never Do

- Do not weaken multi-tenant isolation
- Do not add business logic to views or templates
- Do not use `float` for financial calculations — use `Decimal`
- Do not modify financial ledger entries (they are immutable)
- Do not change Persian UI labels without explicit user request
- Do not run broad refactors
- Do not touch files unrelated to the current task
- Do not silently assume a model field exists — check it
- Do not claim completion without verifying tests pass
- Do not delete historical decisions (ADRs, old comments explaining WHY)

---

## Current Known Critical Issues

Do not accidentally fix these without explicit authorization. Do not accidentally break them further.

| Code | Description | File |
|---|---|---|
| P0-1 | `admin_operator_list` missing role decorator | `apps/tenants/views_admin.py:2125` |
| P0-2 | JWT logout broken — token not blacklisted | `apps/api/auth_views.py:152` |
| P0-3 | Hardcoded `"123456"` in production login | `apps/accounts/views.py:58` |
| P0-4 | `ALLOWED_HOSTS = ["*"]` in base settings | `config/settings/base.py:19` |
| P0-5 | `Customer.name` field doesn't exist | `apps/api/views.py:311` |

---

## Context Handoff Instructions

When ending a session, write a handoff note covering:
1. What task was in progress
2. What files were changed
3. What was NOT yet done
4. What tests were run
5. Any risks noticed

See [AI_HANDOFF_PROTOCOL.md](AI_HANDOFF_PROTOCOL.md).
