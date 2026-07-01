---
Title: Production Readiness Checklist
Layer: Quality Assurance
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: 99_AUDIT_2026_06_30/08_PRODUCTION_READINESS_GAP_ANALYSIS.md
Source of Truth: Audit Report + Code
Depends On: []
Related Documents: ../11_Project_Knowledge/KNOWN_RISKS.md
Reusable Across Projects: Partially
---

# Production Readiness Checklist

**Last audit:** 2026-06-30  
**Overall status:** Ready with Critical Prerequisites

---

## CRITICAL — Must fix before going live

- [ ] **P0-1**: Add `@require_tenant_role("COMPANY_ADMIN")` to `admin_operator_list` at `apps/tenants/views_admin.py:2125`
- [ ] **P0-2**: Install `rest_framework_simplejwt.token_blacklist` in `INSTALLED_APPS` and run migration
- [ ] **P0-3**: Remove hardcoded `user.check_password("123456")` from `apps/accounts/views.py:58`
- [ ] **P0-4**: Uncomment env-var `ALLOWED_HOSTS` line in `config/settings/base.py:19` (remove `["*"]`)
- [ ] **P0-5**: Fix `Customer.objects.create(name=...)` in `apps/api/views.py:311` — use `first_name`/`last_name`

Estimated time to fix all P0s: ~3 hours

---

## HIGH — Fix before significant user traffic

- [ ] Test multi-tenant isolation: confirm 403 returned when user accesses another company's orders/invoices
- [ ] Configure cache backend for multi-worker environments (notification throttle non-functional without it)
- [ ] Decide on technician SMS: remove `if False` from `apps/orders/technician_notifications.py:147` or document as intentional
- [ ] Verify 19 notification events are triggered at correct times (currently some are never triggered)
- [ ] Enforce subscription limits in code (currently defined in DB but not enforced)

---

## MEDIUM — Fix in first sprint after launch

- [ ] Add duplicate `@require_tenant_role` on `admin_operator_create` at `apps/tenants/views_admin.py:1964` (has two identical decorators — remove one)
- [ ] Add multi-tenant isolation tests for all admin views
- [ ] Implement platform SMS template rendering (currently always uses fallback text)
- [ ] Fix `if False` technician SMS if decision is to enable it
- [ ] Add breadcrumb to deep admin pages (financial reports, technician statement)

---

## ARCHITECTURE — Needs attention but not blocking

- [ ] `apps/billing/` — SaaS subscription billing is a stub; implement or document as roadmap item
- [ ] Merge duplicate component templates (`components/` vs `includes/components/`)
- [ ] Add missing sidebar links for orphan pages (financial reports, gateway reconciliation)
- [ ] Restore or redesign customer dashboard (`/<code>/customer/`)
- [ ] Remove deprecated `communication-templates` URL or re-implement

---

## Infrastructure Checklist

- [ ] `DJANGO_SECRET_KEY` set via environment variable (never hardcoded)
- [ ] `DEBUG = False` in production
- [ ] `ALLOWED_HOSTS` configured via `DJANGO_ALLOWED_HOSTS` environment variable
- [ ] PostgreSQL configured (not SQLite)
- [ ] Static files served via CDN or web server (not Django in production)
- [ ] Media files storage configured (S3 or equivalent)
- [ ] Celery or similar configured for async tasks (if SMS/notifications are async)
- [ ] Error monitoring (Sentry or equivalent) configured
- [ ] SSL/TLS certificate active
- [ ] Database backups scheduled

---

## Test Suite Status (as of 2026-06-30)

- Total tests: **1242**
- Order lifecycle: ✅ well covered
- Financial logic: ✅ well covered
- Multi-tenant isolation: ❌ gap — few isolation tests
- Notification events: ❌ gap — untriggered events not tested
- API endpoints: ❌ gap — limited API test coverage

Run full suite: `python manage.py test --verbosity=1`
