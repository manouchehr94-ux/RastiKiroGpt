# Product Roadmap 2026–2030

**Date:** 2026-06-28  
**Author:** Principal Architect  
**Version:** 1.0  
**Planning horizon:** 4 years (7 phases)

This roadmap describes the platform's growth path from its current MVP state to an
open AI-assisted field service platform. Each phase has explicit entry criteria, exit
criteria, and a delivery risk assessment.

Phases are sequential in intent but overlap in practice — the exit criteria of Phase N
are the entry criteria of Phase N+1.

---

## Phase 1 — Current Core SaaS

**Status: In Progress**  
**Target completion: Q3 2026**  
**Effort estimate: 3–4 weeks remaining**

### What Phase 1 Is

Phase 1 is what is already built: the complete business domain for single-geography,
single-currency, multi-tenant field service management. It includes orders, invoices,
online payments (Shaparak), technician ledger, platform fee, SMS notifications, and
a multi-role web interface.

### Goals

- All core business logic is implemented and production-correct
- Financial Core is architecture-frozen and documented (DONE)
- Zero known data-correctness bugs in the happy path
- All test suites pass

### What Remains (from backlog)

- A-001: Docker/docker-compose
- A-002: `.env.example`
- A-005: Cron schedule verified for all management commands
- A-006: Automated DB backup configured
- A-008: Sentry integrated
- A-010: Post-deploy smoke test
- B-013: HTTPS redirect enforced in production settings
- H-001: Backfill cron verified and monitored

### Exit Criteria

1. All management commands confirmed scheduled in production
2. Automated PostgreSQL backup configured and tested once manually
3. Sentry active and receiving test events
4. Post-deploy smoke test passing in staging
5. Health checks (`/health/`, `/health/db/`) returning 200 in production
6. Zero PENDING `FinancialBackfillTask` rows after first production payment

### Estimated Readiness: **Weeks, not months**

### Risks

- Cron scheduling in deployment environment may require significant debugging if
  the hosting provider does not support systemd timers
- First real Shaparak sandbox test may expose callback URL routing issues

---

## Phase 2 — Operational Excellence

**Status: Planning**  
**Target: Q4 2026 – Q1 2027**  
**Effort estimate: 3–4 months**

### Goals

Transform the platform from a "works in demo" state to a "safe to run real business
on" state. Every operational gap identified in the audit is closed.

### Modules Delivered in Phase 2

| Module | Backlog Items | Outcome |
|---|---|---|
| DevOps | A-003, A-007, A-009 | CI/CD, backup verification, staging env |
| Security | B-001–B-014 | Rate limiting, 2FA, session timeout, security headers |
| Monitoring | C-001–C-009 | Error monitoring, structured logging, job monitoring |
| Background Jobs | D-001–D-010 | Celery + Redis, all crons → tasks, Flower dashboard |
| Documentation | O-001–O-010 | Runbooks, onboarding guide, new ADRs |
| Testing | P-001, P-005, P-010 | CI test gate, E2E staging test, manual test plan |
| Billing | J-001–J-007 | Subscription lifecycle, dunning, expiry enforcement |
| SMS | I-001, I-005 | Email channel, SMS opt-out |
| Orders | E-001 | Split services.py |
| API | K-001–K-003 | Versioning, OpenAPI spec, rate limiting |
| Dashboard | L-001, L-002 | Financial and technician KPIs |

### Exit Criteria

1. CI pipeline runs all 83 test files on every PR to main; merge blocked if any fail
2. 2FA enabled for all COMPANY_ADMIN and PLATFORM_OWNER accounts in production
3. Security headers audit passing (A+ rating on securityheaders.com)
4. Celery Beat confirmed running with dashboard access
5. Subscription model live: companies are billed and deactivated on expiry
6. Email notification channel functional for at least 3 event types
7. Operational runbooks completed and tested with at least one real incident

### Risks

- Billing complexity: subscription dunning and proration can become very complex.
  Scope to manual subscription management first (admin sets expiry date) before
  automating. This halves the risk.
- Celery infrastructure: Redis requires additional hosting. If budget is constrained,
  use Django-Q with SQLite broker as a stepping stone.
- 2FA adoption: company admins may resist. Provide a grace period (30 days) then enforce.

---

## Phase 3 — Advanced SaaS

