---
Title: Issue 004 — Numeric Formatting Product Specification
Layer: Epic 002 Product Polish
Audience: Human + AI
Status: Specification Draft — Awaiting Product-Owner Approval (Design Only, No Implementation)
Last Verified: 2026-07-01
Verified Against: apps/common/templatetags/smart_numbers.py, apps/common/templatetags/fa_labels.py, apps/common/phone_utils.py, apps/common/jalali.py, apps/invoices/models.py, apps/payouts/models.py, apps/api/serializers.py, apps/reports/views.py, apps/payouts/views.py, apps/tenants/views_admin.py, static/js/rasti_ui_formatters.js, docs/00_Project/GLOSSARY.md, docs/00_Project/TERMINOLOGY.md, docs/04_Business_Rules/PAYMENT_RULES.md, docs/04_Business_Rules/INVOICE_RULES.md
Source of Truth: This document (once approved) — supersedes ad hoc convention for numeric formatting
Depends On: docs/12_Epic_002_Product_Polish/ISSUE_004_NUMERIC_FORMATTING_AUDIT.md
Related Documents: docs/03_Architecture/TEMPLATE_ARCHITECTURE.md, docs/04_Business_Rules/PAYMENT_RULES.md, docs/04_Business_Rules/INVOICE_RULES.md
Reusable Across Projects: No
---

# Issue 004 — Numeric Formatting Product Specification

**This is a specification, not an implementation plan. No code, templates, or utilities were created or modified while writing this document. Every rule below is stated with its rationale so a future implementer (or a future product-owner revisiting this decision) can judge edge cases without re-deriving the reasoning from scratch.**

This document is written against the findings of `ISSUE_004_NUMERIC_FORMATTING_AUDIT.md` (read in full before this document was written) plus direct verification of storage types, API serialization behavior, and export mechanisms not covered in the original audit (see "Verified Against" above).

---

## 1. General Philosophy

**Rule:** Numeric *formatting* (thousands separators, currency suffixes, masking, digit-locale conversion) is a **presentation-layer concern only**. It happens at the last possible moment — in a Django template filter or a client-side display pass — and never touches how a value is stored, calculated, validated, or transmitted between systems.

**Why:** The audit found the opposite pattern already causing damage: formatting logic (comma-insertion, digit conversion) is duplicated into services, views, and even model `__str__` methods, entangling display concerns with business logic and multiplying the number of places a bug can hide. Keeping formatting at the edge means a single bug fix (e.g., a locale change) touches one filter, not twenty call sites.

**What gets formatted:** Any number *shown to a human* — currency amounts, phone numbers, national IDs, postal codes, percentages, quantities, and date-adjacent counters (pagination, "X روز پیش" style counters).

**What never gets formatted:** Any number used in a calculation, a database query, a URL, an API payload consumed by a machine, a CSV/export file consumed by spreadsheet software, or an idempotency key. These must remain in their raw, locale-independent form (ASCII digits, `Decimal`/`int`, no separators) at all times. Formatting a number that will be parsed again (by a browser form re-submit, by Excel, by another service) is a bug, not a feature — this exact distinction is why CSV export currently emits raw integers rather than comma-separated strings (`apps/reports/views.py:293`, verified), and this specification codifies that existing correct behavior as a rule rather than an accident.

**Where formatting applies, by surface:**

| Surface | Formatting applies? | Why |
|---|---|---|
| Django templates (all roles: admin, technician, customer, public) | Yes | This is the actual point of human consumption. |
| REST API responses (`apps/api/`) | No | Consumed by code (mobile app, JS, integrations), not read directly by a human in most cases; see §15. |
| CSV/Excel export | No (see §2, §16) | Consumed by spreadsheet software that must sort/sum the column; a comma-formatted string is text, not a number, to Excel. |
| Database | No | Storage is never formatted; formatting is not persisted (see §2). |
| SMS/notification message bodies | Yes, but via the *same* backend filters/functions used in templates — SMS text is still human-facing text, just delivered through a different channel. |
| PDF export | Not currently implemented (see §2, §16) — the existing "print" pages (`templates/invoices/print.html`) are HTML rendered for the browser's native print-to-PDF, which already goes through the same template filters as any other page. There is no separate server-generated PDF pipeline today; this specification does not need to define a second set of rules for one, but §17 notes what would be required if one is added later. |
| Admin vs Technician vs Public pages | Same rules everywhere | Formatting must be role-agnostic. The audit found no case where a different format was *intentionally* used per role — inconsistency found was accidental (missing filters), not a deliberate design difference. Divergent formatting per role would itself be a bug under this specification unless explicitly justified by a future ADR. |

---

## 2. Currency Rules

**Official storage unit: Iranian Rial, as an integer (no sub-unit).**

*Why:* Verified directly in the schema — every money-carrying field in the codebase is either `DecimalField(max_digits=12, decimal_places=0, ...)` (`apps/invoices/models.py:150`, `total_amount`) or `PositiveBigIntegerField`/`BigIntegerField` named `*_rial` (`apps/payouts/models.py:74,164,233,388` — `amount_rial`, `total_amount`, `amount_rial`, `fixed_wage_rial`). `decimal_places=0` on every single money field is not an accident — the Iranian Rial has no functional sub-unit in this product's domain (there is no "1.5 Rial" business case). This specification ratifies the existing, universal storage convention rather than inventing a new one.

**Official display unit: Rial**, formatted with thousands separators and the literal suffix "ریال".

*Why Rial and not Toman:* Both a `rial` filter and a `toman` filter exist in `apps/common/templatetags/fa_labels.py`, but direct verification (`grep -rn "|toman" templates/` and `grep` for `|rial` usage) found **zero template call sites for either filter** — every one of the 54 templates that format currency does so via `|smart_number` and appends the literal text "ریال" separately (e.g. `templates/invoices/detail.html:23` — `{{ invoice.total_amount|smart_number }} ریال`). Combined with the storage-layer finding above (every field is named `*_rial`, never `*_toman`), Rial is unambiguously the product's existing standard, even though a `toman` filter sits unused in the codebase. This specification declares Rial official and treats the `toman` filter as dead code to be addressed under Migration Rules (§16) — not because Toman display is forbidden forever, but because introducing a second unit today, with zero current adoption and no product requirement documented anywhere (`GLOSSARY.md`/`TERMINOLOGY.md`/`PAYMENT_RULES.md` contain no mention of Toman as a display requirement), would reintroduce exactly the duplication this specification exists to remove.

