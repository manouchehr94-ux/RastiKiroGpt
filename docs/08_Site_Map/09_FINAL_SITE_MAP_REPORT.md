# ۰۹ — گزارش نهایی نقشه سایت

**تاریخ:** ۱ ژوئیه ۲۰۲۶ (۱۰ تیر ۱۴۰۵)  
**مبنا:** بررسی مستقیم کد — `config/urls.py`، ۲۱ فایل `urls*.py`، فایل‌های view، ۱۹۹+ قالب HTML  
**پروژه:** Rasti SaaS Service Platform — Django 5.1.3

---

## ۱. ساختار کلی سایت

پروژه Rasti یک پلتفرم SaaS با **multi-tenancy مبتنی بر URL** است. ساختار URL به این صورت است:

```
/                           ← بازاریابی عمومی
/login/                     ← ورود یکپارچه (همه نقش‌ها)
/owner-platform/            ← پنل مالک پلتفرم
/admin/                     ← Django Admin (superuser)
/i/<public_code>/           ← لینک کوتاه فاکتور (بدون auth)
/api/auth/                  ← REST API احراز هویت
/api/platform/              ← REST API پلتفرم
/api/<company_code>/        ← REST API tenant
/<company_code>/            ← همه صفحات tenant
  /<code>/admin/            ← پنل مدیر و اپراتور
  /<code>/tech/             ← پنل تکنسین
  /<code>/invoices/         ← فاکتور مشتری و عمومی
  /<code>/payments/         ← پرداخت
  /<code>/request/          ← فرم عمومی درخواست خدمت
```

---

## ۲. آمار کلی

| آیتم | تعداد |
|------|-------|
| URL pattern کل (منحصربه‌فرد) | ۲۳۸ |
| URL عمومی (بدون auth) | ۱۸ |
| URL REST API | ۲۱ |
| URL پنل ادمین/اپراتور | ۹۶ |
| URL پنل تکنسین | ۱۸ |
| URL پلتفرم (مالک) | ۷۰ |
| URL ریدایرکت لگسی | ۷ |
| URL سیستمی | ۸ |
| قالب HTML شناسایی‌شده | ۱۹۹+ |
| قالب منحصربه‌فرد (بدون تکراری) | ≈ ۱۶۸ |
| نقش کاربری | ۵ (+ بازدیدکننده) |
| app Django | ۱۵ |

---

## ۳. سفرهای اصلی کاربر (User Journeys)

### سفر ۱ — درخواست خدمت عمومی (Customer Journey)

```
بازدیدکننده → /<code>/ → /<code>/request/ → پر کردن فرم →
POST → ServiceRequest + Order(PENDING_REVIEW) ایجاد →
ادمین در /<code>/admin/requests/ می‌بیند →
تبدیل به سفارش → /<code>/admin/orders/create/ →
Order(NEW) ایجاد → اختصاص تکنسین → /<code>/admin/orders/<id>/assign/ →
تکنسین در /<code>/tech/orders/available/ می‌بیند →
accept → /<code>/tech/orders/<id>/accept/ → IN_PROGRESS →
اجرای کار → complete → /<code>/tech/orders/<id>/complete/ → DONE →
فاکتور → /<code>/tech/invoices/order/<id>/create/ →
مشتری در /<code>/invoices/<id>/ می‌بیند →
پرداخت → /<code>/invoices/<id>/pay/ → PSP → callback → PAID
```

**مرحله ورود:** صفحه عمومی شرکت  
**مرحله خروج:** رسید پرداخت موفق

---

### سفر ۲ — ورود ادمین و مدیریت روزانه

```
/login/ → POST → /<code>/admin/
→ لیست سفارشات: /<code>/admin/orders/
→ بررسی درخواست‌های لغو
→ اختصاص تکنسین به سفارش‌های NEW
→ بررسی فاکتورها: /<code>/admin/invoices/
→ گزارش مالی: /<code>/admin/financial-reports/summary/
```

---

### سفر ۳ — ورود تکنسین و انجام کار

