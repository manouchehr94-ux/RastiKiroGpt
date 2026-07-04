---
Title: Issue 004 — Global Numeric Formatting Audit
Layer: Epic 002 Product Polish
Audience: Human + AI
Status: Audit Complete — Awaiting Approval (Design Only, No Implementation)
Last Verified: 2026-07-01
Verified Against: apps/common/templatetags/smart_numbers.py, apps/common/templatetags/fa_labels.py, apps/common/templatetags/jalali_tags.py, apps/common/phone_utils.py, apps/common/jalali.py, static/js/rasti_ui_formatters.js, static/js/jalali_datepicker.js, static/js/phase_c2_datetime_local*.js, static/js/rasti_sidebar.js, config/settings/base.py, apps/tenants/views_admin.py, apps/reports/discount_services.py, apps/sms/services.py, apps/sms/services_inbox.py, apps/platform_core/services_platform_sms.py, apps/accounts/views_password_reset.py, apps/*/forms.py, apps/*/models.py, ~200 templates under templates/
Source of Truth: Code
Depends On: docs/12_Epic_002_Product_Polish/ISSUE_001_PUBLIC_PAYMENT_LAYOUT_AUDIT.md, docs/12_Epic_002_Product_Polish/ISSUE_003_NOTIFICATION_PREVIEW_AUDIT.md
Related Documents: docs/03_Architecture/TEMPLATE_ARCHITECTURE.md, docs/04_Business_Rules/PAYMENT_RULES.md
Reusable Across Projects: No
---

# Issue 004 — Global Numeric Formatting Audit

**This is a validation + architecture-design audit only. No code, templates, forms, or tests were modified. Nothing in this document should be implemented until explicitly approved.**

---

## Issue Validation

**The issue is real, current, and more severe than the one-line backlog entry suggests.** This was verified directly in code (not assumed from the backlog), across the full stack:

- **3 independently-implemented currency/thousands-separator formatters** exist and are in live use simultaneously (`smart_number`/`smart_money`, `rial`/`toman`, plus a third, effectively dead, copy in `apps/reports/discount_services.py`).
- **5 independently-implemented Iranian mobile-phone normalizers** exist; the one whose own docstring calls it "Central phone normalization" (`apps/common/phone_utils.py`) is used by the *fewest* call sites of the five.
- **20 independent Persian/Arabic-digit-to-ASCII conversion implementations** exist (9 in Python, 11 in JavaScript), including 9 templates that paste in a byte-identical inline `<script>` block that duplicates logic already loaded globally in `templates/base.html`.
- **Raw, unformatted numbers are rendered directly in production templates today**, most visibly: SMS wallet balances (`templates/sms/outbox_admin_list.html:22`, `outbox_detail.html:55`), platform SMS billing amounts (6 templates using `|floatformat:0`, which strips decimals but adds no thousands separator), and the admin reports revenue total (`templates/reports/list.html:38` — `{{ revenue_summary.total_revenue }} ریال` with zero formatting on a real money figure).
- **National ID and postal code fields have zero formatting, masking, or validation anywhere** — not in Forms, not in models, not in templates, not in JS. They are plain `CharField`s end to end.
- **Phone-number and national-ID input masking do not exist at all** on the frontend — every phone/national-ID `<input>` is a bare `type="text"` with only a placeholder string.
- **No CSS removes native number-input spin buttons anywhere** in the codebase (zero matches for `-webkit-inner-spin-button` / `-moz-appearance` across all of `static/`).
- **`django.contrib.humanize` is installed** (`config/settings/base.py:32`) **but never used** — the team built two parallel custom filter families instead.
- A client-side band-aid (`window.RastiFormatNumbers.apply()` in `static/js/rasti_ui_formatters.js`) already exists specifically to paper over raw, unformatted numbers left in the DOM by the server — direct evidence the team already recognized this exact problem and patched around it rather than fixing the source.

**Conclusion: do not close this issue.** Proceed to design a standard, per the approved scope of this task (design only, no implementation).

---

## Executive Summary

