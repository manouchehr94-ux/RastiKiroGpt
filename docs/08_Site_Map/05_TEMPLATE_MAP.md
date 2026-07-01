# ۰۵ — نقشه قالب‌های HTML

**مبنا:** بررسی مستقیم دایرکتوری `templates/`، خواندن view‌ها  
**تاریخ:** ۱ ژوئیه ۲۰۲۶  
**تعداد کل قالب شناسایی‌شده:** ۱۹۹+

---

## ۱. لایه‌بندی قالب‌ها (Layout Hierarchy)

```
base.html (نیازمند بررسی بیشتر — پایه اصلی)
├── base_dashboard.html
│   ├── templates برای همه پنل‌های authenticated
│   │   ├── TECHNICIAN: bottom nav bar (5 آیتم)
│   │   └── ADMIN/CUSTOMER/PLATFORM: sidebar + header
│   └── block: sidebar_nav (هر پنل پر می‌کند)
│
├── layouts/public.html
│   └── صفحات بازاریابی و عمومی
│
├── layouts/auth.html
│   └── صفحات ورود و ثبت‌نام
│
├── layouts/error.html
│   └── صفحات خطا (400، 403، 404، 500)
│
└── layouts/invoice_print.html
    └── چاپ فاکتور (بدون sidebar/header)
```

---

## ۲. قالب‌های لایه‌بندی

| قالب | توضیح | استفاده |
|------|-------|---------|
| `layouts/public.html` | Layout بازاریابی — header عمومی + footer | صفحات `/`، `/features/`، `/about/`، `/contact/`، `/pricing/` |
| `layouts/auth.html` | Layout احراز هویت — مینیمال | صفحات login، register، password-reset |
| `layouts/error.html` | Layout صفحات خطا | ۴۰۰، ۴۰۳، ۴۰۴، ۵۰۰ |
| `layouts/invoice_print.html` | Layout چاپ — بدون ناوبری | print قالب‌های فاکتور |
| `base_dashboard.html` | Layout اصلی پنل‌ها — sidebar + header | همه صفحات authenticated |

---

## ۳. صفحات خطا

| قالب | URL trigger | Layout |
|------|-------------|--------|
| `400.html` | Bad Request | `layouts/error.html` |
| `403.html` | Forbidden | `layouts/error.html` |
| `404.html` | Not Found | `layouts/error.html` |
| `500.html` | Server Error | `layouts/error.html` |

---

## ۴. قالب‌های احراز هویت

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `accounts/unified_login.html` | `/login/` | `unified_login` | `layouts/auth.html` | همه |
| `accounts/change_password_required.html` | `/account/change-password-required/` | `change_password_required` | `layouts/auth.html` | authenticated |
| `accounts/password_reset_form.html` | `/password-reset/` | `password_reset_form` | `layouts/auth.html` | همه |
| `accounts/password_reset_select.html` | `/password-reset/select/` | `password_reset_select` | `layouts/auth.html` | همه |
| `accounts/password_reset_otp.html` | `/password-reset/verify/` | `password_reset_verify` | `layouts/auth.html` | همه |
| `accounts/password_reset_confirm.html` | `/password-reset/confirm/` | `password_reset_confirm` | `layouts/auth.html` | همه |
| `accounts/platform_login.html` | (لگسی) | `platform_login` | `layouts/auth.html` | (deprecated) |
| `accounts/tenant_login.html` | (لگسی) | (deprecated) | `layouts/auth.html` | (deprecated) |

---

## ۵. قالب‌های عمومی (بازاریابی)

| قالب | URL | View | Layout |
|------|-----|------|--------|
| `public/home.html` | `/` | `views.home` | `layouts/public.html` |
| `public/features.html` | `/features/` | `views.features` | `layouts/public.html` |
| `public/pricing.html` | `/pricing/` | `views.pricing` | `layouts/public.html` |
| `public/about.html` | `/about/` | `views.about` | `layouts/public.html` |
| `public/contact.html` | `/contact/` | `views.contact` | `layouts/public.html` |
| `public/register.html` | `/register/` | `views.register` | `layouts/auth.html` |
| `public/register_verify.html` | `/register/verify/` | `views.register_verify` | `layouts/auth.html` |
| `public/register_success.html` | `/register/success/` | `views.register_success` | `layouts/auth.html` |

