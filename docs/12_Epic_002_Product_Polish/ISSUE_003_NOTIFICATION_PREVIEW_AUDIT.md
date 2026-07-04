---
Title: Issue 003 — Notification Preview Leak Audit
Layer: Epic 002 Product Polish
Audience: Human + AI
Status: Audit Complete — Awaiting Approval
Last Verified: 2026-07-01
Verified Against: apps/notifications/context_processors.py, apps/notifications/selectors.py, templates/layouts/dashboard.html, templates/layouts/technician.html, templates/payments/invoice_checkout.html, templates/invoices/public_detail.html, templates/public/contact.html, templates/components/alert_message.html, apps/invoices/views.py, apps/public/views.py, config/settings/base.py
Source of Truth: Code (docs have a naming conflict on apps/notifications/catalog.py — see Documentation Conflict)
Depends On: docs/12_Epic_002_Product_Polish/ISSUE_001_PUBLIC_PAYMENT_LAYOUT_AUDIT.md, docs/04_Business_Rules/NOTIFICATION_RULES.md
Related Documents: docs/03_Architecture/TEMPLATE_ARCHITECTURE.md, docs/08_Site_Map/05_TEMPLATE_MAP.md
Reusable Across Projects: No
---

# Issue 003 — Notification Preview Leak Audit

## Summary

The phrase "notification preview" maps to **two distinct mechanisms** in this codebase, and both were audited:

1. **The in-app `Notification` model "bell dropdown" preview** (`notif_latest` / `notif_unread_count`, injected by a global context processor) — audited thoroughly. **No current leak found.** It is defended at two independent layers (context processor role-allowlist + template-level `{% if %}` gate) and is not rendered on any public/anonymous page or wrong-role page in the current codebase.
2. **Django "flash message" toasts** (`django.contrib.messages`, rendered via `{% if messages %}` blocks) — these behave like a one-time "preview" of an action's result (success/error banners) and are session-scoped, not page-scoped. **A confirmed, currently-unfixed leak exists here.** This exact bug class was already found and fixed once in this codebase for `templates/invoices/public_detail.html` (see `tests/test_public_invoice_message_leak.py`), but the identical unguarded `{% if messages %}` block still exists, unfixed, in **`templates/payments/invoice_checkout.html`** — the public, unauthenticated payment/checkout page — and in **`templates/public/contact.html`** — the public marketing contact page. Because Django sessions are per-browser-cookie, not per-role or per-page, a message queued by an authenticated admin/staff/customer action in one tab can be displayed on a completely unrelated, anonymous, public page in the same browser session the next time that page is loaded — this is the "leaks into unrelated pages" behavior Issue 003 describes.

The recommended fix mirrors the fix already applied (and tested) for `public_detail.html`: stop rendering raw session messages on public pages; for the one form flow on the checkout page that needs public error/success feedback (discount-code apply), route it through URL query params the same way `public_invoice_apply_discount` already does for the invoice detail page.

## Current Implementation

### Mechanism A — Notification bell "preview" dropdown

