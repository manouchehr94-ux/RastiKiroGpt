# Rasti Service SaaS — Master Project Bible Completion

**Date:** 2026-06-28  
**Source:** Full ZIP review: `Rasti chekFinal 5 tir.zip`  
**Scope:** whole Django SaaS project, not only finance  
**Status:** Supplemental CTO-level completion report

---

## 1. Executive Verdict

The project is a **strong MVP with a production-grade Financial Core and a mature multi-tenant/domain foundation**. It is not yet an operations-ready SaaS because deployment, monitoring, CI/CD, background jobs, security hardening, subscription billing, and formal customer/technician portals are incomplete.

The correct next product phase is **Operational Excellence**, not another business-feature sprint. Before onboarding real paying customers, the system needs a small set of P0 operational controls: Docker/dev parity, CI, Sentry/error monitoring, verified cron or job scheduler, backup/restore verification, HTTPS/security settings, and a staging Shaparak end-to-end payment test.

### Overall Scorecard

| Area | Score | Notes |
|---|---:|---|
| Architecture discipline | 9/10 | Service layer, ADRs, immutable finance, tenant isolation are excellent. |
| Business-domain coverage | 8/10 | Orders/invoices/payments/SMS are strong; billing/reporting/portals are incomplete. |
| Financial Core | 9/10 | Best subsystem; frozen with ADR-004 to ADR-008. |
| Multi-tenancy | 9/10 | Structural company scoping is a major strength. |
| Code maintainability | 7/10 | Good pattern, but hotspot files must be split. |
| Security | 6/10 | Payment-specific security is strong; platform-level hardening missing. |
| Performance/scalability | 6/10 | Acceptable for MVP; needs Celery/Redis/cache/read models later. |
| Testing | 8/10 | Large regression suite; no CI/load/security/PG concurrency. |
| Documentation | 9/10 | RDOS/ADR system is unusually strong. |
| Operational readiness | 4/10 | Main launch blocker. |

---

## 2. Real Project Metrics


| Metric | Value |
|---|---:|
| Total files reviewed (excluding .git/__pycache__) | 770 |
| Python files | 420 |
| Python LOC | 67748 |
| HTML templates | 198 |
| Template LOC | 20464 |
| Markdown docs | 79 |
| Markdown LOC | 6436 |
| CSS files | 17 |
| JS files | 7 |
| SQLite DB files in ZIP | 3 |
| Backup template files (.bak/.bak5) | 22 |
| Django app modules | 15 |


### Largest Files / Hotspots

| # | File | LOC |
|---:|---|---:|
| 1 | `apps/tenants/views_admin.py` | 3309 |
| 2 | `apps/platform_core/management/commands/smoke_regression.py` | 2194 |
| 3 | `static/css/pages.css` | 2143 |
| 4 | `static/css/dashboard.css` | 1574 |
| 5 | `static/css/components.css` | 1402 |
| 6 | `apps/orders/services.py` | 1201 |
| 7 | `docs/00_Project/MASTER_PROJECT_AUDIT_2026-06-28.md` | 938 |
| 8 | `apps/reports/views.py` | 916 |
| 9 | `static/css/layouts.css` | 823 |
| 10 | `apps/accounts/operator_access.py` | 809 |
| 11 | `apps/invoices/views_technician.py` | 806 |
| 12 | `tests/test_p7_verify.py` | 786 |
| 13 | `apps/sms/services.py` | 745 |
| 14 | `apps/notifications/event_catalog.py` | 721 |
| 15 | `apps/platform_core/management/commands/seed_full_demo.py` | 712 |
| 16 | `apps/tenants/models.py` | 710 |
| 17 | `static/css/responsive.css` | 704 |
| 18 | `apps/platform_core/models.py` | 673 |
| 19 | `templates/orders/technician_invoice_create.html` | 654 |
| 20 | `docs/00_Project/FUTURE_PLATFORM_RECOMMENDATIONS_2026-06-28.md` | 621 |
| 21 | `tests/test_task010b_order_wage_posting.py` | 616 |
| 22 | `tests/test_p8_gateway_safety.py` | 609 |
| 23 | `tests/test_task011a_fix1_backfill_direct_settlement.py` | 568 |
| 24 | `tests/test_task008_backfill.py` | 549 |
| 25 | `apps/sms/views.py` | 539 |

