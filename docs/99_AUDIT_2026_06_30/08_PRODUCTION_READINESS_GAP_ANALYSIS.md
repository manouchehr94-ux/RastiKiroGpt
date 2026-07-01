# ۰۸ — تحلیل شکاف آمادگی تولید

**تاریخ:** ۳۰ ژوئن ۲۰۲۶

---

## ارزیابی کلی آمادگی تولید

**امتیاز آمادگی فعلی:** ۶.۵/۱۰  
**شرط ورود به تولید:** رفع ۷ مشکل حیاتی

---

## بلوکرهای حیاتی (P0 — باید پیش از تولید رفع شوند)

### P0-1: نقص امنیتی — view مدیریت اپراتورها بدون احراز نقش
- **فایل:** `apps/tenants/views_admin.py:2125`
- **مشکل:** `admin_operator_list` که ایجاد/ویرایش/حذف اپراتور را مدیریت می‌کند هیچ `@require_tenant_role` ندارد
- **خطر:** هر کاربر login‌شده می‌تواند اپراتور بسازد
- **زمان رفع:** ۳۰ دقیقه
- **راه‌حل:** اضافه کردن `@require_tenant_role("COMPANY_ADMIN")` به view

### P0-2: JWT Logout بی‌اثر است
- **فایل:** `config/settings/base.py` + `apps/api/auth_views.py:163`
- **مشکل:** `rest_framework_simplejwt.token_blacklist` در INSTALLED_APPS نیست
- **خطر:** پس از logout، توکن‌های JWT همچنان معتبر هستند
- **زمان رفع:** ۱ ساعت
- **راه‌حل:** اضافه به INSTALLED_APPS + اجرای migration

### P0-3: رمز عبور هاردکد در کد تولید
- **فایل:** `apps/accounts/views.py:58`
- **مشکل:** `user.check_password("123456")` — رشته رمز عبور پیش‌فرض در کد تولید
- **خطر:** اطلاعات امنیتی لو می‌رود
- **زمان رفع:** ۱۵ دقیقه
- **راه‌حل:** حذف این شرط، اتکا به `user.must_change_password` flag

### P0-4: ALLOWED_HOSTS ناامن در base.py
- **فایل:** `config/settings/base.py:19-20`
- **مشکل:** `ALLOWED_HOSTS = ["*"]` هاردکد؛ خط env-var کامنت شده
- **خطر:** اگر production.py مشکل داشته باشد، host header injection ممکن است
- **زمان رفع:** ۱۰ دقیقه
- **راه‌حل:** uncomment خط env-var و حذف `["*"]` از base.py

### P0-5: باگ Runtime در API مشتریان
- **فایل:** `apps/api/views.py:311,367`
- **مشکل:** `Customer.objects.create(name=...)` — فیلد `name` وجود ندارد
- **خطر:** هر درخواست POST به `/api/<code>/customers/` با TypeError خراب می‌شود
- **زمان رفع:** ۳۰ دقیقه
- **راه‌حل:** جایگزینی `name` با `first_name`/`last_name`

### P0-6: SMS تکنسین برای سفارش جدید دائماً غیرفعال
- **فایل:** `apps/orders/technician_notifications.py:147`
- **مشکل:** `if False and send_sms and ...` — SMS ارسال نمی‌شود
- **خطر:** تکنسین‌ها پیامک سفارش جدید دریافت نمی‌کنند صرف‌نظر از تنظیمات
- **زمان رفع:** ۳۰ دقیقه (تصمیم درباره حذف یا فعال‌سازی)

### P0-7: ارائه‌دهندگان PSP واقعی پیاده‌سازی نشده‌اند
- **فایل:** `apps/payments/providers/`
- **مشکل:** فقط `fake.py` کامل است. ZarinPal، IDPay، NextPay stub هستند
- **خطر:** پرداخت آنلاین واقعی کار نمی‌کند
- **زمان رفع:** ۵-۱۰ روز (وابسته به PSP)

---

## مشکلات مهم (P1 — توصیه می‌شود پیش از تولید رفع شوند)

### P1-1: هیچ تست isolation چند‌مستأجری برای order/invoice
- خطر نشت داده بین شرکت‌ها — باید تأیید شود

### P1-2: Cache backend تعریف نشده
- Throttle در multi-worker بی‌اثر است
- راه‌حل: پیکربندی Redis یا Memcached

### P1-3: ۱۹ رویداد اطلاع‌رسانی trigger نمی‌شوند
- مهم‌ترین: `order_cancelled`, `order_cancel_requested_customer`, `order_rescheduled`