The product has no single numeric-formatting system. Instead it has **at least 6 loosely-related, independently-evolved formatting concerns** (currency, phone, national ID, Persian-digit conversion, percentages, generic thousands-separator/date-counters), each with **multiple competing implementations** that arose from a pattern of copy-paste "hotfixes" rather than editing/reusing an existing shared module. The most-reused, most-robust implementations already exist (`apps/common/templatetags/smart_numbers.py` for currency, `apps/common/phone_utils.py` for phone) but are **not consistently adopted** — sibling filters/functions with weaker guarantees (`fa_labels.rial`/`toman`, four other phone normalizers) coexist and are called from different parts of the codebase, sometimes on the very same page. Frontend duplication is worse than backend duplication: JavaScript number-formatting logic is copy-pasted verbatim into at least 9 individual templates instead of relying on the two shared files already loaded globally on every page. Two entire concerns in the backlog (national ID, postal code) have **no implementation to consolidate** — they need to be built from scratch, not migrated.

This report inventories every implementation found, proposes one server-side and one client-side canonical module per concern (reusing the strongest existing implementation of each wherever one already exists), and lays out a phased, low-risk migration strategy. No code is changed by this report.

---

## Project-wide Inventory

### Backend (Python / Django templates)

| Concern | File | Symbol | Technology | Robustness |
|---|---|---|---|---|
| Currency/thousands-sep | `apps/common/templatetags/smart_numbers.py:59-66` | `smart_number`, `smart_money` filters | Django template filter, `Decimal`-based | High — handles Persian/Arabic digit input, fractions, negative signs |
| Currency/thousands-sep + suffix | `apps/common/templatetags/fa_labels.py:196-209` | `rial`, `toman` filters | Django template filter, `int()`-based | Low — no Persian-digit tolerance; silently falls back to raw unformatted string on any error (`except: return str(value)`) |
| Currency/thousands-sep (dead) | `apps/reports/discount_services.py:18-23` | `_discount_campaign_format_rial` | Plain Python function | Unused — no call sites found; module instead inlines `f"{amount:,} ریال"` directly at lines 316, 423 |
| Phone normalization (documented canonical) | `apps/common/phone_utils.py:26-87` | `normalize_iran_mobile`, `is_valid_iran_mobile` | Plain Python, `str.maketrans` + regex | High — handles Persian digits, `+98`/`0098`/`98`/bare-9 prefixes; has docstring examples |
| Phone normalization | `apps/sms/services.py:28-51` | `normalize_sms_phone_number` | Plain Python, chained `.replace()` | Medium — widest call-site footprint (7+ files) |
| Phone normalization | `apps/sms/services_inbox.py:45-81` | `normalize_phone` | Plain Python, unicode-escape variant | Medium — functionally near-identical to above |
| Phone normalization | `apps/platform_core/services_platform_sms.py:20-39` | `normalize_platform_sms_phone` | Plain Python | Medium — near-verbatim copy of `sms/services.py` version |
| Phone normalization | `apps/accounts/views_password_reset.py:86-108` | `_normalize_phone`, `_mask_phone` | Plain Python, `zip()` loop | Medium — also the only implementation with a display-masking counterpart |
| Persian-digit conversion (general) | `apps/common/jalali.py:12,15-16` | `PERSIAN_DIGITS`, `normalize_digits` | `str.maketrans` | High — most general-purpose; reused cross-module (e.g. by `views_admin.py:1262`) |
| Persian-digit conversion (7 more copies) | see Duplicate Implementations below | — | Mixed | Low — each is a narrow, file-local reimplementation |
| Money parsing from POST | `apps/tenants/views_admin.py:1261-1268` | `_parse_money_from_post` | View-layer helper | Medium — combines `jalali.normalize_digits` + comma-strip + `int(float(...))` |
| Percentage parsing from POST | `apps/tenants/views_admin.py:1271-1284` | `_parse_wage_percent` | View-layer helper, `Decimal`-based, clamps 0–100 | Inconsistent — does **not** call `normalize_digits`, unlike its sibling function two lines above |
| Date formatting | `apps/common/templatetags/jalali_tags.py:6-31` | `jalali_date`, `jalali_datetime` filters | Delegates to `apps/common/jalali.py` | High — single source, no duplication found here |
| National ID | *(none)* | *(none)* | *(none)* | **Missing entirely** — `apps/accounts/models.py:129` is a bare `CharField(max_length=20, blank=True)`, zero validators |
| Postal code | *(none)* | *(none)* | *(none)* | **Missing entirely** — same pattern in `apps/tenants/models.py` merchant-profile fields |
| Django built-in `humanize` | `config/settings/base.py:32` | `intcomma`, etc. | Installed, `INSTALLED_APPS` | **Unused** — zero `{% load humanize %}` in any live template |
| Forms/Widgets | `apps/accounts/forms.py`, `apps/orders/forms.py`, `apps/platform_core/forms.py`, `apps/tenants/forms.py` | plain `CharField`/`IntegerField` | Django Forms | **No custom validation/formatting at the Form layer at all** — zero `clean_<field>` methods for money/phone/national-id fields anywhere; zero custom Field or Widget subclasses in the whole repo |

