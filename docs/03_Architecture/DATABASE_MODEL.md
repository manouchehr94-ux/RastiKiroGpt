---
Title: Database Model and Rules
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/*/models.py, 01_Architecture/DATABASE_RULES.md, AI/STANDARDS/DATABASE_STANDARDS.md
Source of Truth: Code
Depends On: DOMAIN_MODEL.md
Related Documents: SYSTEM_ARCHITECTURE.md, ../07_ADR/ADR-004-Ledger-Discipline.md
Reusable Across Projects: No
---

# Database Model and Rules

---

## Database Configuration

- **Production:** PostgreSQL
- **Development:** SQLite (acceptable for local; PostgreSQL strongly recommended for staging)
- **ORM:** Django ORM
- **Migrations:** Standard Django migrations

---

## Migration Rules

1. Prefer additive migrations (add columns, add tables)
2. Never remove a column without a deprecation period
3. Never delete production financial data
4. Every migration must be reversible unless explicitly documented why not
5. Test all migrations on a copy of production data before running on production
6. Do not create migrations during bug fixes unless the fix requires a schema change

---

## Money / Financial Fields

| Rule | Implementation |
|---|---|
| All monetary values use `DecimalField` | Never `FloatField` |
| Iranian Rial: `decimal_places=0` | No decimal places for Rial |
| No float conversion anywhere | `Decimal("0.05")`, never `0.05` |

---

## Financial Record Immutability

These records are **append-only** after finalization:

- `TechnicianLedgerEntry` — immutable after creation
- `CompanyPlatformFeeEntry` — immutable after creation
- `Invoice` — amounts frozen after `PAID`
- `Payment` — amounts frozen after `PAID`
- Settlement snapshots — immutable after `settled_at`

To correct an error: create a new reversing entry. Never `UPDATE` a finalized financial record.

---

## Multi-Tenant Query Discipline

Every query on company-owned models must include `company=` filter:

```python
# REQUIRED
Order.objects.get(id=pk, company=company)
Invoice.objects.filter(company=company, status="PAID")

# FORBIDDEN
Order.objects.get(id=pk)  # Cross-tenant data leak
Invoice.objects.get(id=pk)  # Cross-tenant data leak
```

---

## Index Strategy

Add database indexes for columns used frequently in:
- Dashboard filtering (company, status, created_at)
- Report aggregation (company, created_at range, technician)
- SMS/notification lookups (recipient, company)
- Invoice/payment lookups (company, reference_id, status)

Avoid over-indexing write-heavy tables (order status log, ledger entries).

---

## Deletion Policy

| Record Type | Policy |
|---|---|
| Companies with financial records | Never hard-delete — use `is_active=False` |
| Orders (any status) | Never delete — use cancellation |
| Invoices | Never delete — use void status |
| Financial ledger entries | Never delete — create reversing entries |
| User accounts | Soft-delete or deactivate only |
| SMS messages, notifications | Can be soft-deleted after archival period |

---

## Key Model Locations

| Model | File |
|---|---|
| `Company` | `apps/tenants/models.py` |
| `CompanyPaymentSettings` | `apps/tenants/models.py` |
| `CompanyFinancialPolicy` | `apps/tenants/models.py` |
| `User` | `apps/accounts/models.py` |
| `Order`, `OrderStatusLog` | `apps/orders/models.py` |
| `Invoice` | `apps/invoices/models.py` |
| `Payment`, `PaymentGateway` | `apps/payments/models.py` |
| `TechnicianLedgerEntry` | `apps/payouts/models.py` |
| `CompanyPlatformFeeEntry` | `apps/payouts/models.py` |
| `Notification` | `apps/notifications/models.py` |
| `SMSMessage` | `apps/sms/models.py` |
| `ServiceRequest` | `apps/public/models.py` |
