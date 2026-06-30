# Rasti Service — گزارش نهایی بررسی Production Readiness

**پروژه:** Rasti Service  
**مسیر پروژه:** `D:\SaaSprojectService\Rasti chekFinal 5 tir`  
**نوع سیستم:** Django 5.2 Multi-Tenant SaaS  
**هدف بررسی:** آمادگی پروژه برای Production و رشد تا بار سنگین  
**تاریخ سند:** 2026-06-29  
**وضعیت:** سند مرجع معماری و ریسک

---

## 1. خلاصه مدیریتی

پروژه Rasti Service از نظر معماری محصول، تفکیک دامنه‌ها، سیستم چندشرکتی، Financial Core، اعلان‌ها، پیامک و تست‌ها مسیر درستی دارد.

اما پروژه در وضعیت فعلی برای بار سنگین Production، مخصوصاً سناریویی مثل 10,000 کاربر همزمان، آماده نیست.

مشکل اصلی پروژه «بد بودن کدنویسی» نیست. مشکل اصلی این است که چند قطعه زیرساختی ضروری هنوز وارد سیستم نشده‌اند:

- Connection Pool برای PostgreSQL
- Redis / Shared Cache
- Cache شدن Tenant Resolution
- حذف `ensure_defaults()` از مسیر داغ Notification/SMS
- مانیتورینگ خطاها
- امن‌سازی فایل‌های حساس KYC
- اصلاح چند Index مهم دیتابیس

این موارد نیازمند بازنویسی پروژه نیستند. باید در یک فاز مشخص به نام **Production Readiness Phase** انجام شوند.

---

## 2. ارزیابی کلی

| بخش | وضعیت |
|---|---|
| معماری Django | خوب |
| معماری Multi-Tenant | خوب |
| Financial Core | قوی |
| Notification / Communication | پایدار برای v1 |
| SMS Outbox | معماری درست، نیازمند بهینه‌سازی |
| Payment | پایه خوب، نیازمند بررسی callback و idempotency |
| امنیت Production | متوسط رو به خوب، چند ریسک مهم دارد |
| Performance فعلی | مناسب توسعه و تست، نه بار سنگین |
| Deployment Readiness | هنوز کامل نیست |
| نیاز به بازنویسی | خیر |

---

## 3. نقاط قوت مهم پروژه

### 3.1 معماری چندشرکتی

وجود `CompanyOwnedModel` و الزام `company` در اکثر مدل‌ها باعث شده پایه Multi-Tenant درست باشد.

### 3.2 تفکیک Appها

ساختار کلی Appها منطقی است:

- tenants
- accounts
- orders
- invoices
- payments
- sms
- notifications
- payouts
- platform_core
- reports
- api

این تفکیک برای SaaS قابل قبول است.

### 3.3 Financial Core

بخش مالی از نظر معماری نسبتاً قوی است:

- Ledger immutable
- idempotency key
- transaction.atomic در مسیرهای مهم
- InvoiceCounter با `select_for_update`
- Backfill task برای خطاهای مالی

این‌ها تصمیم‌های درست و حرفه‌ای هستند.

### 3.4 Notification و Communication

سیستم اعلان داخلی و Communication Matrix به وضعیت مناسبی رسیده‌اند:

- EventKeyهای مستقل
- تنظیمات per-company
- SMS و In-App جدا
- Bell / Badge / Dropdown / Notification Center
- Mark Read / Mark All Read
- تست‌های اختصاصی

این بخش برای v1 قابل Freeze است.

### 3.5 تست‌ها

پروژه تست‌های زیادی دارد. طبق گزارش Claude، حدود 1242 تست در پروژه وجود دارد و بخش Notification/Communication هم 113 تست پاس شده دارد.

---

## 4. ریسک‌های Critical

این موارد قبل از Production جدی باید اصلاح شوند.

### 4.1 نبود Connection Pool

**شدت:** Critical  
**بخش:** Database / Deployment

در حالت فعلی اگر `CONN_MAX_AGE` تنظیم نباشد، Django برای درخواست‌ها Connection کوتاه‌عمر به دیتابیس می‌سازد. PostgreSQL معمولاً تعداد Connection محدودی دارد. در بار بالا، اولین نقطه شکست همین است.

**اقدام پیشنهادی:**

- تنظیم `CONN_MAX_AGE = 60`
- راه‌اندازی PgBouncer
- تست با چند worker واقعی Gunicorn

---

### 4.2 نبود Redis / Shared Cache

**شدت:** Critical  
**بخش:** Cache / Middleware / Session

اگر Cache تنظیم نشده باشد، Django از LocMemCache استفاده می‌کند. LocMemCache بین workerهای Gunicorn مشترک نیست. بنابراین throttleها و cache.addها در multi-worker درست کار نمی‌کنند.

**اقدام پیشنهادی:**

- نصب Redis
- تنظیم `CACHES`
- بعداً انتقال Session به Redis
- استفاده از Redis برای tenant cache و notification badge cache

---

### 4.3 Uncached Tenant Resolution

**شدت:** Critical  
**بخش:** tenants.middleware

در هر request، شرکت از روی `company_code` پیدا می‌شود. اگر این کار هر بار با دیتابیس انجام شود، در بار بالا دیتابیس با queryهای ساده اما پرتعداد اشباع می‌شود.

**اقدام پیشنهادی:**

- cache key: `tenant:company_code:{code}`
- TTL: حدود 5 دقیقه
- invalidation هنگام تغییر Company

---

### 4.4 `ensure_defaults()` در مسیر داغ

**شدت:** Critical  
**بخش:** notifications / sms

گزارش Claude می‌گوید `ensure_defaults()` ممکن است در مسیرهای runtime مثل SMS/Notification اجرا شود و برای هر رویداد تعداد زیادی `get_or_create` بزند.

