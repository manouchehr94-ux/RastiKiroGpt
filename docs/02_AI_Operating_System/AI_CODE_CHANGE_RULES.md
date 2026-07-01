---
Title: AI Code Change Rules
Layer: AI Operating System
Audience: AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code + ADR
Reusable Across Projects: Partially
---

# AI Code Change Rules

These rules govern every code change made by an AI agent in this project.

---

## Rule 1 — Docs First

Before writing any code:
1. Read the relevant docs section
2. Identify the source of truth
3. Read the specific code files that will be changed
4. Understand the test coverage for the area

Never write code from memory. Always read the current state.

---

## Rule 2 — Narrow Changes Only

- Change only what the task requires
- Do not clean up unrelated code
- Do not rename variables not in scope
- Do not add error handling for scenarios that cannot happen
- Do not add fallbacks or feature flags not requested
- Do not refactor while fixing a bug

**Three similar lines is better than a premature abstraction.**

---

## Rule 3 — Tenant Isolation is Sacrosanct

Every query touching company-owned data MUST scope by company:

```python
# FORBIDDEN
Order.objects.get(id=pk)
Invoice.objects.filter(status="PAID")

# REQUIRED
Order.objects.get(id=pk, company=request.company)
Invoice.objects.filter(status="PAID", company=request.company)
```

If you are unsure whether a query is properly scoped, STOP and ask.

---

## Rule 4 — Financial Code Rules

All code touching financial models (`Invoice`, `Payment`, `TechnicianLedgerEntry`, `CompanyPlatformFeeEntry`) must:

- Use `transaction.atomic`
- Use `select_for_update()` where double-processing is possible
- Use `Decimal` only — never `float`
- Use idempotency keys (already established patterns exist)
- Treat ledger entries as immutable — create reversing entries, never edit

---

## Rule 5 — Service Layer Only

Business logic must live in `services.py` files, not in:
- Views (`views.py`, `views_admin.py`)
- Templates (`.html`)
- Models (unless it is a pure model constraint)
- Serializers

If you need to add business logic to a view, create or extend the service instead.

---

## Rule 6 — No Silent Assumptions

If you are not 100% certain a model field, URL name, view function, or app namespace exists:
- Search for it with Grep
- Read the file

Do not assume. Do not guess. Verify.

---

## Rule 7 — No Persian Label Changes

Do not change, translate, or modify any Persian-language strings visible to users unless the user explicitly requests it. This includes:
- Order status labels
- Button text
- Error messages
- Notification templates
- SMS templates

---

## Rule 8 — No Deleting Historical Decisions

Do not:
- Delete ADR files
- Remove comments that explain WHY a decision was made
- Remove historical migration files
- Remove `# noqa` or `# type: ignore` without understanding why they exist

---

## Rule 9 — Test Coverage Required

For any change in:
- Financial logic → add/run integration tests
- Security/permission → add/run permission tests
- Order status transitions → run existing order tests
- Multi-tenant data access → add tenant isolation tests

Do not claim a change is complete unless:
1. Existing tests still pass
2. New tests cover the new behavior

---

## Rule 10 — Report Risks

Every implementation report must include:
- Files changed (with line numbers)
- Tests run (pass/fail count)
- Known risks from the change
- What was NOT changed (but is related)
- Manual QA steps needed

---

## Forbidden Actions Summary

| Action | Why |
|---|---|
| Rewrite an entire module | Risk of losing correct behavior |
| Remove tests | Destroys behavioral guarantees |
| `float` for money | Precision loss in financial calculations |
| Edit a ledger entry | Ledger is immutable (ADR-004) |
| Add logic to views | Violates service-layer architecture |
| Bare `Order.objects.get(id=pk)` | Cross-tenant data leak |
| Change Persian labels | User experience contract |
| Skip running tests | No proof the change is correct |