---

## ۶. قالب‌های عمومی شرکت (Tenant Public)

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `tenants/home.html` | `/<code>/` | `company_home` | `layouts/public.html` | همه |
| `tenants/request_form.html` | `/<code>/request/` | `service_request_view` | `layouts/public.html` | همه |
| `tenants/request_disabled.html` | `/<code>/request/` (اگر غیرفعال) | `service_request_view` | `layouts/public.html` | همه |
| `tenants/request_status.html` | `/<code>/request/status/` | `service_request_status` | `layouts/public.html` | همه |
| `tenants/request_success.html` | (inline در request) | درونی | `layouts/public.html` | همه |

---

## ۷. قالب‌های داشبورد

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `dashboard/home.html` | `/<code>/admin/` | `dashboard_home` | `base_dashboard.html` | COMPANY_ADMIN, COMPANY_STAFF |
| `dashboard/technician_home.html` | `/<code>/tech/` | `technician_home` | `base_dashboard.html` | TECHNICIAN |
| `dashboard/customer_home.html` | `/<code>/customer/` (deprecated) | `customer_home` | `base_dashboard.html` | CUSTOMER |
| `platform_core/dashboard.html` | `/owner-platform/dashboard/` | `platform_dashboard` | `base_dashboard.html` | PLATFORM_OWNER |

---

## ۸. قالب‌های سفارشات

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `orders/list.html` | (redirect مستقیم نمی‌رود) | `order_list` | `base_dashboard.html` | COMPANY_ADMIN, STAFF, CUSTOMER |
| `orders/detail.html` | `/<code>/tech/orders/<id>/` | `order_detail` | `base_dashboard.html` | TECHNICIAN, COMPANY_ADMIN |
| `orders/create.html` | (لگسی) | `order_create` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `orders/technician_available.html` | `/<code>/tech/orders/available/` | `technician_available_orders` | `base_dashboard.html` | TECHNICIAN |
| `orders/technician_my_orders.html` | `/<code>/tech/orders/my/` | `technician_my_orders` | `base_dashboard.html` | TECHNICIAN |
| `orders/technician_invoices.html` | `/<code>/tech/invoices/` | `technician_invoice_list` | `base_dashboard.html` | TECHNICIAN |
| `orders/technician_invoice_create.html` | `/<code>/tech/invoices/order/<id>/create/` | `technician_invoice_create` | `base_dashboard.html` | TECHNICIAN |
| `tenants/admin_orders.html` | `/<code>/admin/orders/` | `admin_orders` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `tenants/admin_order_create.html` | `/<code>/admin/orders/create/` | `admin_order_create` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `tenants/admin_order_detail.html` | `/<code>/admin/orders/<id>/` | `admin_order_detail` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `tenants/admin_order_edit.html` | `/<code>/admin/orders/<id>/edit/` | `admin_order_edit` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `tenants/admin_order_assign.html` | `/<code>/admin/orders/<id>/assign/` | `admin_order_assign` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |

---

