---
Title: Permissions and Access Control
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/accounts/permissions.py, apps/tenants/middleware.py, apps/tenants/views_admin.py
Source of Truth: Code
Depends On: MULTI_TENANCY.md
Related Documents: ../11_Project_Knowledge/KNOWN_RISKS.md
Reusable Across Projects: No
---

# Permissions and Access Control

---

## User Roles

| Role | Code | Scope | Description |
|---|---|---|---|
| Platform Owner | `PLATFORM_OWNER` | Platform-wide | Manages all companies, PSP, KYC |
| Company Admin | `COMPANY_ADMIN` | One company | Full company management |
| Company Staff / Operator | `COMPANY_STAFF` | One company | Order management, limited settings |
| Technician | `TECHNICIAN` | One company | Order execution, own invoices |
| Customer | `CUSTOMER` | One company | Invoice view, payment |

Roles are defined in `UserRole` TextChoices at `apps/accounts/models.py`.

---

## Permission Decorators

### `@require_tenant_role(*roles)`

Location: `apps/accounts/permissions.py`

Checks:
1. User is authenticated
2. User belongs to the tenant company in the URL (`request.company`)
3. User's role matches one of the specified roles

Usage:
```python
from apps.accounts.permissions import require_tenant_role

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def admin_order_list(request, **kwargs):
    ...
```

### `@require_tenant_auth`

Checks authentication + company membership only (no role check).
Used for views accessible by multiple roles.

### `@require_platform_owner`

Checks that the user has `PLATFORM_OWNER` role.
Used for all `/owner-platform/` views.

---

## What Each Role Can Do

### PLATFORM_OWNER

- Access: `/owner-platform/` only
- Can: activate/deactivate payment mode, approve KYC, create/activate gateways
- Can: run reconciliation, resolve `NEEDS_RECONCILIATION`, record platform fee settlement
- Cannot: access any tenant company panel directly

### COMPANY_ADMIN

- Access: `/<code>/admin/` — all admin routes
- Can: manage company users and technicians
- Can: manage orders/invoices within company
- Can: submit KYC, view payment status
- Can: record manual/cash payments per policy
- Can: manage SMS templates, company settings, analytics
- Cannot: activate online payment mode
- Cannot: create platform-owned gateway

### COMPANY_STAFF (Operator)

- Access: `/<code>/admin/` — limited subset
- Can: manage orders (list, detail, create, edit, assign)
- Can: manage customers (list, detail)
- Can: view invoices
- Can: manage public service requests
- Can: send and view notifications
- Cannot: company settings, technician management, financial reports, SMS billing

### TECHNICIAN

- Access: `/<code>/tech/` only
- Can: view and accept available orders
- Can: complete own orders
- Can: create invoices for own completed orders
- Can: view own technician notifications
- Cannot: access admin panel, customer data, company settings

### CUSTOMER

- Access: `/<code>/invoices/`, `/<code>/payments/`
- Can: view own invoices, make payments
- Note: Customer dashboard (`/<code>/customer/`) redirects to public page since Phase 24

---

## Known Security Issue — P0-1

**File:** `apps/tenants/views_admin.py:2125`

`admin_operator_list` is missing its `@require_tenant_role("COMPANY_ADMIN")` decorator.

Any authenticated user (including technicians and customers) who knows the URL can:
- View the operator list
- Create, edit, or delete operators

Additionally, `is_company_admin()` in `apps/tenants/operator_access.py` checks role only — NOT company membership. This creates a cross-tenant escalation path.

**Comparison:**
```python
# admin_operator_create at line 1964 — has duplicate decorator (error) but IS protected
@require_tenant_role("COMPANY_ADMIN")
@require_tenant_role("COMPANY_ADMIN")  # duplicate — one should be removed
def admin_operator_create(request, **kwargs):

# admin_operator_list at line 2125 — MISSING decorator entirely
def admin_operator_list(request, **kwargs):  # BUG: P0-1
```

**Fix:**
```python
@require_tenant_role("COMPANY_ADMIN")
def admin_operator_list(request, **kwargs):
```

---

## Middleware

### TenantMiddleware

Location: `apps/tenants/middleware.py`

Runs on every request to `/<company_code>/` URLs. Sets `request.company` from URL slug.

### OperatorPermissionMiddleware

Location: `apps/tenants/operator_access.py`

Handles operator-specific permission checks. Known issue at line 764: unauthenticated users pass through. The middleware relies on `is_company_admin()` which checks role only, not company membership.

---

## Authentication

- Web UI: Django session authentication
- REST API: JWT tokens via `rest_framework_simplejwt`
- Login URL: `/login/` (unified for all roles)
- Backend: `AllowAllUsersModelBackend` — allows inactive users to authenticate; activity is checked in the view layer only

**Known issue (P0-2):** JWT logout does not blacklist tokens because `rest_framework_simplejwt.token_blacklist` is not in `INSTALLED_APPS`. Tokens remain valid after logout.
