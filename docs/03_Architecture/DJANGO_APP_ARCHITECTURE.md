---
Title: Django App Architecture
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/ directory structure, config/settings/base.py INSTALLED_APPS
Source of Truth: Code
Depends On: SYSTEM_ARCHITECTURE.md
Related Documents: ../01_Human_Engineering/REPOSITORY_STRUCTURE.md
Reusable Across Projects: No
---

# Django App Architecture

---

## App Overview

The project is organized as a Django multi-app project under `apps/`.

```
apps/
├── accounts/           ← Users, auth, roles, permissions, password reset
├── api/                ← REST API (auth, tenant, platform endpoints)
├── billing/            ← SaaS subscription billing (STUB — not implemented)
├── communication/      ← Company communication event configuration
├── dashboard/          ← Role-based dashboard home views (admin + tech + customer)
├── invoices/           ← Invoice lifecycle (public, admin, technician views)
├── notifications/      ← In-app notification catalog and delivery
├── orders/             ← Order lifecycle (technician views + models)
├── payouts/            ← Technician ledger, settlement, financial reports
├── payments/           ← PSP integration, gateway callbacks, verification
├── platform_core/      ← Platform owner panel views and operations
├── public/             ← Public marketing pages, service request form
├── reports/            ← Analytics, customer segmentation, discount campaigns
├── sms/                ← SMS templates, outbox, inbox, diagnostics
└── tenants/            ← Companies, tenant admin views, operator management
```

---

## App Internals Pattern

Each app follows this pattern:

```
apps/<app_name>/
├── __init__.py
├── apps.py             ← AppConfig with app_name
├── models.py           ← Data models
├── services.py         ← Business logic (ALL of it)
├── views.py            ← Thin HTTP handlers
├── urls.py             ← URL patterns for this app
├── serializers.py      ← DRF serializers (API apps only)
├── admin.py            ← Django admin registration
├── migrations/         ← Database migration history
└── tests/              ← Tests for this app
```

Some apps have multiple view/URL files for different roles:
- `apps/invoices/urls.py` + `urls_technician.py` + `urls_public_short.py`
- `apps/notifications/urls.py` + `urls_technician.py`
- `apps/dashboard/urls.py` + `urls_technician.py` + `urls_customer.py`
- `apps/tenants/views.py` + `views_admin.py` (large — 2000+ lines)

---

## The `tenants` App (Most Complex)

`apps/tenants/` is the largest and most complex app. It contains:
- `models.py` — Company model, CompanyPaymentSettings, CompanyFinancialPolicy
- `views.py` — Public company home, service request handler
- `views_admin.py` — All admin/operator views (2000+ lines, 96 URL patterns)
- `urls.py` — 175 lines, all tenant URL patterns
- `services.py` — Company-level business operations
- `operator_access.py` — Operator permission middleware and helpers

---

## The `accounts` App

`apps/accounts/` contains:
- `models.py` — `User` model with `UserRole` TextChoices
- `permissions.py` — `@require_tenant_role`, `@require_platform_owner`, `@require_tenant_auth`
- `views.py` — Unified login view
- `urls_tenant_auth.py` — Tenant login/logout (redirects to `/login/`)
- `urls_password_reset.py` — Password reset flow (4 steps)

---

## The `api` App

`apps/api/` exposes three URL groups:
- `/api/auth/` — 5 endpoints (login, refresh, logout, register, verify)
- `/api/<code>/` — 10 tenant endpoints (orders, invoices, customers, etc.)
- `/api/platform/` — 2 platform endpoints

**Note:** JWT logout is broken (P0-2) — see [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md).

---

## Key Models and Their Locations

| Model | App | File |
|---|---|---|
| `User` | `accounts` | `apps/accounts/models.py` |
| `Company` | `tenants` | `apps/tenants/models.py` |
| `CompanyPaymentSettings` | `tenants` | `apps/tenants/models.py` |
| `CompanyFinancialPolicy` | `tenants` | `apps/tenants/models.py` |
| `Order` | `orders` | `apps/orders/models.py` |
| `Invoice` | `invoices` | `apps/invoices/models.py` |
| `Payment` | `payments` | `apps/payments/models.py` |
| `PaymentGateway` | `payments` | `apps/payments/models.py` |
| `TechnicianLedgerEntry` | `payouts` | `apps/payouts/models.py` |
| `Notification` | `notifications` | `apps/notifications/models.py` |
| `SMSMessage` | `sms` | `apps/sms/models.py` |
| `ServiceRequest` | `public` | `apps/public/models.py` |

---

## INSTALLED_APPS (Relevant Entries)

From `config/settings/base.py`:
```python
INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    ...
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    # ← rest_framework_simplejwt.token_blacklist NOT installed (P0-2)
    # Project apps
    "apps.accounts",
    "apps.tenants",
    "apps.orders",
    "apps.invoices",
    "apps.payments",
    "apps.payouts",
    "apps.notifications",
    "apps.sms",
    "apps.reports",
    "apps.platform_core",
    "apps.public",
    "apps.dashboard",
    "apps.api",
    "apps.billing",  # stub
    "apps.communication",
]
```