## ۹. قالب‌های فاکتور

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `invoices/list.html` | `/<code>/invoices/` | `invoice_list` | `base_dashboard.html` | authenticated |
| `invoices/detail.html` | `/<code>/invoices/<id>/` | `invoice_detail` | `base_dashboard.html` | authenticated |
| `invoices/detail.html` | `/<code>/invoices/public/<code>/` | `public_invoice_detail` | `base_dashboard.html` | همه |
| `invoices/detail.html` | `/i/<public_code>/` | `short_public_invoice_detail` | `base_dashboard.html` | همه |
| `invoices/print.html` | `/<code>/invoices/public/<code>/print/` | `invoice_print` | `layouts/invoice_print.html` | همه |
| `tenants/admin_invoices.html` | `/<code>/admin/invoices/` | `admin_invoice_list` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `tenants/admin_invoice_detail.html` | `/<code>/admin/invoices/<id>/` | `admin_invoice_detail` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `tenants/admin_invoice_edit.html` | `/<code>/admin/invoices/<id>/edit/` | `admin_invoice_edit` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `tenants/technician_invoice_detail.html` | `/<code>/tech/invoices/<id>/` | `technician_invoice_detail` | `base_dashboard.html` | TECHNICIAN |

---

## ۱۰. قالب‌های پرداخت

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `payments/invoice_checkout.html` | `/<code>/invoices/<id>/pay/` | `invoice_pay` | `base_dashboard.html` | authenticated |
| `payments/list.html` | `/<code>/payments/` | `payment_list` | `base_dashboard.html` | authenticated |
| `payments/result.html` | `/<code>/payments/callback/` | `payment_callback` | `base_dashboard.html` | همه |
| `payments/operations_company.html` | `/<code>/admin/payments/operations/` | `company_payment_operations` | `base_dashboard.html` | COMPANY_ADMIN |
| `payments/operations_platform.html` | `/owner-platform/payments/operations/` | `platform_payment_operations` | `base_dashboard.html` | PLATFORM_OWNER |

---

## ۱۱. قالب‌های تکنسین و پرداخت تکنسین

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `payouts/split_snapshot_list.html` | `/<code>/admin/payments/split-snapshots/` | `split_snapshot_list` | `base_dashboard.html` | COMPANY_ADMIN |
| `payouts/split_snapshot_detail.html` | `/<code>/admin/payments/split-snapshots/<id>/` | `split_snapshot_detail` | `base_dashboard.html` | COMPANY_ADMIN |

---

## ۱۲. قالب‌های تنظیمات ادمین

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `tenants/admin_company_settings.html` | `/<code>/admin/settings/` | `admin_company_settings` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_custom_fields.html` | `/<code>/admin/custom-fields/` | `admin_custom_fields` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_notification_settings.html` | `/<code>/admin/settings/notifications/` | `admin_notification_settings` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_operator_list.html` | `/<code>/admin/settings/operators/` | `admin_operator_list` | `base_dashboard.html` | ⚠️ P0-1 |
| `tenants/admin_operator_create.html` | `/<code>/admin/settings/operators/create/` | `admin_operator_create` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_operator_edit.html` | `/<code>/admin/settings/operators/<id>/edit/` | `admin_operator_edit` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_page_edit.html` | `/<code>/admin/page/` | `admin_page_edit` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_branding.html` | `/<code>/admin/branding/` | `admin_branding` | `base_dashboard.html` | COMPANY_ADMIN |

---

## ۱۳. قالب‌های مشتریان

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `tenants/admin_customers.html` | `/<code>/admin/customers/` | `admin_customer_list` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |
| `tenants/admin_customer_detail.html` | `/<code>/admin/customers/<id>/` | `admin_customer_detail` | `base_dashboard.html` | COMPANY_ADMIN, STAFF |

---

