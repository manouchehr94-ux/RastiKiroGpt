---
Title: Invoice Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/invoices/models.py, apps/invoices/services.py
Source of Truth: Code
Depends On: []
Related Documents: PAYMENT_RULES.md, TECHNICIAN_RULES.md, ../05_Workflows/INVOICE_PAYMENT_FLOW.md
Reusable Across Projects: No
---

# Invoice Business Rules

---

## What is an Invoice?

An Invoice is the financial document issued for a completed order. It freezes a financial snapshot when paid. See [../00_Project/GLOSSARY.md](../00_Project/GLOSSARY.md).

---

## Invoice Status Values

| Status | Meaning |
|---|---|
| `DRAFT` | Created but not yet finalized |
| `ISSUED` | Sent to customer, awaiting payment |
| `PAID` | Payment verified |
| `VOID` | Cancelled before payment |

---

## Invoice Creation Rules

### Who can create an invoice?

- **Technician** — can create invoice for own DONE order at `/<code>/tech/invoices/order/<id>/create/`
- **Admin / Operator** — can create invoice from admin panel at `/<code>/admin/invoices/`

### When can an invoice be created?

- Order must be in `DONE` status
- Order must belong to the same company
- Only one active invoice per order (DRAFT or ISSUED)

---

## Invoice Payment Rules

- A customer pays an invoice via the public invoice URL or the customer panel
- Payment is initiated → PSP → callback → verification → `PAID`
- Once `PAID`, the invoice is frozen and must not be modified
- Invoice amount cannot change after `ISSUED` status

---

## PAID Invoice Immutability

When an invoice is `PAID`:
- Line items cannot be changed
- Amounts cannot be changed
- Invoice cannot be voided
- This is the financial snapshot used for all ledger calculations

---

## Public Invoice Links

An invoice can be shared via:
- Full URL: `/<code>/invoices/<id>/` (requires knowledge of company code)
- Short URL: `/i/<public_code>/` (shareable, no auth required)

Both are publicly accessible for `ISSUED` and `PAID` invoices.

---

## Invoice and Technician Wage

When an invoice is marked PAID:
- Technician's portion (based on `CompanyFinancialPolicy`) is credited to their ledger
- Platform commission is created if conditions are met (see [PAYMENT_RULES.md](PAYMENT_RULES.md))

---

## Technician Invoice Short Path

There are two URLs for technician invoice creation that go to the same result:
```
/<code>/tech/orders/<id>/invoice/create/  →  redirects to  →
/<code>/tech/invoices/order/<id>/create/
```

The first is a redirect (legacy). Use the second form in any new links.
