# ۰۱ — فهرست کامل URL‌های پروژه

**مبنا:** `config/urls.py` + تمام `apps/*/urls*.py` (بررسی‌شده مستقیم)  
**تاریخ:** ۱ ژوئیه ۲۰۲۶

---

## راهنمای ستون‌ها

| ستون | توضیح |
|------|-------|
| **URL** | مسیر کامل URL (پارامترهای متغیر با `<type:name>`) |
| **URL Name** | نام Django برای `reverse()` |
| **App** | Django app مسئول |
| **View** | تابع یا کلاس view |
| **Template** | قالب HTML رندرشده (اگر وجود داشته باشد) |
| **نقش مجاز** | نقش‌های کاربری که دسترسی دارند |
| **دسته** | PUBLIC / PRIVATE / ADMIN / TECH / PLATFORM / API / SYSTEM |

---

## ۱. صفحات سیستمی و بهداشتی

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 1 | `/favicon.ico` | `favicon` | config | `rasti_favicon_view` | — | همه | SYSTEM |
| 2 | `/health/` | `health` | platform_core | `health_check` | — | همه | SYSTEM |
| 3 | `/health/db/` | `health-db` | platform_core | `health_db_check` | — | همه | SYSTEM |
| 4 | `/admin/` | — | django.contrib.admin | Django Admin | Django Admin UI | superuser | SYSTEM |

---

## ۲. احراز هویت یکپارچه

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 5 | `/login/` | `login` | accounts | `unified_login` | `accounts/unified_login.html` | همه (بدون auth) | PUBLIC |
| 6 | `/logout/` | `logout` | accounts | `unified_logout` | — (redirect) | authenticated | PRIVATE |
| 7 | `/account/change-password-required/` | `change_password_required` | accounts | `change_password_required` | `accounts/change_password_required.html` | authenticated | PRIVATE |
| 8 | `/password-reset/` | `password_reset` | accounts | `password_reset_form` | `accounts/password_reset_form.html` | همه | PUBLIC |
| 9 | `/password-reset/select/` | `password_reset_select` | accounts | `password_reset_select` | `accounts/password_reset_select.html` | همه | PUBLIC |
| 10 | `/password-reset/verify/` | `password_reset_verify` | accounts | `password_reset_verify` | `accounts/password_reset_otp.html` | همه | PUBLIC |
| 11 | `/password-reset/confirm/` | `password_reset_confirm` | accounts | `password_reset_confirm` | `accounts/password_reset_confirm.html` | همه | PUBLIC |

---

## ۳. صفحات عمومی (بازاریابی)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 12 | `/` | `public:home` | public | `views.home` | `public/home.html` | همه | PUBLIC |
| 13 | `/features/` | `public:features` | public | `views.features` | `public/features.html` | همه | PUBLIC |
| 14 | `/pricing/` | `public:pricing` | public | `views.pricing` | `public/pricing.html` | همه | PUBLIC |
| 15 | `/about/` | `public:about` | public | `views.about` | `public/about.html` | همه | PUBLIC |
| 16 | `/contact/` | `public:contact` | public | `views.contact` | `public/contact.html` | همه | PUBLIC |
| 17 | `/register/` | `public:register` | public | `views.register` | `public/register.html` | همه | PUBLIC |
| 18 | `/register/verify/` | `public:register_verify` | public | `views.register_verify` | `public/register_verify.html` | همه | PUBLIC |
| 19 | `/register/resend-otp/` | `public:register_resend_otp` | public | `views.register_resend_otp` | — (JSON) | همه | PUBLIC |
| 20 | `/register/success/` | `public:register_success` | public | `views.register_success` | `public/register_success.html` | همه | PUBLIC |

---

## ۴. REST API — احراز هویت

| # | URL | URL Name | App | View | Method | دسته |
|---|-----|----------|-----|------|--------|------|
| 21 | `/api/auth/login/` | `api-auth:auth-login` | api | `LoginAPI` | POST | API |
| 22 | `/api/auth/token/refresh/` | `api-auth:auth-token-refresh` | api | `TokenRefreshAPI` | POST | API |
| 23 | `/api/auth/me/` | `api-auth:auth-me` | api | `MeAPI` | GET | API |
| 24 | `/api/auth/logout/` | `api-auth:auth-logout` | api | `LogoutAPI` | POST | API |
| 25 | `/api/auth/change-password/` | `api-auth:auth-change-password` | api | `ChangePasswordAPI` | POST | API |

---

## ۵. REST API — بررسی موجودیت (بدون auth)

| # | URL | URL Name | App | View | دسته |
|---|-----|----------|-----|------|------|
| 26 | `/api/public/check-username/` | `api-check-username` | public | `public_api.check_username` | API |
| 27 | `/api/public/check-company-code/` | `api-check-company-code` | public | `public_api.check_company_code` | API |
| 28 | `/api/public/check-admin-email/` | `api-check-admin-email` | public | `public_api.check_admin_email` | API |
| 29 | `/api/public/check-company-email/` | `api-check-company-email` | public | `public_api.check_company_email` | API |

---

## ۶. REST API — Tenant (زیر `/api/<company_code>/`)

| # | URL | URL Name | App | View | Method | دسته |
|---|-----|----------|-----|------|--------|------|
| 30 | `/api/<code>/orders/` | `api-tenant:orders-list` | api | `OrderListAPI` | GET, POST | API |
| 31 | `/api/<code>/orders/<id>/` | `api-tenant:orders-detail` | api | `OrderDetailAPI` | GET, PUT | API |
| 32 | `/api/<code>/invoices/` | `api-tenant:invoices-list` | api | `InvoiceListAPI` | GET | API |
| 33 | `/api/<code>/notifications/` | `api-tenant:notifications-list` | api | `NotificationListAPI` | GET | API |
| 34 | `/api/<code>/services/` | `api-tenant:services-list` | api | `CompanyServiceListAPI` | GET | API |
| 35 | `/api/<code>/service-requests/` | `api-tenant:service-requests-list` | api | `ServiceRequestListAPI` | GET, POST | API |
| 36 | `/api/<code>/customers/` | `api-tenant:customers-list` | api | `CustomerListAPI` | GET, POST | API |
| 37 | `/api/<code>/customers/<id>/` | `api-tenant:customers-detail` | api | `CustomerDetailAPI` | GET, PUT | API |
| 38 | `/api/<code>/technicians/` | `api-tenant:technicians-list` | api | `TechnicianListAPI` | GET | API |
| 39 | `/api/<code>/dashboard/` | `api-tenant:dashboard` | api | `DashboardAPI` | GET | API |

