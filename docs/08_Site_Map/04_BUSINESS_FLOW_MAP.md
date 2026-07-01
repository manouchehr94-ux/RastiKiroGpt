# ۰۴ — نقشه گردش‌کارهای کسب‌وکار

**مبنا:** `apps/tenants/services.py`، `apps/orders/services.py`، `apps/payments/services.py`، URL‌های بررسی‌شده  
**تاریخ:** ۱ ژوئیه ۲۰۲۶

---

## ۱. ثبت درخواست خدمت عمومی

**Actor:** بازدیدکننده / مشتری (بدون auth)  
**مبدأ:** `/<code>/` یا `/<code>/request/`  
**سرویس:** `ServiceRequestCreateService.create()` در `apps/tenants/services.py`

```mermaid
flowchart TD
    A([بازدیدکننده]) --> B["/<code>/\nصفحه عمومی شرکت"]
    B -->|کلیک 'درخواست خدمت'| C["/<code>/request/\nفرم درخواست"]

    C -->|is_request_form_enabled = False| D["tenants/request_disabled.html\nفرم غیرفعال است"]
    C -->|is_request_form_enabled = True| E[فرم نمایش داده می‌شود]

    E -->|پر کردن: نام، تلفن، آدرس، دسته‌بندی| F[POST]
    F -->|اعتبارسنجی شماره ایرانی| G{تأیید فرم}
    G -->|شماره نامعتبر| H[خطا نمایش داده]
    G -->|معتبر| I["ServiceRequestCreateService.create()\nServiceRequest ایجاد می‌شود\nOrder با status=PENDING_REVIEW ایجاد می‌شود"]
    I -->|اعلان| J["NotificationEventService.emit(\n  'new_service_request'\n)"]
    I --> K["tenants/request_success.html\nپیام موفقیت + کد پیگیری"]
    J --> L["SMS به ادمین شرکت"]

    style I fill:#059669,color:#fff
    style D fill:#dc2626,color:#fff
```

**توجه مهم:** سرویس `ServiceRequestCreateService.create()` هم یک `ServiceRequest` و هم یک `Order` با `status=PENDING_REVIEW` ایجاد می‌کند (مستند در `apps/tenants/services.py:177`).

---

## ۲. بررسی و تبدیل درخواست به سفارش (توسط ادمین)

**Actor:** COMPANY_ADMIN یا COMPANY_STAFF  
**مبدأ:** `/<code>/admin/requests/`

```mermaid
flowchart TD
    A["/<code>/admin/requests/\nلیست درخواست‌های عمومی"] -->|مشاهده| B[انتخاب درخواست]
    B -->|تبدیل به سفارش| C["/<code>/admin/orders/create/\nفرم ایجاد سفارش ادمین"]
    
    DIRECT["ادمین سفارش مستقیم ایجاد می‌کند"] --> C
    
    C -->|POST فرم| D["OrderCreateByAdminService.create()\nOrder با status=NEW"]
    D -->|اعلان| E["NotificationEventService.emit('order_created')"]
    D --> F["/<code>/admin/orders/<id>/\nجزئیات سفارش"]
    F -->|اختصاص تکنسین| G["/<code>/admin/orders/<id>/assign/"]
    G -->|POST| H["order.status = WAITING\norder.technician = technician"]
    H -->|اعلان| I["NotificationEventService.emit(\n  'order_assigned_to_technician'\n)"]
    H --> J["/<code>/admin/orders/<id>/"]

    style D fill:#059669,color:#fff
```

---

## ۳. پذیرش سفارش توسط تکنسین

**Actor:** TECHNICIAN  
**مبدأ:** `/<code>/tech/orders/available/`

```mermaid
flowchart TD
    A["/<code>/tech/\nداشبورد تکنسین"] -->|کلیک| B["/<code>/tech/orders/available/\nسفارشات موجود"]
    B -->|بررسی| C{can_accept_order?}
    C -->|False: زمان یا شرط ندارد| D[سفارش نمایش داده نمی‌شود]
    C -->|True| E["/<code>/tech/orders/<id>/\nجزئیات سفارش"]
    E -->|POST به accept/| F["TechnicianAcceptService.accept()\norder.status = IN_PROGRESS\norder.technician = technician"]
    F -->|اعلان| G["NotificationEventService.emit(\n  'order_accepted_by_technician'\n)"]
    F --> H["/<code>/tech/orders/my/\nسفارشات من"]
    H -->|نمایش در لیست| I["/<code>/tech/orders/<id>/"]

    style F fill:#059669,color:#fff
```

---

## ۴. تکمیل سفارش و صدور فاکتور

**Actor:** TECHNICIAN  
**مبدأ:** `/<code>/tech/orders/my/`