```
/login/?company=<code> → /<code>/tech/
→ سفارشات موجود: /<code>/tech/orders/available/
→ قبول: /<code>/tech/orders/<id>/accept/ (POST)
→ سفارشات من: /<code>/tech/orders/my/
→ تکمیل: /<code>/tech/orders/<id>/complete/ (POST)
→ صدور فاکتور: /<code>/tech/invoices/order/<id>/create/
```

---

### سفر ۴ — مالک پلتفرم و مدیریت

```
/login/ → /owner-platform/dashboard/
→ شرکت‌ها: /owner-platform/companies/
→ اعتبار پیامک: /owner-platform/sms-billing/
→ KYC پذیرنده: /owner-platform/merchant-profiles/
→ تأیید درخواست KYC: /owner-platform/merchant-profile-change-requests/<id>/
→ پایش پرداخت: /owner-platform/payments/operations/
```

---

## ۴. نقشه دسترسی هر نقش

### بازدیدکننده عمومی
- همه صفحات `/` و `/<code>/`
- فرم درخواست خدمت
- مشاهده فاکتور از لینک عمومی
- بازگشت از PSP

### مشتری (CUSTOMER)
- همه صفحات عمومی
- `/<code>/invoices/` — فاکتورهای خود
- `/<code>/payments/` — تاریخچه پرداخت
- **فاقد داشبورد واقعی** (از Phase 24 حذف شد)

### تکنسین (TECHNICIAN)
- `/<code>/tech/` — داشبورد با آمار
- `/<code>/tech/orders/available/` — سفارشات موجود
- `/<code>/tech/orders/my/` — سفارشات اختصاصی
- `/<code>/tech/invoices/` — فاکتورهای صادرشده
- `/<code>/tech/notifications/` — اعلان‌ها

### اپراتور (COMPANY_STAFF)
- `/<code>/admin/` — داشبورد
- سفارشات (لیست، جزئیات، ایجاد، ویرایش، اختصاص)
- مشتریان (لیست، جزئیات)
- فاکتورها (لیست، جزئیات)
- درخواست‌های عمومی
- اعلان‌ها
- **ندارد:** تنظیمات شرکت، مدیریت تکنسین، گزارش‌های مالی

### مدیر شرکت (COMPANY_ADMIN)
- همه صفحات اپراتور +
- تنظیمات کامل شرکت
- مدیریت تکنسین‌ها و تسویه
- گزارش‌های مالی
- پیامک و ارتباطات
- کیف پول پیامک
- درگاه پرداخت و KYC
- گزارش‌های آنالیز

### مالک پلتفرم (PLATFORM_OWNER)
- `/owner-platform/` — کل پنل پلتفرم
- مدیریت شرکت‌ها، پلن‌ها، اشتراک‌ها
- پیامک پلتفرم و صورت‌حساب
- KYC پذیرندگان
- پایش پرداخت
- پیام‌رسانی داخلی

---

## ۵. مشکلات اصلی ناوبری

### مشکل ۱ — آسیب‌پذیری امنیتی P0-1 (بحرانی)
**فایل:** `apps/tenants/views_admin.py:2125`  
**URL:** `/<code>/admin/settings/operators/`

صفحه مدیریت اپراتورها **هیچ decorator امنیتی** ندارد. هر کاربر احراز هویت‌نشده می‌تواند به این صفحه دسترسی داشته باشد و اپراتور جدید ایجاد کند. همچنین به دلیل منطق ناقص `is_company_admin()` در `operator_access.py`، مدیر شرکت A می‌تواند اپراتورهای شرکت B را مدیریت کند (cross-tenant escalation).

**راه‌حل فوری:**
```python
@require_tenant_role("COMPANY_ADMIN")
def admin_operator_list(request, **kwargs):
```

---

### مشکل ۲ — صفحات بدون لینک در sidebar (Orphan Pages)

صفحات مهم زیر در هیچ sidebar/nav لینک ندارند:
- `/<code>/admin/financial-reports/summary/` و پنج گزارش دیگر
- `/<code>/admin/payments/gateway-reconciliation/`
- `/owner-platform/technician-financial-verifications/`
- `/owner-platform/sms-template-requests/`
- `/owner-platform/password-reset-policy/`

