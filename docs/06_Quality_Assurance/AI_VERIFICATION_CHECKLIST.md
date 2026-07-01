---
Title: AI Verification Checklist
Layer: Quality Assurance
Audience: AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code
Reusable Across Projects: Partially
---

# AI Verification Checklist

Use this checklist before declaring any code change complete.

---

## Universal Checks (Every Change)

- [ ] `python manage.py check` passes with no errors
- [ ] No new migration created unintentionally
- [ ] No unrelated files were changed
- [ ] No Persian UI labels were modified without explicit user request
- [ ] No business logic was added to a view or template

---

## Order Changes

- [ ] Status transition is in the allowed list (see ORDER_RULES.md)
- [ ] `OrderStatusLog` entry is created after transition
- [ ] `select_for_update()` used in transition logic
- [ ] `python manage.py test apps.orders --verbosity=2` passes
- [ ] Relevant notification event is triggered (or deliberately skipped with comment)

---

## Financial Changes

- [ ] `transaction.atomic` wraps the operation
- [ ] `select_for_update()` used where parallel execution is possible
- [ ] `Decimal` used for all monetary values (grep `float` in changed files — should be 0)
- [ ] Idempotency key prevents double-processing
- [ ] No existing ledger entries were modified (only new entries created)
- [ ] `python manage.py test apps.payments apps.invoices apps.payouts --verbosity=2` passes

---

## Permission / Security Changes

- [ ] Every admin view has `@require_tenant_role(...)` or `@require_platform_owner`
- [ ] No view was left without a decorator accidentally
- [ ] Tenant isolation: new queries include `company=request.company`
- [ ] Test: unauthorized role gets 302/403 on the changed view
- [ ] Test: cross-company access gets 404 on the changed view
- [ ] P0-1 status unchanged (if not the task): `admin_operator_list` still has correct decorator

---

## URL / Template Changes

- [ ] New URL is documented in `08_Site_Map/01_URL_INVENTORY.md`
- [ ] Template extends correct layout
- [ ] New template is in the correct role-specific folder
- [ ] No new duplicate template created (check `templates/components/` vs `templates/includes/components/`)

---

## After All Checks Pass

Write a report including:
```
## Change Report

Files changed:
- [file:line] — description

Tests run:
- Command: python manage.py test [apps]
- Result: N tests, 0 failures, 0 errors

Risks:
- [list any risks]

Manual QA needed:
- [list steps]
```
