# ۰۳ — گراف ناوبری (Mermaid)

**مبنا:** URL‌های بررسی‌شده، view‌ها، و قالب‌های ناوبری  
**تاریخ:** ۱ ژوئیه ۲۰۲۶

---

## ۱. گراف کلی — ورود و تقسیم نقش‌ها

```mermaid
flowchart TD
    ROOT["/\nصفحه اصلی"] --> LOGIN["/login/\nورود یکپارچه"]
    ROOT --> REGISTER["/register/\nثبت‌نام شرکت"]
    ROOT --> FEATURES["/features/"]
    ROOT --> PRICING["/pricing/"]
    ROOT --> ABOUT["/about/"]
    ROOT --> CONTACT["/contact/"]

    REGISTER --> VERIFY["/register/verify/\nتأیید OTP"]
    VERIFY --> SUCCESS["/register/success/"]

    LOGIN -->|PLATFORM_OWNER| PLATFORM_DASH["/owner-platform/dashboard/"]
    LOGIN -->|COMPANY_ADMIN\nCOMPANY_STAFF| ADMIN_DASH["/<code>/admin/\nداشبورد ادمین"]
    LOGIN -->|TECHNICIAN| TECH_DASH["/<code>/tech/\nداشبورد تکنسین"]
    LOGIN -->|CUSTOMER| CUSTOMER_INV["/<code>/invoices/\nفاکتورها"]
    LOGIN -->|must_change_password| PW_CHANGE["/account/change-password-required/"]

    PW_CHANGE --> LOGIN

    PWRESET["/password-reset/"] --> PWSEL["/password-reset/select/"]
    PWSEL --> PWVERIFY["/password-reset/verify/"]
    PWVERIFY --> PWCONFIRM["/password-reset/confirm/"]
    PWCONFIRM --> LOGIN

    style LOGIN fill:#2563eb,color:#fff
    style PLATFORM_DASH fill:#7c3aed,color:#fff
    style ADMIN_DASH fill:#059669,color:#fff
    style TECH_DASH fill:#d97706,color:#fff
    style CUSTOMER_INV fill:#dc2626,color:#fff
```

---

## ۲. جریان احراز هویت و جلسه

```mermaid
flowchart LR
    UNAUTH([بازدیدکننده]) --> LOGIN["/login/"]
    LOGIN -->|POST موفق| ROLECHECK{بررسی نقش}
    ROLECHECK -->|PLATFORM_OWNER| PO["/owner-platform/dashboard/"]
    ROLECHECK -->|COMPANY_ADMIN\nCOMPANY_STAFF| CA["/<code>/admin/"]
    ROLECHECK -->|TECHNICIAN| TC["/<code>/tech/"]
    ROLECHECK -->|CUSTOMER| CU["/<code>/invoices/"]
    ROLECHECK -->|must_change_password| CP["/account/change-password-required/"]
    
    CP -->|رمز تغییر یافت| ROLECHECK
    
    LOGIN -->|GET ?next=...| NEXTRED["/بازگشت به URL اصلی/"]

    TENANT_LOGIN["/<code>/login/"] -->|301 دائم| LOGIN
    LEGACY["/loginlogin/"] -->|301 دائم| PO
```

---

## ۳. پنل مالک پلتفرم

