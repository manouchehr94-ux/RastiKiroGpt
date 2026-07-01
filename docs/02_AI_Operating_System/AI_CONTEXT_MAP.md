---
Title: AI Context Map — Task to Documents and Code
Layer: AI Operating System
Audience: AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code
Reusable Across Projects: No
---

# AI Context Map

Maps task types to the documents and code files an AI agent should read.

---

## Order Lifecycle Tasks

**When:** Creating, updating, assigning, completing, or cancelling orders.

**Read first:**
- `docs/04_Business_Rules/ORDER_RULES.md`
- `docs/05_Workflows/ORDER_LIFECYCLE.md`
- `docs/07_ADR/ADR-007-Financial-Event-Timeline.md` (if touching financial events)

**Inspect only if changing code:**
- `apps/orders/models.py` — Order model, status choices, transitions
- `apps/orders/services.py` — Order business logic
- `apps/tenants/services.py` — Company-scoped order operations
- `apps/orders/views.py` — Technician order views
- `apps/tenants/views_admin.py` — Admin order views
- `tests/test_order_*.py` or `apps/orders/tests/`

**Constraints:**
- Status machine: `PENDING_REVIEW → NEW → WAITING → IN_PROGRESS → DONE`
- Cancellation path: any status → `CANCEL_REQUESTED → CANCELLED`
- One active technician per order
- Race condition protection via `select_for_update()`

---

## Invoice Tasks

**When:** Creating, viewing, paying, or voiding invoices.

**Read first:**
- `docs/04_Business_Rules/INVOICE_RULES.md`
- `docs/05_Workflows/INVOICE_PAYMENT_FLOW.md`

**Inspect only if changing code:**
- `apps/invoices/models.py`
- `apps/invoices/services.py`
- `apps/invoices/urls.py`, `apps/invoices/urls_technician.py`
- `apps/invoices/views.py`

**Constraints:**
- PAID invoices must never be mutated (financial snapshot frozen)
- Public invoice view (`/i/<code>/`) requires no auth
- Technician can create invoice only for own completed order

---

## Payment Tasks

**When:** Initiating, verifying, or reconciling payments.

**Read first:**
- `docs/04_Business_Rules/PAYMENT_RULES.md`
- `docs/07_ADR/ADR-003-Payment-Architecture.md`
- `docs/07_ADR/ADR-004-Ledger-Discipline.md`
- `docs/07_ADR/ADR-008-Financial-Recovery-Policy.md`

**Inspect only if changing code:**
- `apps/payments/models.py`, `apps/payments/services.py`
- `apps/payments/urls.py` — callback URL is public
- `config/settings/base.py` — payment gateway config

**Constraints:**
- Payment verified only after PSP confirmation — never trust callback alone
- `NEEDS_RECONCILIATION` status for ambiguous outcomes
- Platform commission created only when: `payment_mode=platform_gateway` + `PAID` + `owner_type=platform` + `fee > 0`

---

## Technician / Payout Tasks

**When:** Technician management, wage calculation, or settlement.

**Read first:**
- `docs/04_Business_Rules/TECHNICIAN_RULES.md`
- `docs/04_Business_Rules/PAYOUT_RULES.md`
- `docs/07_ADR/ADR-005-Technician-Service-Pricing.md`
- `docs/07_ADR/ADR-006-Technician-Ledger-Statement-Architecture.md`

**Inspect only if changing code:**
- `apps/payouts/models.py`, `apps/payouts/services.py`
- `apps/tenants/views_admin.py` (technician admin views)

**Constraints:**
- `TechnicianLedgerEntry` is immutable — create reversing entries
- Statement is a calculated view, not a stored document
- Settlement uses `select_for_update()` to prevent race conditions

---

## Notification / SMS Tasks

**When:** Adding, fixing, or configuring notification or SMS events.

**Read first:**
- `docs/04_Business_Rules/NOTIFICATION_RULES.md`
- `docs/04_Business_Rules/SMS_RULES.md`

**Inspect only if changing code:**
- `apps/notifications/catalog.py` — all notification event keys (19 defined, not all triggered)
- `apps/notifications/services.py`
- `apps/sms/services.py`
- `apps/orders/technician_notifications.py` — **P0-6: line 147 has `if False`**

