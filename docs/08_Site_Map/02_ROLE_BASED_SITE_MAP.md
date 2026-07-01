# ۰۲ — نقشه سایت مبتنی بر نقش

**مبنا:** کد مستقیم در `apps/accounts/permissions.py`، `apps/dashboard/views.py`، decorator‌های view  
**تاریخ:** ۱ ژوئیه ۲۰۲۶

---

## ۱. بازدیدکننده عمومی (بدون auth)

### نقطه ورود
`/` — صفحه اصلی بازاریابی

### صفحات قابل دسترس

| صفحه | URL | توضیح |
|------|-----|-------|
| صفحه اصلی | `/` | معرفی پلتفرم Rasti |
| ویژگی‌ها | `/features/` | قابلیت‌های سیستم |
| قیمت‌گذاری | `/pricing/` | پلن‌ها و تعرفه‌ها |
| درباره ما | `/about/` | اطلاعات شرکت |
| تماس | `/contact/` | فرم ارتباطی |
| ثبت‌نام شرکت | `/register/` | ثبت‌نام شرکت جدید در پلتفرم |
| تأیید OTP | `/register/verify/` | تأیید شماره مدیر با OTP |
| موفقیت ثبت‌نام | `/register/success/` | پیام موفقیت پس از ثبت‌نام |
| ورود | `/login/` | فرم ورود یکپارچه |
| بازیابی رمز | `/password-reset/` → `/password-reset/select/` → `/password-reset/verify/` → `/password-reset/confirm/` | جریان ۴ مرحله‌ای بازیابی |
| صفحه عمومی شرکت | `/<code>/` | صفحه معرفی شرکت tenant |
| فرم درخواست خدمت | `/<code>/request/` | ارسال درخواست بدون ورود |
| پیگیری درخواست | `/<code>/request/status/` | بررسی وضعیت با کد/شماره |
| فاکتور عمومی | `/<code>/invoices/public/<public_code>/` | مشاهده فاکتور بدون ورود |
| پرینت فاکتور | `/<code>/invoices/public/<public_code>/print/` | چاپ فاکتور |
| لینک کوتاه فاکتور | `/i/<public_code>/` | لینک مختصر قابل اشتراک |
| callback پرداخت | `/<code>/payments/callback/` | بازگشت از درگاه پرداخت |

### جریان اصلی ناوبری
```
/ → /features/ | /pricing/ | /about/ | /contact/
/ → /register/ → /register/verify/ → /register/success/
/ → /login/ → [redirect به پنل نقش]
/<code>/ → /<code>/request/ → [موفقیت یا خطا]
/<code>/ → /<code>/request/status/
/i/<public_code>/ → مشاهده فاکتور → /<code>/invoices/<id>/pay/
```

### ناحیه‌های ممنوع
- `/<code>/admin/` — نیاز به COMPANY_ADMIN یا COMPANY_STAFF
- `/<code>/tech/` — نیاز به TECHNICIAN
- `/owner-platform/` — نیاز به PLATFORM_OWNER

---

## ۲. مشتری (CUSTOMER)

### نقطه ورود
`/login/?company=<code>` → redirect به `/<code>/invoices/`

### داشبورد اصلی
`/<code>/customer/` — ریدایرکت دائم به صفحه عمومی شرکت (از Phase 24 حذف شده)  
**توجه:** پنل مشتری دیگر وجود ندارد. مشتریان از طریق لینک مستقیم فاکتور و پرداخت دسترسی دارند.

### صفحات قابل دسترس

| صفحه | URL | عملکرد |
|------|-----|---------|
| لیست فاکتورها | `/<code>/invoices/` | همه فاکتورها مرتبط با مشتری |
| جزئیات فاکتور | `/<code>/invoices/<id>/` | مشاهده تفصیلی یک فاکتور |
| پرداخت فاکتور | `/<code>/invoices/<id>/pay/` | شروع فرآیند پرداخت |
| اعمال تخفیف | `/<code>/invoices/<id>/discount/` | اعمال کد تخفیف |
| لیست پرداخت‌ها | `/<code>/payments/` | تاریخچه پرداخت‌ها |
| فاکتور عمومی | `/<code>/invoices/public/<code>/` | مشاهده بدون ورود |
| پرینت فاکتور | `/<code>/invoices/public/<code>/print/` | چاپ |