### Frontend (JavaScript / CSS / template-embedded `<script>`)

| Concern | File | Symbol | Notes |
|---|---|---|---|
| Currency/thousands-sep (DOM-scan, generic) | `static/js/rasti_ui_formatters.js:2-3` | `window.RastiFormatNumbers.apply()` | Global, loaded on every page via `templates/base.html`. Regex-adds commas to any matching leaf element's text content on `DOMContentLoaded` only (no `MutationObserver` — misses dynamically-injected content). Explicitly skips phone-like strings. Adds no currency suffix, no Persian-digit conversion. |
| Currency (narrow, Persian-phrase-specific) | `static/js/rasti_ui_formatters.js:6-30` | `window.RastiFixPersianAmounts` | Global. TreeWalker-based; only fixes the literal Persian phrase pattern "تا سقف X ریال." Duplicated verbatim into 6 more templates (see below) despite already being global. |
| Currency (fallback copy) | `static/js/rasti_sidebar.js` | `formatNumbers()` | Defensive fallback if `window.RastiFormatNumbers` isn't present; uses a **slightly different** selector (`td,th` unscoped vs. `.dashboard-content td,.dashboard-content th`), meaning the fallback path — if it ever fires — formats a broader set of table cells than the canonical path. |
| Currency (page-local, `toLocaleString`) | `templates/orders/technician_invoice_create.html:494-517` | inline `<script>` | Only file using the `Number.toLocaleString("fa-IR", ...)` API instead of manual regex — a fourth distinct code style for the same concern. |
| Currency (page-local, manual regex trio) | `templates/reports/discount_single_customer.html:75-95`, `discount_campaign_preview.html:76-96`, `discount_campaign_manual.html:98-111` | inline `<script>` | Byte-for-byte identical `normalizeDigits/digitsOnly/formatRial` trio pasted into 3 separate templates. |
| Currency (page-local, `RastiFixPersianAmounts` clone) | `templates/sms/outbox_list.html:33-58`, `outbox_detail.html:71-94`, `outbox_admin_list.html:141-164`, `sms/diagnostics.html:79-102`, `platform_core/platform_sms/outbox.html:67-91`, `tenants/admin_technician_form.html:155-188` | inline `<script>`, marker comment `discount_outbox_display_amount_format_7c4` in 5 of the 6 | Byte-for-byte identical to the already-global `RastiFixPersianAmounts` — the single clearest duplication example found in the whole audit. |
| Persian-digit conversion (JS) | `static/js/rasti_ui_formatters.js`, `static/js/jalali_datepicker.js:24-28`, plus the 9 inline-script copies above | 11 total distinct copies | See Duplicate Implementations |
| Numeric input restriction (typing-time) | *(none found)* | — | **No digit-only keydown/keypress restriction exists anywhere.** Reliance is entirely on HTML `inputmode="numeric"` (15 occurrences) vs. native `type="number"` (57 occurrences — the dominant pattern). |
| Live thousands-separator while typing | *(one exception)* | `templates/reports/discount_campaign_manual.html:146` | Only a `blur` handler, not live-as-you-type, and only on this one field. |
| Phone-number input masking | *(none found)* | — | Every phone `<input>` (9+ templates) is bare `type="text"` with only a placeholder. |
| National-ID input masking | *(none found)* | — | All 3 usages route through the shared `templates/tenants/includes/field.html` partial, which is a bare `type="text" dir="ltr"` input. |
| Spin-button removal CSS | *(none found)* | — | Zero matches for `-webkit-inner-spin-button` / `-moz-appearance` across all `static/css/`. |
| Mobile-zoom-on-focus overlap | `static/css/base.css:164-170`, `static/css/tokens.css:142-151` | — | Inputs inherit ambient (sub-16px) font-size; no dedicated fix exists. Directly relevant to sibling EPIC-002 Issue 006 — any CSS touched for spin-button removal will likely sit in the same rule block as a font-size fix, but Issue 006 itself is out of scope here. |

