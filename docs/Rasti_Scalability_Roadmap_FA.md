# Rasti Service — Roadmap بهبود مقیاس‌پذیری

**هدف:** آماده‌سازی مرحله‌ای پروژه برای کاربران بیشتر  
**مبنای سند:** Production Readiness Audit کل پروژه  
**اصل مهم:** بدون بازنویسی، بدون over-engineering، مرحله‌به‌مرحله

---

## 1. اصل راهبردی

هدف این نیست که همین امروز سایت برای 10,000 کاربر همزمان آماده باشد.

هدف درست این است که پروژه طوری رشد کند که از:

- تست داخلی
- اولین مشتری واقعی
- چند شرکت
- ده‌ها شرکت
- صدها شرکت
- هزاران کاربر

عبور کند، بدون اینکه معماری اصلی از هم بپاشد.

---

## 2. مرحله صفر — وضعیت فعلی

### مناسب برای

- توسعه
- تست داخلی
- QA دستی
- تکمیل Featureها
- تثبیت Workflowها

### نامناسب برای

- لانچ عمومی سنگین
- تبلیغات گسترده
- تعداد زیاد کاربران همزمان
- میلیون‌ها رکورد بدون index و cache

---

## 3. Phase 1 — Production کوچک

**هدف:** اولین اجرای واقعی برای مشتری محدود.

### کارها

1. اصلاح production settings
2. حذف `ALLOWED_HOSTS=["*"]`
3. تنظیم `DEBUG=False`
4. تنظیم env واقعی
5. PostgreSQL واقعی
6. اجرای migrationها
7. Gunicorn
8. Nginx
9. collectstatic
10. Backup اولیه

### معیار قبول

- سایت با runserver اجرا نشود.
- سایت با Gunicorn/Nginx بالا بیاید.
- لاگ‌ها قابل خواندن باشند.
- خطای 500 دیده نشود.
- migrationها clean باشند.

---

## 4. Phase 2 — Database Connection Stability

**هدف:** جلوگیری از سقوط دیتابیس در بار همزمان.

### کارها

1. اضافه کردن `CONN_MAX_AGE = 60`
2. نصب PgBouncer
3. تنظیم PostgreSQL max_connections
4. تست چند worker Gunicorn
5. بررسی connection leak

### معیار قبول

- 100 تا 300 کاربر همزمان باعث `too many connections` نشوند.
- connectionها کنترل‌شده باشند.

---

## 5. Phase 3 — Redis و Shared Cache

**هدف:** حذف وابستگی cache به حافظه هر worker.

### کارها

1. نصب Redis
2. تنظیم `CACHES`
3. تست cache در multi-worker
4. انتقال Session به Redis یا cached session
5. استفاده از Redis برای throttleها

### معیار قبول

- cache بین workerها مشترک باشد.
- middleware throttle فقط یک بار اجرا شود، نه به تعداد workerها.
- sessionها در بار بالا دیتابیس را درگیر نکنند.

---

## 6. Phase 4 — Tenant Cache

**هدف:** حذف query دیتابیس برای پیدا کردن Company در هر request.

### کارها

1. cache کردن Company با company_code
2. TTL حدود 5 دقیقه
3. invalidation هنگام تغییر Company
4. تست tenant isolation بعد از cache

### معیار قبول

- requestهای تکراری برای یک company_code دیگر هر بار DB query نزنند.
- نشت tenant اتفاق نیفتد.

---

## 7. Phase 5 — حذف Runtime Seeding

**هدف:** حذف `ensure_defaults()` از مسیرهای پرتکرار.

### مشکل

`ensure_defaults()` برای seed کردن تنظیمات خوب است، اما نباید در مسیر هر event اجرا شود.

### کارها

1. اجرای `ensure_defaults()` هنگام create company
2. management command برای backfill شرکت‌های موجود
3. حذف فراخوانی از `is_enabled` و مسیرهای runtime
4. تست اینکه تنظیمات موجود خراب نشوند

### معیار قبول

- ساخت order/payment/invoice دیگر باعث ده‌ها `get_or_create` نشود.
- testهای Notification و SMS همچنان pass شوند.

---

## 8. Phase 6 — SMS Worker Stabilization

**هدف:** آماده‌سازی SMS Outbox برای حجم بالا.

### کارها

1. batch processing واقعی
2. رفع N+1
3. limit اجباری
4. retry backoff
5. max attempts
6. stuck SENDING cleanup
7. log شکست ارسال

### معیار قبول

- پردازش 100 پیامک با چند query منطقی انجام شود.
- پیامک failed در هر run دوباره بی‌نهایت تلاش نشود.
- پیامک stuck قابل recovery باشد.

---

## 9. Phase 7 — Indexهای ضروری

**هدف:** جلوگیری از کندی در جدول‌های بزرگ.

### Indexهای اولویت‌دار

