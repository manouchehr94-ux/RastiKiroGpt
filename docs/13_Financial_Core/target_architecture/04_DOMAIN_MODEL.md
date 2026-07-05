# 04 — مدل دامنه مالی (Financial Domain Model)

**Version:** v1.0 — Draft — Pending Clarification
**مبنا:** یافته‌های ممیزی `03_MODEL_ANALYSIS.md`

---

## Domain Models Overview

```
FinancialParty (concept)
├── PlatformOwner
├── Organization (Company)
├── Provider (Technician)
└── Customer

Invoice ──┬── InvoiceItem[]
           └── CommissionAllocation (settled_* fields)

PaymentTransaction (Payment)
├── PaymentAttempt[]
└── PaymentSplitSnapshot (1:1)

LedgerEntry
├── TechnicianLedgerEntry (existing)
└── CompanyPlatformFeeEntry (existing)

EscrowRecord (target — new)

SettlementBatch (target — new)
└── SettlementItem[] (target — new)

AdjustmentDocument (target — new)

DiscountRecord
├── DiscountCampaign (existing)
└── DiscountCode (existing)
```

---

## 1. FinancialParty (مفهومی)

هر موجودیت با قابلیت مالکیت مانده، بدهکاری، بستانکاری.

| Party | Existing Model | Ledger |
|---|---|---|
| Platform Owner | implicit (system-level) | CompanyPlatformFeeEntry (creditor side) |
| Organization | `Company` | CompanyPlatformFeeEntry (debtor side) |
| Provider | `Technician` (per company) | TechnicianLedgerEntry |
| Customer | `Customer` | ❌ Missing — target: CustomerFinancialAccount |

---

## 2. Invoice (موجود — بدون تغییر)

**Model:** `apps/invoices/models.Invoice`

| Field Group | Fields |
|---|---|
| Identity | invoice_number, public_code, status |
| Relationships | order, customer, company, created_by |
| Snapshots | customer_name/phone, technician_name/phone, service_title/date |
| Amounts | gross_amount, row_discount_amount, net_amount_before_invoice_discounts, extra_discount_amount, campaign_discount_amount, total_discount_amount, subtotal, tax_amount, total_amount |
| Settlement (frozen at PAID) | settled_service_total, settled_goods_total, settled_travel_total, settled_extra_discount_amount, settled_campaign_discount_amount, settled_*_policy, settled_technician_gross_share, settled_company_gross_share, settled_technician_absorbed_discount, settled_company_absorbed_discount, settled_technician_wage, settled_company_share, settled_payment_method, settled_payment_reference, settled_discount_code_id, settled_at |
| Wage Snapshots | technician_service/goods/travel_wage_percent_snapshot |
| Dates | issued_at, due_at, paid_at |

---

## 3. InvoiceItem (موجود — extension needed)

**Model:** `apps/invoices/models.InvoiceItem`

| Field | Type |
|---|---|
| row_type | service / goods / travel / **additional_discount** (target) / **loyalty_discount** (target) |
| description | CharField |
| quantity | Decimal |
| unit_price | Decimal |
| discount_amount | Decimal |
| total_price | Decimal (computed) |

---

## 4. PaymentTransaction (موجود — Payment)

**Model:** `apps/payments/models.Payment`

Status machine: INITIATED → PENDING → PAID / FAILED / NEEDS_RECONCILIATION / CANCELLED

---

## 5. EscrowRecord (Target — جدید)

```python
class EscrowRecord(CompanyOwnedModel):
    class Status(TextChoices):
        HELD = "held"                    # پول در حساب پلتفرم
        RESERVED_FOR_INVOICE = "reserved"  # اختصاص به فاکتور
        ELIGIBLE_FOR_DISTRIBUTION = "eligible"  # شرایط عملیاتی برآورده
        DISTRIBUTED = "distributed"      # تخصیص محاسبه شده
        PENDING_SETTLEMENT = "pending"   # منتظر تسویه
        SETTLED = "settled"              # وجه منتقل شده
        CLOSED = "closed"               # نهایی

    payment = OneToOneField(Payment)
    invoice = ForeignKey(Invoice)
    amount_rial = PositiveBigIntegerField()
    platform_commission = PositiveBigIntegerField()
    organization_share = PositiveBigIntegerField()
    provider_share = PositiveBigIntegerField()
    status = CharField(choices=Status)
    held_at = DateTimeField()
    released_at = DateTimeField(null=True)
    settled_at = DateTimeField(null=True)
```

---

## 6. SettlementBatch (Target — جدید)

```python
class SettlementBatch(CompanyOwnedModel):
    class Level(TextChoices):
        PLATFORM_TO_ORG = "platform_to_org"
        ORG_TO_PROVIDER = "org_to_provider"

    class Status(TextChoices):
        CALCULATING = "calculating"
        PENDING_APPROVAL = "pending_approval"  # [OPEN-ISSUE: OI-08]
        APPROVED = "approved"
        EXECUTING = "executing"
        COMPLETED = "completed"
        FAILED = "failed"

    level = CharField(choices=Level)
    status = CharField(choices=Status)
    period_start = DateTimeField()
    period_end = DateTimeField()
    net_amount_rial = BigIntegerField()  # net position
    total_credits = PositiveBigIntegerField()
    total_debits = PositiveBigIntegerField()
    items_count = PositiveIntegerField()
    executed_at = DateTimeField(null=True)
    bank_reference = CharField(blank=True)
```

---

## 7. SettlementItem (Target — جدید)

```python
class SettlementItem(CompanyOwnedModel):
    batch = ForeignKey(SettlementBatch)
    invoice = ForeignKey(Invoice)
    amount_rial = BigIntegerField()  # signed: positive = owed, negative = credit
    description = TextField(blank=True)
```

---

## 8. AdjustmentDocument (Target — جدید)

```python
class AdjustmentDocument(CompanyOwnedModel):
    class DocumentType(TextChoices):
        CREDIT_NOTE = "credit_note"
        DEBIT_NOTE = "debit_note"
        REFUND = "refund"

    class Status(TextChoices):
        DRAFT = "draft"
        APPROVED = "approved"
        APPLIED = "applied"
        CANCELLED = "cancelled"

    document_type = CharField(choices=DocumentType)
    status = CharField(choices=Status)
    original_invoice = ForeignKey(Invoice)
    amount_rial = PositiveBigIntegerField()
    reason = TextField()
    approved_by = ForeignKey(CompanyUser, null=True)
    applied_at = DateTimeField(null=True)
```

[OPEN-ISSUE: OI-07]
Current Status: مفاهیم Full Refund, Partial Refund, و Manual Adjustment هنوز تعریف نشده‌اند.
Question for Product Owner: تعریف دقیق هر نوع بازپرداخت و سناریوهای اعمال آن.

---

## 9. Existing Models (بدون تغییر)

تمام مدل‌های زیر بدون تغییر حفظ می‌شوند:
- `TechnicianLedgerEntry`
- `CompanyPlatformFeeEntry`
- `PaymentSplitSnapshot`
- `FinancialBackfillTask`
- `TechnicianServiceRate`
- `CompanyFinancialPolicy`
- `CompanyPaymentSettings`
- `CompanyMerchantProfile`
- `DiscountCampaign` / `DiscountCode`