## ۱۴. قالب‌های مدیریت تکنسین (ادمین)

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `tenants/admin_technicians.html` | `/<code>/admin/technicians/` | `admin_technician_list` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_technician_form.html` | `/<code>/admin/technicians/create/` و `edit/` | `admin_technician_create/edit` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_technician_rates.html` | `/<code>/admin/technicians/rates/` | `admin_technician_rate_overview` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_technician_delete.html` | `/<code>/admin/technicians/<id>/delete/` | `admin_technician_delete` | `base_dashboard.html` | COMPANY_ADMIN |

---

## ۱۵. قالب‌های داده‌های پایه

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `tenants/admin_base_data.html` | `/<code>/admin/base-data/` | `admin_base_data_home` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_base_categories.html` | `/<code>/admin/base-data/categories/` | `admin_base_categories` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_base_category_form.html` | `/<code>/admin/base-data/categories/create/` و `edit/` | چندین view | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_base_category_delete.html` | `/<code>/admin/base-data/categories/<id>/delete/` | `admin_base_category_delete` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_base_items.html` | `/<code>/admin/base-data/items/` | `admin_base_items` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_base_item_form.html` | `/<code>/admin/base-data/items/create/` و `edit/` | چندین view | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/admin_base_item_delete.html` | `/<code>/admin/base-data/items/<id>/delete/` | `admin_base_item_delete` | `base_dashboard.html` | COMPANY_ADMIN |

---

## ۱۶. قالب‌های گزارش مالی

| قالب | URL | View | Layout | نقش |
|------|-----|------|--------|-----|
| `tenants/financial_reports/summary.html` | `/<code>/admin/financial-reports/summary/` | `financial_summary` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/financial_reports/technician_breakdown.html` | `/<code>/admin/financial-reports/technicians/` | `technician_breakdown` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/financial_reports/invoice_settlement_detail.html` | `/<code>/admin/financial-reports/invoices/` | `invoice_settlement_detail` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/financial_reports/cash_control.html` | `/<code>/admin/financial-reports/cash-control/` | `cash_control` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/financial_reports/platform_fee_report.html` | `/<code>/admin/financial-reports/platform-fees/` | `platform_fee_report` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/financial_reports/audit_report.html` | `/<code>/admin/financial-reports/audit/` | `audit_report` | `base_dashboard.html` | COMPANY_ADMIN |
| `tenants/financial_reports/_nav.html` | (include در گزارش‌های مالی) | — | — | — |

---

## ۱۷. قالب‌های پیامک ادمین

| قالب | URL | نقش |
|------|-----|-----|
| `tenants/admin_sms_credit.html` | `/<code>/admin/sms-credit/` | COMPANY_ADMIN |
| `tenants/admin_sms_recharge.html` | `/<code>/admin/sms-credit/recharge/` | COMPANY_ADMIN |
| `tenants/admin_sms_transactions.html` | `/<code>/admin/sms-credit/transactions/` | COMPANY_ADMIN |
| `tenants/admin_sms_invoices.html` | `/<code>/admin/sms-credit/invoices/` | COMPANY_ADMIN |
| `tenants/admin_sms_invoice_detail.html` | `/<code>/admin/sms-credit/invoices/<id>/` | COMPANY_ADMIN |
| `tenants/admin_sms_template_view.html` | `/<code>/admin/communication-settings/template/<key>/` | COMPANY_ADMIN |
| `tenants/admin_comm_settings.html` | `/<code>/admin/communication-settings/` | COMPANY_ADMIN |
| `tenants/admin_comm_cause_detail.html` | `/<code>/admin/communication-settings/cause/<key>/` | COMPANY_ADMIN |
| `tenants/admin_payment_gateway.html` | `/<code>/admin/payment-gateway/` | COMPANY_ADMIN |
| `tenants/admin_payment_gateway_test.html` | `/<code>/admin/payment-gateway/test/` | COMPANY_ADMIN |

---

## ۱۸. قالب‌های پلتفرم (مالک)

