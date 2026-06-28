# Master Project Audit

**Date:** 2026-06-28  
**Author:** Architecture Review (New CTO Perspective)  
**Scope:** Entire SaaS platform — all 15 application modules  
**Status:** Final audit record — read-only

---

## 1. Executive Summary

### Current State

This is a **multi-tenant B2B SaaS platform for home and field service companies** (HVAC,
plumbing, electrical, cleaning, etc.) operating in the Iranian market. Companies
subscribe to the platform to manage their orders, technicians, customers, invoices, and
payments. The platform handles the full lifecycle from customer service request through
technician assignment, work completion, invoicing, and online payment collection.

The platform is built on **Django 5.2 + Django REST Framework** with PostgreSQL (SQLite
for local dev), WhiteNoise for static files, SimpleJWT for API auth, and Gunicorn as the
WSGI server. The codebase comprises **15 Django applications**, **487 URL routes**, and
**83 test files totalling ~20,500 lines of test code**.

### Overall Maturity

**MVP, with a Production-Ready Financial Core**

The business domain logic (orders, invoices, payments, financial core) is implemented at
a level of quality significantly above typical MVP. The Financial Core in particular is
production-grade. However, the operational envelope (CI/CD, monitoring, background jobs,
security hardening, backup verification) is underdeveloped, which prevents classifying
the overall platform as production-ready without conditions.

### Current Development Phase

Phase 2 of 7 (Operational Excellence) — the core domain is complete; the platform now
needs the infrastructure layer to operate it safely at production scale.

### Biggest Strengths

1. Financial Core: immutable ledger, snapshot architecture, idempotency — genuinely excellent
2. Multi-tenancy: structural (CompanyOwnedModel), not convention-based
3. Order engine: rich state machine with guard conditions, audit logs, and eligibility checks
4. SMS architecture: outbox pattern, provider abstraction, credit wallet, template system
5. ADR documentation: ADR-004 through ADR-008 form a best-in-class architecture record
6. Service layer discipline: thin views, service classes, selectors — consistent across all apps
7. Django 5.2: on the latest stable release
8. 487 URL routes: comprehensive web interface coverage

### Biggest Weaknesses

1. No CI/CD pipeline: no automated testing on commit/push
2. No background job infrastructure: cron-dependent for SMS outbox, backfill, payment expiry
3. No error monitoring: production exceptions go to log files only
4. Billing module is skeletal: subscription management is nearly absent
5. API coverage is partial: ~30% of the platform is API-accessible
6. Security hardening gaps: no 2FA, no rate limiting, no session timeout
7. `apps/orders/services.py` is 1,200 lines: approaching God-service territory
8. No Docker/docker-compose: developer onboarding is manual
9. No backup verification: financial data is not confirmed restorable
10. Reporting/BI is basic: the `Report` model exists but is underimplemented

---

## 2. Current Modules

### Module 1 — Authentication & User Management (`apps/accounts`)

**Purpose:** Custom user model (`CompanyUser` extending `AbstractBaseUser`), 5-role system
(PLATFORM_OWNER, COMPANY_ADMIN, COMPANY_STAFF, TECHNICIAN, CUSTOMER), password reset
via SMS OTP, KYC verification status for technicians, customer model.

**Implementation Status:** Complete for core use cases.  
**Estimated Completeness:** 75%  
**Production Readiness:** Yes, with conditions (missing 2FA, session timeout)

**Missing Features:**
- Two-factor authentication (TOTP or SMS) for COMPANY_ADMIN and PLATFORM_OWNER
- Session timeout after inactivity
- Login rate limiting (brute force protection)
- Device/session tracking ("logged in from 3 devices")
- Password strength policy enforcement (length, complexity)
- Account lockout after N failed logins
- OAuth2 / SSO (Google, Microsoft) for company admin login

**Refactoring Need:** Low. The model and service layer are clean.  
**Quality Score: 7/10**

---

### Module 2 — Multi-Tenancy Foundation (`apps/tenants`)

**Purpose:** Defines `Company` (the tenant entity), path-based tenant resolution via
`TenantMiddleware`, `CompanyOwnedModel` base class, `CompanyFinancialPolicy`,
`CompanyPaymentSettings`, `CompanyServiceCategory`, merchant profile (KYC), branding
settings, service request forms.

**Implementation Status:** Core multi-tenancy is solid. Per-company settings model is
comprehensive.  
**Estimated Completeness:** 80%  
**Production Readiness:** Yes

**Missing Features:**
- Self-service company registration with automated activation
- Subscription tier model (which features each company has access to)
- Company onboarding wizard (guided setup flow)
- Per-company feature flags
- Company usage metrics (active users, orders this month, etc.)
- White-label domain support (company.rasti.ir → company.mydomain.ir)
- Tenant data export (GDPR-style "download all my data")

**Refactoring Need:** Low. `tenants/models.py` is 709 lines but well-organised.  
**Quality Score: 8/10**

---

### Module 3 — Orders Engine (`apps/orders`)

**Purpose:** Full order lifecycle management — create, assign, reassign, accept, start,
complete, cancel (with approval flow), recycle, prioritise. Order items, custom fields,
eligibility guards, assignment events, cancel-request review, technician notifications.