```text
CompanyUser(company, role)
CompanyUser(company, is_active)
Order(company, status, created_at)
Order(company, technician, status)
Invoice(company, status, created_at)
Payment(reference_id)
Payment(company, status, created_at)
Notification(company, recipient, created_at)
OrderStatusLog(company, order, created_at)
RegistrationOTP(phone)
```

### معیار قبول

- migrationها ساخته و تست شوند.
- queryهای اصلی با explain بررسی شوند.
- testها pass شوند.

---

## 10. Phase 8 — Observability

**هدف:** فهمیدن خطاها قبل از کاربر.

### کارها

1. نصب Sentry
2. logger استاندارد
3. حذف silent `except: pass`
4. لاگ خطاهای notification/sms
5. health check دیتابیس و Redis
6. alert برای خطاهای payment

### معیار قبول

- Exceptionها دیده شوند.
- خطاهای SMS/Notification مخفی نمانند.
- Production قابل عیب‌یابی باشد.

---

## 11. Phase 9 — Payment Hardening

**هدف:** جلوگیری از خطای مالی.

### کارها

1. review کامل `PaymentCallbackService`
2. verify واقعی gateway
3. amount check
4. idempotency برای callback تکراری
5. transaction.atomic
6. PaymentAttempt logging
7. workflow برای `NEEDS_RECONCILIATION`

### معیار قبول

- callback تکراری پرداخت دوباره نسازد.
- callback جعلی پرداخت را paid نکند.
- اختلاف مبلغ قابل تشخیص باشد.

---

## 12. Phase 10 — Media Security

**هدف:** محافظت از مدارک حساس شرکت‌ها.

### کارها

1. private media path
2. عدم سرو مستقیم `/media/kyc/`
3. authenticated download view
4. یا S3/private bucket با signed URL
5. تست نقش‌ها برای دانلود

### معیار قبول

- کاربر بدون مجوز نتواند فایل KYC ببیند.
- شرکت A نتواند فایل شرکت B را ببیند.

---

## 13. Phase 11 — Celery

**هدف:** جدا کردن کارهای پس‌زمینه از request.

### زمان مناسب

بعد از Redis، tenant cache، SMS stabilization و production کوچک.

### کارها

1. نصب Celery
2. Redis broker
3. Celery Beat
4. SMS worker
5. notification dispatch worker
6. payment cleanup jobs
7. backfill jobs

### معیار قبول

- request کاربر منتظر SMS/Notification نماند.
- jobها retry داشته باشند.
- queue lag قابل مشاهده باشد.

---

## 14. Phase 12 — Load Test واقعی

**هدف:** تصمیم‌گیری بر اساس عدد واقعی.

### ابزارها

- k6
- Locust

### سناریوها

1. login admin
2. dashboard
3. order list
4. create order
5. assign technician
6. technician panel
7. create invoice
8. payment callback
9. notifications
10. communication settings

### پله‌های تست

```text
50 concurrent
100 concurrent
300 concurrent
500 concurrent
1000 concurrent
3000 concurrent
5000 concurrent
10000 concurrent
```

### معیارها

- average response time
- P95
- error rate
- DB connections
- DB CPU
- Redis memory
- queue lag
- slow queries
- SMS throughput

---

## 15. Phase 13 — CDN و Object Storage

**زمان مناسب:** وقتی کاربران و فایل‌ها زیاد شدند.

### کارها

1. static files روی CDN
2. media files روی private storage
3. signed URL برای فایل حساس
4. cache headers

---

## 16. Phase 14 — بهینه‌سازی‌های بعدی

بعد از داشتن داده واقعی:

- query optimization
- read replica
- partitioning log tables
- archive old SMS/Notification
- background report generation
- dashboard caching

---

## 17. چیزهایی که فعلاً نباید انجام شوند

- Kubernetes
- Microservice
- Kafka
- Sharding
- بازنویسی Frontend
- Event Sourcing
- CQRS
- Push Notification قبل از تثبیت Workflow اصلی

---

## 18. ترتیب اجرای پیشنهادی

### فوری قبل از Production

1. production settings
2. CONN_MAX_AGE
3. PgBouncer
4. Redis
5. tenant cache
6. ensure_defaults cleanup
7. KYC media protection
8. payment callback audit
9. Sentry
10. critical indexes

### بعد از Production کوچک

1. Celery
2. SMS worker
3. notification worker
4. CDN
5. Load test

### بعد از رشد واقعی

1. read replica
2. table partitioning
3. advanced caching
4. Push/PWA/Mobile
5. BI/reporting

---

## 19. نتیجه

مسیر مقیاس‌پذیری Rasti Service باید تدریجی باشد. پروژه نیاز به بازنویسی ندارد. با چند اصلاح زیرساختی مهم، می‌تواند از مرحله توسعه وارد Production کوچک شود و سپس مرحله‌به‌مرحله برای کاربران بیشتر آماده شود.
