---
Title: Issue 001 — Public Payment Layout Audit
Layer: Epic 002 Product Polish
Audience: Human + AI
Status: Audit Complete — Awaiting Approval
Last Verified: 2026-07-01
Verified Against: apps/invoices/views.py, apps/invoices/views_public_short.py, apps/payments/views.py, templates/payments/invoice_checkout.html, templates/invoices/public_detail.html, templates/layouts/dashboard.html, templates/includes/nav_admin.html, templates/base.html, templates/base_dashboard.html
Source of Truth: Code (docs were out of date on template names — see Problem Confirmation)
Depends On: docs/03_Architecture/TEMPLATE_ARCHITECTURE.md, docs/08_Site_Map/01_URL_INVENTORY.md, docs/08_Site_Map/05_TEMPLATE_MAP.md
Related Documents: docs/04_Business_Rules/PAYMENT_RULES.md, docs/04_Business_Rules/INVOICE_RULES.md
Reusable Across Projects: No
---

# Issue 001 — Public Payment Layout Audit

## Summary

The actual public **payment/checkout page** (`invoice_pay`, served at `/<code>/invoices/<id>/pay/`) is intentionally unauthenticated ("anyone with the invoice link may pay") but renders using `templates/payments/invoice_checkout.html`, which extends `templates/layouts/dashboard.html` — the same master layout used by the authenticated company admin dashboard. Worse, the checkout template does not merely inherit the layout's role-gated sidebar; it **unconditionally overrides** the `sidebar_nav` block to force-include `includes/nav_admin.html`, the full internal admin navigation menu (orders, customers, operators, technicians, settings, payment gateway config, KYC, SMS credit, financial reports, etc.), regardless of whether the visitor is authenticated. This is the confirmed core defect behind Issue 001.