**Status: Planning**  
**Target: Q2 2027 – Q4 2027**  
**Effort estimate: 6–8 months**

### Goals

Make the platform self-serve, API-accessible, and ready for companies with 10+ technicians
and 1,000+ orders per month. Add the features that separate a "we manage it for you" product
from a "professional business tool."

### Modules Delivered in Phase 3

| Module | Backlog Items | Outcome |
|---|---|---|
| Customer Portal | M-001, M-003, M-005 | Self-service: pay invoices, view orders, track status |
| Technician Portal | M-002, H-007 | View balance, download statement, OTP login |
| Advanced Invoicing | F-001–F-007 | VAT lines, email delivery, due dates, credit notes |
| Advanced Payments | G-001–G-005 | Refund flow, retry, cash collection formal flow |
| Financial | H-003–H-006 | Financial Account Lock, PG concurrency tests |
| API | K-004–K-007 | Full resource coverage, webhooks, API key management |
| Object Storage | N-001–N-003 | Redis cache, MinIO/S3, PostgreSQL FTS |
| Reporting | L-003–L-007 | Custom date ranges, scheduled reports, financial reports |
| Background Jobs | D-007, D-008 | Async PDF and CSV generation |
| Orders | E-003–E-005 | SLA tracking, calendar view, file attachments |
| Notifications | I-003–I-007 | Notification centre, per-user preferences, delivery receipts |
| Testing | P-002–P-009 | PG concurrency tests, API tests, security tests, coverage gate |
| Features | Q-001, Q-005, Q-009 | Feature flags, discount analytics, onboarding wizard |

### Exit Criteria

1. Customer portal live with at least: invoice list, payment, PDF download
2. Technician balance portal live with OTP authentication
3. Public API versioned at `/api/v1/` with OpenAPI documentation
4. Webhook delivery system functional with at least 5 event types
5. At least one company using the API for integration
6. Refund flow tested end-to-end in staging
7. `get_balance()` no longer uses full SUM (Financial Account Lock deployed)
8. 80% test coverage enforced in CI

### Risks

- Refund flow depends on Shaparak supporting programmatic refund initiation — verify
  API capability early. If not supported, implement manual refund workflow first.
- Customer portal authentication via SMS OTP requires separate rate limiting to prevent
  OTP flooding.
- Object storage migration requires moving existing company logos without downtime.

---

## Phase 4 — Enterprise

**Status: Future**  
**Target: 2028**  
**Effort estimate: 6–12 months**

### Goals

Support enterprise companies (50+ technicians, 10,000+ orders per month) with granular
permissions, compliance features, SLA guarantees, and dedicated support channels.

### Modules Delivered in Phase 4

| Module | Backlog Items | Outcome |
|---|---|---|
| RBAC | Q-010 | Granular permission matrix: role + resource + action |
| Compliance | F-002, O-006 | MOADIAN export, audit trail, compliance reporting |
| Performance | N-004, N-005, N-006 | Read replica, cursor pagination, archiving |
| BI/Analytics | L-008 | BI export, materialised views, Metabase integration |
| Enterprise API | K-008 | Python/JS SDK, enterprise API quotas |
| Multi-PSP | G-004 | Gateway routing rules, PSP failover |
| Calendar | E-004, Q-004 | Full scheduling system with drag-and-drop dispatch |
| Mobile App | M-004 | Technician iOS/Android app (or React Native PWA) |
| Mobile Push | I-002 | FCM push notifications for technician app |
| AI Dispatch | None (new) | Rule-based smart order routing to nearest/best technician |
| Workflow Engine | E-006, Q-007 | Configurable order stages per company |
| Tracing | C-010 | OpenTelemetry distributed tracing in production |
| Monitoring | C-006, C-007 | Prometheus + Grafana metrics dashboards |

### Exit Criteria

1. Platform supports one company with 100+ technicians running simultaneously without
   performance degradation
2. RBAC permissions model live and adopted by at least one enterprise company
3. Technician mobile app available on App Store and Google Play
4. MOADIAN VAT export available for companies that require it
5. 99.5% uptime SLA achievable and documented
6. p95 payment verification latency < 3 seconds under load
7. Audit trail complete: every financial write and order state change is attributed

### Risks