**Implementation Status:** Most complex module. Well-implemented core with multiple guard
conditions and state machine.  
**Estimated Completeness:** 75%  
**Production Readiness:** Yes for core workflow

**Missing Features:**
- Calendar/scheduling view (visualise orders by date and technician)
- Map-based order dispatch (location-aware technician routing)
- SLA tracking (alert if order is not assigned within N hours)
- Order templates (create an order from a saved template)
- Recurring orders (monthly service visit)
- Technician mobile check-in/check-out with location
- Photo/file attachments on orders (damage documentation, before/after)
- Customer signature capture on completion
- Order batching (assign multiple orders to one technician visit)

**Refactoring Need:** **High.** `orders/services.py` is 1,200 lines. It contains
`OrderCreateService`, `OrderAssignService`, `OrderUnassignService`,
`OrderAcceptService`, `OrderStartService`, `OrderCompleteService`,
`OrderCancelService`, `OrderRecycleService` — all in a single file. This is the
highest refactoring priority in the codebase. It should be split into
`services_create.py`, `services_assign.py`, `services_complete.py`, etc.  
**Quality Score: 7/10** (good logic, poor organisation)

---

### Module 4 — Customers (`apps/accounts` + embedded)

**Purpose:** Customer model linked to a Company. Customer lookup, creation, phone
validation. Customer-club discount codes (in `apps/reports`).

**Implementation Status:** Basic. Customer model is simple.  
**Estimated Completeness:** 40%  
**Production Readiness:** Yes for current use (admin creates customers)

**Missing Features:**
- Customer self-service portal (view orders, pay invoices, download receipts)
- Customer mobile OTP login (no password required)
- Customer communication history (all SMSes and notifications sent)
- Customer lifetime value reporting
- Customer deduplication (same phone, multiple records)
- Customer segments (e.g., "all customers with >3 orders in the last 6 months")
- Customer opt-out from SMS marketing
- Customer address book (multiple saved addresses)
- Customer satisfaction / NPS survey integration

**Refactoring Need:** Low (model is simple). High investment needed for new features.  
**Quality Score: 5/10** (intentionally thin for V1)

---

### Module 5 — Invoices (`apps/invoices`)

**Purpose:** Invoice lifecycle (DRAFT → ISSUED → PAID → CANCELLED), sequential invoice
numbering, multi-item invoices, settlement snapshot (frozen financial fields at payment),
cancellation request flow, public short-URL for customer payment, technician view.

**Implementation Status:** Core lifecycle solid. Settlement freeze is production-grade.  
**Estimated Completeness:** 80%  
**Production Readiness:** Yes

**Missing Features:**
- VAT / tax line items (MOADIAN compliance for Iranian businesses)
- Invoice PDF delivery by email to customer
- Partial payments / installments
- Recurring invoices (subscription-style billing)
- Credit notes / refund invoices
- Invoice templates (company-branded PDF headers)
- Invoice numbering customisation (year-based reset, custom prefix)
- Invoice due date and payment reminder automation

**Refactoring Need:** Low. Clean service layer.  
**Quality Score: 8/10**

---

### Module 6 — Payments (`apps/payments`)

**Purpose:** Full payment lifecycle — initiation, gateway redirect, callback handling,
verification, expiry, reconciliation. Multi-provider architecture (abstract base + fake
provider + real PSP). Amount tampering detection, payment expiration. Operations
dashboard.

**Implementation Status:** Core payment flow is production-grade. Security hardening
(P8) applied thoroughly.  
**Estimated Completeness:** 75%  
**Production Readiness:** Yes, with Shaparak integration only

**Missing Features:**
- Full refund flow (initiate refund through PSP, record ledger reversal)
- Multi-gateway routing (route to different PSP based on amount, technician status)
- Real-time payment status webhook from PSP (not just callback-on-redirect)
- Payment retry (customer can retry a failed payment on same invoice)
- Multi-currency support (non-rial)
- Cash on delivery formal flow (technician records exact cash received)
- Automated PSP settlement report import and reconciliation

**Refactoring Need:** Low.  
**Quality Score: 8/10**

---

### Module 7 — Financial Core (`apps/payouts`)

**Purpose:** Immutable technician ledger (`TechnicianLedgerEntry`), immutable platform
fee ledger (`CompanyPlatformFeeEntry`), payment split snapshot, backfill task queue,
wage posting on order completion, direct gateway settlement DEBIT, technician statement
projection, statement UI with print/PDF/CSV/reconciliation.

**Implementation Status:** Complete. Architecture-frozen. See dedicated audit document.  
**Estimated Completeness:** 85%  
**Production Readiness:** Yes, with P0 conditions (monitoring, cron verification)

**Missing Features:**
- Financial Account Lock Layer (balance_after concurrency, deferred by design)
- Automated PSP reconciliation
- Technician self-service statement portal
- BI export of ledger data

**Refactoring Need:** None.  
**Quality Score: 9/10**

---

### Module 8 — SMS (`apps/sms`)

**Purpose:** SMS outbox pattern (queue rows, worker processes them), multi-provider
support (Melipayamak + fake), SMS credit wallet per company, template system (master
templates + per-company overrides), SMS inbox/conversation (incoming messages), OTP
for password reset and mobile verification.

**Implementation Status:** Comprehensive. Most sophisticated non-financial module.  
**Estimated Completeness:** 85%  
**Production Readiness:** Yes

