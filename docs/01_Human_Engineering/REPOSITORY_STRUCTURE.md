---
Title: Repository Structure Guide
Layer: Human Engineering
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: Full codebase scan
Source of Truth: Code
Depends On: []
Related Documents: ../03_Architecture/DJANGO_APP_ARCHITECTURE.md
Reusable Across Projects: No
---

# Repository Structure

---

## Top-Level Layout

```
Rasti chekFinal 10 tir/
├── apps/                   ← Django applications
├── config/                 ← Django settings and root URL config
├── templates/              ← All HTML templates (199+)
├── docs/                   ← Engineering Knowledge Base (this folder)
├── requirements.txt        ← Production dependencies
├── requirements-dev.txt    ← Development dependencies
├── manage.py               ← Django management command
├── .env.example            ← Environment variable template
└── static/                 ← Static files (CSS, JS, images)
```

---

## `apps/` — Application Code

```
apps/
├── accounts/           ← Users, auth, roles, permissions
│   ├── models.py           ← User model, UserRole choices
│   ├── permissions.py      ← @require_tenant_role, @require_platform_owner
│   ├── views.py            ← Login view (unified_login)
│   ├── urls_tenant_auth.py ← /<code>/login/, /<code>/logout/
│   └── urls_password_reset.py ← Password reset 4-step flow
│
├── api/                ← REST API (DRF)
│   ├── auth_views.py       ← Login/logout API (P0-2: logout broken)
│   ├── views.py            ← Tenant API views (P0-5: Customer.name bug)
│   └── urls.py             ← API URL routing
│
├── billing/            ← SaaS billing STUB (not implemented)
│
├── communication/      ← Company communication settings
│
├── dashboard/          ← Dashboard home views (role-based)
│   ├── views.py            ← dashboard_home, technician_home, customer_home
│   ├── urls.py             ← /<code>/admin/ home
│   ├── urls_technician.py  ← /<code>/tech/ home
│   └── urls_customer.py    ← /<code>/customer/ (redirects to public)
│
├── invoices/           ← Invoice lifecycle
│   ├── models.py
│   ├── services.py
│   ├── views.py
│   ├── urls.py             ← Customer + public invoice views
│   ├── urls_technician.py  ← Technician invoice views
│   └── urls_public_short.py ← /i/<code>/ short link
│
├── notifications/      ← In-app notifications
│   ├── catalog.py          ← 19 event type definitions
│   ├── services.py
│   ├── urls.py             ← Admin notification views
│   └── urls_technician.py  ← Technician notification views
│
├── orders/             ← Order lifecycle (technician side)
│   ├── models.py           ← Order model, OrderStatus choices
│   ├── services.py         ← Order business logic
│   ├── views.py            ← Technician order views
│   ├── urls_technician.py  ← /<code>/tech/orders/
│   └── technician_notifications.py  ← P0-6: if False at line 147
│
├── payouts/            ← Technician financials
│   ├── models.py           ← TechnicianLedgerEntry (immutable)
│   └── services.py         ← Ledger, settlement logic
│
├── payments/           ← PSP integration
│   ├── models.py           ← Payment, PaymentGateway
│   ├── services.py         ← Payment verification, commission
│   ├── views.py            ← Callback handler (public URL)
│   └── urls.py             ← payment_list, payment_callback
│
├── platform_core/      ← Platform owner operations
│   ├── views.py            ← All @require_platform_owner views
│   └── urls.py             ← /owner-platform/ routes
│
├── public/             ← Public-facing pages
│   ├── views.py            ← Company home, service request
│   └── urls.py             ← /public routes
│
├── reports/            ← Analytics
│   └── urls.py             ← Reports + discount campaign routes
│
├── sms/                ← SMS management
│   └── urls.py             ← Outbox, templates, inbox, diagnostics
│
└── tenants/            ← Core app: company management + ALL admin views
    ├── models.py           ← Company, CompanyPaymentSettings, CompanyFinancialPolicy
    ├── middleware.py        ← TenantMiddleware (sets request.company)
    ├── operator_access.py  ← OperatorPermissionMiddleware (P0-1 related)
    ├── services.py
    ├── views.py            ← Public company home view
    ├── views_admin.py      ← 2000+ lines: ALL admin views (P0-1 at line 2125)
    └── urls.py             ← 175 lines: ALL tenant URLs
```

---

## `config/` — Settings and Configuration

```
config/
├── settings/
│   ├── base.py         ← Base settings (P0-4: ALLOWED_HOSTS = ["*"] here)
│   ├── development.py  ← Local dev overrides
│   └── production.py   ← Production overrides
├── urls.py             ← Root URL configuration
└── wsgi.py             ← WSGI entry point
```

---

## `templates/` — All HTML Templates

```
templates/
├── base_dashboard.html         ← Master layout (role-aware)
├── layouts/                    ← 4 layout files
├── includes/                   ← Shared partials (nav, settings_center)
│   └── components/             ← Shared components (DUPLICATE of components/)
├── components/                 ← Also shared components (DUPLICATE risk)
├── dashboard/
├── tenants/                    ← Admin panel templates (63+ files)
├── orders/
├── invoices/
├── payments/
├── notifications/
├── platform_core/
├── public/
└── accounts/
```

Total: 199+ templates across 15+ subdirectories.

---

## `docs/` — Engineering Knowledge Base

See [../README.md](../README.md) for the complete docs structure.

---

## Key Files to Know

| File | Why it matters |
|---|---|
| `apps/tenants/views_admin.py` | Largest file — all admin views, P0-1 at line 2125 |
| `apps/accounts/permissions.py` | All permission decorators |
| `apps/tenants/middleware.py` | TenantMiddleware — foundation of multi-tenancy |
| `apps/orders/models.py` | Order model and status machine |
| `apps/payments/services.py` | Payment verification and commission logic |
| `apps/payouts/models.py` | TechnicianLedgerEntry (immutable) |
| `config/settings/base.py` | Base settings including P0-4 |
| `config/urls.py` | Root URL tree |
| `templates/base_dashboard.html` | Master dashboard layout |