```mermaid
flowchart TD
    A["/<code>/tech/orders/my/"] --> B["/<code>/tech/orders/<id>/"]
    B -->|POST به complete/| C["OrderCompleteService.complete()\norder.status = DONE"]
    C -->|اعلان| D["NotificationEventService.emit(\n  'order_completed'\n)"]
    C --> E["/<code>/tech/orders/my/"]

    B -->|کلیک صدور فاکتور| F["/<code>/tech/orders/<id>/invoice/create/\nریدایرکت"]
    F --> G["/<code>/tech/invoices/order/<id>/create/\nفرم فاکتور"]
    G -->|POST — مبلغ + اقلام| H{"total_amount > 0?"}
    H -->|بله| I["Invoice ایجاد می‌شود\nstatus = ISSUED\nفاکتور بلافاصله صادر"]
    H -->|صفر| J["Invoice ایجاد می‌شود\nstatus = DRAFT"]
    I -->|اعلان| K["NotificationEventService.emit(\n  'invoice_issued'\n)\nSMS + in-app به مشتری"]
    I --> L["/<code>/tech/invoices/<id>/"]

    style C fill:#059669,color:#fff
    style I fill:#059669,color:#fff
```

---

## ۵. درخواست لغو سفارش و بررسی

**Actor:** TECHNICIAN یا COMPANY_ADMIN (force cancel)  
**مبدأ:** `/<code>/tech/orders/<id>/`

```mermaid
flowchart TD
    A["/<code>/tech/orders/<id>/"] -->|POST به cancel/| B{role چیست؟}
    B -->|COMPANY_ADMIN یا COMPANY_STAFF| C["OrderCancelService.force_cancel()\norder.status = CANCELLED"]
    B -->|TECHNICIAN| D["OrderCancelService.request_cancel()\norder.status = CANCEL_REQUESTED"]

    D -->|اعلان| E["NotificationEventService.emit(\n  'cancel_requested'\n)"]
    D --> F["/<code>/admin/orders/\nادمین می‌بیند"]
    F -->|بررسی ادمین| G["/<code>/admin/orders/<id>/\nجزئیات سفارش"]
    G -->|تأیید| H["/<code>/admin/orders/<id>/cancel-request/approve/"]
    G -->|رد| I["/<code>/admin/orders/<id>/cancel-request/reject/"]
    
    H -->|POST| J["order.status = CANCELLED"]
    I -->|POST| K["order.status = WAITING\nبازگشت به چرخه"]

    C --> L["/<code>/tech/orders/my/"]
    J --> L

    style C fill:#dc2626,color:#fff
    style J fill:#dc2626,color:#fff
    style K fill:#059669,color:#fff
```

---

## ۶. جریان پرداخت آنلاین

**Actor:** CUSTOMER یا بازدیدکننده (از لینک عمومی)  
**مبدأ:** `/<code>/invoices/<id>/` یا `/i/<public_code>/`

```mermaid
flowchart TD
    A["/i/<public_code>/\nیا\n/<code>/invoices/<id>/"] --> B["مشاهده جزئیات فاکتور\nstatus = ISSUED"]
    B -->|کلیک پرداخت| C["/<code>/invoices/<id>/pay/\nصفحه checkout"]
    C -->|بررسی| D{gateway موجود است؟}
    D -->|خیر / FAKE| E["FakePaymentProvider\nدر حالت توسعه"]
    D -->|ZarinPal/IDPay| F["⚠️ commented out\nپیاده‌سازی نشده"]

    E --> G["redirect به PSP خارجی\n(یا صفحه fake)"]
    G -->|بازگشت| H["/<code>/payments/callback/"]
    H -->|اعتبارسنجی amount| I{مبلغ تأیید؟}
    I -->|بله| J["Payment record COMPLETED\nInvoice status = PAID\nTechnicianLedgerEntry ایجاد"]
    I -->|خیر| K["Payment FAILED"]

    J -->|اعلان| L["NotificationEventService.emit('payment_received')"]
    J --> M["payments/result.html\nموفقیت"]
    K --> M

    style J fill:#059669,color:#fff
    style K fill:#dc2626,color:#fff
    style F fill:#f59e0b,color:#000
```

---

## ۷. تسویه با تکنسین (Payout)

**Actor:** COMPANY_ADMIN  
**مبدأ:** `/<code>/admin/technicians/<id>/ledger/`

```mermaid
flowchart TD
    A["/<code>/admin/technicians/\nلیست تکنسین‌ها"] --> B["/<code>/admin/technicians/<id>/ledger/\nدفتر کل"]
    B --> C["/<code>/admin/technicians/<id>/statement/\nصورتحساب"]
    C -->|مشاهده دوره| D{عملیات}
    D -->|PDF| E["/<code>/admin/technicians/<id>/statement/pdf/"]
    D -->|Excel| F["/<code>/admin/technicians/<id>/statement/export/"]
    D -->|چاپ| G["/<code>/admin/technicians/<id>/statement/print/"]
    D -->|تسویه| H["/<code>/admin/technicians/<id>/ledger/settlement/\nPOST"]
    H -->|تأیید| I["TechnicianLedgerEntry ایجاد\n(immutable — نمی‌توان حذف کرد)\nBalance صفر می‌شود"]
    I -->|اعلان| J["NotificationEventService.emit('payout_processed')"]

    B --> K["/<code>/admin/payments/split-snapshots/\nاسناد تقسیم"]
    K --> L["/<code>/admin/payments/split-snapshots/<id>/"]

    style I fill:#7c3aed,color:#fff
```

---

