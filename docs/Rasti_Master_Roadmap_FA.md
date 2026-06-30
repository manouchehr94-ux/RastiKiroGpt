# Rasti Service — Master Roadmap پروژه

**هدف سند:** مشخص کردن وضعیت فعلی پروژه، Featureهای Freeze شده، کارهای باقی‌مانده و مسیر 6 تا 12 ماه آینده  
**وضعیت سند:** مرجع مدیریتی و فنی پروژه

---

## 1. تعریف پروژه

Rasti Service یک SaaS چندشرکتی برای مدیریت شرکت‌های خدماتی است.

هدف پروژه فقط ساخت یک سایت نیست؛ هدف ساخت یک پلتفرم است که بتواند شرکت‌های خدماتی مختلف را پوشش دهد:

- ثبت سفارش
- تخصیص تکنسین
- پیگیری وضعیت کار
- فاکتور
- پرداخت
- پیامک
- اعلان داخلی
- تسویه با تکنسین
- گزارش مالی
- مدیریت چندشرکتی

---

## 2. روش توسعه پروژه

روش توسعه پروژه معماری‌محور بوده است:

1. نیاز محصول مشخص می‌شود.
2. معماری بررسی می‌شود.
3. Claude Code کدنویسی را انجام می‌دهد.
4. ChatGPT نقش Architect / QA / Technical PM دارد.
5. خروجی Claude بررسی می‌شود.
6. تست‌ها اجرا می‌شوند.
7. اگر Feature پایدار بود Freeze می‌شود.
8. بعد از Freeze، سند MD نوشته می‌شود.

اصل مهم:

> Feature بدون تست و بدون معماری قابل قبول، کامل محسوب نمی‌شود.

---

## 3. نقش‌ها در توسعه

### مالک پروژه

- تصمیم محصول
- تجربه کاربری
- اولویت کسب‌وکار
- تست دستی
- تصمیم نهایی

### Claude Code

- کدنویسی
- ساخت migration
- ساخت test
- اجرای test
- گزارش تغییرات

### ChatGPT

- Principal Architect
- Senior Django Engineer
- QA Architect
- Technical PM
- تحلیل ریسک
- بازبینی معماری
- نوشتن prompt دقیق
- تصمیم درباره Freeze

---

## 4. وضعیت فعلی پروژه

### Freeze شده یا تقریباً پایدار

| بخش | وضعیت |
|---|---|
| Financial Core v1 | تقریباً Freeze |
| Technician Wage / Rate | ساخته شده |
| Statement / Ledger / Backfill | ساخته شده |
| SMS visibility | ساخته شده |
| Communication Settings | پایدار |
| Communication Matrix | پایدار |
| In-App Notification v1 | Freeze |
| Notification UX | پایدار |
| Payment Notification EventKeys | استاندارد شده |

---

## 5. قابلیت‌های Notification v1

Notification v1 شامل موارد زیر است:

- Bell
- Badge
- Dropdown
- Notification Center
- Mark Read
- Mark All Read
- Deep Link
- Company Isolation
- User Isolation
- Role-specific EventKey
- Communication Matrix integration

فعلاً موارد زیر عمداً ساخته نشده‌اند:

- Firebase
- Browser Push
- PWA Push
- Native Push
- WebSocket
- SSE
- Email Notification

---

## 6. وضعیت Communication Settings

تصمیم معماری مهم:

> Communication Settings محل ویرایش متن پیام نیست.

شرکت فقط می‌تواند ببیند و فعال/غیرفعال کند:

- SMS برای هر role
- In-App برای هر role

متن پیام‌ها توسط مالک پلتفرم مدیریت می‌شود.

درخواست تغییر متن پیام از سمت شرکت فعلاً نباید در UI دیده شود و اگر مسیر قدیمی وجود دارد باید حذف یا غیرفعال شود.

---

## 7. وضعیت SMS

SMS دارای معماری Outbox است.

وضعیت:

- SMS queue وجود دارد.
- SMS runner دستی وجود دارد.
- Communication Settings وضعیت queue و failed و sent-today را نشان می‌دهد.
- ارسال manual تا limit مشخص وجود دارد.

نیاز آینده:

- cron / task scheduler برای نسخه ساده
- بعداً Celery Beat برای نسخه Production
- retry backoff
- limit اجباری
- monitoring

---

## 8. وضعیت Financial Core

نقاط مثبت:

- Ledger immutable
- idempotency
- InvoiceCounter
- transaction.atomic
- Backfill task
- Technician statement
- Platform fee logic

فعلاً Feature مالی جدید نباید ساخته شود مگر برای رفع باگ یا Production hardening.

---

## 9. اولویت اصلی بعدی

بعد از Freeze Notification/Communication، اولویت اصلی باید باشد:

# Order Lifecycle Audit

چرا؟

چون سفارش قلب سیستم است.

باید از ابتدا تا انتها تست شود:

1. public request
2. admin/operator approval
3. create order
4. assign technician
5. technician acceptance/waiting
6. start service
7. complete service
8. cancellation request
9. cancellation approval/rejection
10. invoice
11. payment
12. notification
13. sms
14. permission per role

---

## 10. Roadmap نسخه 1.0

### هدف v1

یک SaaS قابل استفاده برای شرکت خدماتی واقعی، با قابلیت‌های اصلی.

### باید داشته باشد

- Multi-tenant admin
- Company users
- Operator permission
- Technician panel
- Order lifecycle
- Basic invoice
- Payment flow
- SMS Outbox
- In-App Notification
- Communication Settings
- Financial ledger
- Basic reports
- Production کوچک

