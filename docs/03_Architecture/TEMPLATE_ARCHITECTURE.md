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
├── base_dashboard.html         ← Master dashboard layout (role-aware)
├── layouts/
│   ├── public.html             ← Public/marketing pages layout
│   ├── auth.html               ← Login, registration layout
│   ├── error.html              ← Error pages layout
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

### `base_dashboard.html`

The master template for all authenticated dashboard pages.

- Checks `request.user.role == "TECHNICIAN"` to choose layout branch
- Shows `pw_change_snoozed` banner if user must change password
- Imports: `htmx`, Tailwind CSS, `Alpine.js` (or similar)
- RTL layout (Persian, right-to-left)
- Sidebar slides from right side: `fixed inset-y-0 right-0`

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
