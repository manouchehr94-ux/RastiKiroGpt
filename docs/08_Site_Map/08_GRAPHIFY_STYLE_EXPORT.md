# ۰۸ — خروجی گراف‌مانند (Graphify Style)

**هدف:** ساختار node/edge که می‌تواند در ابزارهای visual مانند Cytoscape، D3.js، Gephi یا Mermaid استفاده شود  
**تاریخ:** ۱ ژوئیه ۲۰۲۶

---

## بخش ۱ — جدول Node‌ها

### Node Types
- `PUBLIC` — صفحه عمومی (بدون auth)
- `AUTH` — صفحه احراز هویت
- `ADMIN` — پنل مدیر/اپراتور
- `TECH` — پنل تکنسین
- `PLATFORM` — پنل مالک پلتفرم
- `CUSTOMER` — منطقه مشتری
- `API` — endpoint استاندارد API
- `SYSTEM` — صفحه سیستمی
- `REDIRECT` — فقط redirect
- `ACTION` — endpoint بدون view صفحه (POST action)

---

### Node Table — Public & Auth

| id | label | type | role | app | route | template |
|----|-------|------|------|-----|-------|----------|
| N001 | صفحه اصلی | PUBLIC | همه | public | `/` | `public/home.html` |
| N002 | ویژگی‌ها | PUBLIC | همه | public | `/features/` | `public/features.html` |
| N003 | قیمت‌گذاری | PUBLIC | همه | public | `/pricing/` | `public/pricing.html` |
| N004 | درباره ما | PUBLIC | همه | public | `/about/` | `public/about.html` |
| N005 | تماس | PUBLIC | همه | public | `/contact/` | `public/contact.html` |
| N006 | ثبت‌نام شرکت | AUTH | همه | public | `/register/` | `public/register.html` |
| N007 | تأیید OTP | AUTH | همه | public | `/register/verify/` | `public/register_verify.html` |
| N008 | موفقیت ثبت‌نام | AUTH | همه | public | `/register/success/` | `public/register_success.html` |
| N009 | ورود یکپارچه | AUTH | همه | accounts | `/login/` | `accounts/unified_login.html` |
| N010 | خروج | ACTION | authenticated | accounts | `/logout/` | — |
| N011 | تغییر رمز اجباری | AUTH | authenticated | accounts | `/account/change-password-required/` | `accounts/change_password_required.html` |
| N012 | بازیابی رمز — فرم | AUTH | همه | accounts | `/password-reset/` | `accounts/password_reset_form.html` |
| N013 | بازیابی رمز — انتخاب | AUTH | همه | accounts | `/password-reset/select/` | `accounts/password_reset_select.html` |
| N014 | بازیابی رمز — OTP | AUTH | همه | accounts | `/password-reset/verify/` | `accounts/password_reset_otp.html` |
| N015 | بازیابی رمز — تأیید | AUTH | همه | accounts | `/password-reset/confirm/` | `accounts/password_reset_confirm.html` |

---

### Node Table — Tenant Public

| id | label | type | role | app | route | template |
|----|-------|------|------|-----|-------|----------|
| N016 | صفحه عمومی شرکت | PUBLIC | همه | tenants | `/<code>/` | `tenants/home.html` |
| N017 | فرم درخواست خدمت | PUBLIC | همه | tenants | `/<code>/request/` | `tenants/request_form.html` |
| N018 | پیگیری درخواست | PUBLIC | همه | tenants | `/<code>/request/status/` | `tenants/request_status.html` |
| N019 | فاکتور عمومی | PUBLIC | همه | invoices | `/<code>/invoices/public/<code>/` | `invoices/detail.html` |
| N020 | لینک کوتاه فاکتور | PUBLIC | همه | invoices | `/i/<public_code>/` | `invoices/detail.html` |
| N021 | پرینت فاکتور | PUBLIC | همه | invoices | `/<code>/invoices/public/<code>/print/` | `invoices/print.html` |
| N022 | بازگشت از PSP | PUBLIC | همه | payments | `/<code>/payments/callback/` | `payments/result.html` |

---

### Node Table — Admin Panel