- RBAC is architecturally complex. A permission model that is too granular creates
  admin burden. Involve 2–3 enterprise customers in the design before building.
- Mobile app requires dedicated mobile engineering skill that may not currently exist.
  React Native PWA is a lower-risk alternative for v1 mobile.
- MOADIAN integration requires acquiring API credentials from the Iranian Tax Authority,
  which has an unpredictable approval timeline.

---

## Phase 5 — Marketplace

**Status: Future**  
**Target: 2028–2029**  
**Effort estimate: 12–18 months**

### Goals

Open the platform beyond company-contracted technicians. Enable independent technicians
to register, be found by multiple companies, and manage their own financial flows across
all companies they work with.

### Modules Delivered in Phase 5

| Module | Outcome |
|---|---|
| Technician Marketplace | Independent technician registration, skills, availability, reviews |
| Company Discovery | Companies can search and invite marketplace technicians for one-off jobs |
| Cross-Company Ledger | Technician ledger that aggregates earnings across multiple company relationships |
| Technician Verification | Document upload, background check, skills certification |
| Marketplace Pricing | Company-posted rates vs technician-negotiated rates |
| Dispute Resolution | Formal dispute workflow between company and technician |
| Technician Dashboard | Marketplace-specific earnings, reviews, booking calendar |
| B2C Payment | Direct customer-to-technician payment for marketplace bookings |

### Exit Criteria

1. At least 100 marketplace technicians registered and verified
2. At least 10 companies using marketplace technicians for at least 10% of their jobs
3. Technician can view unified earnings across all their company relationships
4. Dispute resolution workflow operational with < 48-hour resolution SLA

### Risks

- The marketplace creates a conflict-of-interest if technicians use the marketplace to
  bypass their primary employer company. A "marketplace exclusivity" option per company
  is needed from day one.
- Cross-company ledger is architecturally more complex than the current single-company
  ledger. Requires a new ADR before implementation.
- Legal: independent technician relationships may be classified as employment in some
  jurisdictions. Legal review required before launch.

---

## Phase 6 — Open Platform

**Status: Future**  
**Target: 2029**  
**Effort estimate: 6–12 months**

### Goals

Allow third-party developers to build extensions, integrations, and vertical-specific
customisations without modifying the platform core. Create an ecosystem.

### Modules Delivered in Phase 6

| Module | Outcome |
|---|---|
| Plugin Registry | Register custom hooks at defined extension points |
| App Store | Third-party apps discoverable and installable by companies |
| Developer Portal | API docs, webhook simulator, sandbox environment |
| White-Label | Full rebrand of the platform under a partner's identity |
| Partner Tier | Resellers can manage multiple companies under one partner account |
| Third-Party Auth | OAuth2 login with third-party IdPs |
| SDK v2 | Full-coverage SDK with GraphQL support |

### Exit Criteria

1. At least 3 third-party integrations built by external developers using the public API
2. White-label deployment operating for at least 1 partner
3. Developer portal documentation rated 8+/10 in developer surveys

### Risks

- Plugin architecture with sandbox isolation is technically complex. Sandboxed plugins
  must not be able to access other tenants' data. Security review required per plugin.
- SDK maintenance is ongoing operational burden. Only proceed if API stability is confirmed.

---

## Phase 7 — AI Platform

**Status: Vision**  
**Target: 2030+**  
**Effort estimate: 18–24 months**

### Goals

AI becomes a first-class feature of the platform, not a bolt-on. The platform assists
companies in making better operational decisions, predicts problems before they happen,
and automates routine tasks.

### Modules Delivered in Phase 7

| Module | Outcome |
|---|---|
| AI Dispatch | ML-based order routing: considers technician skill, location, load, past performance |
| AI Anomaly Detection | Flag unusual financial entries, suspicious cancellation rates, outlier invoices |
| Predictive SLA | Predict order completion time from historical data, alert on risk of SLA breach |
| Smart Customer Segmentation | AI-assisted customer targeting for SMS campaigns based on order history and payment patterns |
| Conversational Technician Support | LLM-powered chat for technicians to ask about their schedule, earnings, and orders |
| Automated Reconciliation | AI matches PSP settlement reports against ledger entries, flags discrepancies |
| Dynamic Pricing Suggestion | Suggest invoice prices based on service type, technician skill, market rates |