- **Context processor:** `apps/notifications/context_processors.py:23` — `notification_badge(request)`, registered in `config/settings/base.py` `TEMPLATES[0]["OPTIONS"]["context_processors"]`. Runs on **every** template render, site-wide.
- Safety invariants (all verified in code, matching the function's own docstring):
  - Not authenticated → `{"notif_unread_count": 0, "notif_latest": []}`
  - `request.company is None` (any public/marketing page) → empty
  - `user.role not in {"COMPANY_ADMIN", "COMPANY_STAFF", "TECHNICIAN"}` (excludes `CUSTOMER`, `PLATFORM_OWNER`, anonymous) → empty
  - Any exception → empty (never raises)
  - Queries are always scoped by `company=company, user=user` via `NotificationSelector` (tenant-isolated)
- **Template rendering:** the dropdown markup itself is only inlined in `templates/layouts/dashboard.html:145-188`, wrapped in `{% if request.user.role == "COMPANY_ADMIN" or request.user.role == "COMPANY_STAFF" %}` — a second, independent gate. `templates/layouts/technician.html:66-67` renders only the unread-count badge (no dropdown/list), with no additional template-level role check — it relies on the context processor's allowlist plus the fact that this layout is only reachable via `@require_tenant_role("TECHNICIAN")`-gated views. No other layout (`public.html`, `public_payment.html`, `auth.html`, `error.html`, `invoice_print.html`, `base.html`, `base_dashboard.html`) contains any bell/dropdown/badge markup or references `notif_latest`/`notif_unread_count`.
- **Conclusion:** two-layer defense (processor + template gate) on the one page family that has the dropdown; single-layer (processor + view decorator) on the technician badge. No page was found where this preview renders for an ineligible role or an anonymous/public visitor.

### Mechanism B — Django flash-message "toast" leak (confirmed defect)

`django.contrib.messages` is session-backed and consumed FIFO across **any** view that renders a `{% if messages %}` block — it is not scoped to the page, company, or role that queued the message. A repo-wide search for `{% if messages %}` found 11 templates. Cross-referencing each against its layout/view auth requirement:

| Template | Extends | Auth required? | Leak risk |
|---|---|---|---|
| `templates/payments/invoice_checkout.html` | `layouts/public_payment.html` | **None (intentionally public)** | **Confirmed — see Leak Source** |
| `templates/public/contact.html` | `layouts/public.html` | **None (public marketing page)** | **Confirmed — see Leak Source (lower severity)** |
| `templates/invoices/detail.html` | `layouts/dashboard.html` | `@require_tenant_auth` | Low — private, same-user-session messages only |
| `templates/payouts/technician_ledger.html` | `layouts/technician.html` | `@require_tenant_role("TECHNICIAN")` | Low — private |
| `templates/platform_core/messages/inbox.html` | `layouts/dashboard.html` | Platform-owner gated | Low — private |
| `templates/platform_core/messages/outbox.html` | `layouts/dashboard.html` | Platform-owner gated | Low — private |
| `templates/reports/discount_campaign_manual.html` | `layouts/dashboard.html` | Admin gated | Low — private |
| `templates/sms/outbox_list.html` | `layouts/dashboard.html` | Admin gated | Low — private |
| `templates/components/alert_message.html` | *(reusable partial, not a page)* | N/A | Not itself a leak source — **currently unused/orphaned**, not `{% include %}`d anywhere in the live templates (only referenced in its own usage-doc comment) |
| `templates/invoices/public_detail.html.bak` | *(backup file, not live)* | N/A | Not live — historical, pre-fix snapshot |
| `templates/payments/invoice_checkout.html.bak` | *(backup file, not live)* | N/A | Not live |

`templates/invoices/public_detail.html` (the **currently live** file, not the `.bak`) has **no** `{% if messages %}` block — confirmed by grep. This is the already-applied fix from `tests/test_public_invoice_message_leak.py`.

## Leak Source

**Root cause:** `apps/invoices/views.py` function `invoice_pay` (the checkout view backing `templates/payments/invoice_checkout.html`) uses the raw Django messages framework directly for its own discount-apply and gateway-start actions, instead of the safe query-param pattern already established elsewhere in the same file:

```python
# apps/invoices/views.py — invoice_pay(), action == "apply_discount" branch
if invoice.campaign_discount_amount and invoice.campaign_discount_amount > 0 or getattr(invoice, "discount_code", None):
    messages.error(request, "کد تخفیف قبلاً اعمال شده است.")
    return redirect(f"/{company.code}/invoices/{invoice.id}/pay/")
...
if ok:
    messages.success(request, message)
else:
    messages.error(request, message)
...
return redirect(f"/{company.code}/invoices/{invoice.id}/pay/")
```

Compare with the safe pattern already used for the sibling public path (`_invoice_discount_redirect`, used by `public_invoice_apply_discount` at line 289 and by the private `invoice_apply_discount` at line 269):

```python
def _invoice_discount_redirect(request, invoice, *, public: bool, success: bool, message: str):
    if public:
        # Public pages must not render session messages — they leak admin/tech session
        # state to anonymous visitors. Success is self-evident from the updated total.
        # Errors are surfaced via a URL query param that only this redirect sets.
        if success:
            return redirect(f"/i/{invoice.public_code}/")
        from urllib.parse import urlencode
        return redirect(f"/i/{invoice.public_code}/?{urlencode({'disc_err': message})}")
    ...
```

The comment on this exact helper *already documents the invariant* that `invoice_pay`'s own discount handling violates — `invoice_pay` was evidently never updated to use it (or a `/pay/`-specific equivalent) when the `public_detail.html` fix was made.

Then, `templates/payments/invoice_checkout.html` renders whatever is in the session unconditionally:

```django
{% if messages %}
<div style="margin-bottom:var(--space-4);">
  {% for message in messages %}
  <div class="alert {% if message.tags == 'success' %}alert-success{% else %}alert-danger{% endif %}">
    <div class="alert-body">{{ message }}</div>
  </div>
  {% endfor %}
</div>
{% endif %}
```

**Mechanism:** Django's `SessionStorage` message backend ties queued messages to the session cookie, not to a specific URL or page. Any message queued by *any* view during a request in a given browser session (e.g., an operator recording a cash payment, an admin editing settings, a customer applying a discount on a different invoice) remains queued until the *next* page render that iterates `messages` — regardless of which page that happens to be. Because `invoice_pay` is public (no login required, "anyone with the invoice link may pay" per its own docstring) and is frequently the very first or a very late page loaded in a shared browser session (e.g. staff testing a payment link, or a customer's browser previously used by staff), a stale, unrelated, potentially internal-sounding message (e.g. "دریافت نقدی ثبت شد" — cash payment recorded) can render on the anonymous checkout page.