| id | label | type | role | app | route | template |
|----|-------|------|------|-----|-------|----------|
| N100 | داشبورد ادمین | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | dashboard | `/<code>/admin/` | `dashboard/home.html` |
| N101 | لیست سفارشات | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/orders/` | `tenants/admin_orders.html` |
| N102 | ایجاد سفارش | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/orders/create/` | `tenants/admin_order_create.html` |
| N103 | جزئیات سفارش | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/orders/<id>/` | `tenants/admin_order_detail.html` |
| N104 | ویرایش سفارش | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/orders/<id>/edit/` | `tenants/admin_order_edit.html` |
| N105 | اختصاص تکنسین | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/orders/<id>/assign/` | `tenants/admin_order_assign.html` |
| N106 | درخواست‌های عمومی | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/requests/` | `tenants/admin_requests.html` |
| N107 | لیست مشتریان | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/customers/` | `tenants/admin_customers.html` |
| N108 | جزئیات مشتری | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/customers/<id>/` | `tenants/admin_customer_detail.html` |
| N109 | لیست فاکتورها (ادمین) | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/invoices/` | `tenants/admin_invoices.html` |
| N110 | جزئیات فاکتور (ادمین) | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | tenants | `/<code>/admin/invoices/<id>/` | `tenants/admin_invoice_detail.html` |
| N111 | لیست تکنسین‌ها | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/technicians/` | `tenants/admin_technicians.html` |
| N112 | دفتر کل تکنسین | ADMIN | COMPANY_ADMIN | payouts | `/<code>/admin/technicians/<id>/ledger/` | — |
| N113 | صورتحساب تکنسین | ADMIN | COMPANY_ADMIN | payouts | `/<code>/admin/technicians/<id>/statement/` | — |
| N114 | تنظیمات شرکت | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/settings/` | `tenants/admin_company_settings.html` |
| N115 | مدیریت اپراتورها | ADMIN | ⚠️ P0-1 | tenants | `/<code>/admin/settings/operators/` | `tenants/admin_operator_list.html` |
| N116 | گزارش خلاصه مالی | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/financial-reports/summary/` | `tenants/financial_reports/summary.html` |
| N117 | تفکیک تکنسین | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/financial-reports/technicians/` | `tenants/financial_reports/technician_breakdown.html` |
| N118 | تسویه فاکتورها | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/financial-reports/invoices/` | `tenants/financial_reports/invoice_settlement_detail.html` |
| N119 | کنترل نقدی | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/financial-reports/cash-control/` | `tenants/financial_reports/cash_control.html` |
| N120 | کارمزد پلتفرم | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/financial-reports/platform-fees/` | `tenants/financial_reports/platform_fee_report.html` |
| N121 | حسابرسی مالی | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/financial-reports/audit/` | `tenants/financial_reports/audit_report.html` |
| N122 | عملیات پرداخت | ADMIN | COMPANY_ADMIN | payments | `/<code>/admin/payments/operations/` | `payments/operations_company.html` |
| N123 | تسهیم پرداخت | ADMIN | COMPANY_ADMIN | payouts | `/<code>/admin/payments/split-snapshots/` | `payouts/split_snapshot_list.html` |
| N124 | پیامک صندوق خروجی | ADMIN | COMPANY_ADMIN | sms | `/<code>/admin/sms/outbox/` | — |
| N125 | قالب‌های پیامک | ADMIN | COMPANY_ADMIN | sms | `/<code>/admin/sms/templates/` | — |
| N126 | کیف پول پیامک | ADMIN | COMPANY_ADMIN | platform_core | `/<code>/admin/sms-credit/` | `tenants/admin_sms_credit.html` |
| N127 | تنظیمات ارتباطات | ADMIN | COMPANY_ADMIN | platform_core | `/<code>/admin/communication-settings/` | `tenants/admin_comm_settings.html` |
| N128 | اعلان‌های ادمین | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | notifications | `/<code>/admin/notifications/` | — |
| N129 | برندینگ | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/branding/` | `tenants/admin_branding.html` |
| N130 | داده‌های پایه | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/base-data/` | `tenants/admin_base_data.html` |
| N131 | بخش‌بندی مشتری | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | reports | `/<code>/admin/reports/customer-segments/` | — |
| N132 | کمپین تخفیف | ADMIN | COMPANY_ADMIN, COMPANY_STAFF | reports | `/<code>/admin/reports/discount-campaigns/` | — |
| N133 | درگاه پرداخت (ادمین) | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/payment-gateway/` | `tenants/admin_payment_gateway.html` |
| N134 | پروفایل KYC | ADMIN | COMPANY_ADMIN | tenants | `/<code>/admin/payment/merchant-profile/` | `tenants/merchant_profile.html` |

---

### Node Table — Technician Panel

