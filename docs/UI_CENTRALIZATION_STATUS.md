# وضعیت مرکزی‌سازی UI — رستی‌سرویس

## خلاصه پیشرفت

| فاز | هدف | Inline قبل | Inline بعد | حذف‌شده |
|------|------|-----------|-----------|---------|
| P21 | Financial reports (6 templates) | 120 | 97 | 23 |
| P22 | High-risk (5 templates) | 259 | 0 | 259 |
| P23 | Merchant/Platform/Auth | 158+ | — | 158 |
| **مجموع تا P23** | | **1034+** | **~876** | **~440** |

---

## گروه‌بندی Template‌ها

### ✅ کاملاً مرکزی‌شده (0 inline style)

- `templates/tenants/admin_invoice_detail.html`
- `templates/payouts/technician_ledger.html`
- `templates/payouts/technician_settlement.html`
- `templates/payouts/split_snapshot_list.html`
- `templates/payouts/split_snapshot_detail.html`
- `templates/tenants/financial_reports/summary.html`
- `templates/accounts/password_reset_confirm.html`
- `templates/accounts/tenant_login.html`
- `templates/accounts/platform_login.html`

### ⚠️ تا حد زیادی مرکزی‌شده (< 15 inline)

- `templates/tenants/merchant_profile.html` — ۱۳ باقی (فرم upload + conditional states)
- `templates/payments/operations_company.html` — ۵ باقی (alert banner conditionals)
- `templates/payments/operations_platform.html` — ۸ باقی (platform-specific grid)
- `templates/tenants/financial_reports/*` — ۱۵-۲۸ (table cell RTL alignment)
- `templates/accounts/*.html` — ۰-۱۳ (auth form layouts)

### 🔴 هنوز نیاز به بررسی

- `templates/public/pricing.html` — ۴۰ (marketing page)
- `templates/public/home.html` — ۳۲
- `templates/public/about.html` — ۳۰
- `templates/public/features.html` — ۲۰
- `templates/platform_core/sms_template_requests/*` — ۲۵
- `templates/sms/diagnostics.html` — ۲۳
- `templates/tenants/admin_operator_list.html` — ۲۴
- `templates/tenants/admin_order_create.html` — ۱۷
- `templates/tenants/admin_technician_form.html` — ۱۹
- `templates/components/ui_core_preview.html` — ۳۷ (dev-only preview)

---

## استثناها و دلایل

### Inline Style‌های قابل‌قبول

1. **RTL number alignment** (`text-align:left;direction:ltr;`) — لازم برای اعداد در جدول‌های RTL
2. **Conditional Django template colors** — `{% if x %}class-a{% else %}class-b{% endif %}` در بعضی موارد inline اجتناب‌ناپذیر
3. **Auth form specific spacing** — padding/margin خاص form container
4. **Marketing/public pages** — اولویت پایین‌تر، ریسک صفر

---

## وابستگی dashboard.css

| متریک | مقدار |
|--------|-------|
| خطوط کل | 1392 |
| کلاس‌هایی که duplicate با components.css دارند | ~30 |
| کلاس‌هایی که فقط در dashboard.css هستند | ~80 |
| Templates وابسته به dashboard.css | ~60+ |

**وضعیت:** `dashboard.css` هنوز حذف نشده. حذف نیاز به بررسی تمام ۶۰+ template دارد.

**توصیه فاز بعدی:**
1. شناسایی کلاس‌های dashboard.css که در هیچ template استفاده نمی‌شوند → حذف
2. کلاس‌های duplicate → redirect به components.css
3. کلاس‌های unique → انتقال به components.css/pages.css

---

## فاز‌های بعدی پیشنهادی

| فاز | هدف | ریسک |
|------|------|------|
| P24 | Public/marketing pages CSS | Low |
| P25 | Order/technician admin templates | Medium |
| P26 | SMS/notification templates | Low |
| P27 | dashboard.css cleanup/reduction | Medium |
| P28 | Responsive/mobile final pass | Medium |
