---
Title: Project Overview
Layer: Project
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: 00_Project/PROJECT_VISION.md, codebase
Source of Truth: Code + Policy
Depends On: []
Related Documents: ../11_Project_Knowledge/KNOWN_RISKS.md, ../03_Architecture/SYSTEM_ARCHITECTURE.md
Reusable Across Projects: No
---

# Project Overview — Rasti Service

---

## What Is Rasti Service?

Rasti Service is a multi-tenant SaaS platform for field-service dispatch companies in Iran.

The product is sold to service companies. Rasti does not sell the field service to end customers — it sells the software and infrastructure that companies use to run their operations.

---

## What Does the Platform Do?

Each company tenant gets a full isolated workspace to manage:

| Feature | Description |
|---|---|
| Orders | Field-service dispatch workflow from public request to completion |
| Technicians | Assignment, wage calculation, mobile-friendly technician panel |
| Customers | Customer records attached to orders |
| Invoices | Invoice generation, public payment links, PSP integration |
| Payments | PSP callback handling, manual payments, reconciliation |
| SMS | Credit-based SMS dispatch to customers and technicians |
| Notifications | In-app notification system for all roles |
| Reports | Company admin reporting (revenue, performance) |
| Accounting | Ledger and payout system (V1 implemented; full accounting is future scope) |

---

## Multi-Tenancy Model

Every company gets a unique `company_code`. All URLs are namespaced:

```
/{company_code}/admin/orders/          → Company admin panel
/{company_code}/tech/                  → Technician panel
/{company_code}/invoices/{id}/         → Public invoice
/{company_code}/request/               → Public service request form
```

Tenant isolation is enforced at the middleware level. `TenantMiddleware` sets `request.company` on every request. All querysets must filter by this company.

---

## User Roles

| Role | Description |
|---|---|
| `PLATFORM_OWNER` | Rasti staff — manages all companies |
| `COMPANY_ADMIN` | Company owner or manager |
| `COMPANY_STAFF` | Operator who manages orders day-to-day |
| `TECHNICIAN` | Field worker; sees their assigned orders |
| `CUSTOMER` | End customer (limited access) |

---

## Technology Stack

| Component | Choice |
|---|---|
| Framework | Django 5.1.3 |
| Language | Python 3.11.9 |
| Database | PostgreSQL |
| Frontend | Tailwind CSS (Django templates) |
| Auth | Session auth (admin/staff) + JWT (API) |
| SMS | Third-party SMS gateway (Iranian provider) |
| PSP | Iranian payment gateway (Zarinpal or equivalent) |

---

## Current State (2026-07-01)

- 1242 automated tests
- 238 URL patterns across 21 url files
- 199+ templates
- 5 unresolved P0 (critical) bugs — see [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md)
- Not production-ready until P0 bugs are resolved

---

## Long-Term Vision

Rasti Service should become a reliable operating system for Iranian service companies:
- Simple for small companies
- Scalable for many tenants
- Safe for money-related operations
- Extensible for full accounting, inventory, CRM, mobile apps, and APIs