---

## Existing Formatting Systems

Distilled from the inventory above, there are effectively **6 independent "systems"** operating today, none of which is a deliberate, singular standard:

1. **`smart_numbers.py` (Decimal-based currency filter)** — the strongest existing implementation; a reasonable foundation for a standard.
2. **`fa_labels.py` (`rial`/`toman`, `int()`-based)** — weaker sibling, in parallel use.
3. **`apps/common/phone_utils.py`** — documented as canonical but least-adopted of 5 phone normalizers.
4. **4 other ad hoc phone normalizers**, each scoped to one app/service.
5. **`rasti_ui_formatters.js` (global DOM-scan formatter)** — a client-side compensation layer for gaps in system 1/2, not a designed standard.
6. **Ad hoc inline `<script>` duplication** in ~10 templates — not a system at all, just copy-paste drift from system 5 and from the report-page trio.

No system currently covers: national ID, postal code, live-typing input masks, or spin-button suppression — these are gaps, not competing implementations.

---

## Duplicate Implementations

**Currency/thousands-separator — 3 Python + 6 JS-level duplicates:**
- Python: `smart_numbers.smart_number`/`smart_money` (identical pair — literally the same function registered under two names) vs. `fa_labels.rial`/`toman` vs. dead `discount_services._discount_campaign_format_rial`.
- JS: `RastiFormatNumbers` (global) vs. `rasti_sidebar.js`'s fallback copy vs. `RastiFixPersianAmounts` (global) duplicated verbatim into 6 templates vs. the 3-template `normalizeDigits/digitsOnly/formatRial` trio vs. the 1-off `toLocaleString("fa-IR")` variant.

**Phone normalization — 5 Python implementations**, only one of which is documented as canonical (`phone_utils.normalize_iran_mobile`) and it has the fewest callers of the five.

**Persian/Arabic-digit-to-ASCII conversion — 20 total implementations** (9 Python + 11 JS) — the single most duplicated piece of logic in the product. Every module that needs this rolls its own translation table instead of importing `apps/common/jalali.normalize_digits` (Python) or `RastiFixPersianAmounts._normalizeDigits` (JS, already global).

**National ID / postal code — 0 implementations** (not a duplication problem; a missing-feature problem).

**`django.contrib.humanize` — installed, 0 real usages** — effectively a third, unused currency-formatting option sitting dormant in `INSTALLED_APPS`.

---

## Recommended Standard

Reuse the strongest existing implementation per concern rather than inventing new ones, per the "reuse before creating new" instruction:

