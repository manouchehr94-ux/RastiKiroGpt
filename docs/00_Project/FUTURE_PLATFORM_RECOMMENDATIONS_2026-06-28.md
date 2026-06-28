# Future Platform Recommendations

**Date:** 2026-06-28  
**Author:** Principal Architect Review  
**Scope:** Entire SaaS platform — not only Financial Core  
**Status:** Strategic roadmap — not a sprint plan

---

## Purpose

This document captures everything the platform should eventually become, viewed from the
perspective of a Principal Architect who has reviewed the current state and is planning
for 3–5 years of growth. Each recommendation includes why it matters, the suggested
implementation phase, and priority.

Priority model:
- **P0** — Required before the first paying customer
- **P1** — Required before ~10 active companies
- **P2** — Required before ~100 active companies
- **P3** — Enterprise scale (100+ companies, high volume)
- **P4** — Long-term vision

---

## Platform Health Matrix

| Area | Score (/10) | Confidence | Notes |
|---|---:|---|---|
| Orders | 7 | Medium | Core workflow is solid. Limited custom fields, no workflow branching, no SLA tracking. |
| Invoices | 8 | High | State machine, counter, settlement freeze, cancellation are all well-implemented. |
| Payments | 8 | High | Security hardening, callback validation, amount tampering detection, expiry handling. Single PSP (Shaparak). |
| Financial Core | 8 | High | Immutable ledger, snapshot amounts, idempotency, backfill recovery. Operational monitoring gap. |
| Multi-Tenant | 9 | High | CompanyOwnedModel throughout, TenantMiddleware, per-company gateway/policy. Very solid. |
| Security | 6 | Medium | Payment security is good. No 2FA, no rate limiting, no audit log, no signed webhooks, basic auth model. |
| Performance | 5 | Low | No caching, SUM-based balance, synchronous PDF, no CDN, no async jobs for heavy operations. |
| Testing | 8 | High | Good unit and integration coverage. Missing: PostgreSQL concurrency, load tests, contract tests. |
| Documentation | 9 | High | ADR system is exceptional. Business rules well-documented. Operational runbooks absent. |
| Deployment Readiness | 5 | Low | No verified CI/CD, no health endpoints, no structured monitoring, no rollback verification. |

**Overall Platform Maturity: MVP, trending toward Production Ready**

The core domain logic (orders, invoices, payments, financial) is stronger than most SaaS
products at this stage. The operational and security layers are the gaps that prevent
calling this "production ready" without conditions.

---

## Recommendations

---

### REC-001 — Health Check Endpoints

**Why it matters:** Without a `/health/` endpoint, load balancers cannot verify the
application is alive. Deployment pipelines cannot confirm a deploy succeeded. On-call
engineers cannot distinguish "application down" from "database down" without SSH access.

**Implementation:** A simple view returning `{"status": "ok", "db": "ok", "timestamp": "..."}`.
Include a deep health check (`/health/ready/`) that verifies DB connectivity, pending
backfill task count, and critical service availability.

**Priority:** P0  
**Phase:** Immediately

---

### REC-002 — Error Monitoring (Sentry or Equivalent)

**Why it matters:** Right now, production exceptions are visible only in server logs —
if anyone is reading them. Without error monitoring, the first indication of a
production bug is often a customer complaint. For a financial platform, silent exceptions
are especially dangerous.

**Implementation:** Integrate Sentry (or equivalent: Rollbar, Bugsnag). Configure it to
alert on `logger.critical()` calls — which the financial core already uses for double
failures. Tag events with `company_id` and `payment_id` for fast triage.

**Priority:** P0  
**Phase:** Immediately

---

### REC-003 — Background Job Infrastructure (Celery + Redis/RabbitMQ)

**Why it matters:** The current architecture relies on management commands run by cron for
all async work: financial backfill, SMS delivery, PDF generation. Cron is not reliable,
not observable, not retriable, and not parallelizable. As task volume grows, cron becomes
a liability.