**Missing Features:**
- Delivery receipt tracking (did the message actually reach the handset?)
- SMS opt-out list management (STOP keyword processing)
- International SMS routing (non-Iranian numbers)
- Two-way conversation escalation (route unrecognised SMS to human operator)
- Bulk SMS performance analytics (open rate proxies, response rates)
- A/B testing for SMS templates

**Refactoring Need:** Low. Good separation with providers, templates, outbox.  
**Quality Score: 8/10**

---

### Module 9 — Notifications (`apps/notifications`)

**Purpose:** Event catalog with 60+ business events, in-app notification model,
dispatcher pattern that creates both in-app notifications and queues SMS rows, signal
integration, per-company notification settings.

**Implementation Status:** Good architecture. Event catalog is comprehensive.  
**Estimated Completeness:** 70%  
**Production Readiness:** Yes for SMS and in-app channels

**Missing Features:**
- Email notification channel (zero email delivery currently)
- Push notifications for mobile apps (FCM/APNs)
- Per-user notification preferences ("only notify me for X events")
- Notification centre UI (inbox/bell for admins and technicians)
- Notification read/unread state display in the header
- Bulk notification preferences (company admin sets defaults)

**Refactoring Need:** Low.  
**Quality Score: 7/10**

---

### Module 10 — Platform Core (`apps/platform_core`)

**Purpose:** Platform-level admin functions: SMS gateway management, payment gateway
provisioning, technician KYC verification, communication template management, site
settings, SMS credit alerts, merchant profile (KYC), health check endpoints.

**Implementation Status:** Wide coverage of platform operations.  
**Estimated Completeness:** 70%  
**Production Readiness:** Partial (health checks exist; monitoring not connected)

**Missing Features:**
- Platform-level alerting dashboard (SMS credit low, backfill tasks pending, payment failures)
- Platform audit log (what did the PLATFORM_OWNER do and when?)
- Tenant quota management (limit orders/month per subscription tier)
- Automated onboarding checklist for new companies
- Platform configuration centre (all settings in one place)
- Background job monitoring dashboard

**Refactoring Need:** Medium. `platform_core/models.py` is 672 lines (some models
belong in more specific apps). `views_*.py` proliferation — 12 separate view files.  
**Quality Score: 7/10**

---

### Module 11 — Billing (`apps/billing`)

**Purpose:** Platform-level SaaS billing: company pays Rasti Service for platform
subscription access. `BillingRecord` tracks payment status.

**Implementation Status:** **Skeletal.** The model exists; the business logic is almost
entirely absent.  
**Estimated Completeness:** 20%  
**Production Readiness:** **No**

**Missing Features (i.e., most of the module):**
- Subscription tier model (feature gating per tier)
- Subscription expiry and renewal logic
- Automated dunning (payment reminder sequence before expiry)
- Platform payment integration (company pays via online gateway)
- Subscription status visible to company admin
- Grace period after expiry before company is deactivated
- Subscription upgrade/downgrade with proration
- Invoice generation for platform subscription
- Billing history visible to company admin

**Refactoring Need:** High. The existing model is a placeholder.  
**Quality Score: 2/10** (by design — intentionally thin for V1)

---

### Module 12 — API (`apps/api`)

**Purpose:** DRF REST API with SimpleJWT authentication for mobile and third-party
integration. Covers orders, invoices, notifications, reports, service requests.

**Implementation Status:** Partial. Covers core read/write operations on orders and
invoices but misses payments, financial data, technician management, SMS.  
**Estimated Completeness:** 30%  
**Production Readiness:** No (no versioning, no rate limiting, no OpenAPI spec)

**Missing Features:**
- API versioning (`/api/v1/`)
- OpenAPI spec generation (Swagger/ReDoc)
- Webhook delivery system
- Rate limiting per API key
- Payment initiation and callback via API
- Technician ledger API
- Full resource coverage matching the web interface
- API key management UI (per-company API keys)

**Refactoring Need:** Medium. API views are thin but need versioning strategy.  
**Quality Score: 5/10**

---

### Module 13 — Dashboard (`apps/dashboard`)

**Purpose:** Role-specific dashboards (company admin, technician, customer, platform
owner). Statistics, recent orders, chart data.

**Implementation Status:** Functional. Provides basic KPIs.  
**Estimated Completeness:** 55%  
**Production Readiness:** Yes for basic use

**Missing Features:**
- Financial KPIs (revenue this month, avg invoice value, payment conversion rate)
- Technician performance dashboard (orders per technician, earnings, ratings)
- Customer analytics (new vs returning, top customers by revenue)
- Custom date range selection on all charts
- Real-time updates (WebSocket or polling for live order counts)
- Exportable dashboard data (CSV/PDF of the displayed statistics)
- Platform-wide tenant health dashboard for PLATFORM_OWNER

**Refactoring Need:** Low.  
**Quality Score: 6/10**

---

### Module 14 — Reports (`apps/reports`)

**Purpose:** Report model (metadata + cached result JSONField), discount campaigns
(targeted SMS marketing with discount codes), report selectors for company and platform.

**Implementation Status:** Architecture exists but is underimplemented. Reports are
defined but outputs are basic.  
**Estimated Completeness:** 35%  
**Production Readiness:** Partial

