# Invoice Rules

- Invoice is issued by technician/admin for a tenant company.
- Invoice should show tenant company and issuing user/technician.
- Rasti Service branding is software/platform only.
- One active invoice per order.
- Paid invoices are terminal for normal flow.
- Reversal/refund requires explicit future process.
- Settlement snapshot fields are immutable after `settled_at`.

## Discounts

Discounts are company-level. Rasti Service does not fund them.
