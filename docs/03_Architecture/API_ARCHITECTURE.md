---
Title: API Architecture
Layer: Architecture
Audience: Human + AI
Status: Partial — Future Scope
Last Verified: 2026-07-01
Verified Against: 01_Architecture/API_RULES.md, apps/accounts/views.py (JWT auth)
Source of Truth: ADR + Policy
Depends On: PERMISSIONS.md, MULTI_TENANCY.md
Related Documents: SERVICE_LAYER.md, SYSTEM_ARCHITECTURE.md
Reusable Across Projects: No
---

# API Architecture

---

## Current State

As of 2026-07-01, the Rasti project has:
- **No general REST API** — all views are Django HTML views
- **JWT authentication** — `rest_framework_simplejwt` is installed for future API use
- **JWT logout bug (P0-2)** — token blacklisting is broken; logout does not invalidate tokens

The API layer is planned but not implemented. All rules in this document are the **required design constraints** for when APIs are built.

---

## Required API Rules (Binding When API Is Built)

All future API endpoints must follow these rules:

### 1. Multi-Tenant Isolation
Every API endpoint that returns or modifies company data must:
- Read `request.company` from middleware (same as HTML views)
- Filter all querysets by `company`
- Return 404 (not 403) when a resource belongs to a different company

### 2. Explicit Permission Checks
- Every endpoint must declare its required role
- Use the same `@require_tenant_role`, `@require_platform_owner`, or `@require_tenant_auth` decorators
- No endpoint is public unless explicitly marked

### 3. Stable Error Codes
All API errors must return structured JSON:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable description",
  "field": "field_name_if_relevant"
}
```

Error codes must not change between releases. Error messages may be translated.

### 4. No Leaking Internal IDs
Where a UUID or opaque token is safer than an integer ID, use the opaque token. Integer PKs can be used when they carry no risk (e.g., order ID for a company admin viewing their own data).

### 5. Idempotency for Payment-Like Actions
Any API endpoint that creates a financial record must be idempotent:
- Duplicate requests must not create duplicate ledger entries
- Use idempotency keys or natural uniqueness constraints

### 6. Audit Logging for Financial Changes
Any API endpoint that creates or reads financial data must log:
- Who called it (user ID, role)
- What was changed
- When it happened

---

## JWT Configuration (Current)

JWT is installed via `rest_framework_simplejwt`. Current endpoints (Needs Verification — check `apps/accounts/urls.py`):

- `POST /api/token/` — obtain token pair
- `POST /api/token/refresh/` — refresh access token
- `POST /api/token/blacklist/` — logout (P0-2: currently broken)

**P0-2 Bug:** Token blacklisting is not working correctly. A logged-out JWT token may still be accepted. See [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md).

---

## Future API Design Notes

When the API is built, it should:
1. Version the API from day 1 (`/api/v1/`)
2. Follow the same service-layer pattern — views call `services.py`, never ORM directly
3. Use DRF (Django REST Framework) consistently
4. Have rate limiting at the tenant level (not just IP-level)
5. Return consistent pagination structure for all list endpoints