### نباید در v1 باشد

- Firebase Push
- Mobile native app کامل
- Kubernetes
- Microservice
- BI پیشرفته
- هوش مصنوعی
- Accounting کامل
- Customer app کامل

---

## 11. Roadmap نسخه 1.5

بعد از Production کوچک:

- Redis
- PgBouncer
- tenant cache
- Celery
- SMS worker
- notification worker
- Sentry
- payment reconciliation dashboard
- better permission audit
- private media
- load test تا 500 یا 1000 کاربر

---

## 12. Roadmap نسخه 2.0

وقتی محصول مشتری واقعی و داده واقعی دارد:

- Customer Portal کامل
- PWA
- Browser Push
- Firebase/FCM
- Email Notification
- WhatsApp/Bale/Eitaa integrations در صورت نیاز بازار ایران
- Advanced reports
- BI dashboard
- mobile technician app تکمیل‌تر
- CDN/object storage
- read replica در صورت نیاز

---

## 13. Roadmap 6 ماه آینده

### ماه 1

- Order Lifecycle Audit
- Permission Audit
- QA دستی
- bug fixing
- تکمیل docs
- آماده‌سازی production کوچک

### ماه 2

- Production Readiness Phase
- Redis
- PgBouncer
- tenant cache
- ensure_defaults cleanup
- Sentry
- critical indexes

### ماه 3

- اولین مشتری واقعی یا pilot
- رفع bugهای واقعی
- بهبود UX فرم‌ها
- تست end-to-end
- SMS runner پایدار

### ماه 4

- Celery
- notification worker
- payment hardening
- private media
- dashboard performance

### ماه 5

- Customer Portal اولیه
- PWA پایه
- push notification design
- load test مرحله‌ای

### ماه 6

- تثبیت v1.5
- آماده‌سازی v2
- توسعه بازار
- مستندسازی کامل‌تر

---

## 14. تصمیم درباره Push Notification

فعلاً نباید ساخته شود.

شرط ورود به Push:

1. Order Workflow پایدار باشد.
2. In-App پایدار باشد.
3. SMS پایدار باشد.
4. Redis/Celery آماده باشد.
5. Customer/Technician UX مشخص باشد.

بعد از این‌ها:

- Browser Push
- PWA Push
- Firebase/FCM
- Native Mobile Push

قابل بررسی هستند.

---

## 15. تصمیم درباره Customer Portal

Customer role وجود دارد، اما Customer Portal هنوز محور اصلی نیست.

ترتیب درست:

1. ثبت سفارش عمومی
2. پیامک مشتری
3. public invoice link
4. بعداً customer login
5. بعداً notification center مشتری
6. بعداً PWA مشتری

---

## 16. تصمیم درباره Production Readiness

Production Readiness یک Feature نیست؛ یک فاز مستقل است.

این فاز شامل:

- settings
- DB connection
- Redis
- cache
- media security
- Sentry
- indexes
- payment hardening
- SMS runner
- backup
- health check
- load test

---

## 17. تصمیم درباره Documentation

از این به بعد هر Feature که Freeze می‌شود باید سند MD داشته باشد.

ساختار پیشنهادی:

```text
docs/
  00_ARCHITECTURE/
  01_FEATURES/
  02_PRODUCTION/
  03_QA/
  07_ADR/
  CHANGELOG.md
```

اسناد فعلی پیشنهادی:

- Notification-Architecture.md
- Communication-Architecture.md
- SMS-Architecture.md
- Order-Lifecycle.md
- Production-Readiness-Audit.md
- Scalability-Roadmap.md
- Master-Roadmap.md

---

## 18. ریسک‌های مدیریتی

### ریسک 1: ساخت Feature جدید قبل از تثبیت Order

اگر قبل از Order Lifecycle Audit برویم سراغ Push/PWA/Mobile، پروژه پیچیده می‌شود.

### ریسک 2: over-engineering

نباید الان Kubernetes، microservice یا Kafka وارد شود.

### ریسک 3: مستندسازی نکردن

اگر تصمیم‌ها ثبت نشوند، بعداً علت معماری‌ها فراموش می‌شود.

### ریسک 4: قاطی شدن commitها

هر Feature باید commit جدا داشته باشد.

---

## 19. اصول ادامه توسعه

1. Feature جدید بدون تست نه.
2. تغییر معماری بدون دلیل نه.
3. هر Feature بعد از تست Freeze شود.
4. هر Freeze باید سند داشته باشد.
5. Production readiness را با Feature development قاطی نکنیم.
6. Performance را با حدس حل نکنیم؛ با load test حل کنیم.
7. اول محصول، بعد scale سنگین.
8. اول Order، بعد Push.

---

## 20. نتیجه نهایی

پروژه Rasti Service به مرحله‌ای رسیده که زیرساخت‌های مهم آن شکل گرفته‌اند.

اکنون باید تمرکز از «ساخت زیرسیستم‌های پراکنده» به سمت «تثبیت گردش اصلی محصول» برود.

اولویت‌های واقعی:

1. Order Lifecycle Audit
2. Permission Audit
3. Production Readiness Phase
4. QA دستی end-to-end
5. Pilot واقعی
6. سپس Push/PWA/Customer Portal

این مسیر پروژه را قابل کنترل، قابل توسعه و قابل استفاده برای مشتری واقعی نگه می‌دارد.