**Missing Features:**
- Scheduled report generation (daily/weekly/monthly summaries)
- Report export (CSV, Excel, PDF)
- Financial reports (revenue by service category, invoice payment rates)
- Technician performance reports
- Customer retention / churn reports
- Platform-level reports (revenue across all tenants, top-performing companies)
- BI integration (export to data warehouse)
- Discount campaign analytics (redemption rate, revenue impact)

**Refactoring Need:** Medium. `reports/services.py` is only 14 lines — the selector/service
split needs to be completed.  
**Quality Score: 4/10**

---

### Module 15 — Public / Marketing (`apps/public`)

**Purpose:** Public-facing pages (company registration landing page, service request
forms for customers, company information pages).

**Implementation Status:** Basic.  
**Estimated Completeness:** 40%  
**Production Readiness:** Partial

**Missing Features:**
- Company registration self-service with email verification
- Platform marketing website
- Pricing/plan page
- Customer service request tracking (without login)
- SEO optimisation
- Structured data (JSON-LD) for service business listings

**Refactoring Need:** Low.  
**Quality Score: 5/10**

---

## 3. Cross-Cutting Architecture Review

### Layer Separation — Strong

The service layer pattern (`services.py`, `selectors.py`, `views.py`) is applied
consistently across all apps. Views contain no business logic. Models contain
only model-level validation. Services handle all state transitions. This is the
correct architecture for a Django project at this scale.

### Domain Boundaries — Good with One Exception

Domain boundaries are well-defined. `apps/payments` handles only customer payments;
`apps/billing` handles only platform subscriptions. The exception is `apps/orders/services.py`
at 1,200 lines — this single file handles too many order sub-domains and should be
decomposed.

### Service Layer — Excellent

Static methods in service classes, `@transaction.atomic` decorators, `select_for_update()`
for concurrency, savepoint patterns, try/except for non-blocking side effects. This is
a mature service-layer implementation that will survive the platform growing to 100+
apps with no structural change.

### Model Design — Good

`CompanyOwnedModel` base class enforces tenant scoping structurally. `TextChoices` used
throughout for type-safe enumerated fields. `PositiveBigIntegerField` for rial amounts.
Immutable ledger models with `save()` overrides. The only concern is `tenants/models.py`
(709 lines) and `platform_core/models.py` (672 lines) which contain models that should
live in more specific apps.

### View Design — Good

Views are thin. Template context is prepared by selectors. No business logic in views.
The notable exception is some older views in `platform_core` that contain inline business
decisions. The `views_*.py` proliferation (12 separate files in `platform_core`) is an
organisation smell but not a correctness issue.

### Template Organisation — Good

`templates/` mirrors the app structure. Shared components in `templates/components/` and
`templates/includes/`. Layout inheritance via `templates/layouts/`. This is clean and
maintainable.

### Test Architecture — Excellent

83 test files, ~20,500 lines of test code. Tests are organised per task/feature, not by
model. Shared fixture helpers (`_company()`, `_technician()`, etc.) are defined per file
rather than in a shared conftest — this avoids coupling but creates some duplication.
Test naming is consistent (`test_task010*`, `test_p7_*`). Django `TestCase` throughout
(single-threaded, database isolation per test).

### ADR Quality — Excellent

ADR-001 through ADR-008 form a coherent body of knowledge. ADR-006 and ADR-007
contain executable code examples and anti-pattern bans. `FINANCIAL_ARCHITECTURE_INDEX.md`
is a high-quality navigation layer. This is above average for any team size.

### Documentation — Very Good

`docs/` contains 58 markdown files across 8 sections. Business rules, domain model,
ADRs, testing strategy, deployment, and phase plans are all represented. Operational
runbooks are absent. The documentation is written for developers, not operators.

### Multi-Tenant Safety — Excellent

`CompanyOwnedModel` with mandatory `company` FK on every domain model. `TenantMiddleware`
sets `request.company` on every request. Selectors filter by company. No cross-tenant
query pattern exists without a deliberate override. This is structurally enforced, not
convention-based.

### Financial Isolation — Excellent

Financial writes are in dedicated services. Statement is read-only. No financial write
originates from views or selectors. The ADR anti-pattern ban on reading other ledger
entries to derive amounts is documented and enforced by code review. This subsystem
could be extracted as an independent micro-service without data migration.

### Dependency Direction — Good

Apps depend on: `common` (always), specific other apps (sometimes). No circular
imports detected by Django system check. `from apps.X import Y` patterns are used for
intra-app imports rather than relative imports in most cases — slightly inconsistent
but not problematic.

### Technical Consistency — Good

Python 3.11, Django 5.2, DRF 3.17, SimpleJWT throughout. Type hints used in service
method signatures. Persian strings in model `verbose_name` for admin. Jalali date support
via custom template tags. One inconsistency: some older views use function-based views,
newer ones use class-based or DRF APIView — mixed style is acceptable at this scale.

---

## 4. Missing Platform Capabilities

