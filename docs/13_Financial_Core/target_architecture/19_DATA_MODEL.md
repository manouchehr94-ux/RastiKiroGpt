# 19 — مدل داده پیشنهادی (Proposed Data Model)

**Version:** v1.0 — Draft — Pending Clarification

---

## Existing Tables — NO SCHEMA CHANGES

All existing financial tables remain untouched structurally:

- `invoices_invoice` — 40+ fields including 17 settled_* snapshots
- `invoices_invoiceitem` — row_type, quantity, unit_price, discount_amount, total_price
- `payments_payment` — status, amount, gateway, invoice, reference_id, tracking_code
- `payments_paymentgateway` — owner_type, gateway_type, merchant_id
- `payouts_technicianledgerentry` — immutable; entry_type, source, amount_rial, balance_after
- `payouts_companyplatformfeeentry` — immutable; same pattern
- `payouts_paymentsplitsnapshot` — OneToOne(payment); split amounts
- `payouts_financialbackfilltask` — task_type, status, attempts
- `payouts_technicianservicerate` — fixed_wage_rial per item per technician
- `tenants_companyfinancialpolicy` — discount policies, payout_strategy, platform_fee_percent
- `tenants_companypaymentsettings` — payment_mode, activation_status
- `tenants_companymerchantprofile` — KYC, shaba_number, status

---

## New Columns on Existing Tables


### CompanyFinancialPolicy — 3 new fields

```python
# apps/tenants/models.py — add to CompanyFinancialPolicy

charge_commission_on_cash = models.BooleanField(
    default=False,
    help_text="آیا کارمزد پلتفرم برای پرداخت‌های نقدی هم محاسبه شود؟",
)
# Type: BooleanField
# Nullable: No (NOT NULL, has default)
# Index: No (low-cardinality boolean — not indexed)
# Constraint: None
# Migration safety: AddField with default=False — zero-downtime, no data backfill
# Backward compatibility: Existing behavior unchanged (False = no commission on cash)
# Business rule: R10, R38

rounding_discount_enabled = models.BooleanField(
    default=False,
    help_text="آیا تخفیف رُند در فاکتور فعال باشد؟",
)
# Type: BooleanField
# Nullable: No (NOT NULL, has default)
# Index: No
# Constraint: None
# Migration safety: AddField with default=False — zero-downtime
# Backward compatibility: Existing invoices unaffected
# Business rule: R29

max_rounding_discount_rial = models.PositiveBigIntegerField(
    default=0,
    help_text="حداکثر مبلغ تخفیف رُند مجاز (ریال). صفر = بدون محدودیت.",
)
# Type: PositiveBigIntegerField
# Nullable: No (NOT NULL, has default)
# Index: No
# Constraint: Django built-in (PositiveBigIntegerField enforces >= 0)
# Migration safety: AddField with default=0 — zero-downtime
# Backward compatibility: default 0 means disabled by default
# Business rule: R29
```

### Invoice — 1 new field

```python
# apps/invoices/models.py — add to Invoice

rounding_discount_amount = models.DecimalField(
    max_digits=12,
    decimal_places=0,
    default=0,
    help_text="مبلغ تخفیف رُند اعمال‌شده.",
)
# Type: DecimalField(12,0)
# Nullable: No (NOT NULL, has default)
# Index: No
# Constraint: Application-level: <= max_rounding_discount_rial from policy
# Migration safety: AddField with default=0 — zero-downtime
# Backward compatibility: Existing invoices retain 0 (no rounding discount)
# Business rule: R29
```

---

## New Tables


### EscrowRecord