---

## ۷. REST API — Platform

| # | URL | URL Name | App | View | Method | دسته |
|---|-----|----------|-----|------|--------|------|
| 40 | `/api/platform/companies/` | `api-platform:platform-companies` | api | `PlatformCompanyListAPI` | GET | API |
| 41 | `/api/platform/reports/` | `api-platform:platform-reports` | api | `PlatformReportsAPI` | GET | API |

---

## ۸. صفحه عمومی شرکت (زیر `/<company_code>/`) — بدون auth

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 42 | `/<code>/` | `tenants:home` | tenants | `views.company_home` | `tenants/home.html` | همه | PUBLIC |
| 43 | `/<code>/request/` | `tenants:request` | tenants | `views.service_request_view` | `tenants/request_form.html` یا `tenants/request_disabled.html` | همه | PUBLIC |
| 44 | `/<code>/request/status/` | `tenants:request_status` | tenants | `views.service_request_status` | `tenants/request_status.html` | همه | PUBLIC |

---

## ۹. احراز هویت Tenant (لگسی)

| # | URL | URL Name | App | View | توضیح | دسته |
|---|-----|----------|-----|------|-------|------|
| 45 | `/<code>/login/` | `accounts_auth:login` | accounts | `tenant_login` | ریدایرکت دائم به `/login/?company=<code>` | REDIRECT |
| 46 | `/<code>/login/logout/` | `accounts_auth:logout` | accounts | `tenant_logout` | خروج و ریدایرکت به `/login/` | PRIVATE |

---

## ۱۰. پنل مدیر/اپراتور (زیر `/<code>/admin/`)