```mermaid
flowchart TD
    PD["/owner-platform/dashboard/\nداشبورد"] --> COMP["/owner-platform/companies/\nشرکت‌ها"]
    PD --> PLANS["/owner-platform/plans/\nپلن‌ها"]
    PD --> SUBS["/owner-platform/subscriptions/\nاشتراک‌ها"]
    PD --> REP["/owner-platform/reports/\nگزارش‌ها"]

    COMP --> COMP_D["/owner-platform/companies/<id>/\nجزئیات شرکت"]
    COMP --> COMP_C["/owner-platform/companies/create/\nشرکت جدید"]
    COMP_D --> COMP_E["/owner-platform/companies/<id>/edit/"]
    COMP_D --> COMP_T["/owner-platform/companies/<id>/templates/\nقالب‌های ارتباطی"]
    COMP_D -->|فعال‌سازی| COMP_ACT["activate/deactivate"]

    PD --> SMSBILL["/owner-platform/sms-billing/\nاعتبار پیامک"]
    SMSBILL --> SMSBILL_CO["/sms-billing/companies/"]
    SMSBILL --> SMSBILL_INV["/sms-billing/invoices/"]
    SMSBILL_INV --> SMSBILL_INV_D["/sms-billing/invoices/<id>/"]
    SMSBILL_INV_D -->|تأیید پرداخت| SMSBILL_INV_PAID["mark-paid"]

    PD --> PSMS["/owner-platform/platform-sms/\nپیامک پلتفرم"]
    PSMS --> PSMS_OB["/platform-sms/outbox/"]
    PSMS --> PSMS_T["/platform-sms/templates/"]
    PSMS --> PSMS_P["/platform-sms/provider/"]
    PSMS_OB --> PSMS_OB_D["/outbox/<id>/"]

    PD --> MERCH["/owner-platform/merchant-profiles/\nKYC پذیرندگان"]
    MERCH --> MERCH_D["/merchant-profiles/<id>/"]
    MERCH --> MERCH_CR["/merchant-profile-change-requests/"]
    MERCH_CR --> MERCH_CR_D["/change-requests/<id>/\nتأیید/رد"]

    PD --> PAY_OPS["/owner-platform/payments/operations/\nپایش پرداخت"]
    PD --> SPLIT["/owner-platform/payment-split-snapshots/"]
    SPLIT --> SPLIT_D["/payment-split-snapshots/<id>/"]

    PD --> PG["/owner-platform/payment-gateways/\nدرگاه پرداخت"]
    PG --> PG_S["/payment-gateways/settings/"]
    PG --> PG_T["/payment-gateways/test/"]

    PD --> MSG["/owner-platform/messages/\nپیام‌ها"]
    MSG --> MSG_IN["/messages/inbox/"]
    MSG --> MSG_OUT["/messages/outbox/"]
    MSG --> MSG_C["/messages/create/"]
    MSG_IN --> MSG_D["/messages/<id>/"]

    style PD fill:#7c3aed,color:#fff
```

---

## ۴. پنل مدیر/اپراتور شرکت

```mermaid
flowchart TD
    AD["/<code>/admin/\nداشبورد"] --> ORD["/<code>/admin/orders/\nسفارشات"]
    AD --> CUST["/<code>/admin/customers/\nمشتریان"]
    AD --> TECH_LIST["/<code>/admin/technicians/\nتکنسین‌ها"]
    AD --> INV["/<code>/admin/invoices/\nفاکتورها"]
    AD --> REQ["/<code>/admin/requests/\nدرخواست‌ها"]
    AD --> FIN["/<code>/admin/financial-reports/summary/\nگزارش مالی"]
    AD --> SET["/<code>/admin/settings/\nتنظیمات"]
    AD --> SMS_MENU["/<code>/admin/sms/\nپیامک"]
    AD --> NOT["/<code>/admin/notifications/\nاعلان‌ها"]

    ORD --> ORD_C["/<code>/admin/orders/create/"]
    ORD --> ORD_D["/<code>/admin/orders/<id>/"]
    ORD_D --> ORD_E["/<code>/admin/orders/<id>/edit/"]
    ORD_D --> ORD_A["/<code>/admin/orders/<id>/assign/\nاختصاص تکنسین"]
    ORD_D --> ORD_INV["/<code>/admin/orders/<id>/invoice/create/"]
    ORD_D --> ORD_CR_AP["cancel-request/approve/"]
    ORD_D --> ORD_CR_RJ["cancel-request/reject/"]

    CUST --> CUST_D["/<code>/admin/customers/<id>/"]
    CUST --> CUST_L["/<code>/admin/customers/lookup/\n(AJAX)"]

    TECH_LIST --> TECH_C["/<code>/admin/technicians/create/"]
    TECH_LIST --> TECH_D["/<code>/admin/technicians/<id>/edit/"]
    TECH_LIST --> TECH_LED["/<code>/admin/technicians/<id>/ledger/"]
    TECH_LED --> TECH_STMNT["/<code>/admin/technicians/<id>/statement/"]
    TECH_STMNT --> TECH_STMNT_PDF["statement/pdf/"]
    TECH_STMNT --> TECH_STMNT_EXP["statement/export/"]
    TECH_LED --> TECH_SET["/<code>/admin/technicians/<id>/ledger/settlement/"]
    TECH_LIST --> TECH_RATES["/<code>/admin/technicians/rates/"]

    INV --> INV_D["/<code>/admin/invoices/<id>/"]
    INV_D --> INV_E["/<code>/admin/invoices/<id>/edit/"]
    INV_D --> INV_P["/<code>/admin/invoices/<code>/print/"]

    FIN --> FIN_TECH["financial-reports/technicians/"]
    FIN --> FIN_INV["financial-reports/invoices/"]
    FIN --> FIN_CASH["financial-reports/cash-control/"]
    FIN --> FIN_FEE["financial-reports/platform-fees/"]
    FIN --> FIN_AUD["financial-reports/audit/"]

    SET --> SET_NOT["/<code>/admin/settings/notifications/"]
    SET --> SET_OP["/<code>/admin/settings/operators/\n⚠️ بدون decorator"]
    SET --> SET_BD["/<code>/admin/base-data/"]
    SET --> SET_PG["/<code>/admin/payment-gateway/"]
    SET --> SET_COMM["/<code>/admin/communication-settings/"]
    SET --> SET_BRAND["/<code>/admin/branding/"]

    SMS_MENU --> SMS_TPL["/<code>/admin/sms/templates/"]
    SMS_MENU --> SMS_OB["/<code>/admin/sms/outbox/"]
    SMS_MENU --> SMS_DX["/<code>/admin/sms/diagnostics/"]
    SMS_MENU --> SMS_IN["/<code>/admin/sms/inbox/"]
    SMS_MENU --> SMS_CR["/<code>/admin/sms-credit/\nکیف پول"]

    style AD fill:#059669,color:#fff
    style SET_OP fill:#dc2626,color:#fff
```

