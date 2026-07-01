# ۰۹ — Prompt‌های پیاده‌سازی بعدی برای Claude Code

**تاریخ:** ۳۰ ژوئن ۲۰۲۶  
**هدف:** prompt‌های آماده، ایمن و به‌ترتیب اولویت برای فازهای پیاده‌سازی بعدی

---

> ⚠️ **قانون مهم:** هر prompt را جداگانه و به ترتیب اجرا کنید. قبل از اجرای هر کدام، `git commit` بزنید. هیچ prompt‌ای نباید ماهیت migration موجود را تغییر دهد.

---

## فاز ۰: رفع مشکلات حیاتی (P0)

### Prompt P0-1: رفع نقص امنیتی admin_operator_list

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

SECURITY FIX — do not modify any migration files or models.

Read apps/tenants/views_admin.py starting at line 2100.

The function `admin_operator_list` (around line 2125) handles creating, editing,
and deleting operators via POST action parameter. It currently has NO permission
decorator. This is a CRITICAL security vulnerability.

Fix: Add `@require_tenant_role("COMPANY_ADMIN")` decorator to `admin_operator_list`.
The import for `require_tenant_role` should already exist in that file.

Also verify:
- `admin_operator_create` already has `@require_tenant_role("COMPANY_ADMIN")` twice
  (a known cosmetic bug). Remove the duplicate decorator.

After the fix, run:
  python manage.py test tests/test_p1d_order_detail_permissions.py -v 2

Report: which decorator was added, to which function, and test result.
```

---

### Prompt P0-2: رفع JWT Token Blacklist

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

SECURITY FIX — do not modify migration files for financial apps.

The apps/api/auth_views.py calls token.blacklist() in LogoutAPI (line 163).
But rest_framework_simplejwt.token_blacklist is NOT in INSTALLED_APPS.
This means JWT tokens remain valid after logout.

Steps:
1. Read config/settings/base.py — find INSTALLED_APPS
2. Add "rest_framework_simplejwt.token_blacklist" to THIRD_PARTY_APPS (after rest_framework)
3. Run: python manage.py migrate
4. Run: python manage.py check
5. Run: python manage.py test tests/test_api_order_creation.py -v 2

Report: which line was changed, migration output, test result.
```

---

### Prompt P0-3: حذف رمز عبور هاردکد از login view

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

SECURITY FIX — Read apps/accounts/views.py line 58.

The login view checks:
  if user.check_password("123456"):
      user.must_change_password = True
      ...

This hardcodes "123456" as a known insecure default password in production code.

Fix: The flag `user.must_change_password` already handles the forced-change flow.
Remove the `elif user.check_password("123456"):` branch entirely.
The existing `if user.must_change_password:` check lower in the view is sufficient.

After fix:
  python manage.py check
  python manage.py test tests/ --verbosity=0 2>&1 | tail -5

Report: exact lines removed and test result.
```

---

### Prompt P0-4: اصلاح ALLOWED_HOSTS در base.py

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

CONFIGURATION FIX — Read config/settings/base.py lines 18-21.

Currently:
  # ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="*", cast=Csv())
  ALLOWED_HOSTS = ["*"]

This hardcodes ["*"] in base settings. Production settings override this, but
the commented-out env-var line is the correct approach.

Fix:
1. Uncomment the env-var based line (adapt the variable name if needed)
2. Remove the `ALLOWED_HOSTS = ["*"]` hardcoded line
3. Ensure local.py has `ALLOWED_HOSTS = ["*"]` or `["localhost", "127.0.0.1"]`
4. Ensure production.py still reads ALLOWED_HOSTS from env

Run: python manage.py check --settings=config.settings.local
Report: exact change made.
```

---

### Prompt P0-5: رفع باگ Customer.name در API

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

BUG FIX — Read apps/api/views.py lines 300-380.

The API views for creating and updating customers use:
  Customer.objects.create(..., name=data["name"], ...)
  customer.name = data["name"]

But the Customer model (apps/accounts/models.py:262) has no `name` field.
It has `first_name` and `last_name` separately.

Fix:
1. For create: split name into first_name/last_name (split on first space)
2. For update: same split logic
3. Ensure the serializer (apps/api/serializers.py) also handles this correctly

Run: python manage.py check
Run: python manage.py test tests/test_api_order_creation.py -v 2
Report: exact lines changed.
```

---

### Prompt P0-6: تصمیم درباره SMS تکنسین

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

Read apps/orders/technician_notifications.py line 147.

The SMS block is permanently disabled by `if False and send_sms and ...`

DECISION REQUIRED:
Option A (Activate): Remove `False and` from the condition
Option B (Document): Add a code comment explaining why this is intentionally disabled

If choosing Option A, also verify that the SMS provider for company-level messages
is actually functional before enabling. Read apps/sms/providers/melipayamak.py
lines 397-419 to check if the simple text send is implemented.

Report: which option was chosen and why, plus state of MeliPayamak provider.
```

---

## فاز ۱: تست‌های Isolation چند‌مستأجری

### Prompt P1-1: نوشتن تست‌های cross-tenant isolation

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

Write ISOLATION TESTS. Do not modify any existing code or tests.

Create file: tests/test_multi_tenant_isolation.py

Tests to write (all should return 403 or 404, NOT 200):

1. test_company_a_admin_cannot_view_company_b_order
   - Create two companies: company_a and company_b
   - Create order for company_b
   - Login as company_a admin
   - GET /{company_a.code}/admin/orders/{company_b_order.id}/
   - Assert response.status_code in [403, 404]

