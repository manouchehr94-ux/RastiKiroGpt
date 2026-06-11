# نقشه راه نهایی مرکزی‌سازی UI — رستی‌سرویس (P25)

---

## A. معماری مرکزی CSS فعلی

```
base.html
  └── <link href="static/css/theme.css">
        ├── @import tokens.css      (221 lines — design tokens)
        ├── @import base.css        (377 lines — reset, font-face)
        ├── @import components.css  (1060+ lines — btn, card, badge, table, alert, empty-state)
        ├── @import layouts.css     (654 lines — sidebar, grid, shell)
        ├── @import pages.css       (1400+ lines — page utilities, financial, detail-row)
        ├── @import dashboard.css   (1392 lines — LEGACY)
        └── @import responsive.css  (327 lines — media queries)
```

**اصل:** تغییر یک token در `tokens.css` → تمام صفحات تحت تأثیر.

---

## B. Template گروه‌های کاملاً مرکزی‌شده (0 inline style)

| گروه | فاز |
|------|------|
| `admin_invoice_detail.html` | P22 |
| `technician_ledger.html` | P22 |
| `technician_settlement.html` | P22 |
| `split_snapshot_list.html` | P22 |
| `split_snapshot_detail.html` | P22 |
| `financial_reports/summary.html` | P21 |
| `accounts/password_reset_confirm.html` | P23 |
| `accounts/tenant_login.html` | P23 |
| `accounts/platform_login.html` | P23 |

---

## C. Template گروه‌های تا حد زیادی مرکزی‌شده

| گروه | باقی‌مانده | دلیل |
|------|-----------|------|
| Financial reports (5 file) | 97 | RTL table cell alignment |
| Merchant/KYC | 13 | File upload form + conditional states |
| Payment operations | 13 | Alert banner conditionals |
| Auth (6 files) | 33 | Auth form container spacing |

---

## D. فهرست inline style باقی‌مانده — Top 30

| # | فایل | تعداد | ریسک | حوزه |
|---|------|-------|------|------|
| 1 | `public/pricing.html` | 40 | Low | Marketing |
| 2 | `components/ui_core_preview.html` | 37 | None | Dev preview |
| 3 | `public/home.html` | 32 | Low | Marketing |
| 4 | `public/about.html` | 30 | Low | Marketing |
| 5 | `financial_reports/audit_report.html` | 28 | Low | Read-only table |
| 6 | `platform_core/sms_template_requests/detail.html` | 25 | Low | SMS admin |
| 7 | `admin_operator_list.html` | 24 | Medium | Admin form |
| 8 | `platform_core/sms_template_requests/list.html` | 24 | Low | SMS admin |
| 9 | `sms/diagnostics.html` | 23 | Low | SMS debug |
| 10 | `platform_core/password_reset_policy/list.html` | 22 | Low | Platform admin |
| 11 | `financial_reports/cash_control.html` | 21 | Low | Read-only table |
| 12 | `public/register.html` | 20 | Low | Registration |
| 13 | `public/features.html` | 20 | Low | Marketing |
| 14 | `admin_technician_form.html` | 19 | Medium | Admin form |
| 15 | `financial_reports/invoice_settlement_detail.html` | 17 | Low | Table RTL |
| 16 | `admin_order_create.html` | 17 | Medium | Admin form |
| 17 | `financial_reports/technician_breakdown.html` | 16 | Low | Table RTL |
| 18 | `tenants/home.html` | 15 | Low | Tenant public |
| 19 | `financial_reports/platform_fee_report.html` | 15 | Low | Table RTL |
| 20 | `admin_order_detail.html` | 15 | Medium | Admin display |

**مجموع:** ~876 inline style در ~106 فایل

---

## E. وضعیت dashboard.css

| متریک | مقدار |
|--------|-------|
| خطوط | 1392 |
| کلاس‌های یکتا | 322 |
| کلاس‌های overlap با components.css | **30** |
| Templates وابسته | ~60+ |

### کلاس‌های Overlap (duplicate)

