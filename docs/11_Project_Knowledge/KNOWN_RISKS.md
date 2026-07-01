---
Title: Known Risks and Bugs
Layer: Project Knowledge
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/tenants/views_admin.py, apps/api/auth_views.py, apps/accounts/views.py, config/settings/base.py, apps/api/views.py, apps/orders/technician_notifications.py
Source of Truth: Code
Depends On: []
Related Documents: ../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md
Reusable Across Projects: No
---

# Known Risks and Bugs

All known risks and bugs as of 2026-07-01. Keep this document updated as bugs are fixed.

---

## CRITICAL SECURITY (P0)

### P0-1 — admin_operator_list Missing Decorator

| | |
|---|---|
| **File** | `apps/tenants/views_admin.py:2125` |
| **URL** | `/<code>/admin/settings/operators/` |
| **Severity** | CRITICAL |
| **Status** | OPEN |

`admin_operator_list` has no `@require_tenant_role` decorator. Any authenticated user can access, create, edit, and delete operators for any company.

Additionally, `is_company_admin()` in `operator_access.py` checks role only — not company membership — enabling cross-tenant escalation.

**Fix:**
```python
@require_tenant_role("COMPANY_ADMIN")
def admin_operator_list(request, **kwargs):
```

**Estimated fix time:** 30 minutes

---

### P0-2 — JWT Logout Does Not Invalidate Token

| | |
|---|---|
| **File** | `apps/api/auth_views.py:152` |
| **URL** | `/api/auth/logout/` |
| **Severity** | CRITICAL |
| **Status** | OPEN |

`rest_framework_simplejwt.token_blacklist` is not in `INSTALLED_APPS`. The `LogoutAPI` calls `token.blacklist()` inside a try/except that swallows all exceptions. Result: logout returns HTTP 200 but the token remains valid.

**Fix:**
1. Add `rest_framework_simplejwt.token_blacklist` to `INSTALLED_APPS` in `config/settings/base.py`
2. Run `python manage.py migrate`

**Estimated fix time:** 1 hour

---

### P0-3 — Hardcoded Default Password in Production Login

| | |
|---|---|
| **File** | `apps/accounts/views.py:58` |
| **Severity** | CRITICAL |
| **Status** | OPEN |

```python
user.check_password("123456")  # Default password check in production login
```

This exposes a known default password in the source code. Any user with password `"123456"` can authenticate via this bypass path.

**Fix:** Remove or replace with a configurable setting

**Estimated fix time:** 15 minutes

---

### P0-4 — ALLOWED_HOSTS Wildcard in Base Settings

| | |
|---|---|
| **File** | `config/settings/base.py:19` |
| **Severity** | HIGH |
| **Status** | OPEN |

```python
ALLOWED_HOSTS = ["*"]  # Active
# ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # Commented out
```

Production overrides this, but if `DJANGO_ALLOWED_HOSTS` is not set, the production setting becomes empty `[""]` which rejects all requests.

**Fix:** Uncomment the env-var line, remove the wildcard.

**Estimated fix time:** 10 minutes

---

### P0-5 — Customer API Crashes at Runtime

| | |
|---|---|
| **File** | `apps/api/views.py:311` and `apps/api/views.py:367` |
| **URL** | `/api/<code>/customers/` |
| **Severity** | CRITICAL |
| **Status** | OPEN |

```python
Customer.objects.create(name=...)  # TypeError: Customer has no 'name' field
```

`Customer` model uses `first_name` and `last_name`, not `name`. This crashes with `TypeError` when the API is called.

**Fix:** Change `name=...` to `first_name=..., last_name=...`

**Estimated fix time:** 30 minutes

---

## HIGH PRIORITY

### H-1 — Technician SMS Permanently Disabled

| | |
|---|---|
| **File** | `apps/orders/technician_notifications.py:147` |
| **Severity** | HIGH |
| **Status** | OPEN |

```python
if False and send_sms and notification_settings.send_sms_on_new_order:
```

`if False` permanently prevents this code from running. SMS notifications for new order assignments to technicians never fire, regardless of company configuration.

**Decision needed:** Remove `if False` to enable, or document as intentional.

---

### H-2 — 19 Notification Events Defined, Not All Triggered

| | |
|---|---|
| **Files** | `apps/notifications/catalog.py`, various event triggers |
| **Severity** | HIGH |
| **Status** | OPEN |

19 notification event types are defined. Known untriggered:
- `order_cancelled`
- `order_rescheduled`
- `order_cancel_requested_customer`

Customers and technicians miss expected notifications for these events.

---

### H-3 — Admin Operator Create Has Duplicate Decorator

| | |
|---|---|
| **File** | `apps/tenants/views_admin.py:1964` |
| **Severity** | LOW |
| **Status** | OPEN |

```python
@require_tenant_role("COMPANY_ADMIN")
@require_tenant_role("COMPANY_ADMIN")  # duplicate
def admin_operator_create(request, **kwargs):
```

Not a security issue (view is protected), but the duplicate decorator is noisy. Remove one.

---

## MEDIUM PRIORITY

### M-1 — Duplicate Component Templates

Two sets of component templates exist:
- `templates/components/badge.html`, `empty_state.html`, `stat_card.html`, `status_badge.html`
- `templates/includes/components/badge.html`, etc. (same 4 files)

Changes to one set don't affect the other.

---

### M-2 — Notification Throttle Non-Functional in Multi-Worker Setup

Cache backend is not configured for shared state. In a multi-worker production environment, the notification throttle is per-worker, not global. Duplicate notifications may be sent.

---

### M-3 — Customer Dashboard Broken Since Phase 24

`/<code>/customer/` redirects to public page, not a dashboard. Customer experience after login is incomplete.

---

## STUB / NOT IMPLEMENTED

### S-1 — SaaS Billing Not Implemented

`apps/billing/services.py` is a 6-line stub. Subscription plans, billing cycles, and plan limits exist in the DB but are never enforced. Companies can exceed their subscription limits without any enforcement.

---

## Fixed Issues (Log)

| Issue | Fixed in | Date |
|---|---|---|
| *(none yet)* | | |