| قالب | URL | Layout |
|------|-----|--------|
| `platform_core/dashboard.html` | `/owner-platform/dashboard/` | `base_dashboard.html` |
| `platform_core/reports.html` | `/owner-platform/reports/` | `base_dashboard.html` |
| `platform_core/company_list.html` | `/owner-platform/companies/` | `base_dashboard.html` |
| `platform_core/company_form.html` | `create/` و `edit/` | `base_dashboard.html` |
| `platform_core/company_detail.html` | `/owner-platform/companies/<id>/` | `base_dashboard.html` |
| `platform_core/plan_list.html` | `/owner-platform/plans/` | `base_dashboard.html` |
| `platform_core/plan_form.html` | `create/` و `edit/` | `base_dashboard.html` |
| `platform_core/messages/inbox.html` | `/owner-platform/messages/inbox/` | `base_dashboard.html` |
| `platform_core/messages/outbox.html` | `/owner-platform/messages/outbox/` | `base_dashboard.html` |
| `platform_core/messages/create.html` | `/owner-platform/messages/create/` | `base_dashboard.html` |
| `platform_core/messages/detail.html` | `/owner-platform/messages/<id>/` | `base_dashboard.html` |
| `platform_core/sms_billing/index.html` | `/owner-platform/sms-billing/` | `base_dashboard.html` |
| `platform_core/sms_billing/companies.html` | `/owner-platform/sms-billing/companies/` | `base_dashboard.html` |
| `platform_core/sms_billing/invoices.html` | `/owner-platform/sms-billing/invoices/` | `base_dashboard.html` |
| `platform_core/sms_billing/invoice_detail.html` | `/owner-platform/sms-billing/invoices/<id>/` | `base_dashboard.html` |
| `platform_core/platform_sms/index.html` | `/owner-platform/platform-sms/` | `base_dashboard.html` |
| `platform_core/platform_sms/outbox.html` | `/owner-platform/platform-sms/outbox/` | `base_dashboard.html` |
| `platform_core/platform_sms/detail.html` | `/owner-platform/platform-sms/outbox/<id>/` | `base_dashboard.html` |
| `platform_core/platform_sms/templates.html` | `/owner-platform/platform-sms/templates/` | `base_dashboard.html` |
| `platform_core/platform_sms/template_form.html` | `create/` و `edit/` | `base_dashboard.html` |
| `platform_core/platform_sms/provider.html` | `/owner-platform/platform-sms/provider/` | `base_dashboard.html` |
| `platform_core/platform_sms/message_types.html` | `/owner-platform/platform-sms/message-types/` | `base_dashboard.html` |
| `platform_core/comm_templates/list.html` | `/owner-platform/communication-templates/` | `base_dashboard.html` |
| `platform_core/comm_templates/form.html` | `create/` و `edit/` | `base_dashboard.html` |
| `platform_core/comm_templates/detail.html` | `/owner-platform/communication-templates/<id>/` | `base_dashboard.html` |
| `platform_core/comm_templates/company_list.html` | `/owner-platform/companies/<id>/templates/` | `base_dashboard.html` |
| `platform_core/comm_templates/company_form.html` | `create/` و `edit/` | `base_dashboard.html` |
| `platform_core/payment_gateways/settings.html` | `/owner-platform/payment-gateways/settings/` | `base_dashboard.html` |
| `platform_core/payment_gateways/test.html` | `/owner-platform/payment-gateways/test/` | `base_dashboard.html` |
| `platform_core/merchant_profile_list.html` | `/owner-platform/merchant-profiles/` | `base_dashboard.html` |
| `platform_core/merchant_profile_detail.html` | `/owner-platform/merchant-profiles/<id>/` | `base_dashboard.html` |
| `platform_core/merchant_profile_change_request_list.html` | `/owner-platform/merchant-profile-change-requests/` | `base_dashboard.html` |
| `platform_core/merchant_profile_change_request_detail.html` | `/owner-platform/merchant-profile-change-requests/<id>/` | `base_dashboard.html` |
| `platform_core/password_reset_policy/list.html` | `/owner-platform/password-reset-policy/` | `base_dashboard.html` |
| `platform_core/password_reset_policy/edit.html` | `/owner-platform/password-reset-policy/<id>/` | `base_dashboard.html` |
| `platform_core/merchant_profile.html` | `/<code>/admin/payment/merchant-profile/` | `base_dashboard.html` |
| `tenants/merchant_profile.html` | `/<code>/admin/payment/merchant-profile/` | `base_dashboard.html` |
| `tenants/merchant_profile_edit_request.html` | `/<code>/admin/payment/merchant-profile/edit-request/` | `base_dashboard.html` |