### P1-4: SMS پلتفرم (اشتراک، هشدار کردیت) از متن template استفاده نمی‌کند
- **فایل:** `notifications/dispatchers.py:109-118`
- پیامک‌های مهم پلتفرم همیشه متن fallback ساده ارسال می‌کنند

### P1-5: Footer SMS هرگز اضافه نمی‌شود
- `sms_footer.py` تعریف شده اما `ensure_sms_footer()` در pipeline فراخوانی نمی‌شود

### P1-6: Subscription limits هرگز enforce نمی‌شوند
- Plan.max_users، max_technicians در DB وجود دارند اما هرگز بررسی نمی‌شوند

### P1-7: `balance_after` race condition در اولین ورودی لجر
- **خطر:** دو نوشتن همزمان در لجر خالی تکنسین می‌توانند balance_after نادرست ایجاد کنند
- **وضعیت:** RISK-F1 در FINANCIAL_CORE_FINAL_AUDIT شناسایی شده

---

## شکاف‌های مهم (P2 — قبل از scale)

| مشکل | تأثیر | اقدام |
|---|---|---|
| هیچ Celery/Task Queue | وظایف پس‌زمینه در thread HTTP | نصب و پیکربندی Celery |
| Company lookup بدون cache | هر request یک DB query | پیکربندی Redis + caching |
| هیچ Sentry یا error monitoring | خطاها دیده نمی‌شوند | نصب sentry-sdk |
| هیچ health check endpoint | نمی‌توان load balancer تنظیم کرد | `/health/` وجود دارد — بررسی شود |
| هیچ rate limiting | brute force و DoS ممکن است | نصب django-ratelimit |
| API keys در DB plaintext | اگر DB leak شود، کلیدها لو می‌روند | رمزنگاری در سطح DB |
| SQLite vs PostgreSQL در تست‌ها | race condition‌ها local تست نمی‌شوند | تنظیم PostgreSQL در test pipeline |
| هیچ staging environment | تست روی تولید | راه‌اندازی staging |
| WeasyPrint PDF synchronous | تأخیر در HTTP cycle | async task برای PDF |

---

## وضعیت فعلی ویژگی‌های کلیدی

| ویژگی | وضعیت | یادداشت |
|---|---|---|
| ثبت‌نام شرکت | ✅ کامل | OTP، انتظار بازبینی پلتفرم |
| چرخه عمر سفارش | ✅ کامل | همه ۷ وضعیت، همه انتقال‌ها |
| صورتحساب | ✅ کامل | DRAFT/ISSUED/PAID، محافظت |
| پرداخت نقد | ✅ کامل | از طریق تکنسین |
| پرداخت آنلاین | ❌ ناقص | PSP providers stub هستند |
| دفتر‌کل تکنسین | ✅ کامل | تغییرناپذیر، idempotent |
| اجرت تکنسین | ✅ کامل | بر اساس آیتم و درصد |
| داشبورد ادمین | ✅ کامل | |
| داشبورد تکنسین | ✅ کامل | |
| پنل مشتری | ✅ کامل | |
| پیامک OTP | ✅ کامل | فقط MeliPayamak |
| پیامک سفارش | ⚠️ جزئی | ۱۹ رویداد trigger نمی‌شوند |
| تنظیمات ارتباطی | ✅ کامل | ماتریس کامل |
| KYC تکنسین | ✅ کامل | |
| فرم عمومی مشتری | ✅ کامل | |
| کمپین تخفیف | ✅ کامل | |
| اشتراک SaaS billing | ❌ stub | فقط `BillingRecord` خالی |
| Multi-tenant isolation | ✅ کامل در کد | ❌ تست‌های isolation ندارد |

---

## چک‌لیست آمادگی تولید

### ✅ انجام شده
- [x] `manage.py check` بدون خطا
- [x] ۱۲۴۲ تست pass
- [x] معماری چند‌مستأجری مستحکم
- [x] دفتر‌کل مالی ایمن
- [x] Security headers در production.py
- [x] PostgreSQL در تولید
- [x] خطاهای مهم با try/except کنترل می‌شوند

### ❌ هنوز انجام نشده (P0)
- [ ] رفع نقص امنیتی `admin_operator_list`
- [ ] رفع JWT blacklist
- [ ] حذف `check_password("123456")`
- [ ] اصلاح ALLOWED_HOSTS
- [ ] رفع باگ `Customer.name`
- [ ] تصمیم درباره SMS تکنسین
- [ ] پیاده‌سازی PSP واقعی

### ⚠️ P1 (قبل از scale)
- [ ] Redis cache
- [ ] تست isolation چند‌مستأجری
- [ ] Celery + task queue
- [ ] Error monitoring (Sentry)
- [ ] Staging environment