این الگو برای production خطرناک است.

**اقدام پیشنهادی:**

- اجرای `ensure_defaults()` فقط هنگام ایجاد شرکت
- ساخت management command برای backfill شرکت‌های قدیمی
- حذف فراخوانی از مسیر runtime
- cache کردن تنظیمات event/channel

---

### 4.5 Payment Callback Verification

**شدت:** Critical  
**بخش:** payments

Callback پرداخت نباید فقط با `reference_id` باعث تغییر وضعیت مالی شود. باید verify واقعی از gateway انجام شود و amount/status/idempotency بررسی شود.

**اقدام پیشنهادی:**

- بررسی دقیق `PaymentCallbackService`
- اطمینان از idempotency
- بررسی amount
- ثبت PaymentAttempt
- transaction.atomic برای کل callback

---

### 4.6 `ALLOWED_HOSTS = ["*"]`

**شدت:** Critical  
**بخش:** settings

اگر در base.py مقدار `ALLOWED_HOSTS = ["*"]` فعال باشد، خطرناک است. حتی اگر production.py آن را override کند، این الگو باید حذف شود.

**اقدام پیشنهادی:**

- حذف wildcard از base.py
- اجبار به env
- تست production settings

---

## 5. ریسک‌های High

### 5.1 KYC Media Access

فایل‌های حساس مثل کارت ملی، جواز کسب و مدارک شرکت نباید مستقیم از `/media/` سرو شوند.

**اقدام پیشنهادی:**

- private media
- authenticated download view
- یا storage با signed URL

---

### 5.2 SMS Processor N+1

پردازش SMS نباید ابتدا IDها را بگیرد و بعد برای هر SMS جدا query بزند.

**اقدام پیشنهادی:**

- fetch batch با `select_related`
- limit اجباری
- retry backoff
- timeout برای پیام‌های stuck در SENDING

---

### 5.3 Missing Indexهای مهم

اولویت‌های مهم:

- `CompanyUser(company, role)`
- `Order(company, status, created_at)`
- `Invoice(company, status, created_at)`
- `Payment(reference_id)`
- `Notification(company, recipient, created_at)`
- `OrderStatusLog(company, order, created_at)`
- `RegistrationOTP(phone)`

---

### 5.4 Silent `except: pass`

در event handlerهای سفارش، silent failure خطرناک است. اگر SMS یا Notification ساخته نشود، کسی متوجه نمی‌شود.

**اقدام پیشنهادی:**

- جایگزینی با `logger.exception`
- بعداً ثبت failure metric
- تست اینکه خطا در notification باعث خراب شدن order نشود اما log شود

---

### 5.5 Plaintext API Keys

SMS API Key و Payment API Key نباید در DB خام بمانند.

**اقدام پیشنهادی:**

- field-level encryption
- rotation strategy
- محدود کردن نمایش در admin

---

### 5.6 نبود Rate Limit

Login، OTP، password reset و public submit باید rate limit داشته باشند.

**اقدام پیشنهادی:**

- django-ratelimit یا DRF throttling
- محدودیت per IP و per phone

---

## 6. موارد Medium

این موارد مهم هستند، اما قبل از تکمیل Featureهای محصول فوریت Critical ندارند.

- caching unread badge
- CSP header
- refactor فایل بزرگ `tenants/views_admin.py`
- حذف inline styleها
- انتقال static به CDN
- Docker / nginx config
- Celery کامل
- central logging
- حذف فایل‌های backup static
- ساخت test fixture/factory استاندارد

---

## 7. مواردی که فعلاً نباید انجام شوند

برای وضعیت فعلی پروژه، این موارد زود هستند:

- Microservice
- Kubernetes
- Kafka
- RabbitMQ در همین لحظه
- Sharding
- CQRS
- Event Sourcing
- بازنویسی Frontend با React/Vue
- بازنویسی کل سیستم Notification
- Push Notification قبل از تثبیت کامل Order Workflow

---

## 8. نظر نهایی من درباره گزارش Claude

گزارش Claude از نظر فنی مفید و قابل اتکا است، اما چند جا بدبینانه است.

من با اصل هشدارها موافقم، اما نباید نتیجه بگیریم که پروژه بد ساخته شده است. نتیجه درست این است:

> پروژه از نظر Product Architecture مناسب است، اما از نظر Production Infrastructure هنوز کامل نیست.

پس نباید پروژه را بازنویسی کنیم. باید یک فاز هدفمند Production Readiness تعریف کنیم.

---

## 9. تصمیم نهایی

### وضعیت فعلی

- مناسب برای توسعه جدی
- مناسب برای تست داخلی
- مناسب برای QA دستی
- مناسب برای تکمیل Featureهای نسخه اول
- نه مناسب برای بار سنگین Production

### شرط ورود به Production واقعی

قبل از Production باید حداقل این‌ها انجام شوند:

1. تنظیم production settings
2. PostgreSQL واقعی
3. Gunicorn
4. PgBouncer / CONN_MAX_AGE
5. Redis
6. Tenant cache
7. حذف ensure_defaults از runtime
8. media security برای KYC
9. payment callback audit
10. Sentry / logging
11. Indexهای ضروری

---

## 10. نتیجه

Rasti Service پروژه‌ای است که پایه معماری قابل قبولی دارد. ریسک اصلی در خود محصول نیست، بلکه در آماده‌سازی Production و Scalability است.

مسیر درست این است:

1. Featureهای نسخه اول را کامل کنیم.
2. یک فاز Production Readiness انجام دهیم.
3. Load Test واقعی بگیریم.
4. فقط bottleneckهای واقعی را اصلاح کنیم.
5. بعد وارد Push/PWA/Mobile شویم.