### داشبورد

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 47 | `/<code>/admin/` | `dashboard:home` | dashboard | `dashboard_home` | `dashboard/home.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |

### تنظیمات شرکت

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 48 | `/<code>/admin/page/` | `tenants:admin_page` | tenants | `admin_page_edit` | `tenants/admin_page_edit.html` | COMPANY_ADMIN | ADMIN |
| 49 | `/<code>/admin/settings/` | `tenants:admin_company_settings` | tenants | `admin_company_settings` | `tenants/admin_company_settings.html` | COMPANY_ADMIN | ADMIN |
| 50 | `/<code>/admin/custom-fields/` | `tenants:admin_custom_fields` | tenants | `admin_custom_fields` | `tenants/admin_custom_fields.html` | COMPANY_ADMIN | ADMIN |
| 51 | `/<code>/admin/settings/notifications/` | `tenants:admin_notification_settings` | tenants | `admin_notification_settings` | `tenants/admin_notification_settings.html` | COMPANY_ADMIN | ADMIN |
| 52 | `/<code>/admin/settings/operators/` | `tenants:admin_operator_list` | tenants | `admin_operator_list` | `tenants/admin_operator_list.html` | ⚠️ بدون decorator (P0-1) | ADMIN |
| 53 | `/<code>/admin/settings/operators/create/` | `tenants:admin_operator_create` | tenants | `admin_operator_create` | `tenants/admin_operator_create.html` | COMPANY_ADMIN | ADMIN |
| 54 | `/<code>/admin/settings/operators/<id>/edit/` | `tenants:admin_operator_edit` | tenants | `admin_operator_edit` | `tenants/admin_operator_edit.html` | COMPANY_ADMIN | ADMIN |
| 55 | `/<code>/admin/branding/` | `tenants:admin_branding` | tenants | `admin_branding` | `tenants/admin_branding.html` | COMPANY_ADMIN | ADMIN |

### Base Data (داده‌های پایه)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 56 | `/<code>/admin/base-data/` | `tenants:admin_base_data` | tenants | `admin_base_data_home` | `tenants/admin_base_data.html` | COMPANY_ADMIN | ADMIN |
| 57 | `/<code>/admin/base-data/categories/` | `tenants:admin_base_categories` | tenants | `admin_base_categories` | `tenants/admin_base_categories.html` | COMPANY_ADMIN | ADMIN |
| 58 | `/<code>/admin/base-data/categories/create/` | `tenants:admin_base_category_create` | tenants | `admin_base_category_create` | `tenants/admin_base_category_form.html` | COMPANY_ADMIN | ADMIN |
| 59 | `/<code>/admin/base-data/categories/<id>/edit/` | `tenants:admin_base_category_edit` | tenants | `admin_base_category_edit` | `tenants/admin_base_category_form.html` | COMPANY_ADMIN | ADMIN |
| 60 | `/<code>/admin/base-data/categories/<id>/toggle-active/` | `tenants:admin_base_category_toggle_active` | tenants | `admin_base_category_toggle_active` | — (redirect) | COMPANY_ADMIN | ADMIN |
| 61 | `/<code>/admin/base-data/categories/<id>/delete/` | `tenants:admin_base_category_delete` | tenants | `admin_base_category_delete` | `tenants/admin_base_category_delete.html` | COMPANY_ADMIN | ADMIN |
| 62 | `/<code>/admin/base-data/items/` | `tenants:admin_base_items` | tenants | `admin_base_items` | `tenants/admin_base_items.html` | COMPANY_ADMIN | ADMIN |
| 63 | `/<code>/admin/base-data/items/create/` | `tenants:admin_base_item_create` | tenants | `admin_base_item_create` | `tenants/admin_base_item_form.html` | COMPANY_ADMIN | ADMIN |
| 64 | `/<code>/admin/base-data/items/<id>/edit/` | `tenants:admin_base_item_edit` | tenants | `admin_base_item_edit` | `tenants/admin_base_item_form.html` | COMPANY_ADMIN | ADMIN |
| 65 | `/<code>/admin/base-data/items/<id>/delete/` | `tenants:admin_base_item_delete` | tenants | `admin_base_item_delete` | `tenants/admin_base_item_delete.html` | COMPANY_ADMIN | ADMIN |

### مدیریت تکنسین‌ها

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 66 | `/<code>/admin/technicians/` | `tenants:admin_technicians` | tenants | `admin_technician_list` | `tenants/admin_technicians.html` | COMPANY_ADMIN | ADMIN |
| 67 | `/<code>/admin/technicians/create/` | `tenants:admin_technician_create` | tenants | `admin_technician_create` | `tenants/admin_technician_form.html` | COMPANY_ADMIN | ADMIN |
| 68 | `/<code>/admin/technicians/rates/` | `tenants:admin_technician_rate_overview` | tenants | `admin_technician_rate_overview` | `tenants/admin_technician_rates.html` | COMPANY_ADMIN | ADMIN |
| 69 | `/<code>/admin/technicians/<id>/edit/` | `tenants:admin_technician_edit` | tenants | `admin_technician_edit` | `tenants/admin_technician_form.html` | COMPANY_ADMIN | ADMIN |
| 70 | `/<code>/admin/technicians/<id>/delete/` | `tenants:admin_technician_delete` | tenants | `admin_technician_delete` | `tenants/admin_technician_delete.html` | COMPANY_ADMIN | ADMIN |
| 71 | `/<code>/admin/technicians/<id>/toggle-active/` | `tenants:admin_technician_toggle_active` | tenants | `admin_technician_toggle_active` | — (redirect) | COMPANY_ADMIN | ADMIN |
| 72 | `/<code>/admin/technicians/<id>/ledger/` | `tenants:admin_technician_ledger` | payouts | `technician_ledger` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 73 | `/<code>/admin/technicians/<id>/statement/` | `tenants:admin_technician_statement` | payouts | `technician_statement` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 74 | `/<code>/admin/technicians/<id>/statement/print/` | `tenants:admin_technician_statement_print` | payouts | `technician_statement_print` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 75 | `/<code>/admin/technicians/<id>/statement/pdf/` | `tenants:admin_technician_statement_pdf` | payouts | `technician_statement_pdf` | — (PDF binary) | COMPANY_ADMIN | ADMIN |
| 76 | `/<code>/admin/technicians/<id>/statement/export/` | `tenants:admin_technician_statement_export` | payouts | `technician_statement_export` | — (CSV/Excel) | COMPANY_ADMIN | ADMIN |
| 77 | `/<code>/admin/technicians/<id>/ledger/settlement/` | `tenants:admin_technician_settlement` | payouts | `technician_settlement` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |

### مدیریت مشتریان

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 78 | `/<code>/admin/customers/` | `tenants:admin_customers` | tenants | `admin_customer_list` | `tenants/admin_customers.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 79 | `/<code>/admin/customers/<id>/` | `tenants:admin_customer_detail` | tenants | `admin_customer_detail` | `tenants/admin_customer_detail.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 80 | `/<code>/admin/customers/lookup/` | `tenants:admin_customer_lookup` | tenants | `admin_customer_lookup` | — (JSON AJAX) | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |

### مدیریت سفارشات

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 81 | `/<code>/admin/orders/` | `tenants:admin_orders` | tenants | `admin_orders` | `tenants/admin_orders.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 82 | `/<code>/admin/orders/create/` | `tenants:admin_order_create` | tenants | `admin_order_create` | `tenants/admin_order_create.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 83 | `/<code>/admin/orders/<id>/` | `tenants:admin_order_detail` | tenants | `admin_order_detail` | `tenants/admin_order_detail.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 84 | `/<code>/admin/orders/<id>/edit/` | `tenants:admin_order_edit` | tenants | `admin_order_edit` | `tenants/admin_order_edit.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 85 | `/<code>/admin/orders/<id>/assign/` | `tenants:admin_order_assign` | tenants | `admin_order_assign` | `tenants/admin_order_assign.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 86 | `/<code>/admin/orders/<id>/cancel-request/approve/` | `tenants:admin_cancel_request_approve` | tenants | `admin_cancel_request_approve` | — (redirect) | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 87 | `/<code>/admin/orders/<id>/cancel-request/reject/` | `tenants:admin_cancel_request_reject` | tenants | `admin_cancel_request_reject` | — (redirect) | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 88 | `/<code>/admin/orders/<id>/return-to-cycle/` | `tenants:admin_order_return_to_cycle` | tenants | `admin_order_return_to_cycle` | — (redirect) | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 89 | `/<code>/admin/requests/` | `tenants:admin_requests` | tenants | `admin_request_list` | `tenants/admin_requests.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |

### مدیریت فاکتورها (ادمین)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 90 | `/<code>/admin/invoices/` | `tenants:admin_invoices` | tenants | `admin_invoice_list` | `tenants/admin_invoices.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 91 | `/<code>/admin/orders/<id>/invoice/create/` | `tenants:admin_invoice_create_from_order` | tenants | `admin_invoice_create_from_order` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 92 | `/<code>/admin/invoices/<id>/` | `tenants:admin_invoice_detail` | tenants | `admin_invoice_detail` | `tenants/admin_invoice_detail.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 93 | `/<code>/admin/invoices/<id>/edit/` | `tenants:admin_invoice_edit` | tenants | `admin_invoice_edit` | `tenants/admin_invoice_edit.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 94 | `/<code>/admin/invoices/<public_code>/print/` | `tenants:admin_invoice_print` | tenants | `admin_invoice_print` | `invoices/print.html` | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 95 | `/<code>/admin/invoices/<id>/cancel-request/<req_id>/review/` | `tenants:admin_invoice_cancel_request_review` | tenants | `admin_invoice_cancel_request_review` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |

### گالری

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 96 | `/<code>/admin/gallery/` | `tenants:admin_gallery` | tenants | `admin_gallery_list` | `tenants/admin_gallery.html` | COMPANY_ADMIN | ADMIN |
| 97 | `/<code>/admin/gallery/create/` | `tenants:admin_gallery_create` | tenants | `admin_gallery_create` | `tenants/admin_gallery_form.html` | COMPANY_ADMIN | ADMIN |
| 98 | `/<code>/admin/gallery/<id>/edit/` | `tenants:admin_gallery_edit` | tenants | `admin_gallery_edit` | `tenants/admin_gallery_form.html` | COMPANY_ADMIN | ADMIN |
| 99 | `/<code>/admin/gallery/<id>/delete/` | `tenants:admin_gallery_delete` | tenants | `admin_gallery_delete` | `tenants/admin_gallery_delete.html` | COMPANY_ADMIN | ADMIN |