| id | label | type | role | app | route | template |
|----|-------|------|------|-----|-------|----------|
| N200 | داشبورد تکنسین | TECH | TECHNICIAN | dashboard | `/<code>/tech/` | `dashboard/technician_home.html` |
| N201 | سفارشات موجود | TECH | TECHNICIAN | orders | `/<code>/tech/orders/available/` | `orders/technician_available.html` |
| N202 | سفارشات من | TECH | TECHNICIAN | orders | `/<code>/tech/orders/my/` | `orders/technician_my_orders.html` |
| N203 | جزئیات سفارش | TECH | TECHNICIAN | orders | `/<code>/tech/orders/<id>/` | `orders/detail.html` |
| N204 | لیست فاکتورهای تکنسین | TECH | TECHNICIAN | invoices | `/<code>/tech/invoices/` | `orders/technician_invoices.html` |
| N205 | ایجاد فاکتور تکنسین | TECH | TECHNICIAN | invoices | `/<code>/tech/invoices/order/<id>/create/` | `orders/technician_invoice_create.html` |
| N206 | جزئیات فاکتور تکنسین | TECH | TECHNICIAN | invoices | `/<code>/tech/invoices/<id>/` | `tenants/technician_invoice_detail.html` |
| N207 | اعلان‌های تکنسین | TECH | TECHNICIAN | notifications | `/<code>/tech/notifications/` | — |

---

### Node Table — Customer

| id | label | type | role | app | route | template |
|----|-------|------|------|-----|-------|----------|
| N300 | لیست فاکتورهای مشتری | CUSTOMER | authenticated | invoices | `/<code>/invoices/` | `invoices/list.html` |
| N301 | جزئیات فاکتور مشتری | CUSTOMER | authenticated | invoices | `/<code>/invoices/<id>/` | `invoices/detail.html` |
| N302 | پرداخت فاکتور | CUSTOMER | authenticated | invoices | `/<code>/invoices/<id>/pay/` | `payments/invoice_checkout.html` |
| N303 | لیست پرداخت‌ها | CUSTOMER | authenticated | payments | `/<code>/payments/` | `payments/list.html` |

---

### Node Table — Platform Owner

| id | label | type | role | app | route | template |
|----|-------|------|------|-----|-------|----------|
| N400 | داشبورد پلتفرم | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/dashboard/` | `platform_core/dashboard.html` |
| N401 | گزارش‌ها | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/reports/` | `platform_core/reports.html` |
| N402 | لیست شرکت‌ها | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/companies/` | `platform_core/company_list.html` |
| N403 | جزئیات شرکت | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/companies/<id>/` | `platform_core/company_detail.html` |
| N404 | پلن‌ها | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/plans/` | `platform_core/plan_list.html` |
| N405 | اشتراک‌ها | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/subscriptions/` | — |
| N406 | اعتبار پیامک | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/sms-billing/` | `platform_core/sms_billing/index.html` |
| N407 | شرکت‌ها (SMS billing) | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/sms-billing/companies/` | `platform_core/sms_billing/companies.html` |
| N408 | فاکتورهای پیامک | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/sms-billing/invoices/` | `platform_core/sms_billing/invoices.html` |
| N409 | پیامک پلتفرم | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/platform-sms/` | `platform_core/platform_sms/index.html` |
| N410 | قالب‌های پیامکی | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/platform-sms/templates/` | `platform_core/platform_sms/templates.html` |
| N411 | ارائه‌دهنده SMS | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/platform-sms/provider/` | `platform_core/platform_sms/provider.html` |
| N412 | صندوق خروجی پیامک | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/platform-sms/outbox/` | `platform_core/platform_sms/outbox.html` |
| N413 | پیام‌های داخلی | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/messages/inbox/` | `platform_core/messages/inbox.html` |
| N414 | درگاه پرداخت | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/payment-gateways/settings/` | `platform_core/payment_gateways/settings.html` |
| N415 | عملیات پرداخت پلتفرم | PLATFORM | PLATFORM_OWNER | payments | `/owner-platform/payments/operations/` | `payments/operations_platform.html` |
| N416 | تسهیم پرداخت | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/payment-split-snapshots/` | `payouts/split_snapshot_list.html` |
| N417 | KYC پذیرندگان | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/merchant-profiles/` | `platform_core/merchant_profile_list.html` |
| N418 | درخواست‌های KYC | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/merchant-profile-change-requests/` | `platform_core/merchant_profile_change_request_list.html` |
| N419 | قالب‌های ارتباطی | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/communication-templates/` | `platform_core/comm_templates/list.html` |
| N420 | سیاست بازیابی رمز | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/password-reset-policy/` | `platform_core/password_reset_policy/list.html` |
| N421 | تأیید مالی تکنسین | PLATFORM | PLATFORM_OWNER | platform_core | `/owner-platform/technician-financial-verifications/` | — |

