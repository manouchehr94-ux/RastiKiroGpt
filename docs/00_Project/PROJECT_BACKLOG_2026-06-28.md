# Master Project Backlog

**Date:** 2026-06-28  
**Version:** 1.0  
**Source:** MASTER_PROJECT_AUDIT_2026-06-28.md + FINANCIAL_CORE_FINAL_AUDIT_2026-06-28.md  
**Owner:** Engineering Lead

Effort scale:
- **XS** — < 2 hours (config change, single method, 1 test file)
- **S** — half day (1–3 files, < 50 lines)
- **M** — 1–3 days (1 service + view + tests)
- **L** — 1–2 weeks (new model + service + UI + tests + migration)
- **XL** — 2–4 weeks (multiple apps, new infrastructure layer, full ADR)

---

## CATEGORY A — DevOps and Infrastructure (P0)

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| A-001 | Write `Dockerfile` and `docker-compose.yml` for local dev (Python 3.11, PostgreSQL, volume mounts) | P0 | M | None | v1.0 |
| A-002 | Create `.env.example` file with every required environment variable documented | P0 | XS | None | v1.0 |
| A-003 | Set up GitHub Actions CI pipeline: lint (flake8/ruff) → Django test suite → migration check on every push to main | P0 | M | A-001 | v1.0 |
| A-004 | Configure production environment variables and secrets management (non-.env secrets vault) | P0 | S | None | v1.0 |
| A-005 | Document and verify production cron schedule: `process_sms_outbox`, `expire_pending_payments`, `backfill_financial_ledgers`, `check_sms_credit_alerts` | P0 | S | None | v1.0 |
| A-006 | Set up automated PostgreSQL backup (daily dump + 30-day retention) | P0 | M | None | v1.0 |
| A-007 | Set up automated backup restore verification (weekly restore test to throwaway env, assert record counts) | P0 | M | A-006 | v1.0 |
| A-008 | Add Sentry SDK integration: capture `logger.critical()` / `logger.exception()` in financial services | P0 | S | None | v1.0 |
| A-009 | Write staging environment setup guide (PostgreSQL + env vars + seeded data + cron) | P0 | S | A-001 | v1.0 |
| A-010 | Create post-deploy smoke test script: initiate test payment → verify ledger → assert no PENDING backfill tasks | P0 | M | None | v1.0 |

---

## CATEGORY B — Security Hardening (P1)

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| B-001 | Add `django-ratelimit` to login view (max 10 attempts per 15 min per IP) | P1 | S | None | v1.1 |
| B-002 | Add `django-axes` for account lockout after 5 failed login attempts | P1 | S | None | v1.1 |
| B-003 | Add security headers middleware: HSTS, X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy | P1 | S | None | v1.1 |
| B-004 | Add Content Security Policy headers via `django-csp` | P1 | M | B-003 | v1.1 |
| B-005 | Configure session timeout: `SESSION_COOKIE_AGE = 28800` (8 hours idle) | P1 | XS | None | v1.1 |
| B-006 | Implement TOTP 2FA for COMPANY_ADMIN and PLATFORM_OWNER via `django-otp` | P1 | L | None | v1.2 |
| B-007 | Rate limit SMS OTP endpoints (max 5 OTP requests per phone per hour) | P1 | S | B-001 | v1.1 |
| B-008 | Rate limit payment initiation (max 5 per invoice per 10 min) | P1 | S | None | v1.1 |
| B-009 | Rate limit manual settlement view (max 10 per user per minute) | P1 | S | None | v1.1 |
| B-010 | Audit and remove any `@csrf_exempt` decorators that are not justified | P1 | S | None | v1.1 |
| B-011 | Add MIME-type validation and file size limit on `Company.logo` upload | P1 | S | None | v1.1 |
| B-012 | Move SMS provider credentials from DB to secrets vault (or env vars) | P1 | M | A-004 | v1.2 |
| B-013 | Enforce HTTPS redirect in production settings (`SECURE_SSL_REDIRECT = True`) | P1 | XS | None | v1.0 |
| B-014 | Implement password strength policy (min 8 chars, not entirely numeric) | P1 | XS | None | v1.1 |

---