### پرداخت‌ها و درگاه (ادمین)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 100 | `/<code>/admin/payment-gateway/` | `tenants:admin_payment_gateway` | tenants | `tenant_gateway_settings` | `tenants/admin_payment_gateway.html` | COMPANY_ADMIN | ADMIN |
| 101 | `/<code>/admin/payment-gateway/test/` | `tenants:admin_payment_gateway_test` | tenants | `tenant_gateway_test` | `tenants/admin_payment_gateway_test.html` | COMPANY_ADMIN | ADMIN |
| 102 | `/<code>/admin/payment/merchant-profile/` | `tenants:admin_merchant_profile` | tenants | `merchant_profile_view` | `tenants/merchant_profile.html` | COMPANY_ADMIN | ADMIN |
| 103 | `/<code>/admin/payment/merchant-profile/edit-request/` | `tenants:admin_merchant_profile_edit_request` | tenants | `merchant_profile_edit_request_view` | `tenants/merchant_profile_edit_request.html` | COMPANY_ADMIN | ADMIN |
| 104 | `/<code>/admin/payment/merchant-profile/document/<field>/` | `tenants:admin_merchant_profile_document` | tenants | `serve_profile_document` | — (binary) | COMPANY_ADMIN | ADMIN |
| 105 | `/<code>/admin/payments/operations/` | `tenants:admin_payment_operations` | payments | `company_payment_operations` | `payments/operations_company.html` | COMPANY_ADMIN | ADMIN |
| 106 | `/<code>/admin/payments/split-snapshots/` | `tenants:admin_split_snapshots` | payouts | `split_snapshot_list` | `payouts/split_snapshot_list.html` | COMPANY_ADMIN | ADMIN |
| 107 | `/<code>/admin/payments/split-snapshots/<id>/` | `tenants:admin_split_snapshot_detail` | payouts | `split_snapshot_detail` | `payouts/split_snapshot_detail.html` | COMPANY_ADMIN | ADMIN |
| 108 | `/<code>/admin/payments/gateway-reconciliation/` | `tenants:admin_gateway_reconciliation` | payouts | `gateway_reconciliation` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |

### گزارش‌های مالی

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 109 | `/<code>/admin/financial-reports/summary/` | `tenants:financial_summary` | tenants | `financial_summary` | `tenants/financial_reports/summary.html` | COMPANY_ADMIN | ADMIN |
| 110 | `/<code>/admin/financial-reports/technicians/` | `tenants:financial_technician_breakdown` | tenants | `technician_breakdown` | `tenants/financial_reports/technician_breakdown.html` | COMPANY_ADMIN | ADMIN |
| 111 | `/<code>/admin/financial-reports/invoices/` | `tenants:financial_invoice_settlement` | tenants | `invoice_settlement_detail` | `tenants/financial_reports/invoice_settlement_detail.html` | COMPANY_ADMIN | ADMIN |
| 112 | `/<code>/admin/financial-reports/cash-control/` | `tenants:financial_cash_control` | tenants | `cash_control` | `tenants/financial_reports/cash_control.html` | COMPANY_ADMIN | ADMIN |
| 113 | `/<code>/admin/financial-reports/platform-fees/` | `tenants:financial_platform_fees` | tenants | `platform_fee_report` | `tenants/financial_reports/platform_fee_report.html` | COMPANY_ADMIN | ADMIN |
| 114 | `/<code>/admin/financial-reports/audit/` | `tenants:financial_audit` | tenants | `audit_report` | `tenants/financial_reports/audit_report.html` | COMPANY_ADMIN | ADMIN |

### گزارش‌ها و تخفیف

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 115 | `/<code>/admin/reports/` | `reports:list` | reports | `report_list` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 116 | `/<code>/admin/reports/customer-segments/` | `reports:customer_segments` | reports | `customer_segment_report` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 117 | `/<code>/admin/reports/discount-campaigns/` | `reports:discount_campaign_list` | reports | `discount_campaign_list` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 118 | `/<code>/admin/reports/discount-campaigns/new/` | `reports:discount_campaign_new` | reports | `discount_campaign_create_from_segment` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 119 | `/<code>/admin/reports/discount-campaigns/manual/` | `reports:discount_campaign_manual` | reports | `discount_campaign_create_manual` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 120 | `/<code>/admin/reports/discount-campaigns/customer/<id>/new/` | `reports:discount_campaign_single_customer` | reports | `discount_campaign_single_customer` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 121 | `/<code>/admin/reports/discount-campaigns/<id>/` | `reports:discount_campaign_detail` | reports | `discount_campaign_detail` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |

### پیامک (SMS)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 122 | `/<code>/admin/sms/` | `sms:outbox` | sms | `sms_outbox_admin_list` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 123 | `/<code>/admin/sms/templates/` | `sms:template_list` | sms | `sms_template_list` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 124 | `/<code>/admin/sms/templates/create/` | `sms:template_create` | sms | `sms_template_create` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 125 | `/<code>/admin/sms/templates/<pk>/edit/` | `sms:template_edit` | sms | `sms_template_edit` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 126 | `/<code>/admin/sms/templates/<pk>/toggle/` | `sms:template_toggle` | sms | `sms_template_toggle` | — (redirect) | COMPANY_ADMIN | ADMIN |
| 127 | `/<code>/admin/sms/outbox/` | `sms:outbox_list` | sms | `sms_outbox_admin_list` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 128 | `/<code>/admin/sms/outbox/<pk>/` | `sms:outbox_detail` | sms | `sms_outbox_detail` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 129 | `/<code>/admin/sms/outbox/<pk>/send-now/` | `sms:outbox_send_now` | sms | `sms_outbox_send_now` | — (redirect) | COMPANY_ADMIN | ADMIN |
| 130 | `/<code>/admin/sms/outbox/bulk-retry/` | `sms:outbox_bulk_retry` | sms | `sms_outbox_bulk_retry` | — (redirect) | COMPANY_ADMIN | ADMIN |
| 131 | `/<code>/admin/sms/diagnostics/` | `sms:diagnostics` | sms | `sms_diagnostics` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 132 | `/<code>/admin/sms/inbox/` | `sms:inbox_list` | sms | `sms_inbox_list` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |
| 133 | `/<code>/admin/sms/inbox/<pk>/` | `sms:inbox_detail` | sms | `sms_inbox_detail` | نیازمند بررسی بیشتر | COMPANY_ADMIN | ADMIN |

