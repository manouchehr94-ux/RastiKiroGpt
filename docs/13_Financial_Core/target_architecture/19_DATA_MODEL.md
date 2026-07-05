# 19 — مدل داده پیشنهادی (Proposed Data Model)

**Version:** v1.0 — Draft — Pending Clarification

---

## Existing Tables (NO CHANGES)

These tables exist and must not be altered structurally:

| Table | App | Key Fields |
|---|---|---|
| `invoices_invoice` | invoices | All settled_* fields, status, amounts |
| `invoices_invoiceitem` | invoices | row_type, quantity, unit_price, discount_amount |
| `invoices_invoicecancellationrequest` | invoices | status, invoice FK |
| `invoices_invoicecounter` | invoices | company, last_number |
| `payments_payment` | payments | status, amount, gateway, invoice FK |
| `payments_paymentgateway` | payments | owner_type, gateway_type |
| `payments_paymentattempt` | payments | status, gateway_reference |
| `payouts_technicianledgerentry` | payouts | entry_type, source, amount_rial, balance_after, idempotency_key |
| `payouts_companyplatformfeeentry` | payouts | entry_type, source, amount_rial, balance_after |
| `payouts_paymentsplitsnapshot` | payouts | should_split, amounts |
| `payouts_financialbackfilltask` | payouts | task_type, status, attempts |
| `payouts_technicianservicerate` | payouts | technician, item_definition, fixed_wage_rial |
| `tenants_companyfinancialpolicy` | tenants | policies, payout_strategy, platform_fee_percent |
| `tenants_companypaymentsettings` | tenants | payment_mode, activation_status |
| `tenants_companymerchantprofile` | tenants | KYC fields, shaba_number, status |

---

## New Columns on Existing Tables

### tenants_companyfinancialpolicy

```sql
ALTER TABLE tenants_companyfinancialpolicy 
ADD COLUMN charge_commission_on_cash BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE tenants_companyfinancialpolicy 
ADD COLUMN rounding_discount_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE tenants_companyfinancialpolicy 
ADD COLUMN max_rounding_discount_rial BIGINT NOT NULL DEFAULT 0;

ALTER TABLE tenants_companyfinancialpolicy 
ADD COLUMN settlement_frequency VARCHAR(20) NOT NULL DEFAULT 'manual';

ALTER TABLE tenants_companyfinancialpolicy 
ADD COLUMN settlement_delay_hours INTEGER NOT NULL DEFAULT 0;
```

### invoices_invoiceitem (RowType extension)

No schema change needed — `row_type` VARCHAR already supports new choices.

---

## New Tables

### payouts_escrowrecord

```sql
CREATE TABLE payouts_escrowrecord (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES tenants_company(id),
    payment_id INTEGER UNIQUE REFERENCES payments_payment(id),
    invoice_id INTEGER REFERENCES invoices_invoice(id),
    amount_rial BIGINT NOT NULL,
    platform_commission_rial BIGINT NOT NULL DEFAULT 0,
    organization_share_rial BIGINT NOT NULL DEFAULT 0,
    provider_share_rial BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(25) NOT NULL DEFAULT 'held',
    held_at TIMESTAMP WITH TIME ZONE NOT NULL,
    distributed_at TIMESTAMP WITH TIME ZONE NULL,
    settled_at TIMESTAMP WITH TIME ZONE NULL,
    closed_at TIMESTAMP WITH TIME ZONE NULL,
    settlement_batch_id INTEGER NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_escrow_company_status ON payouts_escrowrecord(company_id, status);
```

### payouts_settlementbatch

```sql
CREATE TABLE payouts_settlementbatch (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES tenants_company(id),
    level VARCHAR(20) NOT NULL,  -- platform_to_org / org_to_provider
    status VARCHAR(20) NOT NULL DEFAULT 'calculating',
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    net_amount_rial BIGINT NOT NULL DEFAULT 0,
    total_credits BIGINT NOT NULL DEFAULT 0,
    total_debits BIGINT NOT NULL DEFAULT 0,
    items_count INTEGER NOT NULL DEFAULT 0,
    executed_at TIMESTAMP WITH TIME ZONE NULL,
    bank_reference VARCHAR(200) DEFAULT '',
    failure_reason TEXT DEFAULT '',
    created_by_id INTEGER NULL REFERENCES accounts_companyuser(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_settlement_company_status ON payouts_settlementbatch(company_id, status);
```

### payouts_settlementitem

```sql
CREATE TABLE payouts_settlementitem (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES tenants_company(id),
    batch_id INTEGER NOT NULL REFERENCES payouts_settlementbatch(id),
    invoice_id INTEGER REFERENCES invoices_invoice(id),
    amount_rial BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_settlement_item_batch ON payouts_settlementitem(batch_id);
```

### payouts_adjustmentdocument

```sql
CREATE TABLE payouts_adjustmentdocument (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES tenants_company(id),
    document_type VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    original_invoice_id INTEGER NOT NULL REFERENCES invoices_invoice(id),
    amount_rial BIGINT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    technician_wage_reversal DECIMAL(12,0) NULL,
    platform_fee_reversal DECIMAL(12,0) NULL,
    company_share_reversal DECIMAL(12,0) NULL,
    created_by_id INTEGER REFERENCES accounts_companyuser(id),
    approved_by_id INTEGER NULL REFERENCES accounts_companyuser(id),
    approved_at TIMESTAMP WITH TIME ZONE NULL,
    applied_at TIMESTAMP WITH TIME ZONE NULL,
    technician_ledger_entry_id INTEGER NULL,
    platform_fee_entry_id INTEGER NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

---

## Migration Safety

| Change Type | Risk | Downtime |
|---|---|---|
| ADD COLUMN (nullable or default) | Zero | None |
| CREATE TABLE | Zero | None |
| ALTER existing column | N/A | N/A — NOT PROPOSED |
| DROP TABLE | N/A | N/A — NOT PROPOSED |
| Data migration | N/A | N/A — NOT PROPOSED |

**تمام تغییرات backward-compatible. هیچ downtime لازم نیست.**