**Implementation:** Replace management command cron with Celery Beat (scheduling) + Celery
workers (execution). Each `FinancialBackfillTask` becomes a Celery task with exponential
backoff. PDF generation, SMS, and notifications all move to background workers. Use Flower
for the task dashboard.

**Priority:** P1  
**Phase:** Before ~10 companies

---

### REC-004 — Global Audit Log

**Why it matters:** Who did what, when, to which record? This question arises in every
serious business: compliance audits, customer disputes, internal investigations. Right now
the answer requires grepping logs, which does not scale.

**Implementation:** A `AuditLogEntry` model capturing: `actor` (CompanyUser), `action`
(created/updated/deleted/verified/settled), `entity_type`, `entity_id`, `company`,
`timestamp`, `ip_address`, `diff` (JSONField with before/after for mutations). Write to it
from a Django signal or a mixin on `save()`. Financial entries (ledger, platform fee) are
already immutable so their audit is implicit — but user actions (creating invoices,
completing orders, manually settling) need explicit audit entries.

**Priority:** P1  
**Phase:** Before ~10 companies — required for any financial dispute resolution

---

### REC-005 — Structured Logging and Observability

**Why it matters:** The current logging uses `logger.exception()`, `logger.warning()`, etc.
without structured fields. Searching logs for "all financial failures for company 42" is
not possible without text parsing. At scale, text log parsing is unreliable and slow.

**Implementation:** Move to structured logging (JSON format) with consistent fields:
`{"level": "error", "company_id": 42, "payment_id": 17, "event": "ledger_write_failed", "key": "..."}`.
Integrate with a log aggregation platform (Loki, OpenSearch, CloudWatch Logs). Add
dashboards for financial event rates, backfill task counts, payment success rates.

**Priority:** P1  
**Phase:** Before ~10 companies

---

### REC-006 — Background Job Dashboard

**Why it matters:** Operators need to see the current state of all background work without
SSH access. How many backfill tasks are pending? How many SMS messages failed? Is the
cron running?

**Implementation:** A Django admin view (or Flower if using Celery) showing:
- `FinancialBackfillTask` summary (pending/processing/resolved/failed counts)
- Recent job runs with duration and outcome
- Any task with `attempts >= 3` highlighted in red
- Last successful run of each job type

**Priority:** P1  
**Phase:** Before ~10 companies

---

### REC-007 — Rate Limiting

**Why it matters:** Without rate limiting, the platform is vulnerable to: API abuse,
SMS flooding (and associated cost), form resubmission loops, brute-force login attempts,
and denial-of-service on payment endpoints.

**Implementation:** Apply rate limits at multiple layers:
- Login: 10 attempts per 15 minutes per IP
- SMS: 5 messages per technician per hour
- Payment initiation: 3 per invoice per 10 minutes
- Manual settlement: 10 per user per minute
- PDF export: 5 per user per minute

Use `django-ratelimit` or a Redis-backed middleware.

**Priority:** P1  
**Phase:** Before ~10 companies — required before public-facing features

---

### REC-008 — API Versioning

**Why it matters:** The platform will eventually have a public API (mobile apps, third-party
integrations, customer portals). Once external callers depend on an API, breaking changes
require versioning. Without versioning from the start, every API change is a potential
breaking change that must be coordinated with all consumers simultaneously.

**Implementation:** Prefix all public API endpoints with `/api/v1/`. Use a request header
(`Accept: application/vnd.rasti.v1+json`) or URL path for versioning. Document the
deprecation policy (minimum 6 months notice for breaking changes).

**Priority:** P1  
**Phase:** Before the first external API integration

---

### REC-009 — Notification Center

**Why it matters:** Currently SMS is the only outbound notification channel. Email,
in-app notifications, and push notifications are all missing. Technicians cannot receive
new order assignments unless someone calls them. Company admins have no in-app alert
system.

**Implementation:** A `Notification` model with: recipient, channel (sms/email/push/in-app),
template, status, sent_at. A `NotificationService` that dispatches to channel adapters.
A per-user notification preference model. An in-app notification bell with an unread count.

**Priority:** P1  
**Phase:** Before ~10 companies