---

### Node Table — System & API

| id | label | type | role | app | route |
|----|-------|------|------|-----|-------|
| N500 | سلامت سرور | SYSTEM | — | platform_core | `/health/` |
| N501 | سلامت دیتابیس | SYSTEM | — | platform_core | `/health/db/` |
| N502 | Django Admin | SYSTEM | superuser | django.admin | `/admin/` |
| N600 | API ورود | API | همه | api | `/api/auth/login/` |
| N601 | API خروج | API | authenticated | api | `/api/auth/logout/` |
| N602 | API من | API | authenticated | api | `/api/auth/me/` |
| N603 | API سفارشات | API | tenant roles | api | `/api/<code>/orders/` |
| N604 | API فاکتورها | API | tenant roles | api | `/api/<code>/invoices/` |
| N605 | API مشتریان | API | tenant roles | api | `/api/<code>/customers/` |
| N606 | API داشبورد | API | tenant roles | api | `/api/<code>/dashboard/` |

---

## بخش ۲ — جدول Edge‌ها

### Edge Types
- `NAVIGATE` — کاربر از صفحه A به B می‌رود
- `REDIRECT` — سرور redirect می‌کند (301/302)
- `POST` — action form submission
- `INCLUDE` — یک template دیگری را include می‌کند
- `REQUIRE_AUTH` — نیاز به احراز هویت
- `REQUIRE_ROLE` — نیاز به نقش خاص
- `LINK` — لینک در sidebar/nav

---

### Edge Table — Auth Flow

| from | to | relationship | reason |
|------|----|-------------|--------|
| N001 | N009 | NAVIGATE | دکمه ورود در header |
| N001 | N006 | NAVIGATE | دکمه ثبت‌نام |
| N006 | N007 | REDIRECT | POST موفق → verify |
| N007 | N008 | REDIRECT | OTP تأیید شد |
| N009 | N100 | REDIRECT | COMPANY_ADMIN/STAFF login |
| N009 | N200 | REDIRECT | TECHNICIAN login |
| N009 | N300 | REDIRECT | CUSTOMER login |
| N009 | N400 | REDIRECT | PLATFORM_OWNER login |
| N009 | N011 | REDIRECT | must_change_password = True |
| N011 | N009 | REDIRECT | رمز تغییر یافت |
| N012 | N013 | NAVIGATE | انتخاب روش بازیابی |
| N013 | N014 | NAVIGATE | ارسال OTP |
| N014 | N015 | NAVIGATE | OTP تأیید شد |
| N015 | N009 | REDIRECT | رمز تنظیم شد |

---

### Edge Table — Admin Navigation

| from | to | relationship | reason |
|------|----|-------------|--------|
| N100 | N101 | LINK | sidebar: سفارشات |
| N100 | N106 | LINK | sidebar: درخواست‌ها |
| N100 | N107 | LINK | sidebar: مشتریان |
| N100 | N109 | LINK | sidebar: فاکتورها |
| N100 | N111 | LINK | sidebar: تکنسین‌ها |
| N100 | N114 | LINK | sidebar: تنظیمات |
| N100 | N116 | LINK | sidebar: گزارش مالی (اگر اضافه شود) |
| N101 | N102 | NAVIGATE | دکمه 'سفارش جدید' |
| N101 | N103 | NAVIGATE | کلیک روی سفارش |
| N102 | N103 | REDIRECT | POST موفق |
| N103 | N104 | NAVIGATE | دکمه ویرایش |
| N103 | N105 | NAVIGATE | دکمه اختصاص تکنسین |
| N103 | N109 | NAVIGATE | ایجاد فاکتور → لیست فاکتورها |
| N111 | N112 | NAVIGATE | کلیک دفتر کل |
| N112 | N113 | NAVIGATE | دکمه صورتحساب |
| N114 | N115 | NAVIGATE | مدیریت اپراتورها |
| N116 | N117 | NAVIGATE | nav: تفکیک تکنسین |
| N116 | N118 | NAVIGATE | nav: تسویه فاکتور |
| N116 | N119 | NAVIGATE | nav: کنترل نقد |
| N116 | N120 | NAVIGATE | nav: کارمزد پلتفرم |
| N116 | N121 | NAVIGATE | nav: حسابرسی |