همه صفحات عمومی بازدیدکننده نیز قابل دسترس هستند.

### جریان اصلی ناوبری
```
/login/ → /<code>/invoices/
/<code>/invoices/ → /<code>/invoices/<id>/ → /<code>/invoices/<id>/pay/ → /<code>/payments/callback/
/<code>/invoices/<id>/pay/ → [redirect به درگاه PSP]
```

### اقدامات مجاز
- مشاهده فاکتورهای خود
- پرداخت آنلاین فاکتور
- اعمال کد تخفیف
- مشاهده تاریخچه پرداخت

### ناحیه‌های ممنوع
- `/<code>/admin/` — ممنوع
- `/<code>/tech/` — ممنوع
- `/owner-platform/` — ممنوع
- فاکتورهای سایر مشتریان — ممنوع (فیلتر company + customer)

### nav_customer.html — آیتم‌های sidebar
```
حساب من:
  • داشبورد → /<code>/customer/
  • فاکتورها → /<code>/invoices/
  • پرداخت‌ها → /<code>/payments/
خدمات:
  • درخواست خدمت → /<code>/request/
  • پیگیری درخواست → /<code>/request/status/
```

---

## ۳. تکنسین (TECHNICIAN)

### نقطه ورود
`/login/?company=<code>` → redirect به `/<code>/tech/`

### داشبورد اصلی
`/<code>/tech/` — داشبورد تکنسین با آمار سفارشات

### صفحات قابل دسترس

| صفحه | URL | عملکرد |
|------|-----|---------|
| داشبورد | `/<code>/tech/` | آمار و سفارشات اخیر |
| سفارشات موجود | `/<code>/tech/orders/available/` | سفارشات قابل پذیرش |
| سفارشات من | `/<code>/tech/orders/my/` | سفارشات اختصاص‌یافته |
| جزئیات سفارش | `/<code>/tech/orders/<id>/` | مشاهده کامل یک سفارش |
| قبول سفارش | `/<code>/tech/orders/<id>/accept/` | POST — قبول کردن |
| تکمیل سفارش | `/<code>/tech/orders/<id>/complete/` | POST — پایان کار |
| لغو سفارش | `/<code>/tech/orders/<id>/cancel/` | POST — درخواست لغو |
| آپدیت وضعیت | `/<code>/tech/orders/<id>/status/` | POST — تغییر وضعیت |
| لیست فاکتورها | `/<code>/tech/invoices/` | فاکتورهای صادرشده توسط من |
| ایجاد فاکتور | `/<code>/tech/invoices/order/<id>/create/` | صدور فاکتور برای سفارش |
| جزئیات فاکتور | `/<code>/tech/invoices/<id>/` | مشاهده فاکتور |
| درخواست لغو فاکتور | `/<code>/tech/invoices/<id>/cancel-request/` | POST |
| تأیید نقد | `/<code>/tech/invoices/<id>/cash-paid/` | POST — پرداخت نقد |
| اعلان‌ها | `/<code>/tech/notifications/` | اعلان‌های دریافتی |
| علامت‌گذاری خوانده | `/<code>/tech/notifications/mark-all-read/` | POST |

### جریان اصلی ناوبری
```
/login/ → /<code>/tech/
/<code>/tech/ ← → /<code>/tech/orders/available/
/<code>/tech/orders/available/ → /<code>/tech/orders/<id>/ → [accept] → /<code>/tech/orders/my/
/<code>/tech/orders/my/ → /<code>/tech/orders/<id>/ → [complete] → /<code>/tech/invoices/order/<id>/create/
/<code>/tech/invoices/order/<id>/create/ → /<code>/tech/invoices/<id>/
```