---

### REC-010 — Customer Timeline

**Why it matters:** A customer's journey — from first contact through order completion,
invoice payment, and any disputes — is currently scattered across Order, Invoice, Payment,
and SMS records. There is no unified view of "what happened with customer X." This makes
customer support conversations very difficult.

**Implementation:** A read-only `CustomerTimeline` projection that assembles events from
multiple models (order status changes, invoice events, payment events, SMS sent) into a
single chronological feed per customer. Implemented as a service layer read (no new DB
writes), optionally cached.

**Priority:** P1  
**Phase:** Before ~10 companies

---

### REC-011 — Feature Flags

**Why it matters:** As the platform grows, some features should roll out gradually (to
beta tenants, to high-trust tenants, or only after specific setup steps). Without feature
flags, a new feature is either on for everyone or deployed as a separate code branch —
neither is safe.

**Implementation:** A simple `CompanyFeatureFlag` model: `company`, `flag_name`, `enabled`.
A `FeatureFlagService.is_enabled(company, flag)` helper. No external dependency needed
for V1; use the DB. Migrate to a dedicated service (LaunchDarkly, Unleash) at scale.

**Priority:** P2  
**Phase:** Before ~100 companies

---

### REC-012 — Permission Matrix and RBAC Granularity

**Why it matters:** The current role system is coarse: `COMPANY_ADMIN`, `TECHNICIAN`,
`PLATFORM_ADMIN`. As the platform matures, tenants will want to grant specific permissions:
"this user can view invoices but not settle them," "this technician can complete orders but
not view the ledger." The current model cannot express this without adding new roles.

**Implementation:** Introduce a `Permission` model with named capabilities
(`invoice.settle`, `ledger.view`, `order.complete`) and a `RolePermission` join model.
Replace hard-coded role checks with `has_permission(user, "invoice.settle")` calls. This
is a prerequisite for any multi-user company scenario (office manager, field supervisor,
etc.).

**Priority:** P2  
**Phase:** Before ~100 companies

---

### REC-013 — Cache Strategy (Redis)

**Why it matters:** The following operations are currently computed on every request:
technician balance (full SUM), statement projection (full ledger scan), company settings
(multiple FK traversals), gateway lookup. At scale, these dominate database load.

**Implementation:**
- Cache `get_balance()` result with a 60-second TTL, invalidated on each ledger write.
- Cache `CompanyPaymentSettings` per company with a 5-minute TTL.
- Cache the company's active gateway with a 10-minute TTL.
- Use Django's cache framework with Redis backend. Mark cache keys by `company_id` for
  easy tenant-scoped invalidation.

**Priority:** P2  
**Phase:** When DB query time on statement views exceeds 500ms

---

### REC-014 — Public API and Webhook System

**Why it matters:** Tenants will want to integrate this platform with their own systems:
CRMs, ERPs, accounting software, mobile apps. A public REST/GraphQL API and a webhook
system are the standard mechanism for this. Without them, integrations require screen
scraping or manual data entry.

**Implementation:**
- Public REST API under `/api/v1/` covering: orders, invoices, payments, technicians.
- `WebhookEndpoint` model: tenant registers a URL + secret + event types.
- `WebhookDelivery` model: tracks each delivery attempt, status, response code.
- HMAC-SHA256 signature on every webhook payload.
- Delivery via Celery task with exponential backoff on failure.

**Priority:** P2  
**Phase:** Before the first third-party integration

---

### REC-015 — Search Infrastructure

**Why it matters:** As invoice and order counts grow, the current filter-based views become
insufficient. Searching "all invoices mentioning customer phone 0912..." or "all orders
containing 'boiler repair'" requires full-text search that Django ORM filter chains cannot
efficiently provide.

**Implementation:** Integrate PostgreSQL full-text search (using `django.contrib.postgres.search`)
for the V1 approach — no additional infrastructure. At scale, evaluate Elasticsearch or
OpenSearch for cross-model search with faceting.

**Priority:** P2  
**Phase:** When tenants with 1,000+ orders report unusable search performance