```python
# apps/payouts/models.py — new model

class EscrowRecord(CompanyOwnedModel):
    class Status(models.TextChoices):
        HELD = "held", "نگهداری"
        RESERVED = "reserved", "رزرو شده"
        DISTRIBUTED = "distributed", "تخصیص یافته"
        PENDING_SETTLEMENT = "pending_settlement", "در انتظار تسویه"
        SETTLED = "settled", "تسویه شده"
        CLOSED = "closed", "بسته شده"

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="escrow_record",
    )
    # Type: OneToOneField (integer FK + UNIQUE)
    # Nullable: No
    # Index: Yes (unique constraint creates implicit index)
    # Constraint: UNIQUE on payment_id — one escrow per payment
    # Business rule: R01, P05

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="escrow_records",
    )
    # Type: ForeignKey (integer, nullable)
    # Nullable: Yes (SET_NULL on delete)
    # Index: Yes (Django default for FK)

    amount_rial = models.PositiveBigIntegerField()
    # Total customer payment amount held in escrow
    # Constraint: >= 0 (PositiveBigIntegerField)

    platform_commission_rial = models.PositiveBigIntegerField(default=0)
    organization_share_rial = models.PositiveBigIntegerField(default=0)
    provider_share_rial = models.PositiveBigIntegerField(default=0)
    # Invariant: platform_commission + organization_share + provider_share = amount_rial
    # Populated when status transitions to DISTRIBUTED

    status = models.CharField(max_length=25, choices=Status.choices, default=Status.HELD, db_index=True)
    # Type: CharField(25)
    # Index: Yes (frequently filtered)

    held_at = models.DateTimeField(auto_now_add=True)
    distributed_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    settlement_batch = models.ForeignKey(
        "payouts.SettlementBatch",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="escrow_records",
    )

    class Meta:
        ordering = ["-held_at"]
        indexes = [
            models.Index(fields=["company", "status"], name="escrow_company_status_idx"),
        ]
```

**Migration safety:** CREATE TABLE — zero-downtime, no existing data affected.
**Backward compatibility:** Completely additive. Existing payment flow unchanged.
**Business rules satisfied:** R01 (legal custody tracking), P05 (escrow vs revenue separation).

---

### SettlementBatch

```python
# apps/payouts/models.py — new model

class SettlementBatch(CompanyOwnedModel):
    class Level(models.TextChoices):
        PLATFORM_TO_ORG = "platform_to_org", "پلتفرم به شرکت"
        ORG_TO_PROVIDER = "org_to_provider", "شرکت به تکنسین"

    class Status(models.TextChoices):
        CALCULATING = "calculating", "در حال محاسبه"
        READY = "ready", "آماده اجرا"
        EXECUTING = "executing", "در حال اجرا"
        COMPLETED = "completed", "تکمیل شده"
        FAILED = "failed", "ناموفق"

    level = models.CharField(max_length=20, choices=Level.choices, db_index=True)
    # Type: CharField(20)
    # Index: Yes (filtered for Level 1 vs Level 2 queries)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CALCULATING, db_index=True)

    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    # Define the time window of invoices included

    net_amount_rial = models.BigIntegerField(default=0)
    # Signed: positive = platform owes org. negative = org owes platform.
    # Type: BigIntegerField (allows negative)
    # Constraint: None (can be zero or negative for netting)

    total_credits = models.PositiveBigIntegerField(default=0)
    total_debits = models.PositiveBigIntegerField(default=0)
    items_count = models.PositiveIntegerField(default=0)

    executed_at = models.DateTimeField(null=True, blank=True)
    bank_reference = models.CharField(max_length=200, blank=True)
    failure_reason = models.TextField(blank=True)

    created_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_settlement_batches",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "level", "status"], name="settlement_batch_idx"),
            models.Index(fields=["company", "period_start", "period_end"], name="settlement_period_idx"),
        ]
```

**Migration safety:** CREATE TABLE — zero-downtime.
**Backward compatibility:** Additive. Existing manual settlements unchanged.
**Business rules satisfied:** R41 (configurable timing), R43 (automatic), R44 (no approval default), R55 (settlement reporting).

---

### SettlementItem

```python
# apps/payouts/models.py — new model

class SettlementItem(CompanyOwnedModel):
    batch = models.ForeignKey(
        SettlementBatch,
        on_delete=models.CASCADE,
        related_name="items",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="settlement_items",
    )
    ledger_entry = models.ForeignKey(
        "payouts.TechnicianLedgerEntry",
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    platform_fee_entry = models.ForeignKey(
        "payouts.CompanyPlatformFeeEntry",
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    amount_rial = models.BigIntegerField()
    # Signed: contribution to net position
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["batch", "invoice"], name="settlement_item_batch_inv_idx"),
        ]
```

