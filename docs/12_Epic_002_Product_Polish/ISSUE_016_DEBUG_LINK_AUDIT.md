---
Title: Issue 016 — Internal Debug Link Audit
Layer: Epic 002 Product Polish
Audience: Human + AI
Status: Audit Complete — Awaiting Approval
Last Verified: 2026-07-01
Verified Against: templates/includes/settings_center.html, apps/sms/urls.py, apps/sms/views.py, apps/accounts/operator_access.py, apps/accounts/views_password_reset.py, config/settings/base.py, config/settings/local.py, config/settings/production.py, config/urls.py, docs/08_Site_Map/01_URL_INVENTORY.md, tests/test_p10_production_security_settings.py
Source of Truth: Code (docs already flag the URL as "needs further review"; a separate, unrelated documentation path conflict was found and is reported below)
Depends On: docs/03_Architecture/PERMISSIONS.md, docs/08_Site_Map/01_URL_INVENTORY.md
Related Documents: docs/12_Epic_002_Product_Polish/ISSUE_001_PUBLIC_PAYMENT_LAYOUT_AUDIT.md, docs/12_Epic_002_Product_Polish/ISSUE_003_NOTIFICATION_PREVIEW_AUDIT.md
Reusable Across Projects: No
---

# Issue 016 — Internal Debug Link Audit

## Summary

There is **no literal "debug" link, page, or tool** anywhere in the codebase (no route, template, or label contains the word "debug" / "دیباگ" outside of standard Django/dev-only code paths). The item the backlog almost certainly refers to is the **"تشخیص و تست پیامک" (SMS Diagnostics & Test) link** in the shared "Settings Center" widget (`templates/includes/settings_center.html`), which:

- Lets a user view the tenant's SMS provider configuration and **send a real test SMS to an arbitrary phone number**.
- Is rendered **unconditionally** — no role check, no `DEBUG` check, no superuser check in the template.
- Is backed by a view gated only by `@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")` — reachable by every company admin in every tenant, in production, always.
- Is independently flagged "نیازمند بررسی بیشتر" ("needs further review") in `docs/08_Site_Map/01_URL_INVENTORY.md:276`, suggesting this was already noticed as an outlier.

**No reusable "DEBUG-gated" or "Super-Admin-only" template visibility pattern currently exists in this codebase.** The closest precedent is a Python/view-level `if settings.DEBUG:` pattern in `apps/accounts/views_password_reset.py` (used to conditionally expose a plaintext OTP code during local development). A template-level equivalent (`{% if debug %}` / `{% if request.user.is_superuser %}`) would need to be introduced for this fix — it does not currently exist anywhere in `templates/`.

**Separately discovered, unrelated defect (must be reported, not silently fixed):** `templates/includes/settings_center.html` is currently corrupted by a global character-substitution bug (every `c` → `l` and every `s` → `t` in the file, confirmed via `git log -p`, introduced in commit `19a830f "sync project for SaasProject repo"`). This breaks **every link in the Settings Center widget**, including the SMS-diagnostics link — `class="btn btn-outline"` renders as `llatt="btn btn-outline"` (a nonexistent attribute) and `href="/{{ company.code }}/admin/sms/diagnostics/"` renders as `href="/{{ lompany.lode }}/admin/tmt/diagnottilt/"` (a broken template-variable name and a URL that does not match any route). This affects five links used across at least nine templates. It is out of scope for Issue 016's fix (a much bigger, unrelated regression) but is flagged here per the audit protocol rather than ignored.

## Root Cause

The SMS diagnostics feature was built as a normal tenant-facing business feature ("Phase 26D" per the code comment in `apps/sms/views.py:496`) and was never intended to be dev-only — but a company admin using it can send a live SMS to any phone number and view internal provider configuration, which is more appropriate for platform-level troubleshooting or local development than for routine, always-on exposure to every paying tenant's admin. No visibility gate (DEBUG, superuser, or feature flag) was ever added when the link was placed in the shared Settings Center widget, so it is unconditionally visible to every `COMPANY_ADMIN` (and any `COMPANY_STAFF` explicitly granted the `sms_diagnostics` operator permission) in every environment, including production.

## Current Rendering

`templates/includes/settings_center.html` (as of the last *correct* version, commit `2a60e7b`; current live version is corrupted — see Summary):