---

### REC-016 — BI / Reporting Layer and Data Warehouse

**Why it matters:** Business owners want to answer questions like: "What is my top
technician's revenue this month?", "Which service category generates the most platform
fee?", "What percentage of invoices are paid online vs. cash?". These questions require
joins across many tables and should not run on the production OLTP database.

**Implementation:**
- Phase 1: A reporting app with pre-computed summary views (daily/weekly/monthly aggregates,
  stored in a `ReportSnapshot` table via a scheduled task).
- Phase 2: Export pipeline to a read replica or data warehouse (Redshift, BigQuery,
  ClickHouse). Build BI dashboards using Metabase or Superset.

**Priority:** P2  
**Phase:** When tenants request historical reporting beyond the 30-day statement view

---

### REC-017 — Mobile API (REST + Push Notifications)

**Why it matters:** Technicians in the field do not use a desktop browser. They need a
mobile app (or PWA) to receive new order assignments, complete orders, view their balance,
and collect payments. The current web interface is not optimised for mobile field use.

**Implementation:**
- A `MobileAPIAuth` token model (JWT or OAuth2) separate from session auth.
- REST endpoints for: technician profile, assigned orders, order completion, payment
  collection, ledger balance.
- Firebase Cloud Messaging (FCM) for push notifications to technician devices.
- A separate `MobileAPIRateLimit` policy to protect from mobile client storms.

**Priority:** P2  
**Phase:** When the first technician reports the web interface is unusable on their phone

---

### REC-018 — Disaster Recovery and Backup Verification

**Why it matters:** Backups are not a safety net unless they are verified to be
restorable. Most SaaS platforms have backups; most have never tested restoring them.
For a financial platform with immutable ledger data, a corrupted or missing backup is
a business-ending event.

**Implementation:**
- Daily automated DB dump + restoration test to a throwaway environment.
- Verification script: restore backup, run a subset of financial integrity tests
  (`test_task007a_financial_integrity`), report pass/fail to monitoring.
- Backup encryption at rest.
- Restore procedure documented and tested by a human at least once per quarter.

**Priority:** P0 (backup must exist), P1 (verification must be automated)  
**Phase:** Immediately

---

### REC-019 — Security Hardening

**Why it matters:** The current security model covers payment-level protections (amount
tampering, callback validation, expiry). Platform-level security is underspecified.

**Specific gaps:**
- No enforced HTTPS redirect
- No Content Security Policy headers
- No HSTS headers
- No 2FA for company admins with financial access
- No session timeout on idle admin sessions
- No IP allowlist option for high-privilege operations
- No signed-in-device tracking

**Implementation:**
- Add `django-csp` for Content Security Policy.
- Add `django-axes` for login rate limiting and account lockout.
- Add TOTP-based 2FA (`django-otp`) for company admin accounts.
- Implement session expiry after 8 hours of inactivity.
- Add security headers middleware (HSTS, X-Frame-Options, X-Content-Type-Options).

**Priority:** P1  
**Phase:** Before ~10 companies

---

### REC-020 — Distributed Tracing

**Why it matters:** At scale, a slow request could be caused by a slow database query, a
slow external API call (Shaparak), a slow cache miss, or a slow background job. Without
distributed tracing, diagnosing cross-service latency issues requires guesswork.

**Implementation:** Integrate OpenTelemetry with auto-instrumentation for Django, SQLAlchemy
(ORM queries), and external HTTP calls. Export traces to Jaeger or Tempo. Add custom spans
for financial service calls (`verify_payment`, `create_snapshot`, `post_for_payment`).

**Priority:** P3  
**Phase:** When p95 latency on financial endpoints exceeds 2 seconds in production

---

### REC-021 — Plugin / Extension Architecture

**Why it matters:** Different tenants will have different needs: custom invoice fields,
custom order workflows, custom payment gateways, custom SMS templates, custom notification
triggers. Without an extension model, every customisation requires a code change and a
deployment.