**Is it session-based?** Yes — this is the entire mechanism. Django messages are stored server-side keyed by session ID, delivered via a cookie-backed session; they are inherently cross-page within one browser session.

**Is it caused by template inheritance?** No. Neither `layouts/public_payment.html` nor `layouts/public.html` (the base layouts) render `{% if messages %}` themselves — each affected page template (`invoice_checkout.html`, `contact.html`) independently chose to add its own local `{% if messages %}` block. The leak is per-template, not inherited from a shared base.

**Is it caused by global context?** Partially — `messages` itself is injected globally by Django's own `django.contrib.messages.context_processors.messages` (standard Django, present in every Django project, not something this codebase can or should remove). The defect is that individual public-facing templates choose to *render* that global variable without checking whether the current page/session is an appropriate place to display it.

## Affected Pages

| URL | View | Confirmed leak-capable |
|---|---|---|
| `/<code>/invoices/<id>/pay/` | `invoice_pay` | **Yes — primary, high-priority instance** (payment page, customer-facing, brand-sensitive, directly related to EPIC-002 Issue 001) |
| `/contact/` | `apps.public.views.contact` | **Yes — secondary, lower-severity instance** (marketing page; `contact` view itself never queues messages today, so no first-party trigger exists yet, but the template is still exploitable by any stale cross-page session message) |

No leak found for: `/<code>/invoices/public/<public_code>/`, `/i/<public_code>/` (already fixed), `/<code>/payments/callback/` (extends `base.html`, no messages block), `/<code>/invoices/public/<public_code>/print/` (standalone document, no messages block), any `/<code>/admin/...` or `/<code>/tech/...` page (all authenticated, private-session-scoped).

## Affected Templates

- `templates/payments/invoice_checkout.html` — lines 17–25 (the `{% if messages %}` block), primary fix target.
- `templates/public/contact.html` — lines 76+ (the `{% if messages %}` block), secondary fix target.

## Affected Views

- `apps/invoices/views.py::invoice_pay` (lines 128–242) — the root-cause view; its own `action == "apply_discount"` branch (lines 180–205) and `action == "start_gateway"` branch (lines 207–231) call `messages.error`/`messages.success` directly instead of a public-safe query-param pattern.
- `apps/public/views.py::contact` (line 41) — does not itself queue any messages today (confirmed by reading the view body — it is a bare `render()`), so it is not a first-party trigger, but its template remains exploitable by any stale message left over from elsewhere in the same session.

No context processor change is required — `notification_badge` (Mechanism A) is not implicated in this leak; it was audited and found already safe.

## Security Impact

- **No cross-tenant data query leak.** This is not an ORM/data-access issue — no `Order`/`Invoice`/`Payment`/`Customer` records are exposed. `MULTI_TENANCY.md`'s "always scope by company" rule is not violated by this defect.
- **Session/content leak across page and (potentially) company boundaries.** Because `invoice_pay` is reachable for *any* company's invoice from the same browser session, a message queued while interacting with Company A's admin/staff flow could render on a public payment page for Company B's invoice if both are loaded in the same browser session. This is a UI/content leak across tenant boundaries, not a data-access leak — but it is inconsistent with the spirit of tenant isolation and could confuse or alarm a customer (e.g., seeing an unrelated internal status message on their own payment page).
- **Information disclosure severity: Low–Medium.** Messages in this codebase are short, human-readable status strings (e.g. "کد تخفیف قبلاً اعمال شده است" — discount already applied; "دریافت نقدی ثبت شد" — cash payment recorded, from other flows). They do not contain financial totals, PII, or credentials, but they do reveal that *some* internal admin/staff action occurred, which is an unnecessary disclosure to an anonymous payer and undermines trust in a payment context.