```django
<div class="card settings-center-card" class="mb-item">
    <div class="card-header">مرکز تنظیمات</div>
    <p style="color:#64748b;margin-top:0;">
        تنظیمات پیامک، نوتیفیکیشن و قوانین عملیاتی شرکت از این بخش در دسترس هستند.
    </p>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.75rem;">
        <a class="btn btn-outline" href="/{{ company.code }}/admin/settings/">تنظیمات سایت</a>
        <a class="btn btn-outline" href="/{{ company.code }}/admin/sms/templates/">تنظیمات پیامک و قالب‌ها</a>
        <a class="btn btn-outline" href="/{{ company.code }}/admin/sms/diagnostics/">تشخیص و تست پیامک</a>
        <a class="btn btn-outline" href="/{{ company.code }}/admin/settings/notifications/">تنظیمات نوتیفیکیشن</a>
        <a class="btn btn-outline" href="/{{ company.code }}/admin/settings/operators/">مدیریت اپراتورها و دسترسی‌ها</a>
    </div>
</div>
```

No `{% if %}` wraps any of the five links — they are all unconditional. This partial is `{% include %}`d by at least 9 templates: `templates/tenants/admin_company_settings.html:9`, `admin_notification_settings.html:9`, `admin_operator_list.html:9`, `admin_operator_create.html:39`, `admin_operator_edit.html:39`, `templates/sms/template_list.html:10`, `sms/template_form.html:11`, `sms/diagnostics.html:11` — i.e., the diagnostics link appears on essentially every operator-facing settings/SMS/operator-management page, not just one.

## Current Protection

| Layer | Status |
|---|---|
| Template-level (`{% if %}` in `settings_center.html`) | **None** — unconditional |
| URL routing (`apps/sms/urls.py:19`) | `path("diagnostics/", views.sms_diagnostics, name="diagnostics")` — no guard, standard route |
| View decorator (`apps/sms/views.py:500`) | `@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")` — requires tenant authentication and one of these two roles; **not** DEBUG-gated, **not** superuser-gated |
| `OperatorPermissionMiddleware` (`apps/accounts/operator_access.py:747-807`) | Only restricts `COMPANY_STAFF` (checked against the `sms_diagnostics` permission key, `apps/accounts/operator_access.py:125,183,230`). **`COMPANY_ADMIN` and any superuser bypass this middleware entirely** (line 771-772: `if is_company_admin(user): return self.get_response(request)`) — so a company admin can never be locked out of this page via the existing permission system, regardless of company policy. |
| `settings.DEBUG` | Not referenced anywhere in `apps/sms/views.py`, `apps/sms/urls.py`, or `templates/includes/settings_center.html` |
| `is_superuser` / `PLATFORM_OWNER` | Not referenced anywhere in the above files, and (confirmed by repo-wide grep) **not referenced in any template in the codebase** — there is no existing template that gates a link/nav item on superuser or platform-owner status |

**Conclusion:** the page is fully accessible in production, to every company admin of every tenant, all the time. It is protected only by ordinary tenant-role authentication — not by `DEBUG` mode and not by any "Super Admin" concept.

## Risk Assessment