## CATEGORY C — Monitoring and Observability (P1)

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| C-001 | Integrate Sentry error monitoring: `sentry-sdk[django]` + alert rules for ERROR+ | P0 | S | None | v1.0 |
| C-002 | Add `FinancialBackfillTask` admin view showing status breakdown and tasks with `attempts >= 3` | P1 | S | None | v1.1 |
| C-003 | Add health check endpoint `/health/backfill/` that returns 503 if any task has been PENDING for 30+ minutes | P1 | S | None | v1.1 |
| C-004 | Implement structured JSON logging format with consistent fields: `company_id`, `payment_id`, `event` | P1 | M | None | v1.1 |
| C-005 | Set up log aggregation (stdout → managed log service or self-hosted Loki) | P1 | M | C-004 | v1.1 |
| C-006 | Add Prometheus metrics endpoint via `django-prometheus`: DB query counts, payment success rate, SMS delivery rate | P2 | M | None | v1.5 |
| C-007 | Deploy Grafana dashboard with: payment success rate, backfill task age, SMS delivery rate, DB connection pool | P2 | L | C-006 | v1.5 |
| C-008 | Add application-level alert: email/Slack when `FinancialBackfillTask` has `attempts >= 3` | P1 | M | C-001 | v1.1 |
| C-009 | Add cron job monitoring: alert when a scheduled job has not run in > 2x its expected interval | P1 | M | A-005 | v1.1 |
| C-010 | Integrate distributed tracing with OpenTelemetry: spans for payment verify, ledger write, SMS dispatch | P3 | L | None | v2.0 |

---

## CATEGORY D — Background Jobs (P1)

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| D-001 | Evaluate Celery + Redis vs Django-Q vs Dramatiq for background job infrastructure | P1 | S | None | v1.2 |
| D-002 | Install and configure Celery + Redis broker | P1 | M | D-001 | v1.2 |
| D-003 | Convert `process_sms_outbox` management command to Celery task with exponential backoff | P1 | M | D-002 | v1.2 |
| D-004 | Convert `backfill_financial_ledgers` management command to Celery Beat task | P1 | M | D-002 | v1.2 |
| D-005 | Convert `expire_pending_payments` management command to Celery Beat task | P1 | M | D-002 | v1.2 |
| D-006 | Convert `check_sms_credit_alerts` management command to Celery Beat task | P1 | S | D-002 | v1.2 |
| D-007 | Move WeasyPrint PDF generation to Celery task with download URL on completion | P2 | M | D-002 | v1.5 |
| D-008 | Move large CSV export to Celery task with download URL on completion | P2 | M | D-002 | v1.5 |
| D-009 | Deploy Flower (Celery monitoring UI) for background job visibility | P1 | S | D-002 | v1.2 |
| D-010 | Add Celery health check to `/health/ready/` endpoint | P1 | S | D-002 | v1.2 |

---

## CATEGORY E — Order Engine Improvements

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| E-001 | Split `apps/orders/services.py` (1,200 lines) into domain-specific files: `services_create.py`, `services_assign.py`, `services_complete.py`, `services_cancel.py` | P1 | M | None | v1.1 |
| E-002 | Write ADR-011 documenting order state machine, guard conditions, and allowed transitions | P1 | S | None | v1.1 |
| E-003 | Add SLA tracking: alert when an order has been in NEW status for more than N hours (company-configurable) | P2 | L | None | v1.5 |
| E-004 | Add calendar / scheduling view for orders (by date + technician lane) | P2 | XL | None | v1.5 |
| E-005 | Add file/photo attachment support on orders (before/after, damage documentation) | P2 | L | Object storage | v1.5 |
| E-006 | Add recurring order templates (scheduled monthly service) | P2 | L | E-002 | v2.0 |
| E-007 | Add technician location check-in on order start (optional GPS record) | P3 | M | Mobile app | v2.0 |
| E-008 | Implement order batching (group multiple orders in one technician trip) | P3 | L | E-004 | v2.0 |

---

## CATEGORY F — Invoice Improvements

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| F-001 | Add VAT / tax line to `InvoiceItem` and `Invoice` (gross, net, VAT amount) | P2 | L | ADR | v1.5 |
| F-002 | Implement MOADIAN (Iranian tax system) export format | P2 | L | F-001 | v2.0 |
| F-003 | Add invoice email delivery to customer (PDF attachment via email channel) | P2 | M | Email channel | v1.5 |
| F-004 | Add invoice due-date field and automated payment reminder SMS | P2 | M | None | v1.5 |
| F-005 | Implement invoice credit note / reversal (for paid invoice corrections) | P2 | L | ADR-009 | v1.5 |
| F-006 | Add company-branded invoice PDF template (logo, header, footer customisation) | P2 | M | None | v1.5 |
| F-007 | Add invoice numbering customisation (annual reset, custom prefix per company) | P2 | S | None | v1.5 |
| F-008 | Write ADR-009 documenting refund and invoice reversal policy | P1 | S | None | v1.2 |