| # | Capability | Priority |
|---|---|---|
| 1 | CI/CD pipeline (GitHub Actions, GitLab CI, or equivalent) | P0 |
| 2 | Docker / docker-compose for local development | P0 |
| 3 | Automated DB backup with restore verification | P0 |
| 4 | Error monitoring (Sentry) | P0 |
| 5 | Environment variable management (.env + secrets vault) | P0 |
| 6 | Background job infrastructure (Celery + Redis) | P1 |
| 7 | Background job monitoring dashboard (Flower) | P1 |
| 8 | Structured logging (JSON format + log aggregation) | P1 |
| 9 | Observability dashboard (metrics for DB queries, payment rates, SMS delivery) | P1 |
| 10 | Security headers middleware (CSP, HSTS, X-Frame-Options) | P1 |
| 11 | Login rate limiting and account lockout | P1 |
| 12 | 2FA for company admin and platform owner | P1 |
| 13 | Global audit log (who did what, when) | P1 |
| 14 | Email notification channel | P1 |
| 15 | Push notifications (FCM for mobile technician app) | P2 |
| 16 | Technician mobile app / PWA | P2 |
| 17 | Customer self-service portal | P2 |
| 18 | API versioning + OpenAPI spec | P2 |
| 19 | Webhook delivery system | P2 |
| 20 | Feature flags (per-company capability gating) | P2 |
| 21 | Subscription management (billing tiers + auto-renewal) | P2 |
| 22 | Redis cache layer (session, balance, settings, gateway) | P2 |
| 23 | Object storage (S3/MinIO for logos, PDFs, order photos) | P2 |
| 24 | Full-text search (PostgreSQL FTS or Elasticsearch) | P2 |
| 25 | VAT / tax invoice lines (MOADIAN compliance) | P2 |
| 26 | Refund flow (PSP-level refund + ledger reversal) | P2 |
| 27 | Order photo/file attachments | P2 |
| 28 | Calendar / scheduling view for orders | P2 |
| 29 | Advanced reporting / BI export | P2 |
| 30 | Distributed tracing (OpenTelemetry) | P3 |
| 31 | Granular RBAC / permission matrix | P3 |
| 32 | Public API SDK (Python, JS) | P3 |
| 33 | Multi-currency support | P3 |
| 34 | Workflow engine (configurable order stages) | P3 |
| 35 | Plugin / extension architecture | P3 |
| 36 | White-label domain support | P3 |
| 37 | AI-assisted technician routing | P4 |
| 38 | AI anomaly detection on financial entries | P4 |
| 39 | Marketplace (technicians registered independently) | P4 |
| 40 | Open API platform (third-party integrations) | P4 |

---

## 5. Code Quality Review

### Folder Structure — Good

```
apps/
  accounts/       — auth, users, roles, technicians, customers
  api/            — DRF REST API
  billing/        — platform-level SaaS billing
  common/         — shared models, utils, template tags
  dashboard/      — role-specific dashboards
  invoices/       — invoice lifecycle
  notifications/  — event catalog, in-app notifications
  orders/         — order engine (most complex)
  payments/       — payment gateway integration
  payouts/        — financial core (ledger, fees, backfill)
  platform_core/  — platform admin and operations
  public/         — public/marketing pages
  reports/        — reporting, discount campaigns
  sms/            — SMS outbox, templates, providers
  tenants/        — multi-tenancy foundation
```

Well-structured. One concern: `platform_core` is a catch-all for platform admin
functionality that should eventually be split into `platform_admin`, `platform_billing`,
and `platform_monitoring`.

### Naming Consistency — Very Good

- Services: `XxxService.verb()` (static method pattern)
- Selectors: `XxxSelector.get_something()` or `XxxSelector.query_something()`
- Views: function-based (`@require_tenant_role`) or DRF APIView
- Templates: `app_name/template_name.html`
- Migrations: sequential numbering with descriptive names
- Test files: `test_task{id}_{name}.py` or `test_p{id}_{name}.py`

The `test_p*` vs `test_task*` naming is the only inconsistency — both patterns exist and
do not clearly distinguish unit from integration tests.

### Service Architecture — Very Good

The pattern is applied consistently. Service classes contain only static methods. All
state transitions go through services. `@transaction.atomic` used appropriately. The only
violation is `orders/services.py` which should be decomposed.

### Fat Models / Fat Views — Clean

No fat views. No fat models (model logic is limited to `save()` overrides for immutability,
`clean()` for validation, and `__str__`). Business logic lives in services. This is
maintained consistently.

### Transaction Usage — Good

`@transaction.atomic` on services. `select_for_update()` for concurrency-sensitive paths
(payments, ledger writes, backfill tasks). Savepoints used for IntegrityError recovery.
The double-lock in `PaymentCallbackService` is harmless but should be refactored.

### Exception Handling — Good for Financial Core, Variable Elsewhere

The financial core has explicit, well-documented exception handling. Other modules have
variable quality: some views catch `Exception` silently, others let exceptions propagate
to Django's 500 handler. A consistent exception handling strategy (with custom exception
types per domain) would improve debuggability.

### Logging — Present but Unstructured

`logging.getLogger(__name__)` is used throughout. `logger.exception()`, `logger.warning()`,
`logger.critical()` calls are meaningful. However, logging is unstructured text — no JSON
format, no consistent field names (`payment_id`, `company_id`, etc.). In production, log
triage requires text parsing rather than structured queries.

### Testability — Excellent

All business logic is in services (statically callable without HTTP context). Tests use
`TestCase` (DB isolation). Factory helper functions are consistent. Mocking is done with
`unittest.mock.patch` only where needed (never for DB — correct). The service layer design
makes adding new tests trivial.