**Constraints:**
- Notifications are per-company configurable
- SMS credit must be checked before sending
- Technician SMS for new orders is disabled by `if False` (bug, not intentional per config)

---

## Security / Permission Tasks

**When:** Reviewing or modifying access control, decorators, or tenant boundaries.

**Read first:**
- `docs/03_Architecture/PERMISSIONS.md`
- `docs/03_Architecture/MULTI_TENANCY.md`
- `docs/11_Project_Knowledge/KNOWN_RISKS.md` (especially P0-1)

**Inspect only if changing code:**
- `apps/accounts/permissions.py` — `@require_tenant_role`, `@require_platform_owner`
- `apps/tenants/middleware.py` — `TenantMiddleware`
- `apps/tenants/operator_access.py` — `is_company_admin()` (known flaw: checks role only, not company)
- `apps/tenants/views_admin.py:2125` — `admin_operator_list` (missing decorator — P0-1)

---

## UI / Template Tasks

**When:** Modifying HTML templates, navigation, or layout.

**Read first:**
- `docs/08_Site_Map/02_ROLE_BASED_SITE_MAP.md`
- `docs/08_Site_Map/05_TEMPLATE_MAP.md`
- `docs/08_Site_Map/06_NAVIGATION_GAPS_AND_RISKS.md`

**Inspect only if changing code:**
- `templates/base_dashboard.html` — master layout
- `templates/layouts/` — 4 layout files (public, auth, error, invoice_print)
- `templates/includes/nav_platform.html` — platform sidebar
- `templates/includes/nav_customer.html` — customer sidebar
- Relevant `templates/<app>/` subfolder

**Constraints:**
- RTL layout (Persian, right-to-left)
- Technician UI: bottom nav (mobile-first)
- Admin UI: sidebar with hamburger on mobile
- Role check: `request.user.role == "TECHNICIAN"` drives layout split

---

## URL / Routing Tasks

**When:** Adding, modifying, or removing URL patterns.

**Read first:**
- `docs/08_Site_Map/01_URL_INVENTORY.md` (238 documented URL patterns)
- `docs/08_Site_Map/README.md`

**Inspect only if changing code:**
- `config/urls.py` — root URL configuration
- `apps/tenants/urls.py` — main tenant URL file (175 lines)
- Relevant `apps/*/urls*.py`

**App namespaces (must match exactly):**
`tenants`, `dashboard`, `dashboard_technician`, `orders_technician`, `invoices`, `invoices_technician`, `payments`, `notifications`, `notifications_technician`, `reports`, `sms`, `public`, `platform_core`, `api-auth`, `api-tenant`, `api-platform`, `accounts_auth`

---

## Architecture / Database Tasks

**When:** Adding models, fields, or changing database structure.

**Read first:**
- `docs/03_Architecture/SYSTEM_ARCHITECTURE.md`
- `docs/03_Architecture/DJANGO_APP_ARCHITECTURE.md`
- `docs/03_Architecture/DATABASE_MODEL.md`
- `docs/07_ADR/` — all relevant ADRs

**Inspect only if changing code:**
- `apps/*/models.py` — specific app models
- `apps/*/migrations/` — check for existing migrations
- `config/settings/base.py` — INSTALLED_APPS, database config

**Constraints:**
- All company-owned models inherit from `CompanyOwnedModel` (or equivalent base)
- Migrations must be reversible
- Never squash migrations in production without authorization

---

## Test Tasks

**When:** Writing, fixing, or running tests.

**Read first:**
- `docs/06_Quality_Assurance/TEST_STRATEGY.md`
- `docs/06_Quality_Assurance/TEST_COVERAGE_MAP.md`

**Inspect only if changing code:**
- `apps/*/tests/` or `tests/` at root level
- Fixture files in `apps/*/fixtures/`

**Run tests:**
```bash
python manage.py test apps.orders --verbosity=2
python manage.py test apps.payments --verbosity=2
python manage.py test --verbosity=1  # full suite (1242 tests)
```