### اقدامات مجاز
- مشاهده سفارشات موجود برای شرکت خود
- پذیرش سفارش (WAITING → IN_PROGRESS)
- تغییر وضعیت سفارش
- تکمیل سفارش (IN_PROGRESS → DONE)
- درخواست لغو سفارش
- صدور فاکتور برای سفارش تکمیل‌شده
- اعمال نقد (cash-paid) بر فاکتور
- مشاهده اعلان‌ها

### ناحیه‌های ممنوع
- `/<code>/admin/` — ممنوع
- `/owner-platform/` — ممنوع
- سفارشات سایر تکنسین‌ها (فیلتر technician)

### bottom navigation (موبایل)
بر اساس `base_dashboard.html`:
```
[داشبورد] [سفارش جدید] [سفارش‌های من] [فاکتورها] [اعلان‌ها]
```

---

## ۴. اپراتور/کارمند (COMPANY_STAFF)

### نقطه ورود
`/login/?company=<code>` → redirect به `/<code>/admin/`

### داشبورد اصلی
`/<code>/admin/` — داشبورد شرکت با آمار سفارشات

### صفحات قابل دسترس

**توجه:** `COMPANY_STAFF` دسترسی مشابه `COMPANY_ADMIN` دارد اما برخی تنظیمات حساس (تنظیمات شرکت، مدیریت اپراتورها، گزارش‌های مالی، KYC) فقط برای `COMPANY_ADMIN` است.

| دسته | صفحات قابل دسترس برای COMPANY_STAFF |
|------|-------------------------------------|
| داشبورد | `/<code>/admin/` |
| سفارشات | لیست، جزئیات، ایجاد، ویرایش، اختصاص، لغو |
| مشتریان | لیست، جزئیات، جستجو (lookup) |
| فاکتورها | لیست، جزئیات، پرینت |
| درخواست‌ها | لیست درخواست‌های عمومی |
| اعلان‌ها | لیست و علامت‌گذاری |

### ناحیه‌های محدود‌شده برای COMPANY_STAFF
- `/<code>/admin/settings/` — تنظیمات شرکت (فقط COMPANY_ADMIN)
- `/<code>/admin/settings/operators/` — مدیریت اپراتورها (⚠️ P0-1: بدون decorator)
- `/<code>/admin/technicians/` — مدیریت تکنسین‌ها (فقط COMPANY_ADMIN)
- `/<code>/admin/financial-reports/` — گزارش‌های مالی (فقط COMPANY_ADMIN)
- `/<code>/admin/payment-gateway/` — تنظیمات درگاه (فقط COMPANY_ADMIN)

---

## ۵. مدیر شرکت (COMPANY_ADMIN)

### نقطه ورود
`/login/?company=<code>` → redirect به `/<code>/admin/`

### داشبورد اصلی
`/<code>/admin/` — داشبورد کامل شرکت

### کل صفحات قابل دسترس

#### داشبورد و تنظیمات
- `/<code>/admin/` — داشبورد
- `/<code>/admin/page/` — ویرایش صفحه عمومی شرکت
- `/<code>/admin/settings/` — تنظیمات عمومی
- `/<code>/admin/custom-fields/` — فیلدهای سفارشی
- `/<code>/admin/settings/notifications/` — تنظیمات اعلان
- `/<code>/admin/settings/operators/` — مدیریت اپراتورها (**⚠️ آسیب‌پذیری P0-1**)
- `/<code>/admin/settings/operators/create/` — ایجاد اپراتور
- `/<code>/admin/settings/operators/<id>/edit/` — ویرایش اپراتور
- `/<code>/admin/branding/` — برندینگ

#### داده‌های پایه
- `/<code>/admin/base-data/` — خانه داده‌های پایه
- `/<code>/admin/base-data/categories/` + CRUD
- `/<code>/admin/base-data/items/` + CRUD