---

## CATEGORY G — Payment Improvements

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| G-001 | Implement full refund flow: PSP-level refund initiation + ledger reversal entry + invoice status update | P2 | XL | ADR-009 | v1.5 |
| G-002 | Add payment retry: customer can retry a failed payment on the same invoice without admin intervention | P2 | M | None | v1.5 |
| G-003 | Implement automated PSP settlement report import and reconciliation comparison against `PaymentSplitSnapshot` | P2 | L | None | v2.0 |
| G-004 | Add multi-gateway routing: route to different PSP based on amount threshold or technician type | P3 | L | None | v2.0 |
| G-005 | Add cash collection formal flow: technician records exact cash amount with timestamp | P2 | M | None | v1.5 |
| G-006 | Add payment receipt PDF (separate from invoice PDF — one-page payment confirmation) | P2 | S | None | v1.5 |

---

## CATEGORY H — Financial Core (P1–P2)

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| H-001 | Verify `process_financial_backfill` cron is scheduled in production and add monitoring | P0 | S | C-009 | v1.0 |
| H-002 | Add admin alert when any `FinancialBackfillTask` has `attempts >= 3` and status is still PENDING | P1 | S | C-001 | v1.1 |
| H-003 | Implement Financial Account Lock Layer (`TechnicianLedgerBalance` per-technician lock row) | P2 | L | None | v1.5 |
| H-004 | PostgreSQL concurrency integration tests: threaded test for concurrent `_write_entry()` | P2 | M | PG test env | v1.5 |
| H-005 | Make `idempotency_key` a required parameter in `record_manual_settlement()` | P2 | S | None | v1.2 |
| H-006 | Replace `get_balance()` full SUM with denormalised running total (requires H-003 first) | P2 | M | H-003 | v2.0 |
| H-007 | Build technician self-service statement portal (OTP login, read-only statement view) | P2 | L | Customer OTP auth | v1.5 |
| H-008 | Write ADR-009 for refund policy and its impact on the ledger | P1 | S | None | v1.2 |

---

## CATEGORY I — SMS and Notifications

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| I-001 | Add email notification channel: `EmailProvider` implementing same dispatcher interface as SMS | P1 | L | None | v1.2 |
| I-002 | Add push notification channel via Firebase Cloud Messaging (FCM) for future mobile app | P2 | L | Mobile app | v2.0 |
| I-003 | Add per-user notification preferences: each user can opt out of specific event categories | P2 | L | None | v1.5 |
| I-004 | Add notification centre UI: bell icon with unread count in header, inbox view | P2 | M | None | v1.5 |
| I-005 | Add SMS opt-out list: process STOP keyword from SMS inbox, respect opt-out in all future sends | P1 | M | None | v1.2 |
| I-006 | Add SMS delivery receipt tracking (if Melipayamak supports status callbacks) | P2 | M | None | v1.5 |
| I-007 | Add bulk SMS analytics: sent count, estimated delivery rate, response rate per campaign | P2 | M | None | v1.5 |

---

## CATEGORY J — Billing and Subscriptions

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| J-001 | Design and write ADR-010 documenting subscription lifecycle, tiers, and company deactivation | P1 | M | None | v1.2 |
| J-002 | Add subscription tier model (`SubscriptionTier`: feature flags, price, limits) | P1 | L | J-001 | v1.3 |
| J-003 | Add subscription period model with start/end dates, status (ACTIVE, EXPIRING, EXPIRED) | P1 | M | J-002 | v1.3 |
| J-004 | Implement subscription expiry: deactivate company access when subscription expires | P1 | M | J-003 | v1.3 |
| J-005 | Implement dunning sequence: email reminder at 7 days, 3 days, 1 day before expiry | P1 | M | J-003, I-001 | v1.3 |
| J-006 | Implement platform payment for subscription: company initiates payment via gateway | P2 | L | J-003 | v1.5 |
| J-007 | Add grace period (7 days after expiry before full deactivation) | P1 | S | J-004 | v1.3 |
| J-008 | Add billing history page for company admin (past subscription invoices, payment history) | P2 | M | J-006 | v1.5 |

---