**Migration safety:** CREATE TABLE — zero-downtime.
**Business rules satisfied:** R45 (settlement unit is invoice).


---

### AdjustmentDocument

```python
# apps/payouts/models.py — new model

class AdjustmentDocument(CompanyOwnedModel):
    class DocumentType(models.TextChoices):
        FULL_REFUND = "full_refund", "بازپرداخت کامل"
        PARTIAL_REFUND = "partial_refund", "بازپرداخت جزئی"
        CREDIT_NOTE = "credit_note", "اعتبارنامه"
        DEBIT_NOTE = "debit_note", "بدهکاری"
        MANUAL_ADJUSTMENT = "manual_adjustment", "اصلاح دستی"

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PENDING_APPROVAL = "pending_approval", "در انتظار تأیید"
        APPROVED = "approved", "تأییدشده"
        APPLIED = "applied", "اعمال‌شده"
        REJECTED = "rejected", "رد شده"
        CANCELLED = "cancelled", "لغو شده"

    document_type = models.CharField(max_length=30, choices=DocumentType.choices, db_index=True)
    # Type: CharField(30)
    # Index: Yes (filtered by type)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    original_invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.CASCADE,
        related_name="adjustment_documents",
    )
    # Constraint: original_invoice.status must be PAID (application-level)

    amount_rial = models.PositiveBigIntegerField()
    # Constraint: <= original_invoice.total_amount (application-level for refunds)

    reason = models.TextField()
    # Required — must explain why adjustment is needed

    # Financial reversal tracking (populated when APPLIED)
    technician_wage_reversal = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True,
    )
    platform_fee_reversal = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True,
    )
    company_share_reversal = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True,
    )

    # Audit
    created_by = models.ForeignKey(
        "accounts.CompanyUser", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_adjustments",
    )
    approved_by = models.ForeignKey(
        "accounts.CompanyUser", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="approved_adjustments",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    # Ledger references (created when APPLIED)
    technician_ledger_entry = models.ForeignKey(
        "payouts.TechnicianLedgerEntry",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="adjustment_documents",
    )
    platform_fee_entry = models.ForeignKey(
        "payouts.CompanyPlatformFeeEntry",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="adjustment_documents",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status", "document_type"], name="adj_doc_status_type_idx"),
            models.Index(fields=["company", "original_invoice"], name="adj_doc_invoice_idx"),
        ]
```

**Migration safety:** CREATE TABLE — zero-downtime.
**Backward compatibility:** Additive. Existing `record_manual_settlement(ADJUSTMENT_*)` continues working for simple technician-level adjustments.
**Business rules satisfied:** R46 (customer adjustments), R52 (correction via separate document).
**Open Issue Impact:** Blocked on OI-07 (refund definitions). Document type choices finalized after PO decision.

---

## Migration Plan Summary

| Table/Column | Type | Downtime | Risk |
|---|---|---|---|
| CompanyFinancialPolicy.charge_commission_on_cash | ADD COLUMN (BooleanField default=False) | None | Zero |
| CompanyFinancialPolicy.rounding_discount_enabled | ADD COLUMN (BooleanField default=False) | None | Zero |
| CompanyFinancialPolicy.max_rounding_discount_rial | ADD COLUMN (BigInt default=0) | None | Zero |
| Invoice.rounding_discount_amount | ADD COLUMN (Decimal default=0) | None | Zero |
| EscrowRecord | CREATE TABLE | None | Zero |
| SettlementBatch | CREATE TABLE | None | Zero |
| SettlementItem | CREATE TABLE | None | Zero |
| AdjustmentDocument | CREATE TABLE | None | Zero |

**Total migrations: 4 ADD COLUMN + 4 CREATE TABLE = 8 operations. All zero-downtime.**
