---
Title: Multi-Tenancy Architecture
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/tenants/middleware.py, apps/orders/models.py, config/urls.py
Source of Truth: Code
Depends On: []
Related Documents: PERMISSIONS.md, SERVICE_LAYER.md
Reusable Across Projects: No
---

# Multi-Tenancy Architecture

---

## Design Pattern

Rasti uses **path-based multi-tenancy** — the company code is the first segment of the URL.

```
/<company_code>/admin/orders/  → admin panel for that company
/<company_code>/tech/          → technician panel for that company
```

There is **no subdomain** tenancy. All tenants share the same database. Data isolation is enforced by:
1. `TenantMiddleware` — sets `request.company`
2. `CompanyOwnedModel` base class — every model scoped to a company
3. Required `company=` filter in all queries

---

## TenantMiddleware

Location: `apps/tenants/middleware.py`

For every request matching `/<slug:company_code>/...`:
1. Looks up `Company.objects.get(code=company_code, is_active=True)`
2. Sets `request.company`
3. Returns 404 if company not found or not active

---

## CompanyOwnedModel

All company-data models inherit from a base class that includes a required `company` ForeignKey.

Examples:
- `Order`
- `Invoice`
- `Payment`
- `Customer`
- `Technician`
- `TechnicianLedgerEntry`

---

## Mandatory Query Pattern

**All** queries on company-owned models must include a `company=` filter.

```python
# CORRECT — always scope by company
order = Order.objects.get(id=order_id, company=request.company)
invoices = Invoice.objects.filter(company=request.company, status="PAID")

# FORBIDDEN — never fetch by ID alone
order = Order.objects.get(id=order_id)  # Cross-tenant data leak
invoice = Invoice.objects.get(id=invoice_id)  # Cross-tenant data leak
```

Payment callback lookup is a special case — must use `company + reference_id`:
```python
payment = Payment.objects.get(reference_id=ref_id, company=company)
```

---

## URL Namespace

Each tenant URL is prefixed with the company code and uses the `tenants` namespace.

Key app namespaces under `/<code>/`:
- `tenants` — root company URL
- `dashboard` — admin/staff dashboard
- `dashboard_technician` — technician dashboard
- `orders_technician` — technician order views
- `invoices`, `invoices_technician` — invoice views
- `payments` — payment views
- `notifications`, `notifications_technician` — notification views
- `reports` — analytics and reporting
- `sms` — SMS management
- `accounts_auth` — tenant-specific auth (redirects to `/login/`)

---

## Cross-Tenant Security Rules

1. Never trust URL parameters for company identification in business logic
2. Always use `request.company` set by TenantMiddleware
3. Use `company=request.company` in every ORM query
4. Callback URLs must validate company + reference together
5. Admin views must use `@require_tenant_role` to enforce company membership

**Known violation (P0-1):** `admin_operator_list` at `apps/tenants/views_admin.py:2125` lacks the `@require_tenant_role` decorator.

---

## Platform-Level vs Tenant-Level

| Prefix | Who sees it | Auth requirement |
|---|---|---|
| `/owner-platform/` | `PLATFORM_OWNER` only | `@require_platform_owner` |
| `/<code>/admin/` | `COMPANY_ADMIN`, `COMPANY_STAFF` | `@require_tenant_role(...)` |
| `/<code>/tech/` | `TECHNICIAN` | `@require_tenant_role("TECHNICIAN")` |
| `/<code>/invoices/` | Public + authenticated | Mixed |
| `/<code>/request/` | Public | No auth |
| `/` | Public | No auth |

The platform owner does NOT use the tenant URL scheme. They log in via `/login/` and are directed to `/owner-platform/dashboard/`.