## CATEGORY K — API and Integrations

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| K-001 | Add API versioning: prefix all existing endpoints with `/api/v1/`, update imports | P1 | M | None | v1.2 |
| K-002 | Add `drf-spectacular` for automatic OpenAPI spec generation and Swagger UI | P1 | S | K-001 | v1.2 |
| K-003 | Add API rate limiting: per-company token rate limits | P1 | S | B-001 | v1.2 |
| K-004 | Add API key management UI: company admin can create, rotate, and revoke API keys | P2 | M | None | v1.5 |
| K-005 | Extend API coverage to: payments (initiation + status), financial statements, technician management | P2 | L | K-001 | v1.5 |
| K-006 | Implement webhook system: `WebhookEndpoint` model, `WebhookDelivery` log, HMAC signing, Celery retry | P2 | XL | D-002, K-001 | v2.0 |
| K-007 | Write API consumer documentation (authentication guide, rate limits, example requests) | P2 | M | K-002 | v1.5 |
| K-008 | Add Python SDK as a thin wrapper around the public API, published to PyPI | P3 | L | K-006 | v3.0 |

---

## CATEGORY L — Dashboard and Reporting

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| L-001 | Add financial KPIs to company dashboard: monthly revenue, avg invoice value, payment conversion rate | P1 | M | None | v1.2 |
| L-002 | Add technician performance dashboard: orders per technician, completion rate, average rating | P1 | M | None | v1.2 |
| L-003 | Add custom date range selection on all dashboard charts | P2 | M | None | v1.5 |
| L-004 | Add exportable dashboard data (CSV/PDF of the current view) | P2 | M | None | v1.5 |
| L-005 | Implement scheduled report generation (daily/weekly/monthly summaries stored in `Report.result_data`) | P2 | L | D-002 | v1.5 |
| L-006 | Add financial reports for company admin: revenue by service category, platform fees paid | P2 | M | None | v1.5 |
| L-007 | Add platform-level reports for PLATFORM_OWNER: revenue across all tenants, top companies, pending issues | P2 | M | None | v1.5 |
| L-008 | Implement BI export: nightly snapshot to a read-optimised store (PostgreSQL materialised views or ClickHouse) | P3 | XL | None | v3.0 |

---

## CATEGORY M — Customer and Technician Portals

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| M-001 | Build customer self-service portal: OTP login, view past invoices, download receipts, pay outstanding invoices | P2 | XL | None | v1.5 |
| M-002 | Build technician self-service portal: OTP login, view balance, download statement PDF | P2 | L | H-007 | v1.5 |
| M-003 | Add customer order tracking page (public URL, no login): order status, technician ETA | P2 | M | None | v1.5 |
| M-004 | Build technician mobile PWA: accept orders, mark complete, view schedule, view earnings | P2 | XL | D-002, I-002 | v2.0 |
| M-005 | Add customer timeline: unified cross-model event feed per customer (orders, invoices, payments, SMS) | P2 | M | None | v1.5 |

---

## CATEGORY N — Data and Storage

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| N-001 | Integrate Redis cache: `get_balance()`, `CompanyPaymentSettings`, gateway lookup | P2 | M | None | v1.5 |
| N-002 | Integrate object storage (MinIO or S3): company logos, generated PDFs, order attachments | P2 | L | None | v1.5 |
| N-003 | Add PostgreSQL full-text search for orders and customers | P2 | M | None | v1.5 |
| N-004 | Add database read replica for report and statement queries | P3 | L | None | v2.0 |
| N-005 | Implement cursor-based pagination for high-volume list APIs | P2 | M | K-001 | v1.5 |
| N-006 | Add data retention policy: archive cancelled orders > 3 years, expired payments > 1 year | P3 | M | None | v2.0 |

---

## CATEGORY O — Documentation and ADRs

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| O-001 | Write ADR-009 — Refund and Invoice Reversal Policy | P1 | S | None | v1.2 |
| O-002 | Write ADR-010 — Subscription and Tenant Lifecycle | P1 | M | J-001 | v1.2 |
| O-003 | Write ADR-011 — Platform Fee Policy on All Payment Methods | P1 | S | None | v1.2 |
| O-004 | Write ADR-012 — Public API Versioning and Contract | P2 | S | K-001 | v1.5 |
| O-005 | Write developer onboarding guide (first day: run locally, run tests, seed demo data) | P1 | M | A-001 | v1.1 |
| O-006 | Write production deployment runbook (step-by-step: migrate, collect static, restart, verify) | P1 | M | None | v1.1 |
| O-007 | Write operational runbooks: SMS credit refill, backfill task intervention, payment reconciliation | P1 | M | None | v1.1 |
| O-008 | Create system architecture diagram (C4 context + container level) | P2 | M | None | v1.5 |
| O-009 | Write ADR for order state machine (guard conditions, transition table) | P1 | S | None | v1.2 |
| O-010 | Update ARCHITECTURE_INDEX with order engine, billing, API, and subscription ADR references | P1 | S | O-001, O-002 | v1.2 |