**Thousands separator:** Comma (`,`), inserted every 3 digits from the right, Latin/ASCII digits in the formatted output (not Persian numerals) — e.g. `1,250,000`.

*Why ASCII digits in output, not Persian numerals:* This matches the current, dominant, live implementation (`smart_numbers._format_decimal`, used in 54 templates) exactly as it exists today — verified in code (`apps/common/templatetags/smart_numbers.py:37-56` builds `f"{int(d):,}"`, which is always ASCII). Switching the *output* to Persian numerals would be a genuine, visible product change (not a consolidation) and is explicitly out of scope for a duplication-removal specification — if the product owner wants Persian-numeral *output* as a future direction, that is a new product decision, not a formatting-consistency fix, and should be raised as an open question (see end of this document) rather than assumed here.

**Negative values:** A leading `-` sign, no parentheses, no red color mandated by this spec (color is a UI/theme concern, not a formatting concern) — e.g. `-500,000`. *Why:* This is what `smart_numbers._format_decimal` already does (`sign = "-" if d < 0 else ""`), and no business rule doc anywhere calls for parenthesized negatives, which is an accounting convention this product's UI does not otherwise use.

**Zero:** Displays as `0`, not blank, not `-`, not `۰ریال` with no space. *Why:* A blank cell for a zero balance is a common source of "did this number just fail to load?" confusion; an explicit `0` is unambiguous. This is also already the behavior of `smart_number` on `0` input (falls through the same integer-formatting path).

**Null / missing:** Must not be passed through the currency filter and rendered as the literal string `"None"`. The template (or the view feeding it) is responsible for supplying a default (typically `0`) or an explicit placeholder (`—`) before the value reaches the currency filter. *Why:* `smart_numbers._clean_number` already returns `None` for `None` input, and `_format_decimal` then returns the *original* value unchanged (line 39-40: `if d is None: return value`) — meaning today, an unguarded `{{ maybe_none|smart_number }}` silently renders the Python `None` object as the string "None" in the page. This is a real, currently-live gap (not previously flagged in the audit) worth calling out explicitly: **the specification requires call sites to guard against `None` before the filter, not inside the filter**, because a filter that silently substitutes `0` for `None` could mask a genuine data bug (e.g., an invoice that never got its `total_amount` calculated) by making it look like a legitimate zero-value invoice.

**Decimals:** Since storage is always `decimal_places=0`, standard currency amounts never carry a fractional part in Rial. `smart_number`'s fraction-handling logic exists for non-Rial numeric contexts (e.g., a wage-rate multiplier that could be fractional) — this specification does not require every use of `smart_number` to be Rial-integer-only, but currency-specifically, the expectation is a whole number.

**Discounts, taxes:** Same rules as currency — they are Rial amounts and follow every rule above. No separate formatting convention.

**Percentages:** See §6 — percentages are a distinct concern (no thousands separator, `%` suffix instead of "ریال").

**Wallet values (SMS credit, technician ledger balances):** Same currency rules apply. The audit found these are the **most frequently unformatted** in the current codebase (`templates/sms/outbox_admin_list.html:22`, `outbox_detail.html:55`, `tenants/admin_sms_credit.html:16` using `|floatformat:0` which strips decimals but adds no separator) — this specification explicitly closes that gap by requiring the same `smart_number`-family filter on every wallet/balance display, with no exception for "internal-looking" numbers. *Why call this out specifically:* wallet balances are real money the tenant has prepaid or is owed; treating them as lower-priority than invoice totals was never a deliberate design decision, just an oversight this spec corrects.

**Reports, invoices, payments, notifications:** All follow the same currency rules — one format, everywhere. *Why not report-specific formatting (e.g., abbreviated "1.2M" for dashboard stat cards):* No such convention exists anywhere in the current codebase, and introducing abbreviated/rounded currency display for financial figures carries real risk of misreading a number in a business context (a report showing "1.2M" when the true figure is 1,249,999 could mislead a company admin making a financial decision). If a future dashboard specifically wants abbreviated large-number display for *non-financial* counters (e.g., "1.2K orders"), that should be a separate, explicitly-scoped decision — not silently bundled into the currency standard.

**SMS message bodies:** Currency mentioned inside an SMS text (e.g., "فاکتور شما به مبلغ ۵۰۰,۰۰۰ ریال صادر شد") must use the same backend formatting function that templates use, not a separate ad hoc `f"{amount:,}"` inline in the SMS-building code. *Why:* SMS templates are still human-facing; a second, unaudited formatting path for SMS text would recreate exactly the duplication problem this specification exists to prevent (the audit already found `apps/reports/discount_services.py:316,423` doing exactly this — an inline `f"{amount:,} ریال"` bypassing every shared filter).

**PDF export:** Not currently implemented as a distinct pipeline (see §1) — the existing invoice "print" page already goes through standard template filters, so no separate rule is needed today. If a true server-rendered PDF pipeline (e.g., WeasyPrint, ReportLab) is added later, it must reuse the same backend formatting functions this specification defines (§11), not reimplement them for the PDF context — flagged in §17 as a forward-compatibility requirement.

**Excel export:** Not currently implemented (no `openpyxl`/`xlsxwriter` found anywhere in the codebase — verified). If added later, numeric cells must be written as native numeric types (`int`/`float`/`Decimal`), never as pre-formatted strings, so that Excel's own locale-aware number formatting and sorting/summing work correctly — the same reasoning as CSV below.

