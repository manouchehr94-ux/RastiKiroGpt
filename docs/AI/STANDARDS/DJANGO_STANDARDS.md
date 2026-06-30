# Django Standards

## Architecture

Use service layer for business logic.

Use selectors for complex reads.

Avoid fat views.

Avoid duplicating business rules in templates.

---

## Multi-Tenant

Always filter tenant-owned queries by company.

Never trust URL/company code alone without validation.

---

## Transactions

Use `transaction.atomic` for financial and state-changing workflows where consistency matters.

---

## Tests

Business rules require tests.