---

## CATEGORY P — Testing Improvements

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| P-001 | Add CI test run to GitHub Actions (A-003): run all 83 test files on every PR | P0 | S | A-003 | v1.0 |
| P-002 | Create PostgreSQL test environment for concurrency tests (separate from SQLite default) | P2 | M | None | v1.5 |
| P-003 | Write threaded concurrency tests for `_write_entry()` against real PostgreSQL | P2 | M | P-002 | v1.5 |
| P-004 | Write API integration tests using DRF test client (authentication, tenant scoping, CRUD) | P2 | M | None | v1.5 |
| P-005 | Write E2E payment flow test using Shaparak sandbox environment | P1 | L | A-009 | v1.2 |
| P-006 | Write load test using Locust for the payment flow (verify + callback) | P3 | M | None | v2.0 |
| P-007 | Write security tests: CSRF bypass, tenant isolation (cross-company data access attempts) | P2 | M | None | v1.5 |
| P-008 | Create shared test fixture file (`tests/conftest.py`) with common company/technician helpers | P2 | S | None | v1.5 |
| P-009 | Add coverage reporting to CI: enforce minimum 80% coverage gate | P2 | S | A-003 | v1.5 |
| P-010 | Write manual test plan for new-customer onboarding scenario (create company → first order → first payment) | P1 | M | None | v1.1 |

---

## CATEGORY Q — Product Features

| ID | Item | Priority | Effort | Dependencies | Milestone |
|---|---|---|---|---|---|
| Q-001 | Add feature flags: `CompanyFeatureFlag(company, flag_name, enabled)` with `FeatureFlagService.is_enabled()` | P2 | M | None | v1.5 |
| Q-002 | Add order photo attachments: before/after photos uploaded by technician on order completion | P2 | L | N-002 | v2.0 |
| Q-003 | Add technician rating: customer can rate technician after order completion (1–5 stars) | P2 | M | M-001 | v2.0 |
| Q-004 | Add calendar/scheduling view with drag-and-drop technician assignment | P3 | XL | E-004 | v2.0 |
| Q-005 | Add discount code redemption analytics: report showing redemption rate per campaign | P2 | M | None | v1.5 |
| Q-006 | Add customer address book: save multiple addresses per customer | P2 | M | None | v1.5 |
| Q-007 | Add order import from CSV: company uploads a CSV to batch-create orders | P3 | L | None | v2.0 |
| Q-008 | Add NPS / satisfaction survey trigger after order completion | P3 | M | M-001 | v2.0 |
| Q-009 | Add company onboarding wizard: guided step-by-step company setup (gateway, SMS, first technician) | P2 | L | None | v1.5 |
| Q-010 | Add RBAC granularity: permission model below role level (e.g., "can view invoices but not settle") | P3 | XL | None | v3.0 |

---

## Backlog Summary

| Category | P0 | P1 | P2 | P3+ | Total |
|---|---|---|---|---|---|
| A. DevOps/Infrastructure | 10 | — | — | — | 10 |
| B. Security | 1 | 13 | — | — | 14 |
| C. Monitoring | 1 | 7 | 2 | — | 10 |
| D. Background Jobs | — | 8 | 2 | — | 10 |
| E. Orders | — | 2 | 3 | 3 | 8 |
| F. Invoices | — | 1 | 7 | — | 8 |
| G. Payments | — | — | 5 | 1 | 6 |
| H. Financial Core | 1 | 3 | 4 | — | 8 |
| I. SMS/Notifications | — | 3 | 4 | — | 7 |
| J. Billing | — | 7 | 1 | — | 8 |
| K. API | — | 3 | 4 | 1 | 8 |
| L. Dashboard/Reporting | — | 2 | 5 | 1 | 8 |
| M. Customer/Technician Portals | — | — | 5 | — | 5 |
| N. Data/Storage | — | — | 4 | 2 | 6 |
| O. Documentation | — | 7 | 3 | — | 10 |
| P. Testing | 2 | 3 | 5 | 1 | 11 |
| Q. Product Features | — | — | 6 | 4 | 10 |
| **Total** | **15** | **59** | **60** | **13** | **147** |