By contrast, the **public invoice detail page** (`invoice_pay`'s neighbor, `public_invoice_detail` / `short_public_invoice_detail`) already renders a fully self-contained standalone HTML document (`invoices/public_detail.html`) with no shared layout at all — it does not exhibit the dashboard-leakage problem, though it is also not using the Design System / `layouts/public.html` conventions.

The **payment result/callback page** (`payment_callback` → `payments/result.html`) extends `base.html` directly (the bare shell, no sidebar) and is already close to an acceptable minimal public page — it is not part of the core problem, but it is not using a named "public payment" layout either.

## Current Implementation

Three distinct pages are involved in the public payment journey. Only one has the confirmed layout defect (`invoice_checkout.html`).

| Page | URL | View | Template | Auth |
|---|---|---|---|---|
| Public invoice detail (tenant-scoped) | `/<code>/invoices/public/<public_code>/` | `apps.invoices.views.public_invoice_detail` | `invoices/public_detail.html` | None |
| Public invoice detail (short link) | `/i/<public_code>/` | `apps.invoices.views_public_short.short_public_invoice_detail` | `invoices/public_detail.html` | None |
| Invoice print | `/<code>/invoices/public/<public_code>/print/` | `apps.invoices.views.invoice_print` | `invoices/print.html` | None |
| **Payment checkout (the actual "payment page")** | `/<code>/invoices/<id>/pay/` | `apps.invoices.views.invoice_pay` | `payments/invoice_checkout.html` | **None (intentional)** |
| Payment result / PSP callback | `/<code>/payments/callback/` | `apps.payments.views.payment_callback` | `payments/result.html` | None |
| Payment list (private) | `/<code>/payments/` | `apps.payments.views.payment_list` | `payments/list.html` | `@require_tenant_auth` |

## URLs Found

- `apps/invoices/urls.py`
  - `path("public/<str:public_code>/", views.public_invoice_detail, name="public_detail")`
  - `path("public/<str:public_code>/print/", views.invoice_print, name="print")`
  - `path("<int:invoice_id>/pay/", views.invoice_pay, name="pay")` ← the payment page
- `apps/invoices/urls_public_short.py` → `path("", short_public_invoice_detail, name="invoice_short_public")` mounted at `/i/<public_code>/`
- `apps/payments/urls.py`
  - `path("", views.payment_list, name="list")`
  - `path("callback/", views.payment_callback, name="callback")`

Confirmed against `config/urls.py` include structure (mounted under `/<company_code>/invoices/` and `/<company_code>/payments/` respectively). Matches `docs/08_Site_Map/01_URL_INVENTORY.md` rows 165, 167, 169, 170, 171, 172 for URL paths, but the doc's **template column is wrong for the public detail rows** (see Problem Confirmation → Documentation Conflict).

## Views Found

- `apps/invoices/views.py`
  - `invoice_pay` (line 128) — **no permission decorator**. Docstring explicitly states: *"This endpoint intentionally does not require login: anyone with the invoice link may pay on behalf of the customer."* This is by design (ADR-level intent, not a bug) — tenant isolation is preserved via company-prefixed URL + company-scoped invoice lookup.
  - `public_invoice_detail` (line 80) — no decorator, renders `invoices/public_detail.html`.
  - `invoice_print` (line 97) — no decorator, renders `invoices/print.html` (already uses the isolated `layouts/invoice_print.html`... actually confirmed the print template is a standalone document, see below).
  - `invoice_apply_discount` / `public_invoice_apply_discount` — private vs. public discount application; the public variant already avoids leaking session messages onto public pages (see Tests Found).
- `apps/invoices/views_public_short.py` — `short_public_invoice_detail`, no auth, global lookup by unique `public_code`, renders `invoices/public_detail.html`.
- `apps/payments/views.py` — `payment_callback` (line 15, no decorator, public PSP callback) and `payment_list` (line 60, `@require_tenant_auth`).

## Templates Found

| Template | Extends | Contains dashboard/admin chrome? |
|---|---|---|
| `templates/payments/invoice_checkout.html` | `layouts/dashboard.html` | **Yes — sidebar shell, hamburger toggle, "پنل مدیریت" branding subtitle, dark-mode toggle, logout link, admin footer, and a hardcoded `{% include "includes/nav_admin.html" %}` in the `sidebar_nav` block (unconditional, not role-gated)** |
| `templates/invoices/public_detail.html` | *(none — standalone `<html>` document)* | No |
| `templates/invoices/print.html` | *(none — standalone `<html>` document, confirmed by reading the file; not `layouts/invoice_print.html` as `TEMPLATE_ARCHITECTURE.md` implies)* | No |
| `templates/payments/result.html` | `base.html` (bare shell, no sidebar) | No |
| `templates/payments/list.html` | `layouts/dashboard.html` | Yes — but this page is `@require_tenant_auth`-gated, so dashboard chrome is expected/correct here. |

`templates/includes/nav_admin.html` — the file force-included by `invoice_checkout.html` — contains links to: dashboard, orders, customers, requests, invoices, operators, technicians, technician rates, custom fields, base data, notifications, SMS outbox, SMS credit, communication settings, company settings, public page settings, payment gateway settings, merchant/KYC profile, reports, discount campaigns, payment operations, split snapshots, financial reports. All of these links point at `@require_tenant_role`/`@require_tenant_auth`-protected admin URLs, so clicking one as an anonymous user redirects to login — there is no direct backend data leak — but the full internal admin site-map and company branding is disclosed to any anonymous person holding a payment link.

## Current Base Layout

The payment checkout page currently extends **`templates/layouts/dashboard.html`** (142 templates extend this file — it is the real, live master dashboard layout). It in turn extends `templates/base.html` (bare HTML shell: theme CSS, Jalali datepicker JS, number formatter JS, Alpine.js).

## Problem Confirmation

**Confirmed.** `invoice_pay` — the one page in this flow that is genuinely "the public payment page" — renders the full company admin dashboard shell (sidebar, topbar, notification-bell markup, dark-mode toggle, logout link, footer) plus an unconditionally-included full admin navigation menu, to anonymous, unauthenticated visitors. This matches the Issue 001 backlog description exactly.

### Documentation Conflict (must be reported per protocol)

Two conflicts between docs and code were found and are reported here rather than silently resolved, per `docs/11_Project_Knowledge/SOURCE_OF_TRUTH.md` Rule 1:

1. **Layout file name mismatch.** `docs/03_Architecture/TEMPLATE_ARCHITECTURE.md` and `docs/04_Business_Rules/PAYMENT_RULES.md` describe `base_dashboard.html` as "the master template for all authenticated dashboard pages." In the current codebase, `templates/base_dashboard.html` exists on disk but **zero templates extend it** (`grep` confirmed 0 matches). The live master layout is `templates/layouts/dashboard.html` (142 templates extend it). `base_dashboard.html` appears to be an orphaned/legacy file. Docs need updating; code is authoritative.
2. **Template map inaccuracy.** `docs/08_Site_Map/05_TEMPLATE_MAP.md` (row for `/<code>/invoices/public/<code>/` and `/i/<public_code>/`) states the template is `invoices/detail.html` extending `base_dashboard.html`. The actual code (`apps/invoices/views.py:90`, `apps/invoices/views_public_short.py:48`) renders `invoices/public_detail.html`, a standalone document with no `{% extends %}` at all. `invoices/detail.html` is a *different* file used only by the private, authenticated `invoice_detail` view. This row in the site map needs correction.

These conflicts do not change the recommendation for Issue 001, but they mean **Issue 001's actual scope is narrower than the backlog phrasing suggests**: only the payment/checkout page (`invoice_checkout.html`) has the dashboard-leakage defect. The public invoice detail and print pages are already isolated (though inconsistent in styling — they use ad hoc inline `<style>` blocks rather than the shared theme/Design System).

## Privacy / Security Risk

- **No direct data leak.** All admin nav links route to `@require_tenant_role`/`@require_tenant_auth`-protected views; an anonymous visitor clicking them is redirected to `/login/`, not shown data.
- **Information disclosure (low-moderate).** The full internal admin site structure (URL paths, feature names: SMS credit, KYC/merchant profile, financial reports, discount campaigns, payment gateway settings) is disclosed to anyone with a payment link — including customers who are not company staff. This reveals internal tooling names and structure unnecessarily and is inconsistent with least-privilege UI exposure.
- **Session/identity confusion risk.** The layout renders `{% block logout_url %}/{{ company.code }}/login/logout/{% endblock %}` and `sidebar_user_name`/role-label blocks meant for authenticated staff. For an anonymous payer these render as empty/broken (no `request.user.get_full_name`), which is a UX defect, not a security one, but it signals the page was never designed for anonymous public use.
- **No multi-tenant isolation violation found.** The `invoice_pay` view correctly scopes the invoice lookup by `company=request.company` (`InvoiceSelector.get_by_id_for_company`), consistent with `MULTI_TENANCY.md`.

## UX Risk

- A customer paying an invoice sees a page branded as an internal "پنل مدیریت" (management panel) rather than a clean payment/checkout experience — this looks unprofessional and can reduce trust at the exact moment a customer is about to enter payment intent.
- The sidebar hamburger toggle, dark-mode toggle, and (empty) notification bell wrapper are irrelevant affordances for a one-time anonymous payment flow and add clutter/confusion, especially on mobile (this page is the primary mobile entry point for customers paying via SMS/link).
- No back-navigation context beyond a single "بازگشت به فاکتور" (back to invoice) link — acceptable, but buried inside dashboard chrome.

## Minimal Safe Fix

1. Create a new, dedicated public layout, e.g. `templates/layouts/public_payment.html`, extending `templates/base.html` directly (not `layouts/dashboard.html`). It should contain:
   - A minimal header showing only the **company name/branding** (`company.name`), no admin nav, no login/logout link, no dark-mode toggle, no notification bell.
   - A centered content area (reuse the same content block name, `{% block content %}`, so `invoice_checkout.html`'s existing `{% block content %}` body can be kept mostly as-is).
   - A minimal footer (optionally reusing the "© Rasti Service" line style already in `layouts/dashboard.html`'s footer, without admin-specific content).
   - RTL, Tailwind/theme.css compatible, consistent with existing design tokens (`--space-*`, `--color-*` custom properties already used throughout `invoice_checkout.html`).
2. Change `templates/payments/invoice_checkout.html` line 1 from `{% extends "layouts/dashboard.html" %}` to the new layout, and **remove** the hardcoded `{% block sidebar_nav %}{% include "includes/nav_admin.html" %}{% endblock %}` override (line 6) and the `sidebar_brand`/`logout_url` block overrides that only make sense for the dashboard shell (lines 4–6), replacing them with whatever blocks the new public layout defines (e.g. a single `{% block company_name %}`).
3. Leave `payments/list.html` untouched (correctly gated, correctly uses the dashboard layout).
4. Leave `invoices/public_detail.html`, `invoices/print.html`, and `payments/result.html` untouched for this issue — they do not exhibit the dashboard-leakage defect. (A follow-up could migrate them to the same new public layout for visual consistency, but that is out of scope per the "narrow change" rule — see Recommendation, Option B.)

## Files Expected to Change

If Option A is approved:

- **New file:** `templates/layouts/public_payment.html` (new dedicated public payment layout)
- **Modified:** `templates/payments/invoice_checkout.html` (change `{% extends %}` target; remove `sidebar_nav`/nav_admin override and dashboard-specific block overrides)
- **Possibly modified:** `templates/base.html` — only if the new layout needs a shared head/script hook not already exposed (expected: no change needed, `extra_head`/`extra_js`/`body` blocks already exist).

No changes expected to: `apps/invoices/views.py`, `apps/invoices/urls.py`, `apps/payments/views.py`, `apps/payments/urls.py`, any model, any migration, any Persian label text (all existing Persian strings can be preserved verbatim), any permission decorator.

## Tests Found

- `tests/test_public_invoice_message_leak.py` — covers `public_invoice_detail` and `short_public_invoice_detail` (the invoice *detail* page, not the checkout page). Confirms no session-message leakage on those two URLs. Does **not** touch `invoice_pay`.
- `tests/test_p14_payment_ops_navigation.py`, `tests/test_p35_final_actual_ui_fixes.py` — grepped for `invoice_pay`/`/pay/`, no matches; these cover admin-side payment operations navigation, not the public checkout page.
- **No test file in the repository references `invoice_pay`, `invoice_checkout.html`, or the `/pay/` URL at all** (confirmed via repo-wide grep across `tests/`).

## Tests Required

For the minimal fix (Option A), add a new test file (e.g. `tests/test_issue001_public_payment_layout.py`) covering:

1. `GET /<code>/invoices/<id>/pay/` as an **anonymous** client returns 200 (confirms the page is still reachable without login — regression guard for the "intentionally public" behavior documented in the view docstring).
2. The response does **not** contain admin-only nav strings, e.g. assert `"اپراتورها"`, `"نیروهای خدماتی"`, `"تعرفه‌های اجرت"`, `"اعتبار پیامک"`, `"گزارش مالی"` are absent from the response body (i.e., `nav_admin.html` content is gone).
3. The response does **not** link to `/admin/settings/operators/`, `/admin/technicians/`, `/admin/payment-gateway/`, etc. (assert absence of `/admin/` substrings tied to nav_admin hrefs).
4. The response still contains the invoice payment content (amount, invoice number, "ورود به درگاه پرداخت" button) — regression guard that the fix didn't break the payable-invoice flow.
5. The response still contains `company.name` for branding continuity.
6. Existing behavior for a non-payable invoice (`invoice.is_payable == False` branch, line 146–153) still renders correctly under the new layout.

## Documentation Updates Required (after implementation, not now)

- `docs/03_Architecture/TEMPLATE_ARCHITECTURE.md` — add `layouts/public_payment.html` to the Template Folder Structure and Key Layout Files sections; correct the `base_dashboard.html` vs `layouts/dashboard.html` naming conflict noted above.
- `docs/08_Site_Map/05_TEMPLATE_MAP.md` — update row 149 (`payments/invoice_checkout.html`) to reference the new layout instead of `base_dashboard.html`; correct rows 135/136 (public invoice detail) to show `invoices/public_detail.html` instead of `invoices/detail.html`.
- `docs/11_Project_Knowledge/KNOWN_RISKS.md` — this audit did not find a P0/P1-severity bug (no direct data leak), but the nav-disclosure issue could be logged as a new Medium-priority entry (e.g. `M-4 — Public payment checkout page exposes internal admin navigation`) until fixed, so it isn't lost if implementation is deferred.

## Risk Level

**Medium.** No multi-tenant isolation violation, no financial-calculation risk, no data leak to unauthorized parties. Risk is UX/information-disclosure and brand-trust related. The fix is template-only (no view, model, migration, or permission changes), which keeps implementation risk low — but the page is customer-facing and payment-adjacent, so any regression (e.g., breaking the "start_gateway" POST flow or discount-code form) has direct revenue impact and must be tested carefully.

## Recommendation

**Option A — Minimal fix.**

Create/reuse a dedicated public payment layout and change only `templates/payments/invoice_checkout.html` (plus the one new layout file). This directly resolves the confirmed defect (dashboard chrome + hardcoded admin nav on an anonymous payment page) without touching the invoice detail/print pages, which do not exhibit the defect and are already isolated standalone documents. This matches the "narrow change" principle in `docs/02_AI_Operating_System/AI_CODE_CHANGE_RULES.md` (Rule 2) and the EPIC-002 instruction to never solve multiple unrelated issues in one commit.

Option B (full public invoice/payment template cleanup — unifying `public_detail.html`, `print.html`, and `result.html` onto the same new layout for visual consistency) is reasonable future work but is broader than what Issue 001 requires and would touch files that currently work correctly; recommend tracking it as a separate follow-up issue rather than bundling it here.

Option C (defer) is not recommended — the defect is real, low-effort to fix, and customer-facing.

## Approval Required

Do not implement until approved.

Options:

A. Minimal fix — create/reuse public payment base layout and change only affected public payment templates. **(Recommended)**

B. Full public payment/invoice layout cleanup — standardize all public invoice/payment templates together.

C. Defer — leave as-is for now.

---

## Implementation Completed (2026-07-01)

Option A approved and implemented.

### Files Changed

- **New:** `templates/layouts/public_payment.html` — dedicated public payment layout. Extends `templates/base.html` directly. Reuses existing, already-styled `.public-shell` / `.public-nav` / `.public-nav-inner` / `.public-nav-brand` / `.public-main` / `.public-container` / `.public-footer` classes from `static/css/layouts.css` (no CSS files were added or modified). Contains: a minimal branding-only header (`{% block company_name %}`), a `{% block content %}`, and a minimal footer. Explicitly contains no sidebar, no admin nav, no dashboard topbar, no logout link, no notification bell, no dark-mode toggle, and no internal admin URLs.
- **Modified:** `templates/payments/invoice_checkout.html` — changed `{% extends "layouts/dashboard.html" %}` to `{% extends "layouts/public_payment.html" %}`; removed the `sidebar_brand`, `logout_url`, and `sidebar_nav` block overrides (the last of which hardcoded `{% include "includes/nav_admin.html" %}`); added a `{% block company_name %}{{ company.name }}{% endblock %}` override matching the new layout's block name. All existing content (payment form, invoice amounts, discount code form/logic, gateway button, non-payable/paid states, Persian labels) was left byte-for-byte unchanged inside `{% block content %}`.
- **New:** `tests/test_issue001_public_payment_layout.py` — regression tests (see below).

No changes were made to `apps/invoices/views.py`, `apps/invoices/urls.py`, `apps/payments/views.py`, `apps/payments/urls.py`, any model, any migration, `templates/invoices/public_detail.html`, `templates/invoices/print.html`, `templates/payments/result.html`, or `templates/payments/list.html`.

### Tests Added

`tests/test_issue001_public_payment_layout.py` (6 tests), following the existing setup pattern used by `tests/test_public_invoice_message_leak.py` (no shared fixture/factory module exists in this repo — each test file defines its own minimal `Company`/`Order`/`Invoice` helpers):

1. `test_anonymous_get_returns_200_for_payable_invoice`
2. `test_response_does_not_contain_admin_nav_labels` — asserts absence of اپراتورها، نیروهای خدماتی، تعرفه‌های اجرت، اعتبار پیامک، گزارش مالی
3. `test_response_does_not_contain_admin_nav_urls` — asserts absence of `/admin/settings/operators/`, `/admin/technicians/`, `/admin/technicians/rates/`, `/admin/sms-credit/`, `/admin/financial-reports/summary/`, `/admin/payment-gateway/`
4. `test_response_contains_payment_content` — asserts invoice number and "پرداخت اینترنتی فاکتور" still present
5. `test_response_contains_company_branding` — asserts `company.name` still present
6. `test_non_payable_invoice_renders_safely` — a PAID invoice still renders 200 with no admin-nav leakage

### Tests Run

```
python manage.py test tests.test_issue001_public_payment_layout -v 2
python manage.py test tests.test_public_invoice_message_leak tests.test_fix3_payment_source_consistency -v 2
```

### Result

All 18 tests passed (6 new + 8 existing invoice-message-leak + 4 existing payment-source-consistency). No failures, no errors, no regressions.

### Remaining Risk

- **Low.** The change is template-only; no view, URL, model, migration, or payment-processing logic was touched.
- `templates/payments/list.html` (the private, authenticated payment list) intentionally still extends `layouts/dashboard.html` — correct, unchanged, out of scope.
- `templates/invoices/public_detail.html`, `templates/invoices/print.html`, and `templates/payments/result.html` were not migrated to the new `public_payment.html` layout — they already render without dashboard chrome (standalone documents / bare `base.html`), so they were left untouched per the "narrow change" rule. Visual inconsistency between these pages and the newly styled checkout page (different header/footer treatment) is a known, accepted follow-up — tracked as future Option B scope, not fixed here.
- The pre-existing `{% if messages %}` block in `invoice_checkout.html` (renders Django session messages) was left as-is — it was out of scope for Issue 001 and is a distinct concern from Issue 003 (notification/message leakage), which is a separate backlog item.
- Manual QA recommended before merge: load `/<code>/invoices/<id>/pay/` in a browser as an anonymous visitor, confirm visual layout (header/footer render correctly, RTL intact, discount form and gateway button still functional), and confirm the discount-apply and start-gateway POST actions still redirect correctly (verified in code review; not covered by an automated browser test).