| Concern | Proposed single source of truth | Rationale |
|---|---|---|
| Currency / thousands-separator (server) | `apps/common/templatetags/smart_numbers.smart_number` (keep `smart_money` as an alias for call-site readability, but implemented as a thin wrapper, as it already is) | Already the most robust implementation (Decimal-based, digit-tolerant, fraction-aware). `fa_labels.rial`/`toman` should become thin wrappers that call `smart_number` and append the suffix, not separate reimplementations. |
| Currency / thousands-separator (client) | `window.RastiFormatNumbers` in `static/js/rasti_ui_formatters.js`, extended with a `MutationObserver` (currently `DOMContentLoaded`-only) | Already global, already loaded everywhere; needs one enhancement (observe dynamic content) rather than replacement. |
| Persian-digit → ASCII (server) | `apps/common/jalali.normalize_digits` (rename/move consideration only if approved later — not done here) | Already the most general-purpose, already reused cross-module. |
| Persian-digit → ASCII (client) | `RastiFixPersianAmounts._normalizeDigits` in `rasti_ui_formatters.js`, promoted to a standalone exported helper (e.g. `window.RastiNormalizeDigits`) so other inline scripts can call it instead of re-declaring it | Already global; just needs to be exposed independently of the narrow `RastiFixPersianAmounts` feature it currently lives inside. |
| Phone normalization (server) | `apps/common/phone_utils.normalize_iran_mobile` / `is_valid_iran_mobile` | Already documented as canonical in its own module docstring; just needs actual adoption by the other 4 call sites. |
| Phone input masking (client) | **New** — none exists today; would need to be built (out of scope to design in full here beyond noting the gap) |
| National ID formatting/validation | **New** — none exists today (server validator + optional display formatter) |
| Postal code formatting/validation | **New** — none exists today (server validator) |
| Percentage parsing (server) | Align `_parse_wage_percent` to call `jalali.normalize_digits` first, matching its sibling `_parse_money_from_post` | Removes the one concrete inconsistency found between two adjacent functions in the same file. |
| Spin-button suppression (client CSS) | **New** — a single global CSS rule (e.g. in `static/css/base.css`, alongside the existing `input, textarea, select` block already noted for Issue 006 overlap) | No implementation exists to reuse; this is additive, not a migration. |
| `django.contrib.humanize` | **Do not adopt** | Two custom filter families already exist and are template-facing throughout the product; migrating to `humanize`'s `intcomma` would be a third parallel system, not a consolidation. Recommend leaving it installed-but-unused, or removing it from `INSTALLED_APPS` in a later, separate cleanup — not a numeric-formatting-standard concern. |

---

## Migration Strategy

1. **No behavior change in phase 1.** Make `fa_labels.rial`/`toman` delegate to `smart_numbers._format_decimal` internally (same output format, just one code path) — a pure refactor, zero template changes required, fully backward compatible.
2. **Backfill missing filters onto raw templates.** Add `|smart_number` (or `|rial`) to the confirmed-raw templates found in this audit (SMS wallet balances, revenue total, `|floatformat:0` money fields) one template at a time, each independently testable and revertable.
3. **Consolidate phone normalization.** Point the 4 non-canonical phone normalizers at `apps/common/phone_utils.normalize_iran_mobile` one call site at a time (service-by-service), keeping each service's public function signature unchanged so callers don't need to change — only the internal implementation is swapped.
4. **Consolidate Persian-digit conversion.** Same approach: swap each of the 9 Python and 11 JS local implementations to import/call the shared helper, one file at a time. The 6 near-identical `RastiFixPersianAmounts`-clone templates are the lowest-risk, highest-value first target (delete the inline `<script>` block entirely, since the identical global version already runs on the same page).
5. **New capabilities (national ID, postal code, phone/national-ID input masking, spin-button CSS) are additive** — they don't migrate anything, so they carry no regression risk against existing behavior and can be sequenced independently/in parallel with steps 1–4.
6. **Percentage-parsing fix** (`_parse_wage_percent`) is a 1-line, 1-file change, isolated from everything else.

### Backward Compatibility

- All proposed server-side changes preserve existing filter/function **names and signatures** — templates calling `|rial`, `|smart_number`, `normalize_sms_phone_number(...)`, etc. do not need to change their call syntax, only the internal implementation is unified.
- Output format of `smart_number`/`smart_money` is unchanged (it becomes the canonical implementation, not a new one) — `rial`/`toman` gain Persian-digit tolerance they lack today (a strict improvement, not a behavior change for the existing all-ASCII-digit inputs they currently handle).
- No database migration is implied by anything in this report — all affected fields (`national_id`, phone fields) are already `CharField`; adding a validator does not require a migration.

---

## Files Potentially Affected

This list is for future implementation planning only — **nothing here is to be changed as part of this audit.**

**Backend consolidation candidates:**
- `apps/common/templatetags/smart_numbers.py`
- `apps/common/templatetags/fa_labels.py`
- `apps/common/phone_utils.py`
- `apps/common/jalali.py`
- `apps/sms/services.py`, `apps/sms/services_inbox.py`
- `apps/platform_core/services_platform_sms.py`
- `apps/accounts/views_password_reset.py`
- `apps/tenants/views_admin.py` (`_parse_money_from_post`, `_parse_wage_percent`)
- `apps/reports/discount_services.py` (remove dead `_discount_campaign_format_rial`, or wire it to the standard if kept)

