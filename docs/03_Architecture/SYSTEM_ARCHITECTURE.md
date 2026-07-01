---
Title: System Architecture
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: config/urls.py, apps/*/models.py, config/settings/base.py
Source of Truth: Code
Depends On: []
Related Documents: DJANGO_APP_ARCHITECTURE.md, MULTI_TENANCY.md, PERMISSIONS.md
Reusable Across Projects: No
---

# System Architecture

## Summary

Rasti is a Django SaaS platform with **URL-based multi-tenancy**. Each tenant company gets a unique URL prefix. The platform supports 5 distinct user roles with strict data isolation between tenants.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Web framework | Django 5.1.3 |
| Language | Python 3.11.9 |
| Database | PostgreSQL (production) |
| ORM | Django ORM |
| CSS | Tailwind CSS |
| Authentication | Django sessions + JWT (REST API) |
| REST API | Django REST Framework + SimpleJWT |
| SMS | Configurable SMS provider (per-company) |
| Payment | PSP gateway (configurable per company) |

---

## Multi-Tenancy Design

All tenant data lives in a shared database, separated by `company` foreign key.

URL structure:
```
/                           → Public marketing (Rasti landing pages)
/login/                     → Unified login (all roles)
/owner-platform/            → Platform owner panel
/admin/                     → Django Admin (superuser only)
/<company_code>/            → Tenant namespace root
  /<code>/admin/            → Admin / Operator panel
  /<code>/tech/             → Technician panel
  /<code>/invoices/         → Customer + public invoice views
  /<code>/payments/         → Payment callback and history
  /<code>/request/          → Public service request form
/i/<public_code>/           → Short public invoice link (no auth)
/api/auth/                  → REST API — authentication
/api/platform/              → REST API — platform operations
/api/<company_code>/        → REST API — tenant operations
```

`TenantMiddleware` (at `apps/tenants/middleware.py`) resolves the company from the URL and sets `request.company`.

---

## Code Architecture Layers

```
┌──────────────────────────────────────────┐
│  Templates (.html)                        │  ← Presentation only
├──────────────────────────────────────────┤
│  Views (views.py / views_admin.py)        │  ← HTTP / UI only, thin
├──────────────────────────────────────────┤
│  Services (services.py)                   │  ← ALL business logic lives here
├──────────────────────────────────────────┤
│  Selectors / Managers                     │  ← Read/query logic
├──────────────────────────────────────────┤
│  Models (models.py)                       │  ← Data + constraints
├──────────────────────────────────────────┤
│  Tests (tests/)                           │  ← Behavior guarantee
└──────────────────────────────────────────┘
```

**Rule:** Business decisions must live in services, never in views or templates.

---

## Key Django Apps

| App | Purpose |
|---|---|
| `apps/accounts/` | Users, authentication, roles, password reset |
| `apps/tenants/` | Companies, tenant admin views, operator management |
| `apps/orders/` | Order lifecycle, technician order views |
| `apps/invoices/` | Invoice creation, public invoice view, payment |
| `apps/payments/` | Payment gateway integration, PSP callbacks |
| `apps/payouts/` | Technician ledger, settlement, financial reports |
| `apps/notifications/` | In-app notification catalog and delivery |
| `apps/sms/` | SMS template management, outbox, credit |
| `apps/reports/` | Analytics and discount campaigns |
| `apps/platform_core/` | Platform owner panel and operations |
| `apps/public/` | Public marketing and service request form |
| `apps/dashboard/` | Role-based dashboard home views |
| `apps/api/` | REST API endpoints |
| `apps/billing/` | SaaS subscription billing (stub — not implemented) |
| `apps/communication/` | Company communication settings |

---

## Data Flow: Service Request to Payment

```
Customer → /<code>/request/
  → ServiceRequest (PENDING_REVIEW)
  
Operator → /<code>/admin/requests/
  → Approve → Order (NEW)
  
Admin → /<code>/admin/orders/<id>/assign/
  → Assign technician → Order (WAITING)
  
Technician → /<code>/tech/orders/available/
  → Accept → Order (IN_PROGRESS)
  → Complete → Order (DONE)
  → Create Invoice → Invoice (ISSUED)
  
Customer → /<code>/invoices/<id>/pay/
  → Payment initiated → PSP
  → Callback → /<code>/payments/callback/
  → Verification → Payment (PAID)
  → Invoice (PAID)
  → Platform commission created (if platform_gateway mode)
```

---

## Configuration Files

| File | Purpose |
|---|---|
| `config/settings/base.py` | Base settings for all environments |
| `config/settings/development.py` | Local dev overrides |
| `config/settings/production.py` | Production overrides |
| `config/urls.py` | Root URL configuration |
| `requirements.txt` | Production dependencies |
| `requirements-dev.txt` | Development-only dependencies |

---

## Test Suite

- **1242 tests** as of 2026-06-30
- Test runner: `python manage.py test`
- High coverage in: order lifecycle, financial logic, payment verification
- Gap areas: multi-tenant isolation, API endpoints, notification triggering

---

## Known Architectural Gaps

1. `apps/billing/` — SaaS subscription system is a stub
2. JWT token blacklisting not installed (P0-2)
3. Subscription limits defined in DB but not enforced
4. Cache backend not configured (notification throttle non-functional in multi-worker setup)
5. `admin_operator_list` missing security decorator (P0-1)

See [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md).
