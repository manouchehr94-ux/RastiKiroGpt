# Project Rules

## Multi-Tenant Rules

Every tenant-owned object must be scoped by company.

A user from one company must never see another company's data.

Any query that returns company data must be company-filtered.

---

## Public Page Rules

Public customer pages must use public layout.

They must not render:

- admin sidebar
- company dashboard chrome
- internal navigation
- debug links

---

## Order Rules

Order is the central workflow.

Invoice, payment, notification, technician actions, and cancellation must respect order state.

---

## Invoice Rules

Invoice creation must be blocked when business state makes it unsafe, including active cancellation request.

Invoice history must remain auditable.

---

## Payment Rules

Online payment must use public-safe customer flow.

Payment gateway readiness must be checked before showing active payment action.

---

## Notification Rules

Every configurable notification must have a real event key.

Do not use empty event keys.

SMS and In-App channels must be configurable per company and per role.

---

## UI Rules

- Mobile technician pages are mobile-first.
- Amounts must use thousands separators.
- Numeric fields must open numeric mobile keyboard.
- Number input spin buttons should be removed globally.
- Persian UI should not show Gregorian dates unless explicitly technical.