**Frontend consolidation candidates:**
- `static/js/rasti_ui_formatters.js`
- `static/js/rasti_sidebar.js`
- `templates/sms/outbox_list.html`, `outbox_detail.html`, `outbox_admin_list.html`, `sms/diagnostics.html`, `platform_core/platform_sms/outbox.html`, `tenants/admin_technician_form.html` (remove inline duplicate scripts)
- `templates/reports/discount_single_customer.html`, `discount_campaign_preview.html`, `discount_campaign_manual.html` (remove inline duplicate scripts)
- `templates/orders/technician_invoice_create.html` (unify with canonical formatter)

**Raw-number template backfill candidates:**
- `templates/sms/outbox_admin_list.html`, `outbox_detail.html`
- `templates/platform_core/sms_billing/index.html`, `invoice_detail.html`, `transactions.html`, `invoices.html`, `companies.html`
- `templates/tenants/admin_sms_credit.html`
- `templates/reports/list.html`
- `templates/platform_core/plan_list.html`

**New-capability files (to be created, not migrated):**
- A national-ID validator (likely `apps/common/national_id.py` or similar, mirroring `phone_utils.py`'s shape)
- A postal-code validator (similar placement)
- Phone/national-ID input-masking JS (new, additive to `static/js/`)
- Spin-button-removal CSS rule (addition to `static/css/base.css`)

**Forms layer (currently bypassed entirely):**
- `apps/accounts/forms.py`, `apps/orders/forms.py`, `apps/platform_core/forms.py`, `apps/tenants/forms.py` — introducing `clean_<field>` methods here (rather than leaving all normalization in the view layer as today) would be an architectural change beyond simple consolidation and should be scoped as its own decision, not folded silently into a "formatting standard" implementation.

---

## Risk Analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Changing `fa_labels.rial`/`toman` internals breaks a template that depends on the exact current `int()`-truncation behavior (e.g. silently truncating a Decimal with a fractional Rial value differently than `smart_number` would) | Low–Medium | `smart_number`'s existing fraction-handling was designed for exactly this; spot-check money fields that are `Decimal` vs. `int` before switching internals. Financial-calculation values themselves are not touched — only *display* formatting. |
| Swapping a phone normalizer's internals changes behavior for an edge-case input format one of the 5 implementations currently handles differently (e.g. an input format `phone_utils` doesn't yet cover) | Medium | Each of the 5 implementations should be diffed input-by-input (unit test parity) before any call site is switched — do this per Rule 9 (test coverage required for any change) before touching `apps/sms/*`, which is explicitly flagged as sensitive ("Do NOT modify notification delivery" / "Do NOT modify SMS logic" in prior EPIC-002 approvals — a full consolidation of `apps/sms/services.py`'s phone normalizer would need explicit sign-off given that constraint). |
| Removing inline `<script>` duplicates from SMS-outbox templates accidentally removes functionality if any of those 6 "identical" copies has silently drifted from the global version | Low | Byte-diff each of the 6 against `rasti_ui_formatters.js`'s `RastiFixPersianAmounts` before deleting, not just visually — this report identified them as identical via direct comparison, but a future implementer should re-verify before deleting each one at time of implementation. |
| Backfilling `|smart_number` onto currently-raw wallet/revenue templates changes visible output (adds commas) — could be perceived as a "UI change" beyond pure bug-fix if any downstream screenshot/QA process expects the raw format | Low | This is the intended fix, not a side effect — flag explicitly in the implementation PR description so QA isn't surprised. |
| New national-ID/postal-code validators could reject previously-accepted (invalid but stored) data on next edit if validation is added at the Form layer | Medium | Any new validator should be display/input-layer only initially (format-as-you-type, non-blocking) rather than a hard `RegexValidator` that blocks saves, until existing stored data is audited for compliance — a data-quality pass, not a formatting-standard task, and should be scoped separately. |
| Percentage-parsing fix to `_parse_wage_percent` changes behavior for any caller currently relying on it silently failing/misparsing Persian-digit percent input | Low | Only 1 file, callers are 2 known lines in the same file (`views_admin.py:1507-1508, 1652-1653`) — narrow, easily tested blast radius. |

**Overall regression risk: Low, if migrated incrementally per the phased strategy above** (thin-wrapper delegation first, call-site swaps one at a time, new capabilities additive). **High risk only if attempted as one large refactor PR** — explicitly not recommended.

---

## Pattern Reuse

Per the "reuse existing patterns before creating new ones" instruction, this report's Recommended Standard section above deliberately does **not** propose new infrastructure for any concern that already has a working implementation:

- Currency: reuse `smart_numbers.py` (already the strongest).
- Phone: reuse `phone_utils.py` (already documented as canonical by its own author).
- Persian-digit conversion: reuse `jalali.normalize_digits` (server) and `RastiFixPersianAmounts._normalizeDigits` (client, needs only to be exposed independently).
- Percentage parsing: reuse the pattern already established by `_parse_money_from_post` (just apply it consistently to its sibling function).

New code is proposed **only** for concerns with zero existing implementation: national ID, postal code, phone/national-ID input masking, and spin-button CSS suppression — consistent with "only create new code if no reusable implementation exists."

---

## Suggested Architecture

*(Design-level sketch only — not an implementation plan for this task.)*

```
apps/common/
├── templatetags/
│   ├── smart_numbers.py     ← canonical currency filters (smart_number, smart_money, rial, toman as thin wrappers)
│   ├── jalali_tags.py       ← unchanged (date formatting, already single-source)
│   └── fa_labels.py         ← non-numeric label filters remain; rial/toman delegate to smart_numbers
├── phone_utils.py           ← canonical phone normalization (existing, gains adopters)
├── jalali.py                ← canonical Persian-digit conversion (existing, gains adopters)
├── national_id.py           ← NEW — validator (+ optional masked-display formatter)
└── postal_code.py           ← NEW — validator

static/js/
├── rasti_ui_formatters.js   ← canonical client formatter; RastiFormatNumbers gains MutationObserver;
│                                RastiFixPersianAmounts's digit-normalizer exposed as window.RastiNormalizeDigits
│                                for reuse by any remaining page-local script
└── (new, small) rasti_input_masks.js   ← NEW — phone/national-ID input masking, if approved

static/css/
└── base.css                 ← + spin-button suppression rule in the existing input/textarea/select block
```

No new Django app, no new context processor, no new template-tag library beyond what already exists in `apps/common/templatetags/` — this keeps the "one templatetags directory" pattern already established (confirmed: `apps/common/templatetags/` is the *only* templatetags directory in the entire product today).

---

## Implementation Phases

*(Sequencing proposal only, for the eventual approved implementation task — not started here.)*

1. **Phase 0 (this report):** Audit and design — complete.
2. **Phase 1 — Zero-risk internal delegation:** `fa_labels.rial`/`toman` call `smart_numbers._format_decimal` internally. `_parse_wage_percent` gains `normalize_digits`. No template changes, no visible output change for currently-well-formed inputs.
3. **Phase 2 — Dead-code removal:** Remove unused `discount_services._discount_campaign_format_rial`, or wire its 2 call sites (lines 316, 423) to `smart_number` instead of their current inline `f"{amount:,}"`.
4. **Phase 3 — Frontend duplicate removal (lowest risk, highest visible cleanup):** Delete the 6 byte-identical `RastiFixPersianAmounts` inline-script clones (the global version already covers the same pages). Delete/unify the 3-template `discount_*` inline trio.
5. **Phase 4 — Raw-template backfill:** Add `|smart_number`/`|rial` to the confirmed-raw wallet/revenue/billing templates, one at a time, each independently tested.
6. **Phase 5 — Phone-normalizer consolidation:** Swap the 4 non-canonical phone normalizers to delegate to `phone_utils.normalize_iran_mobile`, service by service, with input-parity unit tests first (per Risk Analysis — `apps/sms/*` requires extra care given prior "do not modify SMS logic" constraints in this EPIC).
7. **Phase 6 — New capabilities:** National-ID and postal-code validators/formatters, phone/national-ID input masking, spin-button CSS. Fully additive, no migration risk, can run in parallel with phases 1–5.
8. **Phase 7 — Dynamic-content formatting gap:** Add a `MutationObserver` to `RastiFormatNumbers` so AJAX/Alpine-injected content is also formatted (closes a currently-known gap noted in the frontend inventory).

Each phase is independently approvable and revertable — none depends on a later phase being done first.

---

## Tests Required

*(To be written at implementation time — none exist today for this concern.)*

- Unit tests asserting `fa_labels.rial`/`toman` and `smart_numbers.smart_number`/`smart_money` produce identical numeric output for the same input, before and after the Phase 1 delegation change (regression guard for the refactor itself).
- Input-parity tests comparing all 5 phone-normalizer implementations against a shared table of inputs (Persian digits, `+98`, `0098`, bare-9, malformed) — required *before* any Phase 5 consolidation, to prove no behavioral drift exists between them today.
- Template-rendering tests for each backfilled "raw number" template (Phase 4) confirming the previously-raw value now renders with thousands separators — following the exact pattern already used in `tests/test_issue001_public_payment_layout.py` / `tests/test_issue003_notification_message_leak.py` (render the page, assert on response content).
- New validator tests for national ID and postal code once built (Phase 6) — valid/invalid input tables.
- A source-level regression guard (grep-based test, same style as `MessageBlockSourceGuardTest` in `tests/test_issue003_notification_message_leak.py`) asserting the 6 SMS-outbox-family templates no longer contain a duplicate `RastiFixPersianAmounts`-style inline `<script>` block, to prevent the duplication from silently creeping back in.

## Documentation Updates

*(Not performed as part of this audit beyond creating this report — listed for the future approved implementation.)*

- `docs/03_Architecture/TEMPLATE_ARCHITECTURE.md` — currently has no section describing the numeric-formatting filter system at all; should gain one once a standard is implemented.
- A new `docs/04_Business_Rules/` or `docs/03_Architecture/` doc (e.g. `NUMERIC_FORMATTING_STANDARD.md`) documenting the canonical filters/functions per concern, so future AI/human contributors reach for `smart_number`/`phone_utils`/`jalali.normalize_digits` instead of writing a 21st Persian-digit converter.
- `docs/11_Project_Knowledge/KNOWN_RISKS.md` — consider logging the raw/unformatted wallet-balance and revenue-total templates as a known gap until Phase 4 lands.

---

## Recommendation

**Proceed to design-approval, not implementation, at this stage** (as instructed). Within the design, recommend:

- **Adopt `smart_numbers.py` and `phone_utils.py` as the two backend standards** (both already exist, both already the strongest implementations — pure reuse, no new infrastructure).
- **Sequence implementation in the 8 phases above**, starting with the zero-risk internal-delegation phase and the frontend duplicate-removal phase (Phase 3), which are the lowest-risk, highest-visible-cleanup wins and touch no business logic, no views, no URLs, and no migrations.
- **Treat national ID, postal code, and input masking as new, additive scope**, not a migration — and recommend they be split into their own EPIC-002-style issue/approval cycle rather than bundled into "consolidate existing duplicates," since they involve new validation rules (a product decision: what counts as a valid Iranian national ID/postal code) rather than pure refactoring.
- **Explicitly flag `apps/sms/*` phone-normalizer consolidation (Phase 5) for extra scrutiny** given this EPIC's repeated "do not modify SMS logic" instruction in prior issues — recommend a narrow, separately-approved sub-task rather than folding it into a general formatting cleanup.

## Approval Required

Do not implement until approved.

Options:

A. Approve the design as-is and proceed to Phase 1 (zero-risk internal delegation) + Phase 3 (frontend duplicate removal) as the first implementation task — lowest risk, highest cleanup value, no business-logic/SMS/view changes.

B. Approve the full design but request a different phase ordering or scope split (e.g., separate out national ID/postal code into its own issue immediately, as recommended above).

C. Approve only the audit/inventory (no phased plan) and request a narrower follow-up design for a single concern (e.g., currency only, or phone only) before committing to the full 8-phase roadmap.

D. Defer — no further action on Issue 004 for now.