### Reusability — Good

`CompanyOwnedModel`, phone normalization, Jalali dates, and template tags are correctly in
`apps/common`. Provider abstractions (SMS, payments) enable swapping implementations.
The selector pattern means UI and API share the same data access layer.

---

## 6. Technical Debt Register

| # | Debt | Risk | Why It Exists | Solution | Target |
|---|---|---|---|---|---|
| TD-001 | `orders/services.py` 1,200 lines | High | Organic growth; all order services added to one file | Split into `services_create.py`, `services_assign.py`, `services_complete.py`, `services_cancel.py` | v1.1 |
| TD-002 | No CI/CD pipeline | Critical | Not prioritised during initial build | GitHub Actions with `manage.py test` on every push | v1.0 (before customers) |
| TD-003 | No Docker/docker-compose | High | Local dev uses native Python | Add `Dockerfile` + `docker-compose.yml` | v1.0 |
| TD-004 | `billing` module is skeletal | High | Billing is complex and was deferred | Full subscription model with auto-renewal and dunning | v1.5 |
| TD-005 | SMS outbox cron is unverified in production | High | Management command exists but scheduling is manual | Verify cron; add monitoring | v1.0 |
| TD-006 | Payment expiry cron is unverified | High | Same as TD-005 | Verify cron | v1.0 |
| TD-007 | No structured logging | High | Not prioritised | JSON logging format + aggregation | v1.1 |
| TD-008 | No error monitoring (Sentry) | High | Not prioritised | Add Sentry SDK | v1.0 |
| TD-009 | `platform_core` is a catch-all | Medium | Platform admin grew organically | Split into domain-specific admin apps | v2.0 |
| TD-010 | Financial Account Lock deferred | Medium | V1 write volume is low | Implement when concurrent write issues observed | v1.5 |
| TD-011 | `reports/services.py` is 14 lines | Medium | Reports are underimplemented | Build full reporting service | v1.5 |
| TD-012 | API coverage 30% | Medium | API added incrementally | Full resource coverage + versioning | v1.5 |
| TD-013 | No OpenAPI / Swagger spec | Medium | Not generated | Add `drf-spectacular` | v1.5 |
| TD-014 | `record_manual_settlement` UUID fallback | Low | Programmatic callers don't exist yet | Make `idempotency_key` required | v1.2 |
| TD-015 | No PostgreSQL concurrency tests | Low | SQLite masks the race | Threaded test suite on PG | v1.5 |
| TD-016 | No session timeout configuration | Low | Not implemented | Add middleware or `SESSION_COOKIE_AGE` | v1.1 |
| TD-017 | No rate limiting | Low | Not implemented | `django-ratelimit` | v1.1 |
| TD-018 | No security headers | Low | Not implemented | `django-csp` + HSTS + X-Frame | v1.1 |
| TD-019 | WeasyPrint is synchronous in HTTP cycle | Low | V1 volume is low | Move to background task | v1.5 |
| TD-020 | Double-lock in `PaymentCallbackService` | Low | Harmless but misleading | Refactor `verify()` signature | v1.2 |

---

## 7. Business Rule Review

### Well-Defined Rules

- Invoice state machine (cannot skip states; only ISSUED invoices are payable)
- Amount tampering detection (verified amount ≠ expected → NEEDS_RECONCILIATION)
- One active invoice per order (DB constraint)
- Immutable ledger (model-level enforcement)
- Customer discount absorbed by company (ADR-006 §5)
- Technician wage computed at completion time (not at payment time)
- Payment expiry moves to NEEDS_RECONCILIATION (not FAILED)

### Missing or Ambiguous Rules

- **What happens when a PAID invoice needs to be reversed?** No refund policy is documented.
  Refund flow → ledger reversal → invoice status update is not implemented or specified.
- **Technician substitution after order start.** Can you change the technician on an
  in-progress order? The `invoice_blocks_technician_change` guard exists but the policy
  around it is implicit.
- **Platform fee on manual/cash payments.** It appears the platform fee is recorded for
  all payment methods, but the rule around cash-only companies is not explicitly documented.
- **Subscription expiry behaviour.** What happens to a company's data and access when their
  subscription expires? No rule documented or enforced.
- **Concurrent order limit per technician.** `TECHNICIAN_MAX_ACTIVE_ORDERS` exists in
  selectors but the policy decision (who set this, what it means for different service
  types) is not documented.
- **Data retention policy.** How long are cancelled orders, expired payments, and old
  ledger entries retained? No rule.

### Rules Needing ADR

- **ADR-009** — Refund and Invoice Reversal Policy
- **ADR-010** — Subscription and Tenant Lifecycle (activation, suspension, expiry, data retention)
- **ADR-011** — Platform Fee Policy (all payment methods, cash-only companies)

---

## 8. Security Review