---

## ۱۹. قالب‌های اشتراکی (Components)

| قالب | نوع | استفاده در |
|------|-----|-----------|
| `components/breadcrumb.html` | ناوبری breadcrumb | صفحات داخلی |
| `components/pagination.html` | صفحه‌بندی لیست‌ها | همه لیست‌ها |
| `components/stat_card.html` | کارت آمار | داشبوردها |
| `components/status_badge.html` | badge وضعیت سفارش/فاکتور | جداول |
| `components/badge.html` | badge عمومی | جداول |
| `components/empty_state.html` | حالت خالی | لیست‌های خالی |
| `components/form_errors.html` | نمایش خطاهای فرم | همه فرم‌ها |
| `components/table_toolbar.html` | نوار ابزار جدول | لیست‌ها |
| `components/alert_message.html` | پیام alert | موفقیت/خطا |
| `components/page_header.html` | هدر صفحه | صفحات داخلی |
| `components/section_header.html` | هدر بخش | صفحات داخلی |
| `components/ui_core_preview.html` | (توسعه) UI preview | فقط توسعه |
| `includes/nav_platform.html` | sidebar پلتفرم | `/owner-platform/` |
| `includes/nav_customer.html` | sidebar مشتری | `/<code>/customer/` |
| `includes/settings_center.html` | بلوک مرکز تنظیمات | صفحات تنظیمات |
| `includes/components/badge.html` | (duplicate) | نیازمند بررسی بیشتر |
| `includes/components/empty_state.html` | (duplicate) | نیازمند بررسی بیشتر |
| `includes/components/stat_card.html` | (duplicate) | نیازمند بررسی بیشتر |
| `includes/components/status_badge.html` | (duplicate) | نیازمند بررسی بیشتر |
| `tenants/includes/field.html` | سطر فیلد فرم | فرم‌های tenants |
| `tenants/includes/readonly_row.html` | سطر فقط‌خواندنی | جزئیات tenants |
| `platform_core/platform_sms/_quick_actions.html` | دسترسی سریع SMS | پنل پلتفرم |

---

## ۲۰. قالب‌های مشکوک و نیازمند بررسی

| قالب | مشکل |
|------|-------|
| `tenants/admin_base_operators.html` | URL مستقیم پیدا نشد — ممکن است deprecated باشد |
| `tenants/admin_base_operator_form.html` | URL مستقیم پیدا نشد — ممکن است deprecated باشد |
| `tenants/admin_base_operator_delete.html` | URL مستقیم پیدا نشد — ممکن است deprecated باشد |
| `includes/components/badge.html` | تکراری با `components/badge.html` |
| `includes/components/empty_state.html` | تکراری با `components/empty_state.html` |
| `includes/components/stat_card.html` | تکراری با `components/stat_card.html` |
| `includes/components/status_badge.html` | تکراری با `components/status_badge.html` |
| `accounts/platform_login.html` | URL لگسی — احتمالاً unused |
| `accounts/tenant_login.html` | URL لگسی — احتمالاً unused |
| `dashboard/customer_home.html` | صفحه مشتری deprecated از Phase 24 |

---

## خلاصه آماری قالب‌ها

| دسته | تعداد |
|------|-------|
| Layout | 5 |
| خطا | 4 |
| احراز هویت | 8 |
| عمومی (بازاریابی) | 8 |
| عمومی Tenant | 5 |
| داشبورد | 4 |
| سفارشات | 13 |
| فاکتور | 9 |
| پرداخت | 5 |
| تنظیمات ادمین | 8 |
| داده‌های پایه | 7 |
| مشتریان | 2 |
| تکنسین‌ها | 4 |
| گزارش مالی | 7 |
| پیامک | 10 |
| پلتفرم | 37 |
| اشتراکی/Component | 22 |
| مشکوک/deprecated | 10 |
| **جمع** | **≈ 168 منحصربه‌فرد** |
