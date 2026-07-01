# ۰۴ — حسابرسی معماری و طراحی فنی

**تاریخ:** ۳۰ ژوئن ۲۰۲۶

---

## الف — پیکربندی Django

### ۱. تنظیمات (Settings)

**`config/settings/base.py`**

| تنظیم | مقدار | ارزیابی |
|---|---|---|
| `SECRET_KEY` | از env-var `DJANGO_SECRET_KEY` | ✅ |
| `DEBUG` | از env-var، پیش‌فرض `False` | ✅ |
| `ALLOWED_HOSTS` | `["*"]` هاردکد! | ❌ CRITICAL — env-var کامنت شده است |
| `DATABASES` | PostgreSQL از env-vars | ✅ |
| `AUTH_USER_MODEL` | `"accounts.CompanyUser"` | ✅ |
| `AUTHENTICATION_BACKENDS` | `AllowAllUsersModelBackend` | ⚠️ is_active باید دستی بررسی شود |
| `LANGUAGE_CODE` | `"fa-ir"` | ✅ |
| `TIME_ZONE` | `"Asia/Tehran"` | ✅ |
| `CACHES` | تعریف نشده | ❌ پیش‌فرض LocMemCache — throttle بی‌اثر در multi-worker |

**`config/settings/local.py`**
- Database: SQLite (برای توسعه محلی)
- DEBUG = True

**`config/settings/production.py`**
- DEBUG = False ✅
- Security headers تنظیم شده ✅
- `ALLOWED_HOSTS`: اگر `DJANGO_ALLOWED_HOSTS` تنظیم نشده باشد → `[""]` که همه درخواست‌ها را رد می‌کند ❌

### ۲. INSTALLED_APPS

**نقص حیاتی:**
```
# در INSTALLED_APPS نیست:
"rest_framework_simplejwt.token_blacklist"
```
`apps/api/auth_views.py:163` از `token.blacklist()` استفاده می‌کند اما این اپ در `INSTALLED_APPS` نیست. JWT logout بی‌اثر است.

**اپ‌های نصب‌شده به ترتیب:**
```python
DJANGO_APPS = [django.contrib.admin, auth, contenttypes, sessions, messages, staticfiles, humanize]
THIRD_PARTY_APPS = [django_extensions, rest_framework]
LOCAL_APPS = [common, platform_core, tenants, accounts, orders, invoices, payments, billing,
              notifications.NotificationsConfig, sms, reports, payouts, dashboard, api, public]
```
ترتیب `platform_core` و `tenants` قبل از سایرین صحیح است.

---

## ب — Middleware

ترتیب middleware (`base.py:65-79`):
```
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. SessionMiddleware
4. CommonMiddleware
5. CsrfViewMiddleware
6. AuthenticationMiddleware
7. TenantMiddleware            ← بعد از Auth، صحیح ✅
8. OperatorPermissionMiddleware
9. OrderNotificationDispatchMiddleware  ← ⚠️ IO در response cycle
10. MessageMiddleware
11. XFrameOptionsMiddleware
```

**⚠️ نقص:** `OrderNotificationDispatchMiddleware` بعد از get_response() کار می‌کند (بعد از response). این یعنی IO پیامک به cycle درخواست/پاسخ اضافه می‌شود. در صورت خطا، با try/except جلوگیری می‌شود اما تأخیر اضافه می‌شود.

---

## ج — چند‌مستأجری (Multi-tenancy)

### روش پیاده‌سازی: Path-based (مسیر-محور)

```
/rasti-test/admin/orders/     → company.code = "rasti-test"
/api/rasti-test/orders/       → company.code = "rasti-test"
/login/                       → exempt (بدون company)
```

### `TenantMiddleware` (`apps/tenants/middleware.py`)

1. URL اول را تجزیه می‌کند
2. اگر در `TENANT_EXEMPT_PREFIXES` → رد می‌شود
3. `Company.objects.get(code=...)` → ❌ **هیچ caching وجود ندارد** (هر درخواست یک query DB)
4. اگر نیافت یا غیرفعال بود → `Http404`
5. `request.company = company` تنظیم می‌شود

**⚠️ نقص:** Company lookup کش نمی‌شود. در traffic بالا، هر درخواست یک DB query اضافه می‌کند.

### مدل پایه: `CompanyOwnedModel`

```python
# apps/common/models.py:22
class CompanyOwnedModel(TimeStampedModel):
    company = models.ForeignKey("tenants.Company", CASCADE, db_index=True)
```

مدل‌هایی که از این ارث می‌برند (✅): `Order`, `Invoice`, `Payment`, `Technician`, `Customer`, `Notification`, `TechnicianLedgerEntry`

مدل‌هایی که مستقیماً `company` FK دارند اما از CompanyOwnedModel ارث نمی‌برند (⚠️): `CompanyFinancialPolicy`, `CompanySettings`, `CompanyPaymentSettings`, `OrderCustomField` — این مدل‌ها تناقض معماری با قانون "همه مدل‌های مستأجر باید از CompanyOwnedModel ارث ببرند" ایجاد می‌کنند.

### ایزولاسیون query‌ها

**✅ رعایت شده در:**
- `orders/selectors.py` — همه queries با `company=company`
- `invoices/selectors.py` — همه queries با `company=company`
- `dashboard/selectors.py` — همه queries با `company=company`

**❌ استثنا:**
- `orders/views.py:339` — `Order.objects.filter(company=company, ...)` مستقیماً در view (باید از selector استفاده شود)
- `platform_core/views_merchant_profile.py:134` — `CompanyMerchantProfile.objects.get(id=profile_id)` بدون company scope (تحت `@require_platform_owner`)