| Area | Status | Gap | Priority |
|---|---|---|---|
| Authentication | Session-based (web) + JWT (API). `AbstractBaseUser` with hashed passwords. | No 2FA, no account lockout, no device tracking | High |
| Authorization | Decorator-based (`@require_tenant_role`). Role-checked on every view. | No RBAC granularity — all admins have identical permissions | Medium |
| Permissions | `CompanyOwnedModel` enforces data-level isolation | No row-level security in DB | Low |
| Financial security | Amount tampering detection, expiry, NEEDS_RECONCILIATION | No rate limit on payment initiation | Medium |
| Rate limiting | None | All endpoints unlimited | High |
| Audit log | None (field `created_by` exists on some models but no log table) | No record of who did what | High |
| Sensitive data | Passwords hashed (Django PBKDF2). API keys in settings/env. | No secrets vault, no key rotation policy | Medium |
| Secrets management | `python-decouple` reads from env vars. `local.py` has insecure dev key comment | Production secret key rotation is manual | Medium |
| HTTP headers | WhiteNoise serves static files. Headers not hardened. | No CSP, no HSTS, no X-Frame-Options, no X-Content-Type-Options | High |
| Session management | Django session framework. | No idle timeout, no concurrent session limit | Medium |
| Password policy | Minimum length enforced (default Django). | No complexity, no breach detection (HaveIBeenPwned) | Low |
| 2FA | Not implemented | None for any role | High |
| CSRF | Django CSRF middleware active on all POST endpoints | API uses JWT (correctly exempt). `@csrf_exempt` usage should be audited | Low |
| XSS | Django auto-escaping in templates | Custom template tags should be reviewed | Low |
| SQL Injection | Django ORM throughout (parameterized queries) | No raw SQL found | ✓ |
| Tenant isolation | Structural via `CompanyOwnedModel` and `request.company` | Cross-tenant data leak impossible without deliberate bypass | ✓ |
| File uploads | `ImageField` for company logo | No MIME-type validation, no virus scanning, no size limit enforcement | Medium |
| SMS credentials | Stored in `SmsProvider` model (DB) | Credentials in DB rather than secrets vault | Medium |

**Overall Security Score: 6/10** — Payment security is excellent; platform security needs a hardening sprint.

---

## 9. Performance Review

| Area | Status | Risk | Mitigation |
|---|---|---|---|
| Database queries | N+1 in some list views (missing `select_related`/`prefetch_related`) | Medium | Audit with `django-debug-toolbar` |
| Indexes | Financial models have composite indexes. Order, invoice indexes exist. | Low for current scale | Review as table sizes grow |
| Caching | No caching layer (Redis). Every request recomputes settings, balance, gateway. | Low now, High at scale | Add Redis cache for `get_balance()`, `CompanyPaymentSettings`, gateway lookup |
| Pagination | `list_statement()` uses limit/offset. List views have pagination. | Low for current scale | Cursor-based pagination for high-volume feeds |
| Async processing | No async. All operations synchronous in HTTP cycle. | Low for current scale | Celery for SMS outbox, PDF generation, report generation |
| Background jobs | Cron-based management commands (SMS, backfill, payment expiry) | Medium (unverified scheduling) | Move to Celery Beat |
| Large datasets | `get_balance()` does full SUM on all ledger entries per technician | Low now, High at 1,000+ entries | Denormalised running total |
| Reporting | `Report.result_data` is a JSONField — no aggregation optimisation | Low for current scale | Time-series DB or read replica for reporting |
| Search | `ILIKE` filter-based search | Low for current scale | PostgreSQL FTS or Elasticsearch |
| PDF generation | WeasyPrint synchronous in HTTP cycle | Low now (small statements) | Background task + download URL |
| Memory | WhiteNoise serves static files (efficient). No large in-memory structures identified. | Low | Monitor as file upload features are added |
| Future scaling | No horizontal scaling provisions (no shared cache, no background queue) | Medium | Redis + Celery enables horizontal scaling |

**Overall Performance Score: 5/10** — Acceptable at V1 scale; will require investment before 50+ companies.

---

## 10. Testing Review

| Area | Status | Assessment |
|---|---|---|
| Unit coverage | Financial core, orders, payments, SMS all have dedicated suites | Strong |
| Integration coverage | End-to-end payment flow tests (`test_p7_verify.py`) | Good |
| Regression tests | Named test suites run as regression (`test_task*`) | Strong |
| Concurrency tests | None — SQLite in-memory masks races | Gap |
| Performance/load tests | None | Gap |
| Security tests | `test_p10_production_security_settings.py` exists | Partial |
| Manual test plan | Not documented | Gap |
| Staging strategy | Not documented | Gap |
| Test organisation | Per-task naming is consistent; shared fixtures duplicated across files | Acceptable |
| Test runner | Django TestCase throughout | Correct; no pytest |
| Mocking strategy | `unittest.mock.patch` only where needed (never for DB) | Correct |
| Total test files | 83 files, ~20,500 lines | Above average for this codebase size |
| CI execution | Not automated | **Critical gap** |

**Overall Testing Score: 7/10** — Good coverage with a critical gap in CI automation.

---

## 11. Documentation Review

| Folder | Quality | Gaps |
|---|---|---|
| `docs/00_Project/` | Strong — vision, scope, glossary, roadmaps | Operational runbooks absent |
| `docs/01_Architecture/` | Strong — service layer, permissions, multi-tenant, payment | No deployment architecture diagram |
| `docs/02_Development_System/` | Very strong — release checklist, test checklist, ADR template | No onboarding guide for new developers |
| `docs/03_Business/` | Strong — accounting rules, invoice, payment, order rules | Refund policy missing; VAT policy missing |
| `docs/04_Testing/` | Good — test strategy, unit rules, regression | No manual test plan, no staging test plan |
| `docs/05_Deployment/` | Adequate — backup, environments, monitoring, rollback | Monitoring is described but not implemented |
| `docs/06_Phases/` | Good — phases 1-3, roadmap | Roadmap is aspirational, not actioned |
| `docs/07_ADR/` | Excellent — ADR-001 through ADR-008 | ADR-009 (refunds), ADR-010 (subscriptions) missing |