2. test_company_a_admin_cannot_view_company_b_invoice
   - Similar but for invoice detail view

3. test_technician_a_cannot_view_company_b_orders
   - Technician of company_a cannot access company_b orders

4. test_customer_a_cannot_view_company_b_orders
   - Customer of company_a cannot access company_b orders

Use Django TestCase with self.client. Create minimal test fixtures.

Run: python manage.py test tests/test_multi_tenant_isolation.py -v 2
Report: all test results.
```

---

## فاز ۲: اطلاع‌رسانی ناقص

### Prompt P2-1: wire کردن رویدادهای لغوشده سفارش

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

Read the following files:
- apps/orders/services.py:OrderCancelService.force_cancel() (lines 314-363)
- apps/orders/cancel_review_service.py (all)
- apps/notifications/event_catalog.py (EventKey constants)

MISSING: After force_cancel() and after cancel_review_service.approve(),
there is no emit of ORDER_CANCELLED event. Also ORDER_CANCEL_REQUESTED_CUSTOMER
is never emitted when the order moves to CANCEL_REQUESTED.

Fix:
1. In OrderCancelService.force_cancel() after status log, add:
   _emit_order_notification_event("order_cancelled", order, cancelled_by,
                                    payload={"reason": reason})

2. In OrderCancelService.request_cancel() (lines 305-311), the emit for
   "order_cancel_requested_customer" IS already there — verify it is correct.

3. In OrderCancelReviewService.approve(), add:
   from apps.orders.cancel_request_events import dispatch_cancel_approved_events
   (check if this is already being called)

Run existing tests: python manage.py test tests/test_p_order_cancel_waiting.py -v 2
Report: exact changes and test results.
```

---

### Prompt P2-2: رفع footer SMS

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

Read:
- apps/sms/sms_footer.py (ensure_sms_footer function)
- apps/sms/services.py:SMSQueueFromTemplateService.queue_from_template() (lines 421-489)

The footer "لغو ۱۱" is defined in sms_footer.py but never called in the queue pipeline.

Fix: In SMSQueueFromTemplateService.queue_from_template(), after rendering template_text
but before calling SMSQueueService.queue(), add:
  from .sms_footer import ensure_sms_footer, FOOTER_EXCLUDED_KEYS
  if template_key not in FOOTER_EXCLUDED_KEYS:
      rendered_text = ensure_sms_footer(rendered_text)

Run: python manage.py test tests/test_sms_footer_enforcement.py -v 2
Report: exact lines changed and test result.
```

---

## فاز ۳: مستندات جدید

### Prompt P3-1: نوشتن Deployment Runbook

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

Read:
- docs/05_Deployment/ENVIRONMENTS.md
- docs/05_Deployment/RELEASE_PROCESS.md
- docs/05_Deployment/BACKUP.md
- config/settings/production.py
- requirements.txt (to understand deployment dependencies)

Create file: docs/05_Deployment/DEPLOYMENT_RUNBOOK.md

Contents must include:
1. Prerequisites (Python version, PostgreSQL, Redis if needed)
2. First-time setup steps
3. Per-release deployment steps (git pull, migrate, collectstatic, restart)
4. Verification steps after deployment
5. Rollback procedure
6. Environment variables required (list from .env.example)

Write in Persian. Be precise and specific. No placeholders.
Do NOT modify any code files.
```

---

### Prompt P3-2: نوشتن ADR-009 سیاست استرداد

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

Read:
- docs/07_ADR/ADR-TEMPLATE.md
- docs/07_ADR/ADR-004-Ledger-Discipline.md
- docs/03_Business/INVOICE_RULES.md

Create file: docs/07_ADR/ADR-009-Refund-Policy.md

Decision to document:
"How does Rasti handle refund/invoice reversal requests when the invoice is PAID?"

Current state (from code):
- InvoiceCancelService.cancel() rejects PAID invoices
- InvoiceCancellationRequestService.approve() rejects PAID invoices
- No refund path exists in the current codebase

The ADR must document:
1. Context (why refunds are deferred)
2. Decision (refunds are not implemented in V1)
3. Consequences (what this means for support workflows)
4. Future implementation requirements (when this is done)
5. Invariant: completed TechnicianLedgerEntries cannot be reversed — only new entries

Do NOT implement any code. Documentation only.
```

---

## فاز ۴: بهبودهای آینده

### Prompt P4-1: Redis Cache Setup

```
You are working on Rasti SaaS at D:\SaaSprojectService\Rasti chekFinal 10 tir

Read config/settings/base.py CACHES section (currently missing).

Add Redis cache configuration:
1. Add django-redis to requirements.txt if not present
2. Add CACHES configuration in base.py with env-var:
   REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
3. Add fallback LocMemCache for local development (in local.py)
4. Update OrderNotificationDispatchMiddleware.THROTTLE to use the cache

Run: python manage.py check
Note: if Redis is not running locally, this should gracefully fall back.
Report: changes made and check result.
```

---

## نکات مهم برای همه Prompt‌ها

1. **هرگز migration‌های مالی را تغییر ندهید** (apps/invoices/migrations, apps/payouts/migrations)
2. **هر تغییر → git commit → سپس تغییر بعدی**
3. **پس از هر فاز تمام تست‌ها را اجرا کنید:** `python manage.py test --verbosity=0`
4. **تست‌های موجود را حذف نکنید**
5. **حداکثر ۵ فایل در یک session تغییر دهید**