#### تکنسین‌ها
- `/<code>/admin/technicians/` — لیست
- `/<code>/admin/technicians/create/` — ایجاد
- `/<code>/admin/technicians/rates/` — نرخ‌ها
- `/<code>/admin/technicians/<id>/edit/` + delete + toggle
- `/<code>/admin/technicians/<id>/ledger/` — دفتر کل
- `/<code>/admin/technicians/<id>/statement/` — صورتحساب (+ print/pdf/export)
- `/<code>/admin/technicians/<id>/ledger/settlement/` — تسویه

#### مشتریان
- `/<code>/admin/customers/` — لیست
- `/<code>/admin/customers/<id>/` — جزئیات
- `/<code>/admin/customers/lookup/` — جستجو AJAX

#### سفارشات
- `/<code>/admin/orders/` — لیست کامل
- `/<code>/admin/orders/create/` — ایجاد سفارش توسط ادمین
- `/<code>/admin/orders/<id>/` — جزئیات
- `/<code>/admin/orders/<id>/edit/` — ویرایش
- `/<code>/admin/orders/<id>/assign/` — اختصاص تکنسین
- تأیید/رد درخواست لغو
- بازگشت به چرخه
- `/<code>/admin/requests/` — لیست درخواست‌های عمومی

#### فاکتورها
- `/<code>/admin/invoices/` — لیست
- ایجاد از روی سفارش
- جزئیات، ویرایش، پرینت
- بررسی درخواست لغو

#### گالری
- `/<code>/admin/gallery/` + CRUD

#### پرداخت‌ها
- `/<code>/admin/payment-gateway/` + تست
- `/<code>/admin/payment/merchant-profile/` + درخواست ویرایش
- `/<code>/admin/payments/operations/`
- `/<code>/admin/payments/split-snapshots/`
- `/<code>/admin/payments/gateway-reconciliation/`

#### گزارش‌های مالی
- `/<code>/admin/financial-reports/summary/`
- `/<code>/admin/financial-reports/technicians/`
- `/<code>/admin/financial-reports/invoices/`
- `/<code>/admin/financial-reports/cash-control/`
- `/<code>/admin/financial-reports/platform-fees/`
- `/<code>/admin/financial-reports/audit/`

#### پیامک و ارتباطات
- `/<code>/admin/sms/` — صندوق خروجی
- `/<code>/admin/sms/templates/` + CRUD
- `/<code>/admin/sms/outbox/` + جزئیات + ارسال فوری
- `/<code>/admin/sms/diagnostics/`
- `/<code>/admin/sms/inbox/`
- `/<code>/admin/sms-credit/` — کیف پول پیامک
- `/<code>/admin/sms-credit/recharge/` — شارژ
- `/<code>/admin/sms-credit/transactions/`
- `/<code>/admin/sms-credit/invoices/`
- `/<code>/admin/communication-settings/` — تنظیمات اعلان
- `/<code>/admin/communication-settings/cause/<key>/`
- `/<code>/admin/communication-settings/template/<key>/`

#### گزارش‌ها
- `/<code>/admin/reports/` — لیست گزارش‌ها
- `/<code>/admin/reports/customer-segments/`
- `/<code>/admin/reports/discount-campaigns/` + CRUD

#### اعلان‌ها
- `/<code>/admin/notifications/`

### جریان اصلی ناوبری
```
/login/ → /<code>/admin/
/<code>/admin/ → /<code>/admin/orders/ → /<code>/admin/orders/create/
/<code>/admin/orders/<id>/ → /<code>/admin/orders/<id>/assign/ → تکنسین
/<code>/admin/orders/<id>/ → /<code>/admin/orders/<id>/invoice/create/ → /<code>/admin/invoices/<id>/
/<code>/admin/technicians/<id>/statement/ → PDF یا Export
```

---

## ۶. مالک پلتفرم (PLATFORM_OWNER)

### نقطه ورود
`/login/` → redirect به `/owner-platform/dashboard/`

### داشبورد اصلی
`/owner-platform/dashboard/` — داشبورد سراسری پلتفرم

### کل صفحات قابل دسترس

#### داشبورد و گزارش
- `/owner-platform/dashboard/` — آمار کل پلتفرم
- `/owner-platform/reports/` — گزارش‌های تجمیعی

