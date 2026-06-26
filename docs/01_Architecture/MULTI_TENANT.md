# Multi-Tenant Rules

Every company owns its own data.

## Mandatory

- Every financial/order/customer/technician query must be scoped by company.
- Never fetch by `id` alone.
- Callback lookups must use `company + reference_id`.
- Admin views must respect tenant role and company scope.
- Cross-company data leakage is a blocker bug.

## Forbidden

```python
Payment.objects.get(id=payment_id)
Invoice.objects.get(id=invoice_id)
Order.objects.get(id=order_id)
```

Use company-scoped queries.