### اعتبار پیامک (SMS Credit)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 134 | `/<code>/admin/sms-credit/` | `tenants:admin_sms_credit` | platform_core | `tenant_sms_credit` | `tenants/admin_sms_credit.html` | COMPANY_ADMIN | ADMIN |
| 135 | `/<code>/admin/sms-credit/recharge/` | `tenants:admin_sms_recharge` | platform_core | `tenant_sms_recharge` | `tenants/admin_sms_recharge.html` | COMPANY_ADMIN | ADMIN |
| 136 | `/<code>/admin/sms-credit/transactions/` | `tenants:admin_sms_transactions` | platform_core | `tenant_sms_transactions` | `tenants/admin_sms_transactions.html` | COMPANY_ADMIN | ADMIN |
| 137 | `/<code>/admin/sms-credit/invoices/` | `tenants:admin_sms_invoices` | platform_core | `tenant_sms_invoices` | `tenants/admin_sms_invoices.html` | COMPANY_ADMIN | ADMIN |
| 138 | `/<code>/admin/sms-credit/invoices/<id>/` | `tenants:admin_sms_invoice_detail` | platform_core | `tenant_sms_invoice_detail` | `tenants/admin_sms_invoice_detail.html` | COMPANY_ADMIN | ADMIN |

### تنظیمات ارتباطات

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 139 | `/<code>/admin/communication-settings/` | `tenants:admin_communication_settings` | platform_core | `tenant_comm_settings` | `tenants/admin_comm_settings.html` | COMPANY_ADMIN | ADMIN |
| 140 | `/<code>/admin/communication-settings/cause/<key>/` | `tenants:admin_comm_cause_detail` | platform_core | `tenant_comm_cause_detail` | `tenants/admin_comm_cause_detail.html` | COMPANY_ADMIN | ADMIN |
| 141 | `/<code>/admin/communication-settings/template/<key>/` | `tenants:admin_sms_template_view` | platform_core | `tenant_sms_template_view` | `tenants/admin_sms_template_view.html` | COMPANY_ADMIN | ADMIN |

### اعلان‌های ادمین

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 142 | `/<code>/admin/notifications/` | `notifications:list` | notifications | `notification_list` | نیازمند بررسی بیشتر | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 143 | `/<code>/admin/notifications/mark-all-read/` | `notifications:mark_all_read` | notifications | `notification_mark_all_read` | — (redirect) | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |
| 144 | `/<code>/admin/notifications/<id>/read/` | `notifications:mark_read` | notifications | `notification_mark_read` | — (redirect) | COMPANY_ADMIN, COMPANY_STAFF | ADMIN |

---

## ۱۱. پنل تکنسین (زیر `/<code>/tech/`)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 145 | `/<code>/tech/` | `dashboard_technician:home` | dashboard | `technician_home` | `dashboard/technician_home.html` | TECHNICIAN | TECH |
| 146 | `/<code>/tech/orders/` | `orders_technician:orders_root_redirect` | orders | `RedirectView → available/` | — | TECHNICIAN | TECH |
| 147 | `/<code>/tech/orders/available/` | `orders_technician:available` | orders | `technician_available_orders` | `orders/technician_available.html` | TECHNICIAN | TECH |
| 148 | `/<code>/tech/orders/my/` | `orders_technician:my_orders` | orders | `technician_my_orders` | `orders/technician_my_orders.html` | TECHNICIAN | TECH |
| 149 | `/<code>/tech/orders/<id>/` | `orders_technician:detail` | orders | `order_detail` | `orders/detail.html` | TECHNICIAN | TECH |
| 150 | `/<code>/tech/orders/<id>/accept/` | `orders_technician:accept` | orders | `order_accept` | — (redirect) | TECHNICIAN | TECH |
| 151 | `/<code>/tech/orders/<id>/complete/` | `orders_technician:complete` | orders | `order_complete` | — (redirect) | TECHNICIAN | TECH |
| 152 | `/<code>/tech/orders/<id>/cancel/` | `orders_technician:cancel` | orders | `order_cancel` | — (redirect) | TECHNICIAN | TECH |
| 153 | `/<code>/tech/orders/<id>/status/` | `orders_technician:status_update` | orders | `technician_status_update` | — (redirect) | TECHNICIAN | TECH |
| 154 | `/<code>/tech/orders/<id>/invoice/create/` | `orders_technician:invoice_create` | orders | `technician_invoice_create` (redirect) | — | TECHNICIAN | TECH |
| 155 | `/<code>/tech/invoices/` | `invoices_technician:list` | invoices | `technician_invoice_list` | `orders/technician_invoices.html` | TECHNICIAN | TECH |
| 156 | `/<code>/tech/invoices/order/<id>/create/` | `invoices_technician:create_from_order` | invoices | `technician_invoice_create` | `orders/technician_invoice_create.html` | TECHNICIAN | TECH |
| 157 | `/<code>/tech/invoices/<id>/` | `invoices_technician:detail` | invoices | `technician_invoice_detail` | `tenants/technician_invoice_detail.html` | TECHNICIAN | TECH |
| 158 | `/<code>/tech/invoices/<id>/cancel-request/` | `invoices_technician:cancel_request` | invoices | `technician_invoice_cancel_request` | — (redirect) | TECHNICIAN | TECH |
| 159 | `/<code>/tech/invoices/<id>/cash-paid/` | `invoices_technician:cash_paid` | invoices | `technician_invoice_mark_cash_paid` | — (redirect) | TECHNICIAN | TECH |
| 160 | `/<code>/tech/notifications/` | `notifications_technician:list` | notifications | `notification_list` | نیازمند بررسی بیشتر | TECHNICIAN | TECH |
| 161 | `/<code>/tech/notifications/mark-all-read/` | `notifications_technician:mark_all_read` | notifications | `notification_mark_all_read` | — (redirect) | TECHNICIAN | TECH |
| 162 | `/<code>/tech/notifications/<id>/read/` | `notifications_technician:mark_read` | notifications | `notification_mark_read` | — (redirect) | TECHNICIAN | TECH |

---