**Interpretation:** the most important refactor hotspot is `apps/tenants/views_admin.py` at 3309 lines, then `apps/orders/services.py` at 1201 lines. These are not necessarily broken, but they are maintainability risks.

---

## 3. Module Scorecard Based on ZIP Inspection

| App | Py files | LOC | Classes | Functions | Migrations | Templates | Score | Risk | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| accounts | 16 | 2654 | 42 | 103 | 7 | 8 | 7.5/10 | Medium | Auth solid; needs 2FA/rate limits/session policy |
| api | 7 | 990 | 42 | 31 | 0 | 0 | 5/10 | High | Partial DRF API; no versioning/OpenAPI/full coverage |
| billing | 9 | 112 | 7 | 3 | 3 | 0 | 2/10 | Critical | SaaS subscription billing mostly placeholder |
| common | 12 | 923 | 8 | 48 | 0 | 0 | 8/10 | Low | Shared utilities clean and low risk |
| dashboard | 11 | 349 | 5 | 13 | 0 | 3 | 6/10 | Medium | Basic KPI surface; analytics incomplete |
| invoices | 17 | 2860 | 24 | 83 | 5 | 5 | 8/10 | Medium | Strong lifecycle/settlement; refunds/VAT missing |
| notifications | 21 | 2586 | 28 | 81 | 3 | 2 | 7/10 | Medium | Event catalog strong; email/push/user prefs missing |
| orders | 21 | 4176 | 41 | 94 | 5 | 8 | 7/10 | High | Business flow rich; services.py and views_admin.py too large |
| payments | 21 | 2199 | 34 | 47 | 3 | 5 | 8/10 | Medium | Good PSP flow; refund/retry/automated PSP reconciliation missing |
| payouts | 16 | 2553 | 31 | 55 | 8 | 7 | 9/10 | Low | Financial core strongest subsystem; monitoring dependencies remain |
| platform_core | 39 | 8330 | 86 | 236 | 6 | 46 | 7/10 | High | Broad platform admin; catch-all module and large files |
| public | 6 | 631 | 2 | 18 | 0 | 8 | 5/10 | Medium | Basic marketing/public request flow |
| reports | 10 | 1745 | 22 | 50 | 3 | 7 | 4/10 | High | Models exist; reporting engine underbuilt |
| sms | 35 | 4891 | 63 | 112 | 9 | 6 | 8/10 | Medium | Outbox/provider/template/inbox strong; delivery receipts/opt-out incomplete |
| tenants | 18 | 6239 | 60 | 184 | 6 | 62 | 8/10 | Medium | Multi-tenant base strong; large admin views and onboarding gaps |

---

## 4. Module Dependency Graph


```text
Public / API / Dashboard / Tenant Admin
        ↓
Orders ──────→ Invoices ──────→ Payments
  │              │               │
  │              └────→ Payouts ←─┘
  │                       ↑
  └────→ Notifications → SMS

Tenants / Accounts / Common are foundation modules used by most apps.
Platform Core is an operations/admin layer that currently depends on many modules.
Reports and Dashboard consume domain data and should remain read/projection layers.
```


### Direct App Dependencies Detected from Python Imports

| App | Depends on |
|---|---|
| accounts | common, sms, tenants |
| api | accounts, invoices, notifications, orders, reports, tenants |
| billing | — |
| common | — |
| dashboard | accounts, invoices, orders, platform_core, tenants |
| invoices | accounts, common, notifications, orders, payments, payouts, reports, tenants |
| notifications | accounts, common, invoices, orders, platform_core, sms, tenants |
| orders | accounts, common, invoices, notifications, payouts, sms, tenants |
| payments | accounts, common, invoices, payouts, reports, tenants |
| payouts | accounts, common, invoices, orders, payments, tenants |
| platform_core | accounts, common, dashboard, invoices, notifications, orders, payments, payouts, reports, sms, tenants |
| public | accounts, notifications, sms, tenants |
| reports | accounts, common, invoices, orders, platform_core, sms, tenants |
| sms | accounts, common, notifications, platform_core, reports, tenants |
| tenants | accounts, common, invoices, notifications, orders, payments, payouts, platform_core, sms |