**Implementation:**
- A `PluginRegistry` that allows registering hooks at defined extension points:
  `on_order_completed`, `on_invoice_paid`, `on_payment_verified`.
- Per-tenant plugin configuration.
- Sandboxed execution (no arbitrary code execution; plugins are registered Python classes,
  not user scripts).
- A first-party plugin for Shaparak split routing (currently hard-coded) as a reference
  implementation.

**Priority:** P3  
**Phase:** When the first enterprise tenant requests a custom integration that cannot be
configured without code

---

### REC-022 — Object Storage for Documents

**Why it matters:** PDF statements are currently generated on-demand. As technician history
grows, generated PDFs become slow to produce and expensive to regenerate. Generated invoices
sent to customers need a permanent, accessible URL. Media uploads (order photos, damage
documentation) need a storage layer that is not the application server.

**Implementation:** Integrate S3-compatible object storage (AWS S3, MinIO, Liara Object
Storage). Store: generated PDFs (with pre-signed download URLs), invoice PDFs sent to
customers, order media attachments, backup archives.

**Priority:** P2  
**Phase:** When PDF generation time exceeds 3 seconds or storage on the application server
exceeds 1GB

---

### REC-023 — Customer Self-Service Portal

**Why it matters:** Customers currently have no visibility into their own invoices or
payment history. They receive an invoice link but cannot log in to see past transactions.
This creates support load: "what did I pay for in March?" becomes an admin task.

**Implementation:**
- A customer-facing portal (separate from the company admin) with: invoice history,
  payment status, ability to pay outstanding invoices online, PDF download.
- Customer authentication via phone OTP (no password required — SMS-based login).
- Read-only access scoped strictly to their own invoices and payments.

**Priority:** P2  
**Phase:** When customer support requests about "what did I pay" exceed 10% of all support
tickets

---

### REC-024 — Technician Self-Service Portal

**Why it matters:** Technicians currently have no way to view their own balance, statement,
or payment history without asking the company admin. The ledger and statement engine
already exists — it just needs a technician-facing UI with appropriate authentication.

**Implementation:**
- A technician-facing portal (mobile-first) with: statement view, balance display, PDF
  download of their own statement.
- Authentication via OTP (phone-based, no company admin required).
- Read-only; no financial writes from the technician portal.

**Priority:** P2  
**Phase:** When the first technician dispute about their balance is reported

---

### REC-025 — Workflow Engine for Order State

**Why it matters:** The current order state machine is simple: draft → in_progress → done.
Real field service workflows are more complex: quote → accepted → scheduled → en_route →
arrived → in_progress → completed → quality_checked → invoiced. Without a flexible state
machine, every new workflow step requires a code change.