## ۱۲. صفحات مشتری/عمومی Tenant

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 163 | `/<code>/invoices/` | `invoices:list` | invoices | `invoice_list` | `invoices/list.html` | authenticated | PRIVATE |
| 164 | `/<code>/invoices/<id>/` | `invoices:detail` | invoices | `invoice_detail` | `invoices/detail.html` | authenticated | PRIVATE |
| 165 | `/<code>/invoices/<id>/pay/` | `invoices:pay` | invoices | `invoice_pay` | `payments/invoice_checkout.html` | authenticated | PRIVATE |
| 166 | `/<code>/invoices/<id>/discount/` | `invoices:apply_discount` | invoices | `invoice_apply_discount` | — (redirect) | authenticated | PRIVATE |
| 167 | `/<code>/invoices/public/<public_code>/` | `invoices:public_detail` | invoices | `public_invoice_detail` | `invoices/detail.html` | همه (بدون auth) | PUBLIC |
| 168 | `/<code>/invoices/public/<public_code>/discount/` | `invoices:public_apply_discount` | invoices | `public_invoice_apply_discount` | — (redirect) | همه | PUBLIC |
| 169 | `/<code>/invoices/public/<public_code>/print/` | `invoices:print` | invoices | `invoice_print` | `invoices/print.html` | همه | PUBLIC |
| 170 | `/<code>/payments/` | `payments:list` | payments | `payment_list` | `payments/list.html` | authenticated | PRIVATE |
| 171 | `/<code>/payments/callback/` | `payments:callback` | payments | `payment_callback` | `payments/result.html` | همه (PSP callback) | PUBLIC |
| 172 | `/i/<public_code>/` | `invoice_short_public` | invoices | `short_public_invoice_detail` | `invoices/detail.html` | همه | PUBLIC |
| 173 | `/<code>/customer/` | `tenants:customer_home_redirect` | tenants | `redirect_customer_to_public` | — (redirect) | همه | REDIRECT |

---

## ۱۳. پنل مالک پلتفرم (زیر `/owner-platform/`)

### داشبورد و گزارش

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 174 | `/owner-platform/` | `platform_core:root` | platform_core | `platform_dashboard` | `platform_core/dashboard.html` | PLATFORM_OWNER | PLATFORM |
| 175 | `/owner-platform/dashboard/` | `platform_core:dashboard` | platform_core | `platform_dashboard` | `platform_core/dashboard.html` | PLATFORM_OWNER | PLATFORM |
| 176 | `/owner-platform/reports/` | `platform_core:reports` | platform_core | `platform_reports` | `platform_core/reports.html` | PLATFORM_OWNER | PLATFORM |

### مدیریت شرکت‌ها

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 177 | `/owner-platform/companies/` | `platform_core:companies` | platform_core | `company_list` | `platform_core/company_list.html` | PLATFORM_OWNER | PLATFORM |
| 178 | `/owner-platform/companies/create/` | `platform_core:company_create` | platform_core | `company_create` | `platform_core/company_form.html` | PLATFORM_OWNER | PLATFORM |
| 179 | `/owner-platform/companies/<id>/` | `platform_core:company_detail` | platform_core | `company_detail` | `platform_core/company_detail.html` | PLATFORM_OWNER | PLATFORM |
| 180 | `/owner-platform/companies/<id>/edit/` | `platform_core:company_edit` | platform_core | `company_edit` | `platform_core/company_form.html` | PLATFORM_OWNER | PLATFORM |
| 181 | `/owner-platform/companies/<id>/activate/` | `platform_core:company_activate` | platform_core | `company_activate` | — (redirect) | PLATFORM_OWNER | PLATFORM |
| 182 | `/owner-platform/companies/<id>/deactivate/` | `platform_core:company_deactivate` | platform_core | `company_deactivate` | — (redirect) | PLATFORM_OWNER | PLATFORM |
| 183 | `/owner-platform/companies/<id>/templates/` | `platform_core:company_comm_templates` | platform_core | `company_templates_list` | `platform_core/comm_templates/company_list.html` | PLATFORM_OWNER | PLATFORM |
| 184 | `/owner-platform/companies/<id>/templates/create/` | `platform_core:company_comm_template_create` | platform_core | `company_template_create` | `platform_core/comm_templates/company_form.html` | PLATFORM_OWNER | PLATFORM |
| 185 | `/owner-platform/companies/<id>/templates/<tid>/edit/` | `platform_core:company_comm_template_edit` | platform_core | `company_template_edit` | `platform_core/comm_templates/company_form.html` | PLATFORM_OWNER | PLATFORM |
| 186 | `/owner-platform/companies/<id>/templates/<tid>/reset/` | `platform_core:company_comm_template_reset` | platform_core | `company_template_reset` | — (redirect) | PLATFORM_OWNER | PLATFORM |

### پلن‌ها و اشتراک‌ها

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 187 | `/owner-platform/plans/` | `platform_core:plans` | platform_core | `plan_list` | `platform_core/plan_list.html` | PLATFORM_OWNER | PLATFORM |
| 188 | `/owner-platform/plans/create/` | `platform_core:plan_create` | platform_core | `plan_create` | `platform_core/plan_form.html` | PLATFORM_OWNER | PLATFORM |
| 189 | `/owner-platform/plans/<id>/edit/` | `platform_core:plan_edit` | platform_core | `plan_edit` | `platform_core/plan_form.html` | PLATFORM_OWNER | PLATFORM |
| 190 | `/owner-platform/subscriptions/` | `platform_core:subscriptions` | platform_core | `subscription_list` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 191 | `/owner-platform/subscriptions/create/` | `platform_core:subscription_create` | platform_core | `subscription_create` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 192 | `/owner-platform/subscriptions/<id>/edit/` | `platform_core:subscription_edit` | platform_core | `subscription_edit` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 193 | `/owner-platform/subscriptions/<id>/activate/` | `platform_core:subscription_activate` | platform_core | `subscription_activate` | — (redirect) | PLATFORM_OWNER | PLATFORM |
| 194 | `/owner-platform/subscriptions/<id>/cancel/` | `platform_core:subscription_cancel` | platform_core | `subscription_cancel` | — (redirect) | PLATFORM_OWNER | PLATFORM |

