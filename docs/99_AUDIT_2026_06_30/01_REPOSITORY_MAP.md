# ۰۱ — نقشه مخزن کد و توضیح ماژول‌ها

**تاریخ:** ۳۰ ژوئن ۲۰۲۶  
**منبع:** بررسی مستقیم ساختار دایرکتوری و خواندن فایل‌های کلیدی

---

## ساختار سطح اول

```
D:\SaaSprojectService\Rasti chekFinal 10 tir\
├── apps/                    ← ۱۵ اپلیکیشن Django
├── config/                  ← تنظیمات، URLs، WSGI
├── docs/                    ← مستندات کامل
├── templates/               ← ۱۹۹ template HTML
├── static/                  ← CSS، JS، فونت‌ها
├── media/                   ← فایل‌های آپلود شده
├── tests/                   ← ۸۸ فایل تست (همه در یک پوشه)
├── scripts/                 ← اسکریپت‌های کمکی
├── seed/                    ← داده‌های اولیه
├── manage.py
├── requirements.txt
└── .env.example
```

---

## اپلیکیشن‌های Django (apps/)

### ۱. `apps.common` — پایه مشترک
- **مدل‌ها:** `TimeStampedModel`, `CompanyOwnedModel`
- **نقش:** base abstract model که همه مدل‌های مستأجر از آن ارث می‌برند
- **فایل‌های کلیدی:** `models.py`, `jalali.py`, `phone_utils.py`
- **وضعیت:** ✅ فعال، پایه معماری

### ۲. `apps.platform_core` — هسته پلتفرم
- **مدل‌ها:** `Plan`, `Subscription`, `CompanySMSWallet`, `PlatformSiteSettings`, `CompanyMerchantProfile`, `CompanyPaymentSettings`, `CompanyMerchantProfileChangeRequest`, `PlatformSMSProviderSetting`, `PlatformSMSOutbox`, `PlatformBillingInvoice`
- **نقش:** مدیریت پلتفرم SaaS (اشتراک، کردیت SMS، درگاه پلتفرم، تنظیمات سایت)
- **فایل‌های کلیدی:** `models.py`, `services_communication.py` (deprecated), `services_sms_credit.py`, `services_payment_gateway.py`
- **وضعیت:** ✅ فعال. ⚠️ `services_communication.py` به‌طور رسمی deprecated است

### ۳. `apps.tenants` — مستأجران (شرکت‌ها)
- **مدل‌ها:** `Company`, `CompanySettings`, `CompanyPage`, `CompanyService`, `CompanyServiceCategory`, `CompanyServiceSubCategory`, `CompanyFinancialPolicy`, `CompanyPaymentSettings`, `CompanyMerchantProfile`, `OrderCustomField`, `ServiceRequest`
- **نقش:** مدیریت مستأجران، صفحه عمومی، دسته‌بندی خدمات، فرم درخواست عمومی
- **فایل‌های کلیدی:** `middleware.py` (TenantMiddleware), `models.py`, `services.py`, `views_admin.py`
- **وضعیت:** ✅ فعال، هسته چند‌مستأجری

### ۴. `apps.accounts` — کاربران و نقش‌ها
- **مدل‌ها:** `CompanyUser` (AUTH_USER_MODEL), `Technician`, `TechnicianSkill`, `TechnicianCategorySkill`, `Customer`, `OperatorPermission`, `RegistrationOTP`, `PasswordResetOTP`, `PasswordResetSMSBillingPolicy`
- **نقش:** مدل کاربر سفارشی، نقش‌ها، پروفایل تکنسین، مشتریان، مجوزها
- **فایل‌های کلیدی:** `models.py`, `permissions.py`, `operator_access.py`
- **وضعیت:** ✅ فعال. ⚠️ ۱ نقص امنیتی در views.py

### ۵. `apps.orders` — سفارشات (هسته اصلی)
- **مدل‌ها:** `Order`, `OrderItemDefinition`, `OrderItemValue`, `OrderStatusLog`
- **نقش:** چرخه عمر کامل سفارش
- **فایل‌های کلیدی:** `models.py`, `services.py`, `selectors.py`, `eligibility.py`, `cancel_review_service.py`, `recycle_service.py`, `assignment_events.py`, `order_events.py`, `cancel_request_events.py`
- **وضعیت:** ✅ کامل، مستحکم

### ۶. `apps.invoices` — صورتحساب
- **مدل‌ها:** `Invoice`, `InvoiceItem`, `InvoiceCancellationRequest`, `InvoiceCounter`
- **نقش:** ایجاد، صدور، پرداخت، لغو صورتحساب
- **فایل‌های کلیدی:** `models.py`, `services.py`, `services_settlement.py`, `services_wage.py`, `services_cancel_request.py`
- **وضعیت:** ✅ کامل، محافظت‌شده

### ۷. `apps.payments` — پرداخت‌ها
- **مدل‌ها:** `PaymentGateway`, `Payment`, `PaymentAttempt`
- **نقش:** شروع، callback، تأیید، انقضا، reconciliation پرداخت
- **فایل‌های کلیدی:** `models.py`, `services.py`, `services_expiration.py`, `services_reconciliation.py`
- **وضعیت:** ✅ کامل. ⚠️ ارائه‌دهندگان واقعی PSP (ZarinPal، IDPay) stub هستند

### ۸. `apps.payouts` — تسویه مالی تکنسین
- **مدل‌ها:** `TechnicianLedgerEntry`, `PaymentSplitSnapshot`, `CompanyPlatformFeeEntry`, `FinancialBackfillTask`, `TechnicianServiceRate`
- **نقش:** دفتر‌کل تکنسین، تسویه مستقیم، کارمزد پلتفرم، صورت‌حساب مالی
- **فایل‌های کلیدی:** `models.py`, `services.py`, `services_statement.py`, `services_split.py`, `services_direct_settlement.py`, `services_backfill.py`, `services_order_wages.py`
- **وضعیت:** ✅ کامل، دفتر‌کل تغییرناپذیر