### Prerequisites for Phase 7

1. At least 18 months of production data (10,000+ orders, 1,000+ technicians)
2. Data warehouse operational (Phase 4 exit)
3. ML engineering skill on the team
4. GDPR/data protection review if expanding beyond Iran

### Exit Criteria

- AI dispatch demonstrably reduces average order-to-assignment time by > 20%
- Anomaly detection flags > 80% of manually identified irregularities with < 10% false positive rate

---

## Roadmap Timeline Summary

```
2026  Phase 1: Core SaaS (COMPLETE)
      Phase 2: Operational Excellence (Q4 2026 – Q1 2027)

2027  Phase 3: Advanced SaaS (Q2 2027 – Q4 2027)

2028  Phase 4: Enterprise (Q1 2028 – Q4 2028)
      Phase 5: Marketplace (Q3 2028 – Q2 2029)

2029  Phase 6: Open Platform (Q1 2029 – Q3 2029)

2030  Phase 7: AI Platform (Q1 2030+)
```

---

## Funding and Team Scaling Implications

| Phase | Recommended Team Size | Key Hires |
|---|---|---|
| Phase 1 | 1–2 developers | — |
| Phase 2 | 2–3 developers | DevOps/platform engineer |
| Phase 3 | 3–5 developers | Backend + frontend specialist |
| Phase 4 | 5–8 developers | Mobile developer, security engineer |
| Phase 5 | 8–12 developers | Product manager, marketplace specialist |
| Phase 6 | 12–20 developers | Developer relations, SDK engineer |
| Phase 7 | 20+ developers | ML engineer, data scientist |

---

## Architecture Evolution by Phase

| Area | Phase 1–2 | Phase 3–4 | Phase 5–6 | Phase 7 |
|---|---|---|---|---|
| Job queue | cron → Celery | Celery | Celery with priority queues | ML inference queue |
| Storage | Local/default | MinIO / S3 | Multi-region S3 | Data lake |
| Cache | None | Redis | Redis cluster | Feature store |
| DB | Single PG | PG + read replica | PG primary + replicas | PG + data warehouse |
| Search | ILIKE filter | PG FTS | Elasticsearch | Vector search |
| Auth | Session + JWT | Session + JWT + 2FA | OAuth2 + SSO | MFA + passkeys |
| API | DRF REST (partial) | DRF REST (full, versioned) | REST + webhooks | REST + GraphQL |
| Observability | Sentry | Sentry + Prometheus | Grafana + OTel | ML observability |
| Deployment | Manual | CI/CD (GitHub Actions) | Blue/green deploy | GitOps |

---

## Risk Register (Roadmap-Level)

| Risk | Probability | Impact | Phase | Mitigation |
|---|---|---|---|---|
| Shaparak API changes break payment flow | Medium | Critical | 1–7 | Abstract PSP layer, integration tests |
| Melipayamak changes break SMS | Medium | High | 1–4 | Multi-provider architecture already in place |
| Regulatory change (MOADIAN, data localisation) | High | High | 3–7 | Legal advisory from Phase 3; modular compliance layer |
| Team grows faster than architecture can absorb | Medium | High | 4–7 | Service layer discipline enables independent parallel work |
| Marketplace creates off-platform competition | Low | High | 5 | Exclusivity options, platform value proposition clarity |
| ML models trained on biased data produce poor dispatch decisions | Medium | Medium | 7 | Human-in-the-loop override on all AI dispatch decisions |
| Open plugin ecosystem introduces security vulnerabilities | Medium | Critical | 6 | Plugin sandboxing, security review for every published plugin |

---

## Key Architectural Non-Negotiables (Preserved Across All Phases)

These principles from RDOS v1.0 must survive every phase of growth:

1. **Immutable financial ledger.** Every financial write is append-only. Never update or delete ledger rows.
2. **Amounts from authoritative snapshots.** No ledger amount is derived from another ledger entry.
3. **Multi-tenant isolation is structural.** `CompanyOwnedModel` enforces company scoping on every domain model.
4. **Service layer is the only write path.** No financial write originates from views, serializers, signals, or templates.
5. **Every financial write has a deterministic idempotency key.** Retries are always safe.
6. **Non-blocking financial side effects.** Payment success is never rolled back due to a ledger failure.