### پیامک پلتفرم

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 195 | `/owner-platform/platform-sms/` | `platform_core:platform_sms` | platform_core | `platform_sms_index` | `platform_core/platform_sms/index.html` | PLATFORM_OWNER | PLATFORM |
| 196 | `/owner-platform/platform-sms/message-types/` | `platform_core:platform_sms_message_types` | platform_core | `platform_sms_message_types` | `platform_core/platform_sms/message_types.html` | PLATFORM_OWNER | PLATFORM |
| 197 | `/owner-platform/platform-sms/templates/` | `platform_core:platform_sms_templates` | platform_core | `platform_sms_templates` | `platform_core/platform_sms/templates.html` | PLATFORM_OWNER | PLATFORM |
| 198 | `/owner-platform/platform-sms/templates/create/` | `platform_core:platform_sms_template_create` | platform_core | `platform_sms_template_create` | `platform_core/platform_sms/template_form.html` | PLATFORM_OWNER | PLATFORM |
| 199 | `/owner-platform/platform-sms/templates/<id>/edit/` | `platform_core:platform_sms_template_edit` | platform_core | `platform_sms_template_edit` | `platform_core/platform_sms/template_form.html` | PLATFORM_OWNER | PLATFORM |
| 200 | `/owner-platform/platform-sms/templates/<id>/delete/` | `platform_core:platform_sms_template_delete` | platform_core | `platform_sms_template_delete` | — (redirect) | PLATFORM_OWNER | PLATFORM |
| 201 | `/owner-platform/platform-sms/provider/` | `platform_core:platform_sms_provider` | platform_core | `platform_sms_provider_settings` | `platform_core/platform_sms/provider.html` | PLATFORM_OWNER | PLATFORM |
| 202 | `/owner-platform/platform-sms/outbox/` | `platform_core:platform_sms_outbox` | platform_core | `platform_sms_outbox` | `platform_core/platform_sms/outbox.html` | PLATFORM_OWNER | PLATFORM |
| 203 | `/owner-platform/platform-sms/outbox/process/` | `platform_core:platform_sms_process_outbox` | platform_core | `platform_sms_process_outbox` | — (redirect) | PLATFORM_OWNER | PLATFORM |
| 204 | `/owner-platform/platform-sms/outbox/<id>/` | `platform_core:platform_sms_outbox_detail` | platform_core | `platform_sms_outbox_detail` | `platform_core/platform_sms/detail.html` | PLATFORM_OWNER | PLATFORM |
| 205 | `/owner-platform/platform-sms/outbox/<id>/send-now/` | `platform_core:platform_sms_outbox_send_now` | platform_core | `platform_sms_outbox_send_now` | — (redirect) | PLATFORM_OWNER | PLATFORM |

### صورت‌حساب پیامک

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 206 | `/owner-platform/sms-billing/` | `platform_core:sms_billing` | platform_core | `sms_billing_index` | `platform_core/sms_billing/index.html` | PLATFORM_OWNER | PLATFORM |
| 207 | `/owner-platform/sms-billing/settings/` | `platform_core:sms_billing_settings` | platform_core | `sms_billing_settings` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 208 | `/owner-platform/sms-billing/companies/` | `platform_core:sms_billing_companies` | platform_core | `sms_billing_companies` | `platform_core/sms_billing/companies.html` | PLATFORM_OWNER | PLATFORM |
| 209 | `/owner-platform/sms-billing/transactions/` | `platform_core:sms_billing_transactions` | platform_core | `sms_billing_transactions` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 210 | `/owner-platform/sms-billing/invoices/` | `platform_core:sms_billing_invoices` | platform_core | `sms_billing_invoices` | `platform_core/sms_billing/invoices.html` | PLATFORM_OWNER | PLATFORM |
| 211 | `/owner-platform/sms-billing/invoices/<id>/` | `platform_core:sms_billing_invoice_detail` | platform_core | `sms_billing_invoice_detail` | `platform_core/sms_billing/invoice_detail.html` | PLATFORM_OWNER | PLATFORM |
| 212 | `/owner-platform/sms-billing/invoices/<id>/mark-paid/` | `platform_core:sms_billing_invoice_mark_paid` | platform_core | `sms_billing_invoice_mark_paid` | — (redirect) | PLATFORM_OWNER | PLATFORM |

### پیام‌رسانی داخلی

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 213 | `/owner-platform/messages/` | `platform_core:messages` | platform_core | `message_index` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 214 | `/owner-platform/messages/inbox/` | `platform_core:messages_inbox` | platform_core | `message_inbox` | `platform_core/messages/inbox.html` | PLATFORM_OWNER | PLATFORM |
| 215 | `/owner-platform/messages/outbox/` | `platform_core:messages_outbox` | platform_core | `message_outbox` | `platform_core/messages/outbox.html` | PLATFORM_OWNER | PLATFORM |
| 216 | `/owner-platform/messages/create/` | `platform_core:messages_create` | platform_core | `message_create` | `platform_core/messages/create.html` | PLATFORM_OWNER | PLATFORM |
| 217 | `/owner-platform/messages/<id>/` | `platform_core:messages_detail` | platform_core | `message_detail` | `platform_core/messages/detail.html` | PLATFORM_OWNER | PLATFORM |

### قالب‌های ارتباطی

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 218 | `/owner-platform/communication-templates/` | `platform_core:comm_templates` | platform_core | `comm_template_list` | `platform_core/comm_templates/list.html` | PLATFORM_OWNER | PLATFORM |
| 219 | `/owner-platform/communication-templates/create/` | `platform_core:comm_template_create` | platform_core | `comm_template_create` | `platform_core/comm_templates/form.html` | PLATFORM_OWNER | PLATFORM |
| 220 | `/owner-platform/communication-templates/<id>/` | `platform_core:comm_template_detail` | platform_core | `comm_template_detail` | `platform_core/comm_templates/detail.html` | PLATFORM_OWNER | PLATFORM |
| 221 | `/owner-platform/communication-templates/<id>/edit/` | `platform_core:comm_template_edit` | platform_core | `comm_template_edit` | `platform_core/comm_templates/form.html` | PLATFORM_OWNER | PLATFORM |