---

### مشکل ۳ — تجربه مشتری ضعیف

پس از login، مشتری به `/<code>/invoices/` هدایت می‌شود اما اگر مستقیم به `/<code>/customer/` برود ریدایرکت به صفحه عمومی می‌شود — نه داشبورد. این رفتار گیج‌کننده است.

---

### مشکل ۴ — قالب‌های تکراری

چهار قالب component در دو مکان موازی وجود دارند:
- `templates/components/*.html`
- `templates/includes/components/*.html`

---

### مشکل ۵ — SMS تکنسین همیشه غیرفعال

کد `if False and send_sms and ...` در `apps/orders/technician_notifications.py:147` باعث می‌شود هیچ SMS برای تکنسین‌ها ارسال نشود حتی اگر تنظیمات فعال باشد.

---

## ۶. مستنداتی که هنوز وجود ندارند

| مستند مورد نیاز | وضعیت |
|----------------|--------|
| نقشه sidebar دقیق ادمین (HTML کامل) | نیازمند بررسی بیشتر |
| دقیقاً کدام view‌های SMS نقش COMPANY_STAFF دارند | نیازمند بررسی بیشتر |
| قالب‌های `reports/views.py` | نیازمند بررسی بیشتر |
| URL ناوبری breadcrumb در صفحات داخلی | نیازمند بررسی بیشتر |
| view‌های `payouts/views.py` برای statement | نیازمند بررسی بیشتر |

---

## ۷. گام‌های پیشنهادی بعدی

### اولویت اول — امنیتی
1. **اضافه کردن `@require_tenant_role("COMPANY_ADMIN")` به `admin_operator_list`** — در `apps/tenants/views_admin.py:2125`
2. **حذف decorator تکراری از `admin_operator_create`** — در `apps/tenants/views_admin.py:1964`

### اولویت دوم — ناوبری
3. **اضافه کردن لینک گزارش‌های مالی به sidebar ادمین**
4. **اضافه کردن لینک‌های orphan به sidebar پلتفرم** (`technician-financial-verifications`، `sms-template-requests`، `password-reset-policy`)

### اولویت سوم — تجربه کاربری
5. **رفع تجربه مشتری**: بازطراحی `/<code>/customer/` به یک داشبورد واقعی
6. **ادغام قالب‌های تکراری** در `templates/includes/components/` و `templates/components/`
7. **رفع `if False` در SMS تکنسین** در `technician_notifications.py:147`

### اولویت چهارم — مستندسازی
8. **مستندسازی sidebar view هر قالب** — به خصوص برای اپراتور
9. **افزودن breadcrumb به صفحات عمیق** (statement، financial reports)

---

## ۸. نتیجه‌گیری

پروژه Rasti یک ساختار URL منسجم و منطقی دارد. تفکیک `/<code>/admin/` ، `/<code>/tech/` و `/<code>/invoices/` کاملاً حرفه‌ای است. استفاده از URL-based tenancy با middleware بدون نقص عمده‌ای کار می‌کند.

**نقاط قوت:**
- تفکیک نقش‌ها در URL — قابل درک و مقیاس‌پذیر
- پشتیبانی کامل از ریدایرکت‌های لگسی
- REST API جداگانه از UI
- لینک کوتاه فاکتور (`/i/<code>/`) برای اشتراک‌گذاری آسان

**نقاط ضعیف:**
- یک آسیب‌پذیری بحرانی در دسترسی به اپراتورها
- چندین صفحه مهم بدون لینک در ناوبری (orphan)
- تجربه مشتری پس از Phase 24 ناقص
- قالب‌های تکراری که باعث سردرگمی توسعه می‌شوند
- SMS تکنسین با `if False` کاملاً غیرفعال

**جمع‌بندی:** با رفع P0-1 و اضافه کردن لینک‌های orphan به sidebar، ساختار ناوبری به یک سطح قابل قبول برای production می‌رسد. سایر مشکلات می‌توانند در اسپرینت‌های بعدی رفع شوند.