- **Not an authentication bypass.** `sms_diagnostics` is correctly behind `@require_tenant_role`; no anonymous or cross-tenant access was found. Tenant isolation is intact — `SMSDiagnosticsService.get_provider_info(company=company)` and `send_test(company=company, ...)` are both company-scoped.
- **Real-world impact if misused:** any company admin (a normal customer of the platform, not Rasti staff) can trigger a live SMS send to an arbitrary phone number and can view internal SMS provider configuration details. This is a legitimate, if sensitive, business feature — but treating it as "always visible in the primary settings navigation" (rather than an intentionally-discoverable diagnostic tool) increases the chance of accidental misuse (e.g., an admin experimenting with "test SMS" against a real customer's number) and unnecessarily exposes provider configuration details in the default UI surface of every tenant.
- **Not a data leak / not a cross-tenant issue.** No violation of `MULTI_TENANCY.md`'s company-scoping rule was found.
- **The character-corruption bug (separate finding) currently makes this a moot point in practice** — right now, the rendered `href` is malformed (`/{{ lompany.lode }}/admin/tmt/diagnottilt/`) and does not resolve to any real Django route, so clicking the button in the *current* broken state 404s. This does **not** mean the underlying exposure is safe to ignore: (a) the view itself remains reachable if a user knows/types the correct URL directly, and (b) once the unrelated corruption bug is eventually fixed (by anyone, for any reason), the link becomes clickable again with zero additional protection — so the underlying Issue 016 concern must still be fixed independently of that bug.

## Pattern Reuse

- **No template-level DEBUG or Super-Admin visibility pattern exists to reuse.** Confirmed by repo-wide search: no template anywhere uses `{% if debug %}`, `{% if settings.DEBUG %}`, `{% if request.user.is_superuser %}`, or `{% if ... == "PLATFORM_OWNER" %}` to conditionally show/hide a link or nav item. Separation between the operator nav (`templates/includes/nav_admin.html`) and the platform-owner nav (`templates/includes/nav_platform.html`) is achieved structurally (two entirely separate files, each included only under its own URL prefix/layout), not via an in-template conditional — so that separation technique doesn't directly transfer to a single shared partial like `settings_center.html`.
- **Closest existing precedent (Python-level, not template-level):** `apps/accounts/views_password_reset.py:71,263,273,290,333` — `if settings.DEBUG:` used to conditionally store/expose a plaintext OTP code (`_SK_DEV_CODE`) only in local development. This establishes that `if settings.DEBUG:` is already an accepted, idiomatic pattern in this codebase for gating dev-only behavior at the Python level.
- **Django's built-in `debug` context processor is already registered** (`config/settings/base.py:90`, `"django.template.context_processors.debug"`), which would expose a `{{ debug }}` template variable — but it is **currently inert**: Django's built-in processor only sets `debug=True` when both `settings.DEBUG` is true AND the requester's IP is in `INTERNAL_IPS`, and `INTERNAL_IPS` is not set anywhere in this codebase. Using `{% if debug %}` as-is today would therefore always evaluate to `False`, everywhere, including in local dev — this processor is not currently usable for a simple "hide in production" check.
- **Superuser/Platform-Owner gating precedent (Python-level only):** `is_company_admin()` in `apps/accounts/operator_access.py:513` and a superuser check at `apps/tenants/views_admin.py:2766` exist, but these gate view-level *access decisions*, not link *visibility* in a shared template.

**Recommendation on reuse:** since no template-level pattern exists to copy verbatim, the minimal fix should introduce a small, single-purpose template conditional (`{% if request.user.is_superuser %}` and/or a settings-driven flag), following the *spirit* of the existing `if settings.DEBUG:` Python precedent rather than inventing new infrastructure (no new context processor, template tag, or feature-flag system is needed for a single link).

## Files Affected

If Option A (see Recommendation) is approved, the following would be the minimal in-scope files:

- `templates/includes/settings_center.html` — wrap the single diagnostics `<a>` link in a conditional (exact condition TBD by approval — see Recommendation options).

No other file should need to change for the minimal fix. (The unrelated character-corruption bug in this same file is a separate, much larger fix and is explicitly **not** included in this scope — see Documentation Updates / Recommendation.)

## Minimal Safe Fix

Wrap only the one diagnostics link (`templates/includes/settings_center.html`, the "تشخیص و تست پیامک" `<a>` tag) in a template conditional. Two equally minimal options, to be decided by the approver (not implemented here):

- **A1 — DEBUG-only:** `{% if debug %}` is not usable as-is (see Pattern Reuse — the processor is currently inert without `INTERNAL_IPS`). A working equivalent would require passing a `debug`/`show_sms_diagnostics` boolean into context from every view that renders `settings_center.html` (9 call sites), which is not minimal. A simpler equivalent is a custom template check against `settings.DEBUG` — Django template language cannot access `settings.DEBUG` directly without either a context processor already exposing it correctly, or a small template tag. This makes "DEBUG mode" alone awkward to implement with a single-file, zero-view-change change.
- **A2 — Super Admin only (`is_superuser`):** `{% if request.user.is_superuser %}` — `request.user` is already available in every template (via Django's built-in `django.contrib.auth.context_processors.auth` and `django.template.context_processors.request`, both already registered in `config/settings/base.py`). This requires **zero** Python/view changes and **zero** new context processors — it is a pure, one-line template edit. This is the more minimal of the two options.
- **A3 — Combination:** `{% if request.user.is_superuser or debug %}` — same caveat as A1 on `debug` being inert without `INTERNAL_IPS`; would effectively behave the same as A2 alone unless `INTERNAL_IPS`/context-processor gap is also fixed (out of scope).

Given the "minimal, safe, isolated" instruction and the goal ("hide under DEBUG mode or Super Admin only" — an *or*, not an *and*), **A2 (`is_superuser`-only)** is the option that requires no infrastructure changes and no additional files. This is recommended as the base of Option A; final wording of the conditional is left for approval.

## Tests Found

- `tests/test_p10_production_security_settings.py` — verifies `settings.DEBUG` is `False` in production settings and that media-file serving is `DEBUG`-guarded. **Does not** cover `settings_center.html`, `sms_diagnostics`, or any operator-settings link visibility.
- No test anywhere references `settings_center.html`, `sms_diagnostics` link visibility, or operator-facing "debug" concerns.

## Tests Needed

If Option A2 is approved and implemented:

1. A `COMPANY_ADMIN` (non-superuser) GET of a page that includes `settings_center.html` (e.g. `/<code>/admin/settings/`) must **not** contain the "تشخیص و تست پیامک" link text/href.
2. A Django superuser (if reachable through this template path) GET of the same page **does** show the link — confirms the gate isn't overly aggressive. (Needs a decision on whether "superuser" in this codebase is ever a `COMPANY_ADMIN`-role user with `is_superuser=True`, or only reachable via `/admin/` Django admin / platform owner accounts — should be clarified before writing this test, since `PLATFORM_OWNER` users do not use the tenant URL scheme per `MULTI_TENANCY.md`.)
3. Existing SMS/operator-settings tests (if any reference this include indirectly) continue to pass — confirmed no such tests currently exist, so no regression risk there.
4. The `sms_diagnostics` **view/URL itself** should still be tested as reachable directly by `COMPANY_ADMIN`/permitted `COMPANY_STAFF` (unchanged behavior — only the nav *link* is hidden, not the page itself, per "Keep preview isolated"-style minimal-scope reasoning already used in Issues 001/003) — no regression test currently exists for this either; may be worth adding as a baseline.

## Documentation Updates Required (after implementation, not now)

- `docs/08_Site_Map/01_URL_INVENTORY.md:276` — update the "نیازمند بررسی بیشتر" (needs further review) note once resolved, reflecting the new visibility rule.
- `docs/03_Architecture/PERMISSIONS.md` — has an unrelated file-path conflict discovered during this audit: it references `apps/tenants/operator_access.py` (lines 121, 152) for `is_company_admin()`, but the actual file is `apps/accounts/operator_access.py`. This is not part of Issue 016's fix but is flagged here per `SOURCE_OF_TRUTH.md` Rule 1 rather than silently ignored; recommend a separate documentation correction pass.
- A new tracked item (separate from Issue 016) should be opened for the `templates/includes/settings_center.html` character-corruption bug — it currently breaks 5 links across 9 templates and is unrelated to visibility/permissions.

## Risk Level

**Low.** The fix (Option A2) is a single-line template conditional using data already available in every template context, touching one file. No view, URL, permission decorator, model, or migration changes. No risk to tenant isolation, notification delivery, SMS logic, or business logic.

## Recommendation

**Option A — Minimal fix: hide the SMS-diagnostics link behind `{% if request.user.is_superuser %}`** in `templates/includes/settings_center.html` only. This satisfies the backlog's stated goal ("Hide under DEBUG mode or Super Admin only") using the simpler, zero-infrastructure half of that "or," requires no view/context changes, and leaves the underlying `sms_diagnostics` page and its existing tenant-role/operator-permission protections completely untouched (so a company admin who currently has legitimate reasons to use it can still reach it directly by URL if the product owner decides that's acceptable — or the URL itself can be further restricted in a follow-up if the approver wants the page itself, not just the link, closed off).

The separately-discovered `settings_center.html` corruption bug is **not** part of this recommendation — it is a pre-existing, unrelated regression affecting all five links in this widget and should be triaged and fixed as its own item, ideally before or alongside this fix (since editing the same file for Issue 016 will require touching corrupted markup regardless — the approver should decide whether the corruption fix and the Issue 016 visibility fix are combined into one commit as a practical necessity, or sequenced as two separate approvals).

## Approval Required

Do not implement until approved.

Options:

A. Minimal fix — wrap only the SMS-diagnostics link in `templates/includes/settings_center.html` with `{% if request.user.is_superuser %}` (or an approver-specified equivalent condition). **(Recommended)**

B. Broader fix — additionally repair the unrelated character-corruption bug in the same file (all five links), since implementing A requires editing this file anyway.

C. Defer — leave as-is for now.