#### مدیریت شرکت‌ها
- `/owner-platform/companies/` — لیست همه شرکت‌ها
- `/owner-platform/companies/create/` — ایجاد شرکت
- `/owner-platform/companies/<id>/` — جزئیات + آمار
- `/owner-platform/companies/<id>/edit/` — ویرایش
- activate / deactivate
- مدیریت قالب‌های ارتباطی شرکت

#### پلن و اشتراک
- `/owner-platform/plans/` + CRUD
- `/owner-platform/subscriptions/` + CRUD
- activate / cancel

#### پیامک پلتفرم
- `/owner-platform/platform-sms/` — صندوق خروجی
- message-types — نوع پیام‌ها
- templates — قالب‌ها + CRUD
- provider — تنظیمات ارائه‌دهنده
- outbox + detail + send-now

#### صورت‌حساب پیامک
- `/owner-platform/sms-billing/` — داشبورد
- settings — تعرفه‌گذاری
- companies — موجودی شرکت‌ها
- transactions — تراکنش‌ها
- invoices + detail + mark-paid

#### پیام‌رسانی داخلی
- inbox / outbox / create / detail

#### قالب‌های ارتباطی (جهانی)
- `/owner-platform/communication-templates/` + CRUD

#### درگاه پرداخت
- `/owner-platform/payment-gateways/` + settings + test

#### پرداخت‌ها
- `/owner-platform/payments/operations/` — داشبورد پایش
- `/owner-platform/payment-split-snapshots/` + detail

#### KYC / پروفایل پذیرنده
- `/owner-platform/merchant-profiles/` — لیست
- detail + document
- change-requests + detail + document

#### تأیید مالی تکنسین
- `/owner-platform/technician-financial-verifications/` + detail

#### سیاست بازیابی رمز
- `/owner-platform/password-reset-policy/` + edit per company

#### درخواست‌های قالب پیامک
- `/owner-platform/sms-template-requests/` + detail + approve + reject

### جریان اصلی ناوبری
```
/login/ → /owner-platform/dashboard/
/owner-platform/companies/ → /owner-platform/companies/<id>/ → [activate/deactivate]
/owner-platform/merchant-profiles/ → /owner-platform/merchant-profile-change-requests/<id>/ → [approve/reject]
/owner-platform/sms-billing/ → /owner-platform/sms-billing/companies/ → صدور فاکتور → mark-paid
/owner-platform/platform-sms/outbox/ → send-now
```

### sidebar پلتفرم (از nav_platform.html)
```
مدیریت پلتفرم:
  • داشبورد
  • شرکت‌ها
  • پلن‌ها
  • اشتراک‌ها
مالی و اعتبار:
  • اعتبار پیامک
  • پایش پرداخت‌ها
  • تسهیم پرداخت‌ها
  • پروفایل پذیرندگان (KYC)
  • درگاه پرداخت
ارتباطات:
  • پیام‌ها
  • پیامک پلتفرم
  • قالب‌های پیامکی
تحلیل:
  • گزارش‌ها
```

### ناحیه‌های محدود
- `/<code>/admin/` — فقط از طریق صفحه شرکت (company_detail) امکان‌پذیر نیست
- مالک پلتفرم به داده‌های tenant دسترسی مستقیم از UI ندارد، فقط از داشبورد و گزارش‌ها

---

## خلاصه مقایسه‌ای نقش‌ها

| صفحه/قابلیت | بازدیدکننده | مشتری | تکنسین | اپراتور | مدیر | مالک |
|-------------|-------------|-------|---------|---------|------|------|
| صفحات بازاریابی | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| فرم درخواست خدمت | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| فاکتور عمومی | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| فاکتورها (خود) | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| پرداخت | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| داشبورد تکنسین | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| مدیریت سفارش | ❌ | ❌ | جزئی | ✅ | ✅ | ❌ |
| تنظیمات شرکت | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| گزارش مالی | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| مدیریت شرکت‌ها | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| پیامک پلتفرم | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