### ۹. `apps.billing` — صورتحساب اشتراک SaaS
- **مدل‌ها:** `BillingRecord`
- **نقش:** صورتحساب از پلتفرم به شرکت (نه از مشتری به شرکت)
- **فایل‌های کلیدی:** `models.py`, `services.py`
- **وضعیت:** ❌ Stub — فقط ۶ خط کد، بدون منطق تجاری

### ۱۰. `apps.notifications` — اطلاع‌رسانی
- **مدل‌ها:** `Notification`, `NotificationSetting`, `NotificationEvent`
- **نقش:** کاتالوگ رویدادها، dispatch، in-app، پشتیبانی از SMS
- **فایل‌های کلیدی:** `event_catalog.py`, `dispatchers.py`, `message_builders.py`, `recipients.py`, `services_events.py`, `signals.py`, `sync.py`
- **وضعیت:** ✅ فعال. ⚠️ ۱۹ رویداد trigger نمی‌شوند

### ۱۱. `apps.sms` — پیامک
- **مدل‌ها:** `SMSTemplate`, `SMSOutbox`, `SMSInbox`, `SMSMasterTemplate`, `SMSTemplateChangeRequest`, `SMSMasterTemplateProviderConfig`
- **نقش:** ارسال، دریافت، صف، template، provisioning
- **فایل‌های کلیدی:** `models.py`, `models_master.py`, `models_inbox.py`, `services.py`, `template_resolver.py`, `sms_footer.py`, `provisioning.py`, `default_template_texts.py`
- **وضعیت:** ✅ فعال. ⚠️ ارائه‌دهنده MeliPayamak simple-text send پیاده‌سازی نشده

### ۱۲. `apps.reports` — گزارشات و کمپین تخفیف
- **مدل‌ها:** `DiscountCampaign`, `DiscountCode`, `DiscountCampaignRecipient`, `DiscountCampaignAllowedPhone`
- **نقش:** گزارش مالی، کمپین تخفیف، کدهای تخفیف
- **فایل‌های کلیدی:** `models.py`, `selectors.py`, `services.py`, `discount_services.py`
- **وضعیت:** ✅ فعال

### ۱۳. `apps.dashboard` — داشبورد نقش‌محور
- **مدل‌ها:** ندارد (فقط selectors و views)
- **نقش:** داشبورد مدیر شرکت، تکنسین، مشتری
- **فایل‌های کلیدی:** `views.py`, `selectors.py`, `urls_technician.py`, `urls_customer.py`
- **وضعیت:** ✅ فعال

### ۱۴. `apps.api` — REST API
- **مدل‌ها:** ندارد
- **نقش:** API برای مشتری، درخواست خدمت، احراز هویت JWT
- **فایل‌های کلیدی:** `auth_views.py`, `views.py`, `serializers.py`, `permissions.py`
- **وضعیت:** ⚠️ پیاده‌سازی جزئی. باگ Customer.name. JWT blacklist شکسته

### ۱۵. `apps.public` — صفحات عمومی
- **مدل‌ها:** ندارد
- **نقش:** صفحه اصلی، pricing، ثبت‌نام شرکت، OTP
- **فایل‌های کلیدی:** `views.py` (ثبت‌نام شرکت), `api_views.py` (بررسی username/code), `services.py`
- **وضعیت:** ✅ فعال

---

## پیکربندی Django (config/)

| فایل | نقش | وضعیت |
|---|---|---|
| `settings/base.py` | تنظیمات مشترک | ✅ با ۲ نقص (ALLOWED_HOSTS، CACHES) |
| `settings/local.py` | SQLite، DEBUG=True | ✅ محلی |
| `settings/production.py` | PostgreSQL، DEBUG=False، security headers | ✅ با ۱ نقص (ALLOWED_HOSTS default) |
| `urls.py` | مسیریابی اصلی | ✅ با احتمال تعارض api namespace |
| `wsgi.py` | رابط WSGI | ✅ |

---

## پوشه تست‌ها (tests/)

- **تعداد کل:** ۸۸ فایل تست، ۱۲۴۲ تست، تمام pass
- **سبک نام‌گذاری:** `test_p[شماره]_*.py` و `test_task[شماره]_*.py` — نشان‌دهنده تست‌های وابسته به patch/task
- **هیچ تستی در داخل اپ‌ها نیست** — همه در `tests/` ریشه

---

## پوشه templates (templates/)

- **۱۹۹ فایل HTML**
- **زنجیره ارث:** `base.html → layouts/{dashboard,technician,auth,public,error,invoice_print}.html → templates/*/`
- **RTL/فارسی:** `<html lang="fa" dir="rtl">` در `base.html`
- **فونت:** Vazirmatn از `static/fonts/`
- **مشکل اصلی:** وجود `base_dashboard.html` legacy (تکراری با `layouts/dashboard.html`)

---

## فایل‌های ریشه پروژه

| فایل | نقش |
|---|---|
| `manage.py` | Django CLI |
| `requirements.txt` | وابستگی‌های Python |
| `.env.example` | نمونه متغیرهای محیطی |
| `db.sqlite3` | DB محلی (SQLite) |
| `db_before_*.sqlite3` | اسنپ‌شات‌های قبل از تست (نباید در git باشند) |
| `docs.zip` | آرشیو مستندات (نباید در git باشد) |
| `MANIFEST.md` | نیازمند بررسی بیشتر |
