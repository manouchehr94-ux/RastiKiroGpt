# ممیزی کامل مرکزی‌سازی UI — رستی‌سرویس (P28)

---

## وضعیت کلی

| متریک | مقدار |
|--------|-------|
| **کل template‌ها** | 187 |
| **بدون inline style (کاملاً مرکزی)** | **83 (44%)** |
| **با inline style (نیاز به بررسی)** | 104 |
| **کل inline styles باقی‌مانده** | **691** |
| **CSS entrypoint** | `theme.css` → تمام صفحات |

---

## Template‌های کاملاً متصل (0 inline style)

**83 template** شامل:
- تمام P22 high-risk templates (invoice detail, ledger, settlement, snapshots)
- `financial_reports/summary.html` (P21)
- `admin_technician_form.html` (P27)
- Auth: `password_reset_confirm.html`, `tenant_login.html`, `platform_login.html`
- بسیاری از includes, components, base layouts

---

## Template‌های با بیشترین inline style (Top 20)

| # | فایل | Inline | دسته | ریسک |
|---|------|--------|------|------|
| 1 | `components/ui_core_preview.html` | 37 | Dev preview | None |
| 2 | `financial_reports/audit_report.html` | 28 | Table RTL | Low |
| 3 | `platform_core/sms_template_requests/detail.html` | 25 | SMS admin | Low |
| 4 | `platform_core/sms_template_requests/list.html` | 24 | SMS admin | Low |
| 5 | `sms/diagnostics.html` | 23 | SMS debug | Low |
| 6 | `platform_core/password_reset_policy/list.html` | 22 | Platform | Low |
| 7 | `financial_reports/cash_control.html` | 21 | Table RTL | Low |
| 8 | `financial_reports/invoice_settlement_detail.html` | 17 | Table RTL | Low |
| 9 | `financial_reports/technician_breakdown.html` | 16 | Table RTL | Low |
| 10 | `tenants/home.html` | 15 | Tenant public | Low |
| 11 | `financial_reports/platform_fee_report.html` | 15 | Table RTL | Low |
| 12 | `admin_notification_settings.html` | 15 | Settings | Low |
| 13 | `admin_base_categories.html` | 14 | Admin form | Medium |
| 14 | `platform_core/password_reset_policy/edit.html` | 14 | Platform | Low |
| 15 | `layouts/auth.html` | 14 | Layout | Low |
| 16 | `merchant_profile.html` | 13 | KYC form | Medium |
| 17 | `admin_sms_invoice_detail.html` | 13 | SMS billing | Low |
| 18 | `admin_sms_credit.html` | 13 | SMS credit | Low |
| 19 | `public/pricing.html` | 13 | Marketing | Low |
| 20 | `accounts/change_password_required.html` | 13 | Auth | Low |

---

## تحلیل inline styles باقی‌مانده

### قابل‌قبول (Acceptable Exceptions)

| نوع | تعداد تقریبی | دلیل |
|------|-----------|------|
| RTL table cells (`text-align:left;direction:ltr`) | ~100 | عددها باید LTR باشند |
| `display:none` (hidden fields) | ~15 | JS functionality |
| Grid layouts (`display:grid;grid-template-columns:...`) | ~20 | page-specific responsive |
| `position:absolute` (screen-reader) | ~5 | accessibility |

### قابل حذف (Should Migrate)

| نوع | تعداد تقریبی | کلاس جایگزین |
|------|-----------|-------------|
| Color hardcoded (`#64748b`, `#475569`) | ~40 | `.stat-card-hint`, `.section-title` |
| Spacing (`margin/padding` inline) | ~60 | `.mb-item`, `.mb-block` |
| Font/weight inline | ~30 | `.detail-value-strong`, `.public-card-title` |
| Background/border | ~25 | `.report-card`, `.card`, `.alert` |

---

## وابستگی‌های CSS Legacy

| فایل | خطوط | وضعیت |
|------|-------|--------|
| `dashboard.css` | 1392 | **Legacy** — 322 class، 30 overlap با components.css |
| `theme.css` | 32 | ✅ Central entrypoint |
| `tokens.css` | 262 | ✅ Design tokens |
| `components.css` | 1060+ | ✅ Shared components |
| `pages.css` | 1500+ | ✅ Page utilities |
| `layouts.css` | 654 | ✅ Layout system |
| `responsive.css` | 327 | ✅ Media queries |

---

## توصیه‌ها برای رسیدن به 100%

### فوری (Quick wins)

1. **SMS templates** (P28 scope: ~72 inline) — patterns مشابه P27
2. **Platform admin pages** (password_reset_policy, sms_template_requests: ~85) — low risk
3. **Notification settings** (admin_notification_settings: 15) — single file

### میان‌مدت

4. **Financial report tables** — RTL alignment inline‌ها قابل‌قبول‌اند، اما color/font-weight‌ها هنوز قابل migration
5. **`dashboard.css` reduction** — حذف 30 duplicate، شناسایی unused

### بلندمدت

6. **`ui_core_preview.html`** — dev-only، اولویت صفر
7. **Marketing pages remaining** (hero/grid) — page-specific layouts، acceptable
8. **100% target:** رسیدن به <100 inline style (از ~691 → ~140 acceptable exceptions)

---

## Definition of Done برای 100% Centralization

- [ ] تمام templates از `base.html` → `theme.css` load می‌کنند ✅ (P24)
- [ ] inline styles < 150 (فعلی: 691 → هدف: <150)
- [ ] تمام hardcoded hex colors حذف
- [ ] `dashboard.css` به <200 line رسیده
- [ ] تمام صفحات اصلی visual review شده
- [ ] تمام تست‌ها pass