## Tenant Impact

No violation of `apps/tenants/middleware.py` (`TenantMiddleware`) scoping and no ORM query without a `company=` filter was found in this investigation. The impact is UI-content leakage that can cross company boundaries only in the sense described above (same browser session visiting different companies' public pages) — it is not a `request.company` resolution bug and does not affect the `Notification` bell mechanism (Mechanism A), which is correctly and independently company-scoped.

## Minimal Implementation Plan

1. In `apps/invoices/views.py`, change `invoice_pay`'s `action == "apply_discount"` branch to use the existing `_invoice_discount_redirect(request, invoice, public=True, success=..., message=...)` helper (or an equivalent `/pay/`-specific query-param redirect) instead of `messages.error`/`messages.success` + plain `redirect(...)`.
2. In `templates/payments/invoice_checkout.html`, remove the `{% if messages %}` block (lines 17–25) and instead render any error via a URL query param (e.g. `request.GET.disc_err`), mirroring the pattern already used in `templates/invoices/public_detail.html` (see its `{% if request.GET.disc_err %}` block).
3. For the `action == "start_gateway"` branch's error path (gateway not configured / `ValueError` from `PaymentStartService.start`), apply the same query-param pattern rather than `messages.error`.
4. Apply the identical fix (remove `{% if messages %}`) to `templates/public/contact.html`, since it is also a public, anonymous page with no legitimate use for cross-session message display today. If the contact form is later given server-side validation feedback, it should use the same request-scoped (non-session) pattern.
5. Do not touch `notification_badge` context processor or `layouts/dashboard.html`/`layouts/technician.html` bell markup — Mechanism A is already correctly isolated and out of scope for this fix.

## Files Expected to Change

- `apps/invoices/views.py` — `invoice_pay` function only (discount-apply and gateway-start error/success paths)
- `templates/payments/invoice_checkout.html` — remove `{% if messages %}` block, add query-param-based error display
- `templates/public/contact.html` — remove `{% if messages %}` block
- Test: new file, e.g. `tests/test_issue003_notification_message_leak.py`

No changes expected to: `apps/notifications/*`, `apps/payments/views.py`, any model, any migration, any permission decorator, `layouts/dashboard.html`, `layouts/technician.html`, `layouts/public_payment.html` (the layout added for Issue 001 needs no change — the leak is inside the child template, not the layout).

## Tests Found

- `tests/test_public_invoice_message_leak.py` — covers `public_invoice_detail` and `short_public_invoice_detail` only (the invoice *detail* page). Does **not** cover `invoice_pay`/`invoice_checkout.html`.
- `tests/test_issue001_public_payment_layout.py` (added for Issue 001) — covers admin-nav-chrome leakage on the checkout page, but does **not** test message/session leakage.
- No test in the repository exercises `messages` + `invoice_pay` together, and no test covers `public/contact.html` messages behavior at all (confirmed via repo-wide grep for `contact` in `tests/`).

## Tests Required

New file `tests/test_issue003_notification_message_leak.py`, following the same pattern as `tests/test_public_invoice_message_leak.py`:

1. Inject a stale session message (as `test_public_invoice_message_leak.py` does via `SessionStorage`), then `GET /<code>/invoices/<id>/pay/` and assert the stale marker text is **not** present in the response.
2. Confirm the checkout page still renders 200 and still shows invoice/payment content after the fix (regression guard).
3. Submit the `apply_discount` POST action with an already-applied discount (or invalid code) and assert the resulting error is shown via the redirected page (query-param path) without ever exposing it through `{% if messages %}`.
4. Repeat test 1 for `GET /contact/` — inject a stale session message, assert it does not render on the public contact page.
5. Optional defense-in-depth test: confirm `templates/payments/invoice_checkout.html` and `templates/public/contact.html` no longer contain the literal string `{% if messages %}` (a simple template-source regression guard, consistent with how strictly Issue 001's fix was verified).

## Documentation Updates Required (after implementation, not now)

- `docs/04_Business_Rules/NOTIFICATION_RULES.md` — this doc references `apps/notifications/catalog.py`, which does not exist in the current codebase (the actual file is `apps/notifications/event_catalog.py`). This is a pre-existing documentation conflict, unrelated to Issue 003's fix but discovered during this audit; flagging per `SOURCE_OF_TRUTH.md` Rule 1 rather than silently ignoring it. Recommend a doc correction pass (separate from Issue 003 implementation).
- `docs/03_Architecture/TEMPLATE_ARCHITECTURE.md` — add a short note under "Known Template Issues" once fixed, mirroring the Issue 001 entry style.
- `docs/11_Project_Knowledge/KNOWN_RISKS.md` — consider logging this as a new entry until fixed (e.g. `M-5 — Public payment/contact pages can render stale session messages from unrelated pages`).

## Risk Level

**Medium.** No tenant data-query violation, no financial-calculation change, no permission-decorator change. The fix touches one view function's control flow (redirect target construction) on a payment-adjacent page, so it must be tested carefully to avoid breaking the discount-apply or gateway-start flows — but the change is narrow (mirrors an existing, already-tested pattern in the same file) and template-only elsewhere.

## Recommendation

**Option A — Minimal fix**, scoped to exactly the pattern already proven safe in this codebase: replace `messages.error`/`messages.success` + `{% if messages %}` with the existing query-param redirect pattern (`_invoice_discount_redirect`-style) for `invoice_pay`'s two POST actions, and strip the now-redundant `{% if messages %}` block from both `invoice_checkout.html` and `contact.html`. This directly resolves the confirmed leak with a change shape the codebase has already validated once (the `public_detail.html` fix + its test), keeping risk low and scope narrow per `docs/02_AI_Operating_System/AI_CODE_CHANGE_RULES.md` Rule 2.

A broader option (auditing and hardening *every* messages-rendering template, or introducing a shared "public-safe alert" component) is not recommended for this issue — the eight other templates that render `{% if messages %}` are all behind authentication and pose materially lower risk; bundling their cleanup here would violate the "never solve multiple unrelated issues in one commit" instruction.

Deferring is not recommended — the leak is real, has a known-good fix pattern already in the codebase, and directly affects the same customer-facing payment page just hardened in Issue 001.

## Approval Required

Do not implement until approved.

Options:

A. Minimal fix — apply the existing public-safe query-param redirect pattern to `invoice_pay`'s discount/gateway actions and remove the unguarded `{% if messages %}` blocks from `invoice_checkout.html` and `contact.html`. **(Recommended)**

B. Broader fix — additionally audit/harden all remaining `{% if messages %}` templates (all currently behind authentication) for defense-in-depth, and/or introduce a shared "public page" convention that forbids session-message rendering outright.

C. Defer — leave as-is for now.

---

## Implementation Completed (2026-07-01)

Option A approved and implemented.

### Root Cause

`apps/invoices/views.py::invoice_pay` used `django.contrib.messages` (`messages.error`/`messages.success`) directly for its `apply_discount` and `start_gateway` POST actions, then redirected back to the same anonymous `/pay/` URL. `templates/payments/invoice_checkout.html` rendered `{% if messages %}` unconditionally. Because Django session messages are keyed to the browser session, not to any specific page or company, a message queued anywhere else in that session (e.g. an admin/staff action, or a discount error on a *different* invoice) would render on the next load of this public, unauthenticated payment page — regardless of who or what queued it. `templates/public/contact.html` had the identical unguarded `{% if messages %}` block with no first-party trigger today, but was equally exploitable by the same cross-page leak.

### Pattern Reused

Reused the **existing public-safe query-param redirect pattern** already established in the same file: `apps/invoices/views.py::_invoice_discount_redirect` (used by `public_invoice_apply_discount` for `/i/<public_code>/` and `/<code>/invoices/public/<public_code>/`), which redirects with a `?disc_err=<message>` query string instead of queuing a session message, and is read back in `templates/invoices/public_detail.html` via `{% if request.GET.disc_err %}`. No new leak-handling mechanism was invented — the same approach was applied to `invoice_pay`, using a dedicated `pay_err` query param (kept distinct from `disc_err` because `/pay/` surfaces both discount errors and gateway-start errors through the same channel, whereas `disc_err` on the invoice-detail page is discount-specific only).

### Files Changed

- **`apps/invoices/views.py`** — added a small `_pay_redirect(company, invoice, *, error=None)` helper (same shape as `_invoice_discount_redirect`'s public branch) directly above `invoice_pay`. Replaced all four `messages.error`/`messages.success` call sites inside `invoice_pay` (invoice-already-discounted guard, discount-apply success/failure, gateway-not-configured, gateway-start `ValueError`, gateway-start-failed) with `_pay_redirect(...)` calls. Removed the now-unused `from django.contrib import messages` import from the view. No other function in the file was touched.
- **`templates/payments/invoice_checkout.html`** — replaced the `{% if messages %}...{% endfor %}{% endif %}` block with a single `{% if request.GET.pay_err %}` block rendering the same `alert alert-danger` markup. No other markup changed.
- **`templates/public/contact.html`** — removed the dead `{% if messages %}` block. No query-param replacement was added here because the `contact` view (`apps/public/views.py::contact`) never queues a message today (confirmed: it is a bare `render()`, GET-only) — there was nothing to preserve, only a leak surface to remove.
- **`tests/test_issue003_notification_message_leak.py`** — new test file (see below).

No changes were made to `apps/notifications/*`, `apps/payments/*`, any model, any migration, any permission decorator, `apps/tenants/middleware.py`, `layouts/dashboard.html`, `layouts/technician.html`, or any other template.

### Tests Added

`tests/test_issue003_notification_message_leak.py` (11 tests):

- `PublicPaymentMessageLeakTest` (5 tests): `/pay/` returns 200; a stale injected session message does not render on `/pay/`; invoice/payment content still renders correctly alongside a stale message; posting `apply_discount` on an already-discounted invoice redirects with `pay_err=` in the URL and leaves zero entries in `django.contrib.messages` (verified via `response.context["messages"]`); a stale message queued while interacting with one company does not leak onto a **different** company's `/pay/` page in the same browser session (multi-tenant isolation check).
- `PublicContactMessageLeakTest` (2 tests): `/contact/` returns 200; a stale injected session message does not render on `/contact/`.
- `MessageBlockSourceGuardTest` (2 tests): source-level regression guard confirming neither `invoice_checkout.html` nor `contact.html` contains a raw `{% if messages %}` block.

### Tests Executed

```
python manage.py test tests.test_issue003_notification_message_leak -v 2
python manage.py test tests.test_notifications_ux tests.test_notifications_core tests.test_public_invoice_message_leak tests.test_issue001_public_payment_layout tests.test_fix3_payment_source_consistency -v 2
```

`tests.test_notifications_ux` and `tests.test_notifications_core` are the existing regression suites for Mechanism A (the notification bell/badge/dropdown — badge scoping, tenant isolation, mark-read, pagination, deep links, payment-success event-key gating). Neither file, nor any code they exercise, was modified by this fix; they were run specifically to prove the Notification Bell continues to work exactly as before.

### Results

**All 82 tests passed** (11 new + 71 existing across the five files above). No failures, no errors, no regressions.

### Remaining Risk

- **Low.** The change is confined to one view function's redirect construction and two template fragments; no notification delivery, SMS, tenant-resolution, or permission logic was touched.
- Mechanism A (the bell/badge preview) was audited in the original report and confirmed already safe; it was intentionally left untouched, and the full existing bell test suite (`test_notifications_ux.py`, `test_notifications_core.py`) continues to pass unmodified, confirming no regression.
- `templates/public/contact.html`'s contact form itself has no server-side POST handler in `apps/public/views.py::contact` (it is GET-only) — this is a pre-existing, unrelated gap noted during the audit and left out of scope for Issue 003 (no business logic was to be added).
- The eight other `{% if messages %}` templates identified in the audit (all behind authentication — `invoices/detail.html`, `payouts/technician_ledger.html`, `platform_core/messages/inbox.html`/`outbox.html`, `reports/discount_campaign_manual.html`, `sms/outbox_list.html`) were left unchanged per the approved Option A scope; they pose materially lower risk since they are only reachable by authenticated users viewing their own session's own messages.
- `apps/notifications/catalog.py` vs `apps/notifications/event_catalog.py` documentation conflict (found during the audit) remains unaddressed — flagged for a separate documentation correction pass, not part of this fix.