---

## ۵. پنل تکنسین

```mermaid
flowchart TD
    TH["/<code>/tech/\nداشبورد تکنسین"] --> ORD_AV["/<code>/tech/orders/available/\nسفارشات موجود"]
    TH --> ORD_MY["/<code>/tech/orders/my/\nسفارشات من"]
    TH --> INV_T["/<code>/tech/invoices/\nفاکتورهای من"]
    TH --> NOT_T["/<code>/tech/notifications/\nاعلان‌ها"]

    ORD_AV --> ORD_D["/<code>/tech/orders/<id>/\nجزئیات سفارش"]
    ORD_MY --> ORD_D

    ORD_D -->|POST| ORD_ACC["/<code>/tech/orders/<id>/accept/\n→ IN_PROGRESS"]
    ORD_D -->|POST| ORD_COMP["/<code>/tech/orders/<id>/complete/\n→ DONE"]
    ORD_D -->|POST| ORD_CAN["/<code>/tech/orders/<id>/cancel/\n→ CANCEL_REQUESTED"]
    ORD_D -->|POST| ORD_STAT["/<code>/tech/orders/<id>/status/\nآپدیت وضعیت"]

    ORD_D -->|پس از DONE| INV_C["/<code>/tech/invoices/order/<id>/create/\nصدور فاکتور"]
    INV_C --> INV_D["/<code>/tech/invoices/<id>/\nجزئیات فاکتور"]
    INV_D -->|POST| INV_CP["/<code>/tech/invoices/<id>/cash-paid/\nنقد"]
    INV_D -->|POST| INV_CR["/<code>/tech/invoices/<id>/cancel-request/\nدرخواست لغو"]

    NOT_T -->|POST| NOT_READ["/<code>/tech/notifications/mark-all-read/"]

    style TH fill:#d97706,color:#fff
    style ORD_ACC fill:#059669,color:#fff
    style ORD_COMP fill:#059669,color:#fff
    style ORD_CAN fill:#dc2626,color:#fff
```

---

## ۶. جریان فاکتور و پرداخت (مشتری)

```mermaid
flowchart LR
    INV_L["/<code>/invoices/\nلیست فاکتورها"] --> INV_D["/<code>/invoices/<id>/\nجزئیات"]
    INV_D -->|کلیک پرداخت| INV_PAY["/<code>/invoices/<id>/pay/\nصفحه checkout"]
    INV_PAY -->|redirect به PSP| PSP_EXT[["درگاه پرداخت\n(خارجی)"]];
    PSP_EXT -->|callback| PAY_CB["/<code>/payments/callback/\nبازگشت از PSP"]
    PAY_CB -->|موفق| PAY_RES["payments/result.html\nموفقیت"]
    PAY_CB -->|ناموفق| PAY_RES

    INV_D --> INV_DISC["/<code>/invoices/<id>/discount/\nتخفیف"]
    INV_DISC --> INV_D

    PUBINV_SHORT["/i/<public_code>/\nلینک کوتاه"] --> INV_PUB["/<code>/invoices/public/<code>/\nفاکتور عمومی"]
    INV_PUB --> INV_PRINT["/<code>/invoices/public/<code>/print/"]
    INV_PUB --> INV_PAY

    style PSP_EXT fill:#6b7280,color:#fff
    style PAY_RES fill:#059669,color:#fff
```

---

## ۷. جریان درخواست خدمت عمومی