**CSV export:** Numbers must always be written **raw** — no thousands separators, ASCII digits, and the correct raw type (the value's own `int`/`Decimal`, not a display string). This is already the codebase's actual behavior (verified: `apps/reports/views.py:293`, `row["invoice_sum"]` is a raw `int`) and this specification ratifies it as a firm rule rather than a coincidence. *Why:* A CSV cell containing `"1,250,000"` is interpreted by Excel/Sheets as **text**, not a number — it cannot be summed, sorted numerically, or used in a formula without the end user manually cleaning the column first. This is a correctness requirement, not a style preference.

---

## 3. Phone Number Rules

**Storage format: `09xxxxxxxxx` — exactly 11 ASCII digits, always starting with `09`.**

*Why:* This is already explicitly documented as the contract in the existing canonical module's own docstring (`apps/common/phone_utils.py:4-5`: "All phone storage in the database uses the format: 09xxxxxxxxx (11 digits)"). This specification adopts that existing, already-correct contract rather than inventing a new one.

**Internal/normalized format (used for storage, lookups, comparisons, deduplication):** Same as storage format — `09xxxxxxxxx`. There is no separate "internal" format distinct from storage; keeping these identical avoids yet another conversion step and matching bug class.

**Display format:** By default, the same `09xxxxxxxxx` form, left-to-right (`dir="ltr"` / `.ltr-cell` styling, already used consistently across templates per the audit's file samples). No parentheses, no dash-grouping (e.g., not `0912-123-4567`) unless a future UI decision explicitly requests it — no such requirement exists in any current design doc.

*Why no dash-grouping by default:* No business rule doc or existing template requests it, and adding it purely for "readability" would be a cosmetic product decision outside a duplication-removal specification's scope. If desired, this should be raised as an explicit open question (see end of document), because it changes what a copy-pasted phone number looks like and could affect downstream paste-into-another-system workflows.

**Masking (partial display, e.g., for privacy in shared/exported views):** One existing implementation already does this — `apps/accounts/views_password_reset.py:105-108`, `_mask_phone()`, producing `phone[:4] + "***" + phone[-3:]` (e.g., `0912***567`). This specification adopts this as the standard masking format *where masking is used*, but does not mandate masking phone numbers everywhere — masking is a privacy decision made per-screen (e.g., "is this phone number visible to a technician who shouldn't see the customer's full number?") which is a permissions question (`docs/03_Architecture/PERMISSIONS.md`), not a formatting question. This specification only fixes the *format* of the mask when a screen has already decided to mask.

**Input normalization (what a user may type, and how it becomes the storage format):**

The normalizer must accept, and correctly convert to `09xxxxxxxxx`:
- Persian digits (۰۹۱۲...) and Arabic-Indic digits (٠٩١٢...)
- International format with `+98`, `0098`, or bare `98` prefix
- The short form without the leading zero (`9121234567`)
- Input containing spaces, dashes, parentheses, or a zero-width non-joiner (already handled by the existing canonical implementation, `apps/common/phone_utils.py:60`)

*Why this exact list, no more no less:* This is precisely the input space the existing, most-robust implementation (`normalize_iran_mobile`) already handles and has doctested examples for (`apps/common/phone_utils.py:39-51`). This specification does not expand scope beyond what's already proven correct — it standardizes on it.

**Persian digits / English digits:** A user must be able to type either, and the result must always be stored and displayed in English (ASCII) digits. *Why:* Storage in Persian numerals would break every downstream integer/regex operation (SMS gateway APIs, uniqueness lookups) that assumes ASCII digits — this is not a display preference, it's a data-integrity requirement, and matches the existing normalizer's actual behavior.

**International format:** Only Iranian mobile numbers are in scope for this specification (the product is Iran-only per `docs/00_Project/PROJECT_SCOPE.md`'s domain — verified indirectly via the existing `_IRAN_MOBILE_RE = re.compile(r"^09\d{9}$")` being the only validation pattern anywhere in the codebase). If the product ever needs to support non-Iranian phone numbers, that is a new product requirement (see §17), not a formatting-consistency fix.

**Validation:** A phone number is valid if and only if, after normalization, it matches `09` followed by exactly 9 more digits (11 digits total). This is already the existing rule (`phone_utils.is_valid_iran_mobile`); this specification does not change the validation rule, only requires it be applied consistently everywhere a phone number is accepted (see §16 for how the 4 other, non-canonical, normalizers should be reconciled).

**Masking on input (as-you-type formatting):** Not currently implemented anywhere (verified: no phone input mask exists in any template). This specification does **not** mandate live input masking (e.g., auto-inserting spaces as `0912 123 4567` while typing) as a hard requirement — it is a UX enhancement, not a duplication fix, and should be scoped as new work (§16/§17), not implied by this document. If implemented later, it must call the same shared normalization logic defined here, not a new one.

---

## 4. National ID Rules

**Current state: no storage convention, no validation, no display convention exists anywhere in the codebase today** (verified: `apps/accounts/models.py:129` is a bare `CharField(max_length=20, blank=True)`, and a repo-wide search for checksum/`mod 11`/weighting logic — the standard Iranian national-ID validation algorithm — returned zero hits). This section therefore *defines* a rule rather than *consolidating* existing ones — this is new-feature specification, not migration, and should be flagged to the product owner as such (see open questions).

**Storage:** 10 ASCII digits, no separators, no leading/trailing whitespace, stored as-is in the existing `national_id` `CharField`. *Why keep it a `CharField` and not an `IntegerField`:* a valid Iranian national ID can have leading zeros (e.g., `0012345678`), which an integer type would silently strip — this specification explicitly forbids ever storing national ID as a numeric type, only as a fixed-format digit string.

**Display:** The raw 10-digit string, optionally grouped for readability as `XXX-XXXXXX-X` (a common Iranian convention: 3 digits, 6 digits, 1 check digit) purely as a *display* transformation, never altering the stored value. *Why offer grouping as optional rather than mandatory:* no existing template does this today, and mandating a new visual convention with zero current precedent is a product decision, not a pure consistency fix — flagged as an open question below rather than decided unilaterally here.

**Validation (recommended, not yet decided — see open questions):** The standard Iranian national-ID checksum: 10 digits, where the 10th digit is a checksum computed from the first 9 using a fixed weighting scheme (multiply digit *i* — 1-indexed from the left — by (11 − *i*) for *i* = 1..9, sum, take mod 11; the result — or a mod-11-of-that-result rule for the 10 vs 11 edge case — must equal the 10th digit). *Why recommend this specific algorithm rather than "any 10-digit string":* it is Iran's actual national standard for this identifier, well-documented and stable, and enforcing it would catch obvious typos (transposed digits, wrong digit count) at data-entry time rather than storing garbage that fails later at a critical moment (e.g., a KYC submission bounced by a payment provider). This specification recommends validating it, but does not mandate blocking form submission on failure — see the Migration Rules note on new validators being non-blocking until existing stored data is audited (§16), since this field already has unvalidated data in production today (unverified but likely, given zero validation has ever existed).

**Masking:** Not currently implemented, no existing convention. If masking is desired for privacy (e.g., showing only the last 4 digits to a technician), that is a permissions decision layered on top of this formatting spec, following the same masking-format precedent already established for phone numbers in §3 (prefix/suffix visible, middle replaced with `*`) for consistency, if and when a screen requires it.

**Admin visibility:** `COMPANY_ADMIN` and `PLATFORM_OWNER` roles currently see the raw field (per the 3 template usages found in the audit, all under merchant-profile/KYC screens, all admin-only routes). This specification does not change *who* can see it — that remains a `PERMISSIONS.md` concern — it only standardizes *how* it looks once a role is already permitted to see it.

**Public visibility:** National ID must never appear on any public (unauthenticated) page or in any customer-facing invoice/notification. *Why state this explicitly even though no current leak was found:* the field only exists today inside merchant-profile/KYC screens (all `COMPANY_ADMIN`-gated), so there is no current violation — but this specification exists partly to prevent *future* accidental exposure (e.g., someone adding national ID to an invoice PDF for "verification purposes" without realizing the sensitivity), so it is stated as a hard rule here rather than left implicit.

---

## 5. Postal Code Rules

**Current state: identical situation to National ID — no storage convention, no validation, no display convention exists** (verified: postal-code fields on the merchant-profile model are plain text, zero validators, per the same audit finding covering both fields together).

**Storage:** 10 ASCII digits, no separators, `CharField` (same leading-zero reasoning as National ID — Iranian postal codes can begin with any digit including patterns that would be mishandled by numeric storage, and postal codes are an identifier, not a quantity, so they should never be stored as a number type).

**Display:** Raw 10-digit string, optionally grouped as `XXXXX-XXXXX` (5+5, the standard Iranian postal-code display convention) as a display-only transformation. Same "optional, flagged as open question" status as National ID grouping — no existing precedent to consolidate, this would be new.

**Validation:** Iranian postal codes are 10 digits with some structural constraints (they must not be entirely repeated digits, e.g., `0000000000` is invalid) but do not have a public checksum algorithm as well-defined/standardized as the national-ID one. This specification recommends, at minimum, a length-and-digit-only check (10 ASCII digits, not all identical), and does not recommend attempting a more elaborate validation without an authoritative source for the exact rule — inventing a stricter validator than the country's actual postal system enforces risks rejecting genuinely valid codes.

**Formatting:** Same digit-normalization rule as every other numeric-adjacent identifier in this document — Persian-digit input must be accepted and converted to ASCII on the way in; the stored and canonically-displayed form is always ASCII digits.

---

## 6. Percent Rules

**Storage:** `Decimal`, unconstrained-by-default range unless a specific field requires clamping (the one existing precedent, `apps/tenants/views_admin.py:1271-1284` `_parse_wage_percent`, clamps to 0–100 for a wage-percentage field specifically — that clamping is a business rule of *that* field, not a generic formatting rule; a discount percentage, for example, might have different valid bounds). This specification does not mandate a universal numeric range for "percent" as a type — range validation belongs to the specific business field, not to formatting.

**Display:** The numeric value followed by a `%` sign, no thousands separator (percentages are never large enough to need one under any current business rule), ASCII digits — e.g. `12.5%`, `100%`, `0%`. *Why no separate "percent filter" recommendation beyond what's described:* no dedicated percent-formatting filter currently exists in the codebase, and the concern is narrow enough (append `%`, no separator) that it doesn't require a new abstraction distinct from the general digit-normalization rule already covering every other numeric input.

**Input:** Same Persian/English digit-normalization requirement as every other numeric field in this document. The audit found one concrete, currently-live inconsistency here worth calling out again: `_parse_wage_percent` (`apps/tenants/views_admin.py:1271`) does **not** call the shared digit-normalizer that its sibling function `_parse_money_from_post` (two lines above) does — meaning today, a Persian-digit percentage input silently fails to parse correctly where the equivalent money input would succeed. This specification requires **every** numeric input parser, regardless of concern (money, percent, phone, national ID, postal code, quantity), to apply the same digit-normalization step before attempting to parse the value — no numeric input parser is exempt.

**Output:** Percent values must never be silently confused with a raw fraction (e.g., storing `0.125` and displaying it as `"0.125%"` instead of `"12.5%"`, or vice versa). This specification does not mandate a single storage convention (whole-number-percent vs. fraction) across all percent fields, because the audit found existing fields already committed to one or the other in ways that would require a data migration to unify (out of scope for a formatting specification) — but it requires that **whichever convention a given field uses, the display layer must apply the correct, matching multiplication/no-multiplication step**, and that this be documented per-field (in the model's field `help_text` or the relevant Business Rules doc) so a future formatting call site doesn't guess wrong.

---

## 7. Quantity Rules

**Integers (order item counts, technician order counts, notification counts, pagination counts):** Displayed as plain ASCII digits, with a thousands separator applied only once the value is large enough to plausibly need one (per the existing `smart_number`/`RastiFormatNumbers` convention of only reformatting 4+ digit numbers — verified: `rasti_ui_formatters.js:2`, regex `/^[-+]?\d{4,}$/`). *Why keep the existing 4-digit threshold rather than always adding separators:* small counts (order counts, unread-notification counts, page numbers) reading as "1,234" would look stylistically odd for what are almost always small numbers in this product's actual usage (a company rarely has 1,000+ orders in one list view) — the existing threshold already reflects sensible, tested judgment and this specification keeps it rather than replacing it without cause.

**Decimal quantities (e.g., a service quantity that could be fractional — verified to exist as a concept via `InvoiceItem.quantity` fields referenced in the audit, e.g. `templates/invoices/print.html`'s `item.quantity|smart_number`):** Use the same `smart_number`-family formatter, which already correctly preserves and trims fractional parts (`apps/common/templatetags/smart_numbers.py:48-54` — strips trailing zeros from the fraction but keeps genuine decimal precision). No new rule needed; this is already correctly handled by the recommended standard formatter.

**Large numbers (e.g., a report showing tens of millions of Rial, or a platform-wide statistic):** Always shown in full with thousands separators — this specification explicitly rejects abbreviated notation ("1.2M", "45K") anywhere numbers currently render in full, for the same reason stated in §2 (currency reports): abbreviation risks misreading a figure that may inform a real financial or operational decision. If a future dashboard *specifically* wants abbreviated display for a non-critical, glanceable stat card, that must be an explicit, separately-scoped UI decision, not a default behavior under this specification.

---

## 8. Date Interaction

**Rule:** Where a numeric value is displayed adjacent to or combined with a Jalali date (e.g., "۳ روز پیش" / "3 days ago", a pagination string like "صفحه ۲ از ۱۰", or a report row showing both a date and an amount), the numeric-formatting rules in this document (ASCII digits in output, correct thousands separators where applicable) apply independently of, and consistently with, the existing Jalali date-formatting system (`apps/common/jalali.py`, `jalali_tags.py` — already single-sourced, per the audit, with no duplication found there).

**Consistency requirement:** A page must never mix Persian-numeral dates with ASCII-numeral amounts (or vice versa) in a way that looks inconsistent to the user within the same view. *Why this needs stating explicitly:* the audit found the *existing* Jalali date system already renders using whatever digit convention its own formatter produces (not audited in depth here, out of this specification's direct scope), while this specification's currency/quantity rules mandate ASCII output — if the date system's digit output convention ever diverges from this specification's, that mismatch should be resolved by making them consistent with each other (which one wins is a product decision, flagged as an open question below), not left as a silent inconsistency.

---

## 9. Forms

**Desktop vs. mobile:** The underlying value entered, validated, and stored must be identical regardless of device — there is no separate "mobile numeric format." Only the *input mechanism* (see below) may reasonably differ.

**Numeric keyboard on mobile:** Every field that only accepts digits (phone, national ID, postal code, OTP, quantity, amount) should present a numeric keyboard on mobile devices via `inputmode="numeric"` (already the correct, existing HTML mechanism used in 15 places per the audit — just inconsistently applied, since `type="number"` is used 57 times instead, which triggers spin buttons and a *different*, sometimes worse, mobile keyboard depending on browser). This specification recommends `type="text" inputmode="numeric"` (with appropriate `pattern=` for basic client-side shape hinting) as the standard input mechanism for digit-only fields, over native `type="number"`. *Why prefer text+inputmode over native number inputs:* native `type="number"` inputs (a) show spin buttons the product has never intentionally wanted (confirmed: zero CSS anywhere suppresses them, and a sibling EPIC-002 issue exists specifically to remove them), (b) silently strip leading zeros and cannot hold formatted values like thousands separators without JS fighting the browser's own re-parsing, and (c) on some mobile browsers do not present the compact numeric keypad users expect, and can present a keyboard with `-`/`e`/`.` keys irrelevant to a Rial amount or a phone number. `type="text" inputmode="numeric"` avoids all three problems while still triggering the numeric keypad on mobile.

**Paste handling:** A user must be able to paste a phone number, national ID, amount, or OTP code containing Persian digits, spaces, or common separators (dashes, parentheses) and have it accepted — the same normalization rule from §3 (and generalized to every numeric field in §11) applies to pasted content exactly as it does to typed content. *Why call this out separately:* paste events do not always fire the same input-event listeners as typing in every browser/JS pattern; an implementer must verify normalization triggers on paste, not just on keydown, or this specification's "accept Persian digits" guarantee will silently fail for pasted input specifically — a known class of bug this document exists to prevent by stating the requirement explicitly rather than leaving it assumed.

**Persian digits / English digits (as typed):** A user must never be blocked from typing Persian digits into a numeric field — the field accepts either digit set and normalizes silently, with no error message shown for "wrong digit type." *Why:* Persian keyboard layouts on Iranian phones/computers default to Persian numerals; rejecting them at the input layer would be actively hostile to the product's actual user base, and the existing canonical phone/date normalizers already treat this as a non-negotiable requirement (confirmed by their doctested examples).

**Validation timing:** Format-shape validation (is this 11 digits, does it start with 09, is the checksum correct) should happen on blur or on submit, not on every keystroke — live, per-keystroke validation error messages ("invalid phone number") while a user is still mid-typing an incomplete number is a well-known anti-pattern that this specification explicitly rejects as a default. Live *formatting* (see §10) is different from live *validation* and may happen per-keystroke; validation feedback should not.

---

## 10. Frontend Formatting

**Live (as-you-type) formatting:** Reserved for cases where it materially helps the user confirm what they're entering as they type — the audit found exactly one existing precedent for this (a blur-only reformat on a discount-cap field, `templates/reports/discount_campaign_manual.html:146`) and zero true live/per-keystroke reformatting anywhere. This specification does not mandate adding live thousands-separator-while-typing to every amount field as a hard requirement — it is a UX enhancement (§16/§17 scope), but *if* implemented, it must preserve cursor position (see below) and must not fight the user's typing (a common bug where inserting a comma while typing causes the cursor to jump to the end of the field).

**Blur formatting:** The safer, lower-risk default recommended by this specification for any field that benefits from visual confirmation of a large number (e.g., "did I really type 10 zeros?") — reformat the field's displayed value only when the user leaves the field, not while they're actively typing. This avoids the cursor-jump and typing-interruption problems live formatting is prone to, while still giving the user a chance to visually confirm the amount before submitting.

**Typing behavior:** While a field has focus and the user is actively typing, the raw value (digits only, whatever the user has typed, Persian or English) should be what's visible and editable — no forced reformatting mid-keystroke unless the live-formatting enhancement above is specifically implemented with cursor-preservation handled correctly.

**Cursor preservation:** Any client-side reformatting that rewrites an input's `value` while the field still has focus (whether live or on some other trigger) must recompute and restore the cursor position relative to the *digits*, not the raw character offset — inserting or removing a comma before the cursor shifts the digit-relative position, and naive reformatting implementations that don't account for this produce a well-known, frustrating bug (the cursor jumping to the end of the field after every keystroke). This specification requires this be explicitly handled by any live-formatting implementation, not left as an afterthought — the audit found no evidence any current JS formatter deals with this edge case at all (none of the found implementations write back into an active `<input>`'s value; they only reformat static/rendered text nodes), so this would be new-ground work if live-formatting is ever added to real editable inputs, not a migration from an existing correct pattern.

---

## 11. Backend Formatting

**Validation:** Happens before normalization is even attempted where the input is fundamentally malformed (e.g., empty string, non-digit garbage after normalization) — reject with a clear error, in Persian, matching the product's existing UI-language convention (`docs/02_AI_Operating_System/AI_CODE_CHANGE_RULES.md` Rule 7 — no Persian label changes without request, which extends by the same logic to new Persian validation-error text needing to match existing tone/style, not be invented ad hoc).

**Normalization:** Always happens server-side too, never trusting that client-side normalization ran — every numeric input (money, phone, national ID, postal code, percent, quantity) must pass through the same digit-normalization step (Persian/Arabic → ASCII) at the point it's read from `request.POST`/a Form's cleaned data, *before* any parsing to `int`/`Decimal`/regex-validation happens. *Why never trust client-side normalization alone:* the audit found API clients, direct POST requests (bypassing JS entirely), and even some existing server code paths (the `_parse_wage_percent` gap in §6) that do not go through any client-side JS at all — server-side normalization is the only universally-reliable point, and client-side normalization (if/when added per §9/§10) is a UX nicety layered on top, not a substitute.

**Database:** Never stores a formatted value — always the raw, normalized form (ASCII digits, correct type per field: `Decimal` for money, string for phone/national-ID/postal-code, `Decimal` for percent). This specification forbids ever writing a comma-separated or Persian-digit string to any database column, under any circumstance, including "for display convenience" — that would resurrect exactly the duplication/inconsistency problem this document exists to prevent, one column at a time.

**Services / Selectors:** Business-logic layers (`services.py`, `selectors.py` per `docs/03_Architecture/SERVICE_LAYER.md`) work with raw, normalized values only — a service function must never receive or return a comma-formatted string, and must never itself call a display-formatting filter (this is already implicit in the existing service-layer architecture rule that "business logic lives in services only," and this specification extends that rule explicitly to numeric formatting: formatting is not business logic, and a service function found calling `smart_number` internally is a spec violation, not a shortcut).

**Forms:** The audit found **zero** custom `clean_<field>` methods for any money/phone/national-id field anywhere in the codebase today — all normalization currently happens ad hoc in the view layer instead. This specification does not mandate migrating every existing view-layer normalization into the Form layer (that would be an architectural change beyond a formatting-consistency fix, explicitly flagged as an open question below) — but it does establish that **wherever** normalization happens (Form, view, or service), it must call the single shared normalization function for that concern (§16), not a locally-reimplemented copy.

**Serializers:** REST API serializers (`apps/api/serializers.py`) must continue returning **raw** values — this is already the existing, correct behavior (Django REST Framework's `ModelSerializer` serializes a `DecimalField` as a string representation of the raw number, e.g. `"1250000"`, not `"1,250,000"` or `"1,250,000 ریال"` — verified: `InvoiceSerializer` at `apps/api/serializers.py:65-78` uses plain `ModelSerializer` fields with no custom `to_representation` override). This specification ratifies that as a firm rule (see §15) rather than something to "fix."

---

## 12. Template Rules

**Required filter:** Any numeric value that is money (an amount, a balance, a total, a discount, a wallet figure) rendered in a Django template **must** be piped through the currency-formatting filter (`smart_number`/`smart_money`, per the Recommended Standard in the audit) before display. A bare `{{ invoice.total_amount }}` with no filter is a specification violation.

**Forbidden patterns:**
- `{{ some_amount }}` with no filter, where `some_amount` is a currency/money value (found live today in `templates/reports/list.html:38` and others — explicitly called out as violations to fix under Migration Rules, §16).
- `{{ some_amount|floatformat:0 }}` used as a substitute for currency formatting — `floatformat` strips decimals but adds no thousands separator, and is not a currency-aware filter; it is a formatting-adjacent trap that looks like it's "handling" the number but doesn't apply the separator convention this document requires (found live today in 6+ templates in `platform_core/sms_billing/` and `admin_sms_credit.html`).
- Any inline `<script>` block inside a template that reimplements comma-insertion, digit-normalization, or currency formatting logic that a shared, globally-loaded JS module already provides — this duplicates the exact anti-pattern the audit spent most of its findings documenting (9+ templates currently do this).
- Piping a phone number, national ID, postal code, or OTP code through `smart_number`/`smart_money`/`rial`/`toman` — these are identifiers, not currency, and must never receive thousands separators (the audit confirmed this specific bug class does **not** currently exist anywhere — this rule exists to keep it that way, not to fix an existing violation).

**Example (descriptive, not implementation code):** A template rendering an invoice total should apply the currency filter and append the literal Persian Rial suffix as static text, exactly matching the pattern already used correctly in 54 templates today — this specification asks for *consistency* with that existing, dominant, correct pattern, not a new one.

---

## 13. JavaScript Rules

**One formatter only.** There must be exactly one globally-loaded JS module responsible for each formatting concern (comma-insertion/currency display, Persian-digit normalization) — today this is `static/js/rasti_ui_formatters.js`, already loaded on every page via `templates/base.html`. This specification designates it the single source of truth for client-side formatting going forward.

**No duplicated scripts.** No template may contain an inline `<script>` block that reimplements logic already available in the global formatter file. The audit found at least 9 templates violating this today (6 byte-identical copies of `RastiFixPersianAmounts`, 3 near-identical copies of a `normalizeDigits/digitsOnly/formatRial` trio) — every one of these is a specification violation to be resolved under Migration Rules (§16).

**Reusable modules:** Where a formatting *helper function* (not just the auto-applying DOM-scan behavior) is needed by page-local code (e.g., a page that wants to manually format one specific computed value, not rely on the automatic DOM-scanning pass), it must call an exported function from the single global module (e.g., a digit-normalizer exposed as a standalone, independently-callable function on the shared `window` namespace) rather than each page declaring its own local copy of the same 5-line loop. This specification does not mandate a specific module-loading mechanism (ES modules, bundler, etc.) beyond what the codebase already uses (plain global `<script>` tags, no build step, per `templates/base.html`'s existing pattern) — introducing a build pipeline is a much larger architectural decision outside this document's scope.

---

## 14. Accessibility

**Screen readers:** A formatted number like `1,250,000 ریال` should read sensibly when a screen reader encounters it — commas are not announced as words by most screen readers (they're typically treated as a brief pause), so `1,250,000` is read as "one million two hundred fifty thousand" correctly by most Persian/English screen-reader engines without special markup. This specification does not require additional ARIA labeling beyond what templates already provide, since no accessibility regression was found in the audit — but flags that any *future* abbreviated-number display (e.g., "1.2M", explicitly rejected as a default in §2/§7) would need an accessible full-value equivalent (e.g., a `title`/`aria-label` attribute) if ever introduced, precisely because abbreviations are the case where screen-reader ambiguity becomes a real risk.

**Copy & paste:** A formatted value (with commas) copied out of the UI and pasted into another field (e.g., an admin copies "1,250,000" from one screen and pastes it into a search box or another form field) must still be accepted by this specification's paste-handling rule (§9) — the comma must be stripped during normalization exactly like any other separator character, so that copy-paste between the product's own screens always works, not just fresh typing.

**RTL/LTR:** Numeric values (amounts, phone numbers, national IDs, postal codes) must render left-to-right even inside an otherwise-RTL Persian page — this is already the consistent existing convention (`.ltr-cell`, `dir="ltr"` used throughout the templates surveyed in the audit) and this specification ratifies it as a firm rule: no numeric value should ever be allowed to render with RTL digit-ordering, which would visually reverse the number and make it unreadable/miskeyable. This is arguably the most safety-critical rule in this entire document for a financial product — a reversed amount is not a cosmetic bug, it is a potential financial error if a human transcribes it elsewhere.

---

## 15. API Rules

**APIs return raw values, never display-formatted values.** This is already the existing, correct behavior (verified: `InvoiceSerializer` and all other `ModelSerializer`-based serializers in `apps/api/serializers.py` return DRF's default `Decimal`-as-string representation, e.g. `"1250000"`, with no thousands separator, no currency suffix, ASCII digits) and this specification makes it an explicit, permanent rule rather than an implicit accident.

*Why:* API responses are consumed by other software (a future mobile app, JS running in the browser that will itself apply this specification's frontend formatting rules, or a third-party integration) — not read directly by a human. Baking in Persian-locale display formatting at the API layer would force every consumer to *undo* it before they could do any calculation with the value, and would hard-couple the API's data shape to one specific display convention, breaking the moment any consumer needs the raw number (which is most consumers, most of the time).

**Should APIs ever return a formatted/localized value?** Only as an *additional*, clearly-named, optional field alongside the raw one (e.g., a hypothetical `total_amount_display` string field alongside the raw `total_amount`), never as a replacement for the raw value, and only when a specific, real consumer need is identified (e.g., a mobile app that wants to avoid reimplementing the Persian-formatting rules itself). No such need has been identified in this audit — this specification does not recommend adding formatted fields to any serializer today, only states the rule for if/when the need arises.

---

## 16. Migration Rules

**How existing duplicated implementations should be removed** (restating and slightly expanding the audit's phased plan, now anchored to this specification's rules rather than just "consolidate duplicates" in the abstract):

1. **Safest first — internal delegation with zero visible change.** Make the weaker/duplicate implementation of a concern call the stronger one internally (e.g., `fa_labels.rial`/`toman` delegate to `smart_numbers`'s formatting logic), with no template or call-site changes. This is the lowest-risk migration step because output for every currently-well-formed input is provably identical before and after.
2. **Remove dead code next.** The `rial`/`toman` filters have zero live call sites (verified in this document) — once behind the delegation from step 1, they can be safely removed entirely in a later pass with no template impact, since nothing calls them. Same for `apps/reports/discount_services._discount_campaign_format_rial` (also zero call sites, verified in the audit).
3. **Remove inline-script duplication before touching backend consolidation.** The 9+ templates with duplicated JS are the lowest-risk, highest-visible-cleanup target because deleting an inline `<script>` block that exactly duplicates an already-globally-loaded function cannot change behavior — the global version already runs on the same page. This should be verified by direct comparison (not assumed) immediately before each deletion, per the audit's Risk Analysis.
4. **Backfill missing filters onto currently-raw templates one at a time**, each independently tested and revertable, in order of financial sensitivity (wallet balances and revenue totals first, since these are real money currently displayed with zero formatting).
5. **Consolidate phone-normalizer call sites last, and most carefully**, specifically because `apps/sms/*` is explicitly flagged elsewhere in this EPIC as sensitive ("do not modify SMS logic" appears as a standing instruction across prior EPIC-002 approvals) — any change here should go through its own narrow approval, with input-parity tests proving no behavioral drift between the 5 existing implementations before any call site is switched, exactly as the audit's Risk Analysis already recommends.
6. **New capabilities (national ID, postal code validation, input masking, spin-button CSS) are purely additive** and carry no migration risk since nothing existing is being changed — they can proceed independently of, and in parallel with, steps 1-5.

**Rollback strategy:** Because every migration step above is designed to be a small, independently-deployable, independently-revertable change (per-file, per-template, per-call-site), rollback is simply reverting that one commit/PR — this specification deliberately avoids recommending any "big bang" migration (e.g., a single PR that swaps every phone-normalizer call site at once) specifically because a big-bang change would make rollback all-or-nothing and make it hard to isolate which specific change caused a regression if one appears in production. Financial-data correctness (currency amounts) and delivery-critical data (phone numbers used for SMS) are both areas where this product's own operating rules (`docs/02_AI_Operating_System/AI_CODE_CHANGE_RULES.md` Rule 4, "Financial Code Rules") already demand exactly this kind of caution.

---

## 17. Future Extensions

**Multiple currencies:** Not a current requirement (the product is explicitly Iran-only, single-currency, per `docs/00_Project/PROJECT_SCOPE.md`'s framing and the ADRs establishing Rasti as a Rial-only SaaS provider — `docs/07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md`). If ever required, the architecture this specification describes (one canonical formatting function per concern, called everywhere, formatting only at the display edge) is already the correct shape to extend — a future currency parameter would be threaded through the same single formatting function rather than requiring a rewrite, *because* this specification insists on consolidation now rather than accepting today's 3-implementation sprawl. This is presented as a structural benefit of doing the consolidation, not as a promise that multi-currency support is planned.

**Multiple locales / multiple languages:** Similarly not a current requirement (Persian UI, English code identifiers, per `AI_AGENT_START_HERE.md`'s explicit framing of the product). The same reasoning applies: a single, consolidated formatting function is the correct foundation to eventually parameterize by locale (digit set, separator character, RTL/LTR digit direction) if the product ever needs it — but this specification does not design that parameterization now, since no requirement for it exists today, and speculative locale-abstraction would itself violate the "don't build for hypothetical future requirements" principle this specification otherwise follows throughout.

**PDF/Excel export pipelines:** If added later, they must reuse this specification's backend formatting functions (§11) rather than reimplementing formatting for the new export context — explicitly noted here so a future implementer building a PDF/Excel feature checks this document first rather than writing a 4th currency formatter.

---

## Summary of This Specification (for quick reference)

| Concern | Storage | Display | Digit set (output) | Separator |
|---|---|---|---|---|
| Currency (Rial) | Integer, no decimals | `X,XXX,XXX ریال` | ASCII | Comma, every 3 digits |
| Phone | `09xxxxxxxxx`, 11 digits | Same, `dir="ltr"` | ASCII | None |
| National ID | 10 digits, `CharField` | Raw or optionally grouped (open question) | ASCII | None (or optional dash-grouping) |
| Postal code | 10 digits, `CharField` | Raw or optionally grouped (open question) | ASCII | None (or optional dash-grouping) |
| Percent | `Decimal`, per-field range | `X%` or `X.X%` | ASCII | None |
| Quantity | `Decimal`/`int` | Same as currency rules if 4+ digits | ASCII | Comma if 4+ digits |
| API responses | n/a | Raw, unformatted | ASCII | None |
| CSV/Excel export | n/a | Raw, native numeric type | ASCII | None |

---

## Approval Required

This is a specification, not an implementation. Approving this document does not create, modify, or delete any file beyond this one. A separate approval is required before any Migration Rules (§16) step is implemented.

Options:

A. Approve this specification as the official numeric-formatting standard and proceed to scope the first Migration Rules implementation phase (internal delegation + dead-code identification, per §16 step 1-2 — lowest risk).

B. Approve this specification with modifications — see Open Questions below; resolve them first, then re-issue a final version.

C. Reject and request a different approach (e.g., a different official currency unit, a different digit-output convention, or a different scope for National ID/Postal Code).

---

## Open Questions Requiring Product-Owner Decisions

These are called out throughout the document above; consolidated here for convenience. None of them block approving the *rest* of this specification — each is independently resolvable and only affects its own narrow section.

1. **Rial confirmed as official unit — but should the dead `toman` filter be deleted outright, or kept (unused) in case a future "show in Toman" UI toggle is wanted?** (§2) Recommendation in this document leans toward deletion as dead code, but this is a product call, not a technical one.
2. **Should National ID and Postal Code display ever be grouped with dashes (e.g., `XXX-XXXXXX-X` / `XXXXX-XXXXXX`), or always shown as a raw 10-digit string?** (§4, §5) No existing precedent either way.
3. **Should National ID validation (the mod-11 checksum) be enforced as a blocking Form validator, or left as a non-blocking, display-only sanity check, given that existing stored data has never been validated and may already contain invalid values?** (§4, §16)
4. **Should phone-number display ever use dash-grouping (e.g., `0912-123-4567`) instead of the current unbroken `09xxxxxxxxx` form?** (§3) No current precedent; purely cosmetic if changed.
5. **Should live (as-you-type) thousands-separator formatting be added to amount input fields as new UX work, or is blur-only formatting sufficient?** (§10) This is a UX investment decision, not a consistency fix — flagged as optional, new scope either way.
6. **Does the existing Jalali date-formatting system's digit-output convention (audited separately, not deeply re-verified in this document) already match this specification's "always ASCII digits in output" rule, or is there a mismatch that needs its own reconciliation?** (§8) This document flags the *requirement* for consistency but did not re-audit the date system's own current output in depth, since that was outside the numeric-formatting audit's stated scope.
7. **Should this specification's Form-layer requirement ("wherever normalization happens, call the shared function") be strengthened later into a mandate that normalization *must* happen in a Form's `clean_<field>` method specifically (rather than the view layer, as today)?** (§11) This is a real architectural change beyond formatting consolidation, explicitly not decided in this document.