### درگاه پرداخت (پلتفرم)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 222 | `/owner-platform/payment-gateways/` | `platform_core:platform_gateways` | platform_core | `platform_gateway_index` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 223 | `/owner-platform/payment-gateways/settings/` | `platform_core:platform_gateway_settings` | platform_core | `platform_gateway_settings` | `platform_core/payment_gateways/settings.html` | PLATFORM_OWNER | PLATFORM |
| 224 | `/owner-platform/payment-gateways/test/` | `platform_core:platform_gateway_test` | platform_core | `platform_gateway_test` | `platform_core/payment_gateways/test.html` | PLATFORM_OWNER | PLATFORM |

### پرداخت‌ها (پلتفرم)

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 225 | `/owner-platform/payments/operations/` | `platform_core:platform_payment_operations` | payments | `platform_payment_operations` | `payments/operations_platform.html` | PLATFORM_OWNER | PLATFORM |
| 226 | `/owner-platform/payment-split-snapshots/` | `platform_core:split_snapshots` | platform_core | `split_snapshot_list` | `payouts/split_snapshot_list.html` | PLATFORM_OWNER | PLATFORM |
| 227 | `/owner-platform/payment-split-snapshots/<id>/` | `platform_core:split_snapshot_detail` | platform_core | `split_snapshot_detail` | `payouts/split_snapshot_detail.html` | PLATFORM_OWNER | PLATFORM |

### KYC / پروفایل پذیرنده

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 228 | `/owner-platform/merchant-profiles/` | `platform_core:merchant_profiles` | platform_core | `merchant_profile_list` | `platform_core/merchant_profile_list.html` | PLATFORM_OWNER | PLATFORM |
| 229 | `/owner-platform/merchant-profiles/<id>/` | `platform_core:merchant_profile_detail` | platform_core | `merchant_profile_detail` | `platform_core/merchant_profile_detail.html` | PLATFORM_OWNER | PLATFORM |
| 230 | `/owner-platform/merchant-profiles/<id>/document/<field>/` | `platform_core:merchant_profile_document` | platform_core | `serve_profile_document` | — (binary) | PLATFORM_OWNER | PLATFORM |
| 231 | `/owner-platform/merchant-profile-change-requests/` | `platform_core:merchant_profile_change_requests` | platform_core | `change_request_list` | `platform_core/merchant_profile_change_request_list.html` | PLATFORM_OWNER | PLATFORM |
| 232 | `/owner-platform/merchant-profile-change-requests/<id>/` | `platform_core:merchant_profile_change_request_detail` | platform_core | `change_request_detail` | `platform_core/merchant_profile_change_request_detail.html` | PLATFORM_OWNER | PLATFORM |
| 233 | `/owner-platform/merchant-profile-change-requests/<id>/document/<field>/` | `platform_core:merchant_profile_change_request_document` | platform_core | `serve_change_request_document` | — (binary) | PLATFORM_OWNER | PLATFORM |

### تأیید مالی تکنسین‌ها

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 234 | `/owner-platform/technician-financial-verifications/` | `platform_core:technician_verifications` | platform_core | `verification_list` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 235 | `/owner-platform/technician-financial-verifications/<id>/` | `platform_core:technician_verification_detail` | platform_core | `verification_detail` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |

### سیاست بازیابی رمز

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 236 | `/owner-platform/password-reset-policy/` | `platform_core:password_reset_policy` | platform_core | `policy_list` | `platform_core/password_reset_policy/list.html` | PLATFORM_OWNER | PLATFORM |
| 237 | `/owner-platform/password-reset-policy/<id>/` | `platform_core:password_reset_policy_edit` | platform_core | `policy_edit` | `platform_core/password_reset_policy/edit.html` | PLATFORM_OWNER | PLATFORM |

### درخواست‌های تغییر قالب پیامک

| # | URL | URL Name | App | View | Template | نقش مجاز | دسته |
|---|-----|----------|-----|------|----------|----------|------|
| 238 | `/owner-platform/sms-template-requests/` | `platform_core:owner_sms_template_requests` | platform_core | `request_list` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 239 | `/owner-platform/sms-template-requests/<id>/` | `platform_core:owner_sms_template_request_detail` | platform_core | `request_detail` | نیازمند بررسی بیشتر | PLATFORM_OWNER | PLATFORM |
| 240 | `/owner-platform/sms-template-requests/<id>/approve/` | `platform_core:owner_sms_template_request_approve` | platform_core | `request_approve` | — (redirect) | PLATFORM_OWNER | PLATFORM |
| 241 | `/owner-platform/sms-template-requests/<id>/reject/` | `platform_core:owner_sms_template_request_reject` | platform_core | `request_reject` | — (redirect) | PLATFORM_OWNER | PLATFORM |

---

## ۱۴. ریدایرکت‌های لگسی

| # | URL | URL Name | توضیح | دسته |
|---|-----|----------|-------|------|
| 242 | `/loginlogin/` | `legacy_loginlogin` | ریدایرکت به `/owner-platform/dashboard/` یا `/login/` | REDIRECT |
| 243 | `/loginlogin/<path>` | `legacy_loginlogin_sub` | ریدایرکت به `/owner-platform/<path>` | REDIRECT |
| 244 | `/<code>/technician/` | `tenants:legacy_technician_redirect` | ریدایرکت به `/<code>/tech/` | REDIRECT |
| 245 | `/<code>/orders/` | `tenants:legacy_orders_redirect` | ریدایرکت به پنل مناسب | REDIRECT |
| 246 | `/<code>/orders/<subpath>` | `tenants:legacy_orders_catch_all` | ریدایرکت به پنل مناسب | REDIRECT |
| 247 | `/<code>/reports/` | `tenants:legacy_reports_redirect` | ریدایرکت به `/<code>/admin/reports/` | REDIRECT |
| 248 | `/<code>/notifications/` | `tenants:legacy_notifications_redirect` | ریدایرکت به پنل مناسب | REDIRECT |

---

## خلاصه آماری

| دسته | تعداد URL |
|------|-----------|
| SYSTEM | 4 |
| PUBLIC | 18 |
| PRIVATE (auth required) | 6 |
| ADMIN (COMPANY_ADMIN/STAFF) | 96 |
| TECH (TECHNICIAN) | 18 |
| PLATFORM (PLATFORM_OWNER) | 68 |
| API | 21 |
| REDIRECT | 7 |
| **جمع کل** | **≈ 238** |