## ۸. ثبت شرکت جدید (توسط مدیر پلتفرم)

**Actor:** PLATFORM_OWNER  
**مبدأ:** `/owner-platform/companies/create/`

```mermaid
flowchart TD
    A["/owner-platform/companies/\nلیست شرکت‌ها"] --> B["/owner-platform/companies/create/\nفرم شرکت جدید"]
    B -->|POST| C["Company.objects.create()\ncode منحصربه‌فرد"]
    C --> D["provision_company_communication_defaults()\nقالب‌های SMS پیش‌فرض ایجاد"]
    D --> E["/owner-platform/companies/\nبازگشت به لیست"]
    E -->|اشتراک| F["/owner-platform/subscriptions/create/\nاشتراک برای شرکت"]
    F -->|activate| G["شرکت فعال می‌شود\n/<code>/ قابل دسترس"]

    style C fill:#059669,color:#fff
    style D fill:#2563eb,color:#fff
```

---

## ۹. جریان پیامک و اعلان

**مبنا:** `apps/notifications/services.py`، `apps/sms/services.py`

```mermaid
flowchart TD
    EVENT["رویداد کسب‌وکار\n(هر action در سرویس‌ها)"] --> EMIT["NotificationEventService.emit(\n  event_key, company, actors\n)"]

    EMIT --> CHECK_IN_APP{in-app فعال؟}
    EMIT --> CHECK_SMS{SMS فعال؟}

    CHECK_IN_APP -->|بله| IN_APP_DB["Notification در دیتابیس\n→ admin/notifications/ یا tech/notifications/"]
    CHECK_IN_APP -->|خیر| IN_APP_SKIP[نادیده]

    CHECK_SMS -->|بله| SMS_CHECK_TKMPL{قالب SMS موجود؟}
    CHECK_SMS -->|خیر| SMS_SKIP[نادیده]
    CHECK_SMS -->|⚠️ if False| DEAD_CODE["کد SMS تکنسین\nهرگز اجرا نمی‌شود (P0-6)"]

    SMS_CHECK_TKMPL -->|بله| SMS_Q["SMSOutbox ایجاد\n(queue)"]
    SMS_CHECK_TKMPL -->|خیر| SMS_SKIP2[نادیده]

    SMS_Q -->|ارسال| MELIPAYAMAK["MeliPayamak API\n(ارائه‌دهنده SMS)"]
    MELIPAYAMAK -->|موفق| SMS_SENT["status = SENT"]
    MELIPAYAMAK -->|ناموفق| SMS_FAIL["status = FAILED\nretry queue"]
    SMS_FAIL -->|ادمین| ADMIN_SMS["/<code>/admin/sms/outbox/\nارسال دوباره"]

    style DEAD_CODE fill:#dc2626,color:#fff
    style MELIPAYAMAK fill:#6b7280,color:#fff
```

---

## ۱۰. جریان KYC / پروفایل پذیرنده

**Actor:** COMPANY_ADMIN → PLATFORM_OWNER  
**مبدأ:** `/<code>/admin/payment/merchant-profile/`

```mermaid
flowchart TD
    A["/<code>/admin/payment/merchant-profile/\nمشاهده پروفایل"] --> B{پروفایل وجود دارد؟}
    B -->|خیر| C["ایجاد اولیه پروفایل"]
    B -->|بله| D["مشاهده وضعیت فعلی"]
    D -->|درخواست ویرایش| E["/<code>/admin/payment/merchant-profile/edit-request/\nفرم درخواست تغییر"]
    E -->|POST + بارگذاری مدارک| F["MerchantProfileChangeRequest ایجاد"]
    F -->|اعلان| G["/owner-platform/merchant-profile-change-requests/\nمالک پلتفرم می‌بیند"]
    G --> H["/owner-platform/merchant-profile-change-requests/<id>/\nبررسی مدارک"]
    H -->|تأیید| I["پروفایل به‌روزرسانی\nشرکت می‌تواند پرداخت دریافت کند"]
    H -->|رد| J["درخواست رد شد"]

    style I fill:#059669,color:#fff
    style J fill:#dc2626,color:#fff
```

---

## خلاصه جریان‌های اصلی

| # | جریان | Actor اصلی | تعداد URL درگیر |
|---|-------|-----------|----------------|
| 1 | ثبت درخواست خدمت | بازدیدکننده | 2 |
| 2 | تبدیل درخواست به سفارش | COMPANY_ADMIN/STAFF | 3 |
| 3 | پذیرش سفارش | TECHNICIAN | 3 |
| 4 | تکمیل + صدور فاکتور | TECHNICIAN | 4 |
| 5 | درخواست لغو | TECHNICIAN + COMPANY_ADMIN | 4 |
| 6 | پرداخت آنلاین | CUSTOMER | 4 + PSP خارجی |
| 7 | تسویه با تکنسین | COMPANY_ADMIN | 4 |
| 8 | ثبت شرکت جدید | PLATFORM_OWNER | 3 |
| 9 | پیامک و اعلان | (سیستم) | async |
| 10 | KYC / پذیرنده | COMPANY_ADMIN + PLATFORM_OWNER | 4 |