**Architectural observation:** `platform_core` and `tenants` are the most connected modules. This is expected for admin/tenant infrastructure, but they should not keep accumulating unrelated responsibilities. Long-term, `platform_core` should be split into operations, platform billing, platform messaging, and platform monitoring.

---

## 5. Product Evolution Story

```text
Foundation / Multi-Tenant
        ↓
Orders and technician workflow
        ↓
Invoices and payment lifecycle
        ↓
Financial Core and immutable ledger
        ↓
Technician compensation and statements
        ↓
SMS / notification / UI hardening
        ↓
Architecture freeze and ADR system
        ↓
Current stage: Operational Excellence required before scale
```

This story matters because it shows the project did not grow randomly. The highest-risk subsystem, finance, was not patched onto the product as an afterthought; it was hardened with snapshots, backfill, idempotency, statements, exports, and ADRs.

---

## 6. Business Coverage Matrix

| Business capability | Coverage | Notes |
|---|---:|---|
| Tenant/company management | 80% | Core tenant model and settings exist; onboarding/subscription lifecycle incomplete. |
| Operator/admin order intake | 85% | Strong, with validation and status flows. |
| Public order/request intake | 70% | Exists, but customer self-service tracking is thin. |
| Technician assignment/workflow | 80% | Accept/start/complete/cancel/recycle rules exist; mobile UX still missing. |
| Invoice lifecycle | 80% | Strong; refund/VAT/credit-note not implemented. |
| Online payments | 80% | Shaparak-oriented flow strong; refund/retry/multi-PSP incomplete. |
| Technician compensation | 90% | Completed and frozen for V1. |
| Platform fee accounting | 85% | Strong core; monitoring/reconciliation needs ops layer. |
| SMS notifications | 85% | Strong architecture; opt-out/delivery receipts missing. |
| In-app notifications | 65% | Event catalog strong; notification center/user prefs incomplete. |
| Customer portal | 20% | Public flows exist; true portal missing. |
| Technician portal | 30% | Technician views exist; self-service statement/mobile portal missing. |
| SaaS billing/subscriptions | 20% | Placeholder; must be built before commercial scaling. |
| Reporting/BI | 35% | Basic reports; not a mature analytics layer. |
| Public API/integrations | 30% | DRF exists; needs versioning/OpenAPI/webhooks. |

---

## 7. Hard Non-Negotiables

These rules should not be broken in future development:

1. Financial ledger remains immutable; corrections use adjustment entries.
2. Ledger amounts come from authoritative business snapshots, not other ledger rows.
3. Every financial write must have deterministic idempotency.
4. Tenant isolation must remain structural via company ownership.
5. Views/templates must never contain financial write logic.
6. Service layer remains the only write path for domain state changes.
7. New financial features require ADR update and regression tests.
8. Billing (`company → platform`) remains separate from payments (`customer → company`).
9. SMS and payment providers stay behind provider abstractions.
10. Operational features should be built before more large product features.

---

## 8. Completion Gaps Missing from Prior Reports

The previous Claude reports were strong but incomplete as a permanent project bible. This supplemental report adds:

- Real ZIP-derived metrics and LOC counts.
- Module dependency graph from Python imports.
- Hotspot file list.
- Business coverage matrix.
- Cleanup/quarantine plan for obsolete files.
- Separation of launch blockers vs future scale items.
- Explicit non-negotiable principles.

---

## 9. Immediate Launch Blockers

| Priority | Item | Why it blocks launch |
|---|---|---|
| P0 | Verify financial/SMS/payment expiry cron jobs | Backfill/recovery and SMS queue depend on scheduled jobs. |
| P0 | Sentry/error monitoring | Financial `logger.critical()` must page someone, not disappear into logs. |
| P0 | CI pipeline | 83 test files must run before merge/deploy. |
| P0 | Backup and restore verification | Financial data without tested backup is unacceptable. |
| P0 | Staging Shaparak E2E test | Unit tests cannot replace a real gateway callback test. |
| P0 | Clean dev/prod environment hygiene | DB dumps and local artifacts must not ship with the codebase. |

---

## 10. Final CTO Position

I would continue investing. I would not rewrite the project. I would freeze the Financial Core. I would onboard the first paying customer only after the P0 operational controls are completed and verified. I would not approach enterprise customers until security/RBAC/audit log/monitoring/subscription billing are mature.