---

## د — سیستم احراز هویت و نقش‌ها

### مدل کاربر

```python
# accounts/models.py:59
class CompanyUser(AbstractBaseUser, PermissionsMixin):
    company = ForeignKey(Company, null=True)   # null برای PLATFORM_OWNER
    username = CharField(unique=True)
    role = CharField(choices=UserRole)
    is_active = BooleanField(default=True)
    must_change_password = BooleanField(default=False)
```

### نقش‌ها (`UserRole`)

| نقش | مقدار DB | توضیح |
|---|---|---|
| PLATFORM_OWNER | `"PLATFORM_OWNER"` | ادمین کل پلتفرم |
| COMPANY_ADMIN | `"COMPANY_ADMIN"` | مدیر شرکت |
| COMPANY_STAFF | `"COMPANY_STAFF"` | اپراتور (دسترسی محدود) |
| TECHNICIAN | `"TECHNICIAN"` | تکنسین |
| CUSTOMER | `"CUSTOMER"` | مشتری |

### مکانیزم مجوزها

1. **`@require_platform_owner`** — فقط PLATFORM_OWNER
2. **`@require_tenant_role(*roles)`** — role + company membership  
3. **`OperatorPermissionMiddleware`** — per-URL, per-COMPANY_STAFF گرانول
4. **`OperatorPermission` model** — جدول مجوز URL-level برای COMPANY_STAFF

**❌ نقص حیاتی:** `admin_operator_list` (`tenants/views_admin.py:2125`) هیچ decorator احراز نقشی ندارد.

---

## ه — لایه سرویس (Service Layer)

### اصول رعایت‌شده

✅ همه servi‌ها از `@transaction.atomic` استفاده می‌کنند  
✅ `select_for_update()` در عملیات‌های حساس (assign, pay, settle)  
✅ Services هرگز مستقیماً `request` نمی‌گیرند  
✅ Views به‌عنوان thin layer عمل می‌کنند

### الگوی selector/service

```
View → Selector (read) / Service (write) → Model
```

**استثنا:** `orders/views.py:339` مستقیماً `Order.objects.filter()` را فراخوانی می‌کند.

---

## و — پایگاه داده

### نوع DB

- محلی: SQLite (در `local.py`)
- تولید: PostgreSQL از env-vars

**⚠️ خطر:** SQLite رفتار `select_for_update()` متفاوتی نسبت به PostgreSQL دارد. تست‌های concurrency روی SQLite معتبر نیستند.

### ایندکس‌ها

موارد خوب:
- `Order.Meta.indexes = [(company, status), (company, customer), (company, technician)]`
- `TechnicianLedgerEntry.idempotency_key` — unique
- `SMSOutbox.Meta.indexes = [(company, status), (status, send_at)]`

موارد احتمالاً کمبود:
- `OrderStatusLog`: بدون compound index روی `(company, order)`
- `NotificationEvent`: بدون compound index روی `(company, event_key, created_at)`

---

## ز — REST API

### وضعیت فعلی

- نصب: `rest_framework` + `rest_framework_simplejwt` (در requirements اما نه در INSTALLED_APPS)
- احراز: SessionAuthentication (برای tenant views) + JWT (برای mobile API)
- namespace‌ها: `api-auth`, `api-platform`, `api-tenant`
- **⚠️ باگ:** `apps/api/views.py:311` — `Customer.objects.create(name=...)` فیلد وجود ندارد

### نقاط قوت

- مجوزبندی مناسب در اکثر view‌های API
- DRF pagination پیکربندی شده (20 مورد)

---

## ح — ایستا و media

### CSS Architecture

```
static/css/theme.css ← entrypoint
  @import tokens.css     (متغیرهای طراحی)
  @import base.css       (ریست، فونت)
  @import components.css (دکمه، کارت، badge)
  @import layouts.css    (sidebar، topbar)
  @import pages.css      (صفحات خاص)
  @import dashboard.css  (utility classes)
  @import responsive.css (media queries)
```

**⚠️ مشکل:** ۹ فایل CSS با `@import` به‌صورت زنجیری بارگذاری می‌شوند. در HTTP/1.1 این یعنی ۹ درخواست متوالی. هیچ build/bundle step وجود ندارد.

**⚠️ مشکل:** Alpine.js و ApexCharts از CDN خارجی بارگذاری می‌شوند بدون fallback محلی.

**⚠️ مشکل:** `js/rasti_sidebar.js` و inline sidebar script در `layouts/dashboard.html` هر دو `openSidebar/closeSidebar` تعریف می‌کنند.

---

## ط — امنیت

| آیتم | وضعیت | جزئیات |
|---|---|---|
| SECRET_KEY از env | ✅ | بدون hardcode |
| DEBUG=False در تولید | ✅ | `production.py:24` |
| HTTPS headers | ✅ | در `production.py` |
| ALLOWED_HOSTS | ❌ | `base.py:20` = `["*"]` hardcode |
| CSRF | ✅ | middleware فعال |
| SQL injection | ✅ | ORM استفاده می‌شود |
| رمز عبور هاردکد | ❌ | `views.py:58` — `check_password("123456")` |
| API keys در DB | ⚠️ | `merchant_id`, `api_key` به‌صورت plaintext ذخیره می‌شوند |
| KYC media files | ⚠️ | نیازمند بررسی که فقط platform owner دسترسی دارد |
| Rate limiting | ❌ | روی هیچ endpoint ای پیاده‌سازی نشده |
| CACHES backend | ❌ | throttle در multi-worker بی‌اثر |