---

### Edge Table — Technician Navigation

| from | to | relationship | reason |
|------|----|-------------|--------|
| N200 | N201 | LINK | bottom nav: سفارش جدید |
| N200 | N202 | LINK | bottom nav: سفارش‌های من |
| N200 | N204 | LINK | bottom nav: فاکتورها |
| N200 | N207 | LINK | bottom nav: اعلان‌ها |
| N201 | N203 | NAVIGATE | کلیک روی سفارش موجود |
| N202 | N203 | NAVIGATE | کلیک روی سفارش من |
| N203 | N203 | POST | accept / complete / cancel / status-update |
| N203 | N205 | NAVIGATE | دکمه صدور فاکتور |
| N205 | N206 | REDIRECT | POST موفق |
| N204 | N206 | NAVIGATE | کلیک فاکتور |

---

### Edge Table — Customer Flow

| from | to | relationship | reason |
|------|----|-------------|--------|
| N300 | N301 | NAVIGATE | کلیک فاکتور |
| N301 | N302 | NAVIGATE | دکمه پرداخت |
| N302 | N022 | REDIRECT | بازگشت از PSP |
| N019 | N302 | NAVIGATE | دکمه پرداخت از لینک عمومی |
| N020 | N019 | REDIRECT | لینک کوتاه → detail |

---

### Edge Table — Platform Owner Navigation

| from | to | relationship | reason |
|------|----|-------------|--------|
| N400 | N402 | LINK | sidebar: شرکت‌ها |
| N400 | N404 | LINK | sidebar: پلن‌ها |
| N400 | N405 | LINK | sidebar: اشتراک‌ها |
| N400 | N406 | LINK | sidebar: اعتبار پیامک |
| N400 | N415 | LINK | sidebar: پایش پرداخت‌ها |
| N400 | N416 | LINK | sidebar: تسهیم پرداخت‌ها |
| N400 | N417 | LINK | sidebar: KYC |
| N400 | N414 | LINK | sidebar: درگاه پرداخت |
| N400 | N413 | LINK | sidebar: پیام‌ها |
| N400 | N409 | LINK | sidebar: پیامک پلتفرم |
| N402 | N403 | NAVIGATE | کلیک روی شرکت |
| N403 | N406 | NAVIGATE | اعتبار پیامک از صفحه شرکت |
| N406 | N407 | NAVIGATE | لیست شرکت‌ها |
| N406 | N408 | NAVIGATE | لیست فاکتورها |
| N417 | N418 | NAVIGATE | درخواست‌های ویرایش |
| N409 | N412 | NAVIGATE | صندوق خروجی |
| N409 | N410 | NAVIGATE | قالب‌ها |
| N409 | N411 | NAVIGATE | ارائه‌دهنده |

---

### Edge Table — Template Inclusions

| from | to | relationship | reason |
|------|----|-------------|--------|
| `base_dashboard.html` | `includes/nav_platform.html` | INCLUDE | زمانی که PLATFORM_OWNER است |
| `base_dashboard.html` | `includes/nav_customer.html` | INCLUDE | زمانی که CUSTOMER است |
| `base_dashboard.html` | bottom nav | INCLUDE | زمانی که TECHNICIAN است |
| همه صفحات ADMIN | `components/breadcrumb.html` | INCLUDE | (پیشنهادی — فعلاً اختیاری) |
| همه لیست‌ها | `components/pagination.html` | INCLUDE | صفحه‌بندی |
| همه لیست‌ها | `components/empty_state.html` | INCLUDE | حالت خالی |
| همه داشبوردها | `components/stat_card.html` | INCLUDE | کارت آمار |
| همه جداول | `components/status_badge.html` | INCLUDE | نمایش وضعیت |

---

## بخش ۳ — جدول خلاصه گراف

| آیتم | تعداد |
|------|-------|
| Node کل | 95 |
| Node عمومی (N0xx) | 22 |
| Node ادمین (N1xx) | 35 |
| Node تکنسین (N2xx) | 8 |
| Node مشتری (N3xx) | 4 |
| Node پلتفرم (N4xx) | 22 |
| Node سیستم/API (N5xx/N6xx) | 11 |
| Edge ناوبری اصلی | 65+ |
| Edge Include قالب | 12+ |
