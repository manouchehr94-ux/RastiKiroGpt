# Database Standards

## General

Use migrations deliberately.

Avoid unnecessary schema changes.

Preserve historical financial data.

---

## Indexes

Large tables should have indexes for common filters:

- company
- status
- created_at
- recipient
- technician
- invoice/payment identifiers

---

## Financial Data

Do not overwrite historical financial records.

Corrections should be adjustment records.