**Missing ADRs:**
- ADR-009 — Refund and Invoice Reversal Policy
- ADR-010 — Subscription and Tenant Lifecycle
- ADR-011 — Platform Fee Policy on All Payment Methods
- ADR-012 — API Versioning and Public API Contract

**Outstanding documentation gaps:**
- Developer onboarding guide
- Production deployment runbook
- Operational runbooks (cron monitoring, backfill intervention, SMS credit refill)
- Architecture diagram (system context, deployment topology)

**Overall Documentation Score: 8/10**

---

## 12. Production Readiness

### Development Environment

**Score: 7/10** — Good foundation (Django 5.2, clean settings split, SQLite for dev).
**Gap:** No Docker. No `.env.example`. Manual Python setup required.

### Staging Environment

**Score: 3/10** — No staging environment is documented or confirmed to exist.
**Required:** A staging environment that mirrors production (PostgreSQL, same cron jobs,
same environment variables) is mandatory before the first paying customer.

### Production Environment (V1 — single-digit tenants)

**Score: 6/10** — Gunicorn + WhiteNoise + PostgreSQL are correct. Health check endpoints
exist. `production.py` settings file exists.  
**Gaps:** No confirmed cron scheduling, no error monitoring, no backup verification,
no security headers.

### Enterprise Production (100+ tenants, high volume)

**Score: 2/10** — Missing: Celery, Redis, object storage, CDN, horizontal scaling,
distributed tracing, advanced monitoring, RBAC, multi-region.  
Not in scope for V1 but a clear roadmap exists.

---

## 13. Product Vision

### 1 Year (2027)

If architecture discipline continues: the platform reaches 10–20 active companies, the
operational layer is complete (Celery, monitoring, CI/CD), the customer and technician
portals are live, the API is versioned and documented, and billing is fully automated.
The Financial Core is running in production without manual intervention. Monthly revenue
from subscriptions is measurable.

The biggest risks to achieving this: billing module delay blocks subscription automation;
CI/CD absence slows deployment confidence; security hardening gaps delay enterprise
prospects.

### 3 Years (2029)

With consistent execution: 50–200 companies across multiple service verticals (HVAC,
plumbing, cleaning, pest control). A public API with documented webhooks enables third-party
integrations. A marketplace allows technicians to register independently and be found by
multiple companies. Mobile apps (iOS/Android) for technicians replace the web portal.
BI reporting provides company owners with genuine business insights.

### 5 Years (2031)

At scale: the platform becomes the dominant field-service management SaaS in the Iranian
market, with potential for regional expansion (Turkey, Gulf). AI-assisted dispatch
optimises technician routing in real time. The plugin architecture allows vertical-specific
customisations. The financial layer is expanded to support company-to-technician advance
payments, benefit programs, and potentially direct IBAN settlement.

---

## 14. Final CTO Verdict

### Would I continue investing in this project? **Yes, unconditionally.**

The architecture decisions are sound. The Financial Core is production-grade. The service
layer discipline will allow the team to scale without accumulating architectural debt.
The documentation quality is exceptional. These are not easy to retrofit — they were done
correctly from the start.

### Would I rewrite any subsystem? **No.**

No subsystem needs a rewrite. `orders/services.py` needs to be split (not rewritten),
and `billing` needs to be built out (not redesigned). The model design, service layer,
and multi-tenancy foundation do not require changes.

### Would I freeze any subsystem? **Yes — the Financial Core.**

The Financial Core is architecture-frozen per ADR-004 through ADR-008. This is correct.
No new financial features should be added without an ADR update and regression sign-off.

### Would I approve paying customers today? **Yes, with three conditions:**

1. The `FinancialBackfillService` cron must be verified as running and monitored.
2. Error monitoring (Sentry or equivalent) must be active in production.
3. An end-to-end payment flow test must be completed in a staging environment.

These three conditions are 1–2 days of work each. They are not architectural — they are
deployment hygiene. Without them, a production payment failure could go unnoticed.

### Would I approve enterprise customers? **Not yet.**

Enterprise customers require: 2FA, audit log, RBAC granularity, SLA guarantees,
enterprise billing, and a Service Level Agreement. None of these exist. Target: 12–18
months of operational maturity before approaching enterprise.

### Would I approve international expansion? **Not yet.**

The platform is tightly coupled to Iranian market specifics: Shaparak (Iranian PSP),
Melipayamak (Iranian SMS), Jalali dates, rial currency, MOADIAN tax system. International
expansion requires a modular provider layer for all market-specific dependencies, plus
multi-currency, multi-timezone, and legal entity separation. Target: phase 4 (36+ months).

---

**Summary verdict:** A strong MVP with a production-grade financial core, built on an
architecture that will scale. The team has earned the right to onboard paying customers
after closing the operational hygiene gaps. The investment is justified.