```mermaid
flowchart TD
    HOME["/<code>/\nصفحه شرکت"] --> REQ["/<code>/request/\nفرم درخواست خدمت"]
    HOME --> STAT["/<code>/request/status/\nپیگیری"]

    REQ -->|form enabled| REQ_FORM[فرم پر کردن]
    REQ -->|form disabled| REQ_DIS["tenants/request_disabled.html"]
    REQ_FORM -->|POST موفق| REQ_SUCCESS["tenants/request_success.html\nداخل همان صفحه"]

    REQ_SUCCESS -->|پس از پذیرش توسط ادمین| ORD_ADMIN["/<code>/admin/requests/\nادمین می‌بیند"]
    ORD_ADMIN -->|تبدیل به سفارش| ORD_D["/<code>/admin/orders/<id>/"]
    ORD_D --> ORD_A["/<code>/admin/orders/<id>/assign/\nاختصاص تکنسین"]

    STAT -->|وارد کردن کد| STAT_RES["tenants/request_status.html\nنتیجه"]

    style REQ fill:#2563eb,color:#fff
```

---

## ۸. چرخه عمر سفارش (Order Lifecycle)

```mermaid
stateDiagram-v2
    [*] --> PENDING_REVIEW : public request_form\n(/<code>/request/)
    [*] --> NEW : admin order_create\n(/<code>/admin/orders/create/)

    PENDING_REVIEW --> NEW : ادمین — admin_requests\nتبدیل درخواست به سفارش

    NEW --> WAITING : ادمین — admin_order_edit\nاختصاص اولیه

    WAITING --> IN_PROGRESS : تکنسین — tech/orders/<id>/accept/

    IN_PROGRESS --> DONE : تکنسین — tech/orders/<id>/complete/
    IN_PROGRESS --> CANCEL_REQUESTED : تکنسین — tech/orders/<id>/cancel/

    WAITING --> CANCEL_REQUESTED : ادمین/مشتری

    CANCEL_REQUESTED --> CANCELLED : ادمین — admin_cancel_request_approve/
    CANCEL_REQUESTED --> WAITING : ادمین — admin_cancel_request_reject/

    DONE --> [*]
    CANCELLED --> [*]

    DONE --> NEW : ادمین — admin_order_return_to_cycle/
```

---

## ۹. جریان ایجاد و تسویه فاکتور

```mermaid
flowchart TD
    ORDER_DONE["سفارش در وضعیت DONE"] -->|تکنسین| TECH_INV["/<code>/tech/invoices/order/<id>/create/"]
    ORDER_DONE -->|ادمین| ADMIN_INV["/<code>/admin/orders/<id>/invoice/create/"]

    TECH_INV --> INV_ISSUED["فاکتور ISSUED"]
    ADMIN_INV --> INV_ISSUED

    INV_ISSUED -->|مشتری| INV_VIEW["/<code>/invoices/<id>/\nمشاهده"]
    INV_VIEW -->|پرداخت آنلاین| PAY_ONLINE[["درگاه PSP"]]
    INV_VIEW -->|تکنسین نقد| CASH["/<code>/tech/invoices/<id>/cash-paid/"]

    PAY_ONLINE -->|callback موفق| INV_PAID["فاکتور PAID"]
    CASH --> INV_PAID

    INV_PAID -->|split| LEDGER["TechnicianLedgerEntry\nایجاد می‌شود"]
    LEDGER -->|تسویه توسط ادمین| SETTLE["/<code>/admin/technicians/<id>/ledger/settlement/"]

    INV_ISSUED -->|درخواست لغو از تکنسین| CANCEL_REQ["/<code>/tech/invoices/<id>/cancel-request/"]
    CANCEL_REQ -->|بررسی ادمین| ADMIN_REV["/<code>/admin/invoices/<id>/cancel-request/<req_id>/review/"]

    style INV_PAID fill:#059669,color:#fff
    style SETTLE fill:#7c3aed,color:#fff
```

---

## ۱۰. جریان اعلان و پیامک

```mermaid
flowchart LR
    EVENT["رویداد کسب‌وکار\n(order accept, invoice issued, ...)"] --> NOTIF_SVC["NotificationEventService.emit()"]

    NOTIF_SVC -->|in-app| NOTIF_DB["Notification record\ndر دیتابیس"]
    NOTIF_SVC -->|SMS| SMS_QUEUE["SMSOutbox queue"]

    NOTIF_DB -->|ادمین| ADM_NOT["/<code>/admin/notifications/"]
    NOTIF_DB -->|تکنسین| TECH_NOT["/<code>/tech/notifications/"]

    SMS_QUEUE -->|process| MELI["MeliPayamak API\n(خارجی)"]
    MELI -->|outbox ادمین| ADMIN_SMS["/<code>/admin/sms/outbox/"]
    MELI -->|outbox پلتفرم| PLAT_SMS["/owner-platform/platform-sms/outbox/"]

    style EVENT fill:#6b7280,color:#fff
    style MELI fill:#dc2626,color:#fff
```