این 30 کلاس هم در `dashboard.css` و هم در `components.css` تعریف شده‌اند.
`components.css` بعد از `dashboard.css` load می‌شود → components.css برنده.

### استراتژی migration

1. **فاز ۱ (P29):** کلاس‌های duplicate حذف از dashboard.css (30 class)
2. **فاز ۲:** کلاس‌های unique که فقط در 1-2 template استفاده‌اند → inline یا pages.css
3. **فاز ۳:** کلاس‌های unique پرکاربرد → انتقال به components.css
4. **فاز ۴:** dashboard.css خالی → حذف فایل + حذف @import از theme.css

---

## F. فازهای بعدی پیشنهادی

### P26 — Public/Marketing Pages Centralization

| آیتم | مقدار |
|------|-------|
| هدف | pricing, home, about, features, register templates |
| فایل‌ها | ~6 template |
| Inline | ~160 |
| ریسک | **Low** — صفحات marketing بدون form حساس |
| تغییر | inline → class |
| تغییر ندهید | SEO/content، form actions |
| تست | render 200، no sensitive data |
| بررسی بصری | /, /features/, /pricing/, /about/ |

### P27 — Orders/Admin Forms Centralization

| آیتم | مقدار |
|------|-------|
| هدف | order create/detail/edit, technician form, operator list |
| فایل‌ها | ~8 template |
| Inline | ~120 |
| ریسک | **Medium** — admin forms with POST actions |
| تغییر | inline → class، فقط presentation |
| تغییر ندهید | form logic, POST actions, CSRF |
| تست | render 200، CSRF preserved |
| بررسی بصری | /admin/orders/create/, /admin/technicians/ |

### P28 — SMS/Notification UI Centralization

| آیتم | مقدار |
|------|-------|
| هدف | SMS templates, diagnostics, platform SMS settings |
| فایل‌ها | ~6 template |
| Inline | ~95 |
| ریسک | **Low** — display/settings pages |
| تغییر | inline → class |
| تغییر ندهید | SMS logic, template rendering |
| تست | render 200 |
| بررسی بصری | /admin/sms/, /owner-platform/platform-sms/ |

### P29 — Dashboard.css Legacy Reduction

| آیتم | مقدار |
|------|-------|
| هدف | حذف 30 duplicate class، شناسایی unused classes |
| فایل‌ها | static/css/dashboard.css |
| ریسک | **Medium** — ممکن است ظاهر تغییر کند |
| تغییر | حذف duplicates، unused → remove |
| تغییر ندهید | هیچ template logic |
| تست | all pages render 200، visual review |
| بررسی بصری | تمام صفحات اصلی |

### P30 — Responsive/Mobile Final Pass

| آیتم | مقدار |
|------|-------|
| هدف | بررسی mobile breakpoints، sidebar collapse، table overflow |
| فایل‌ها | responsive.css + template adjustments |
| ریسک | **Medium** — mobile UX |
| تغییر | media queries، mobile-safe overflow |
| تغییر ندهید | desktop layout |
| تست | render 200 at 375px viewport |
| بررسی بصری | mobile emulator |

### P31 — Visual Regression Checklist

| آیتم | مقدار |
|------|-------|
| هدف | مستندسازی screenshot-based QA |
| فایل‌ها | docs/ only |
| ریسک | **None** |
| تغییر | documentation |
| تست | — |

---

## G. تعریف «تمام‌شده» (Definition of Done)

پروژه مرکزی‌سازی UI تکمیل است وقتی:

- [x] تمام base templates از theme.css load می‌کنند (P24 ✅)
- [x] tokens.css شامل تمام color/radius/shadow/spacing هست (P18 ✅)
- [x] components.css شامل btn/card/badge/table/alert/empty-state هست (P19 ✅)
- [x] pages.css شامل page utilities هست (P20-P22 ✅)
- [ ] inline styles به حداقل ضروری رسیده (<100 total)
- [ ] dashboard.css حذف یا reduced به <200 line
- [ ] تمام صفحات اصلی visual review شده
- [ ] تمام تست‌ها pass
- [ ] هیچ hardcoded hex color جدید اضافه نشده