**Implementation:**
- A configurable state machine per company (company can define their own order stages).
- Optional SLA timers (alert if an order has been in "arrived" state for more than 30 min).
- Stage-specific mandatory fields (e.g., "technician must upload a photo before marking
  complete").
- Built on top of the existing `Order` and `OrderStatusLog` models.

**Priority:** P3  
**Phase:** When the first enterprise tenant requires a multi-stage workflow

---

### REC-026 — AI-Assisted Operations

**Why it matters:** As the platform scales, manual review of anomalies becomes infeasible.
AI can assist with: anomaly detection in financial entries, smart routing of new orders to
available technicians, automatic categorization of customer service requests, and predictive
maintenance scheduling.

**Specific near-term use cases:**
- **Anomaly detection:** Flag `TechnicianLedgerEntry` rows with an amount > 2 standard
  deviations from the technician's historical average. Alert for manual review.
- **Smart order routing:** Given a new order's location and category, suggest the most
  available technician with relevant `TechnicianServiceRate` entries.
- **Duplicate invoice detection:** Flag invoices from the same order within 24 hours as
  potentially duplicate.

**Implementation:** Start with rule-based heuristics (no ML required). Move to ML models
when labelled training data from the platform is available (typically after 12+ months of
real data).

**Priority:** P4  
**Phase:** When the platform has enough data to train meaningful models (>10,000 orders)

---

### REC-027 — Multi-Currency and Multi-PSP Support

**Why it matters:** The current platform is hard-coded to rial (Shaparak). If the platform
expands to other markets (or if clients operate internationally), this assumption must be
relaxed.

**Implementation:**
- Add a `currency` field to `Invoice`, `Payment`, and `TechnicianLedgerEntry` (default
  `"IRR"` for backwards compatibility).
- Abstract the PSP layer (already partially done via `PaymentGateway.gateway_type`) to
  support multiple PSP adapters per company.
- Add currency conversion audit trail for cross-currency transactions.

**Priority:** P3  
**Phase:** When the first non-rial client is onboarded

---

### REC-028 — SDK and Developer Documentation

**Why it matters:** Once the public API exists (REC-014), third-party developers need to
integrate with it. Without an SDK, every integration is a custom HTTP client. Without
documentation, integrations are impossible.

**Implementation:**
- An OpenAPI spec generated from Django REST Framework (`drf-spectacular`).
- Auto-generated SDKs for Python, JavaScript, and PHP (the most common languages in the
  Iranian SaaS ecosystem) via `openapi-generator`.
- A developer portal with: authentication guide, webhook guide, example use cases,
  sandbox environment access.

**Priority:** P3  
**Phase:** When the first third-party developer integration is requested

---

### REC-029 — Incremental Invoice Counter Resilience

**Why it matters:** The current `InvoiceCounter` uses `select_for_update()` with
`get_or_create()` to generate sequential invoice numbers. Under very high invoice creation
rates (thousands per second), this serialization becomes a bottleneck. A gap in the
sequence (from a failed transaction) may also cause compliance questions in formal audit
scenarios.

**Implementation:** For V1, the current approach is correct and sufficient. At scale,
consider a PostgreSQL sequence (`CREATE SEQUENCE`) per company, which is contention-free
and never produces gaps under concurrent load.

**Priority:** P3  
**Phase:** When invoice creation rate exceeds 100/minute per company

---

### REC-030 — Compliance and Tax Integration

**Why it matters:** Iranian businesses are subject to VAT reporting requirements and
may eventually need to integrate with the `سامانه مودیان` (Taxpayer System / MOADIAN).
The platform currently has no VAT field on invoices and no tax-reporting export.

**Implementation:**
- Add `vat_percent` and `vat_amount` to `Invoice` and `InvoiceItem`.
- Add a tax-line `InvoiceItem.RowType.TAX` for VAT display.
- Build a `TaxReportExportService` that generates the required format for MOADIAN.
- Ensure `settled_*` fields include VAT amounts for accurate ledger entries.

**Priority:** P2  
**Phase:** When the first company requests VAT-inclusive invoices or MOADIAN reporting

---

## CTO Decision

### If I were the CTO of this project...

**Yes, but only after completing the listed P0 items.**

The domain logic — orders, invoices, payments, financial ledger — is at a level of
quality I rarely see in early-stage SaaS products. The immutable ledger, snapshot
architecture, and recovery policy are production-grade decisions. The ADR documentation
system is exceptional.

What prevents me from saying "yes today" without qualification is the operational layer.
This platform handles real money. When a ledger write fails silently, no one currently
knows about it. The `FinancialBackfillService` is the safety net — but only if someone
has verified it is running in production and someone is watching it. Right now, neither
of those is confirmed.

**P0 items that must be completed before the first paying customer:**

1. **REC-001** — Health check endpoints: load balancer and deployment pipeline require this.
2. **REC-002** — Error monitoring: `logger.critical()` calls must reach an alert channel, not just a log file.
3. **REC-018 (backup)** — A financial platform without verified backups is not production-ready.
4. **Financial Audit P0.1** — Verify and monitor the `FinancialBackfillService` cron.
5. **Financial Audit P0.2** — End-to-end staging payment test against Shaparak sandbox.

If those five items are confirmed complete, I would approve onboarding the first paying
customer — with the expectation that P1 items (audit log, rate limiting, structured logging,
background job infrastructure) are completed before the 10th company is onboarded.

The core is sound. The operational envelope needs to be closed.
