---
Title: Template Architecture
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: templates/base_dashboard.html, templates/layouts/, templates/includes/
Source of Truth: Code
Depends On: SYSTEM_ARCHITECTURE.md
Related Documents: ../08_Site_Map/05_TEMPLATE_MAP.md, ../08_Site_Map/02_ROLE_BASED_SITE_MAP.md
Reusable Across Projects: No
---

# Template Architecture

---

## Template Folder Structure

```
templates/
├── base.html                   ← Bare HTML shell (theme CSS, Alpine.js, no chrome)
├── base_dashboard.html         ← Orphaned/legacy file — 0 templates extend it (verified 2026-07-01). Do not use for new work.
├── layouts/
│   ├── dashboard.html          ← ACTUAL master dashboard layout (role-aware) — 142 templates extend this
│   ├── public.html             ← Public/marketing pages layout
│   ├── public_payment.html     ← Dedicated public payment/checkout layout (no sidebar, no admin nav, no auth-only controls) — added EPIC-002 Issue 001
│   ├── auth.html                ← Login, registration layout
│   ├── error.html               ← Error pages layout
│   └── invoice_print.html      ← Print-optimized invoice layout
├── includes/
│   ├── nav_platform.html       ← Platform owner sidebar navigation
│   ├── nav_customer.html       ← Customer sidebar navigation
│   ├── settings_center.html    ← Settings hub widget (obfuscated CSS classes)
│   └── components/             ← Shared UI components (badge, stat_card, etc.)
├── components/                 ← DUPLICATE of includes/components/ (4 files overlap)
├── dashboard/                  ← Dashboard home templates
├── tenants/                    ← Admin panel templates (63+ files)
├── orders/                     ← Technician order templates
├── invoices/                   ← Invoice templates
├── payments/                   ← Payment templates
├── notifications/              ← Notification templates
├── platform_core/              ← Platform owner panel templates
├── public/                     ← Public pages templates
└── accounts/                   ← Auth templates
```

Total: 199+ templates, approximately 168 unique (excluding duplicates).

---

## Layout Hierarchy

```
base_dashboard.html
  ├── TECHNICIAN role → sticky header + bottom navigation (5 items, mobile-first)
  │     ├── داشبورد → /<code>/tech/
  │     ├── سفارش جدید → /<code>/tech/orders/available/
  │     ├── سفارش‌های من → /<code>/tech/orders/my/
  │     ├── فاکتورها → /<code>/tech/invoices/
  │     └── اعلان‌ها → /<code>/tech/notifications/
  │
  └── ADMIN/authenticated → sidebar + header with hamburger
        ├── nav_platform.html (for PLATFORM_OWNER)
        ├── nav_customer.html (for CUSTOMER)
        └── admin sidebar (in base_dashboard.html)
```

---

## Key Layout Files

### `layouts/dashboard.html` (verified 2026-07-01 — this is the live master layout, not `base_dashboard.html`)

The master template for all authenticated dashboard pages. Extends `base.html`.

- Renders sidebar nav via `{% block sidebar_nav %}`, gated by `request.user.role`
- Shows `pw_change_snoozed` banner if user must change password
- Imports: theme CSS, Jalali datepicker JS, number formatter JS, Alpine.js
- RTL layout (Persian, right-to-left)
- Sidebar slides from right side

> **Note:** `templates/base_dashboard.html` also exists on disk and was previously documented as the master dashboard layout, but 0 templates currently extend it (verified via repo-wide grep, 2026-07-01). Treat it as orphaned/legacy — do not extend it for new work.

### `layouts/public_payment.html`

Added for EPIC-002 Issue 001 (2026-07-01). Extends `base.html` directly. A minimal public layout for anonymous, unauthenticated payment/checkout pages — branding-only header, single content block, minimal footer. Explicitly excludes: sidebar, admin navigation, logout link, notification bell, dark-mode toggle, and any internal admin URLs. Used by `templates/payments/invoice_checkout.html`.

### `layouts/public.html`

Used by: public marketing pages, service request form, company home page

### `layouts/auth.html`

Used by: login, registration, password reset pages

### `layouts/invoice_print.html`

Used by: invoice PDF/print pages (no navigation, print-optimized)

### `layouts/error.html`

Used by: 404, 403, 500 error pages

---

## Known Template Issues

### Public Payment Page Used Admin Dashboard Layout (Fixed — EPIC-002 Issue 001)

`templates/payments/invoice_checkout.html` (the anonymous, unauthenticated invoice payment/checkout page at `/<code>/invoices/<id>/pay/`) previously extended `layouts/dashboard.html` and unconditionally force-included `includes/nav_admin.html` (the full internal admin navigation menu) regardless of authentication state. Fixed by introducing `layouts/public_payment.html` and switching the checkout template to extend it. See `docs/12_Epic_002_Product_Polish/ISSUE_001_PUBLIC_PAYMENT_LAYOUT_AUDIT.md` for the full audit and implementation record.

### Duplicate Component Templates

Four component templates exist in two locations:

| In `components/` | In `includes/components/` |
|---|---|
| `badge.html` | `badge.html` |
| `empty_state.html` | `empty_state.html` |
| `stat_card.html` | `stat_card.html` |
| `status_badge.html` | `status_badge.html` |

A change to one location does not affect the other. This causes maintenance risk and potential UI inconsistency.

### Customer Dashboard

`/<code>/customer/` redirects to the public company page since Phase 24. The template `dashboard/customer_home.html` still exists but is only reached via `/<code>/customer/dashboard/` which itself redirects. The customer experience is incomplete.

### Deprecated Templates

Several templates appear deprecated but may still be referenced:
- `tenants/operator/old_*.html` — Needs Verification
- `communication/old_templates/` — Needs Verification

---

## RTL Considerations

- All templates use RTL layout (Persian)
- Sidebar is on the right: `right-0`
- Admin sidebar toggle uses `translate-x-full` for right-side slide
- Bottom nav for technicians is RTL-compatible
- Test on Safari iOS and Chrome Android — both must render correctly
