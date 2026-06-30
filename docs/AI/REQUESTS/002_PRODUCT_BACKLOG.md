# Request 002 — Product Polish Backlog

Priority: High  
Mode: Incremental fixes  
Rule: One issue per commit unless explicitly grouped.

---

## Issue 001 — Public payment uses admin layout

Public invoice payment must open a dedicated public checkout page, not company dashboard layout.

Expected:

- no sidebar
- no admin chrome
- anonymous access
- invoice summary only
- safe gateway state display

---

## Issue 002 — Communication Matrix incomplete

Matrix must include all core roles:

- admin
- operator
- technician
- customer

Templates should exist for all meaningful event/role pairs except survey-related items.

Company can enable/disable channels, not edit text.

---

## Issue 003 — Notification preview leaks into pages

Notification dropdown content must not render inside unrelated admin pages.

It should appear only in:

- bell dropdown
- notification center
- badge count

---

## Issue 004 — Global numeric formatting

Amounts must be formatted with thousands separators.

Numeric fields must open numeric mobile keyboard.

Phone, national ID, postal code, OTP must preserve leading zero.

---

## Issue 005 — Cancellation request locks invoice creation

When technician requests cancellation, invoice creation must be blocked until resolution.

Must be enforced in UI and backend.

---

## Issue 006 — Mobile zoom on input focus

Input/textarea focus must not break mobile layout.

Use mobile-safe font-size and avoid disabling user zoom globally.

---

## Issue 007 — Dashboard chart dates

Dashboard chart dates must be Jalali in Persian UI.

---

## Issue 008 — Admin invoice edit parity

Admin invoice edit page must support the same core invoice capabilities as technician invoice creation page.

---

## Issue 009 — Technician canceled filter

Technician orders page must include "لغو شده" filter.

---

## Issue 010 — Standardize toolbars

Related admin modules should use the clean toolbar pattern already used in financial report pages.

---

## Issue 011 — Reports page redesign

Admin reports page must use current design system.

---

## Issue 012 — Statement page audit

Find and document the statement/account page. If missing, report required route and UI.

---

## Issue 013 — Technician mobile-first panel

All technician panel pages must be mobile-first.

---

## Issue 014 — Remove number spin buttons

Remove numeric input spin buttons globally.

---

## Issue 015 — Technician dashboard monthly stats

Technician dashboard must show current month completed orders and relevant summary stats.

---

## Issue 016 — Remove internal debug link

Operator settings page shows unrelated debug/test link. Hide under DEBUG or super-admin-only.
