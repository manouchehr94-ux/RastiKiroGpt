# 14 — موتور بازپرداخت و اصلاح (Refund & Adjustment Engine)

**Version:** v1.0 — Draft — Pending Clarification

---

[OPEN-ISSUE: OI-06]
**Current Status:** هیچ قاعده تجاری تعریف نمی‌کند که overpayment مشتری چگونه مدیریت شود.
**Question for Product Owner:** در صورت پرداخت بیشتر از مبلغ فاکتور: Wallet، Refund، یا Credit Balance؟

[OPEN-ISSUE: OI-07]
**Current Status:** Product Owner درخواست توضیح بصری مفاهیم Full Refund, Partial Refund, و Manual Adjustment کرده.
**Question for Product Owner:** تعریف دقیق و تصمیم‌گیری درباره هر نوع.

---

## معماری پیشنهادی (منتظر OI resolution)

### AdjustmentDocument Model

```python
class AdjustmentDocument(CompanyOwnedModel):
    class DocumentType(TextChoices):
        FULL_REFUND = "full_refund"        # بازپرداخت کامل
        PARTIAL_REFUND = "partial_refund"  # بازپرداخت جزئی
        CREDIT_NOTE = "credit_note"        # اعتبارنامه (کسر از فاکتور بعدی)
        DEBIT_NOTE = "debit_note"          # بدهکاری اضافی
        MANUAL_ADJUSTMENT = "manual_adjustment"  # اصلاح دستی

    class Status(TextChoices):
        DRAFT = "draft"
        PENDING_APPROVAL = "pending_approval"
        APPROVED = "approved"
        APPLIED = "applied"
        REJECTED = "rejected"
        CANCELLED = "cancelled"

    document_type = CharField(choices=DocumentType)
    status = CharField(choices=Status, default=Status.DRAFT)
    original_invoice = ForeignKey(Invoice, related_name="adjustment_documents")
    amount_rial = PositiveBigIntegerField()
    reason = TextField()
    
    # Financial reversal tracking
    technician_wage_reversal = DecimalField(null=True)
    platform_fee_reversal = DecimalField(null=True)
    company_share_reversal = DecimalField(null=True)
    
    # Approval
    created_by = ForeignKey(CompanyUser)
    approved_by = ForeignKey(CompanyUser, null=True)
    approved_at = DateTimeField(null=True)
    applied_at = DateTimeField(null=True)
    
    # Ledger references (created when applied)
    technician_ledger_entry = ForeignKey(TechnicianLedgerEntry, null=True)
    platform_fee_entry = ForeignKey(CompanyPlatformFeeEntry, null=True)
```

---

## Refund Orchestration Flow

```
1. Admin creates AdjustmentDocument(type=FULL_REFUND, status=DRAFT)
2. System calculates reversal amounts:
   - technician_wage_reversal = invoice.settled_technician_wage
   - platform_fee_reversal = computed from CompanyPlatformFeeEntry
   - company_share_reversal = invoice.settled_company_share
3. Admin approves → status = APPROVED
4. RefundExecutionService.execute():
   a. TechnicianLedgerService.create_debit(source=ADJUSTMENT) — reverse wage
   b. PlatformFeeService._write_entry(type=CREDIT, source=REFUND) — reverse fee
   c. EscrowRecord.status → CLOSED (with refund note)
   d. Gateway refund API call (if online payment)
   e. AdjustmentDocument.status → APPLIED
5. Financial events published: refund_issued
```

---

## Partial Refund

مشابه Full Refund اما:
- `amount_rial` < `original_invoice.total_amount`
- Reversal amounts proportional
- Original invoice remains PAID (immutable — R52)

---

## Credit Note

- مشتری credit balance دریافت می‌کند (قابل استفاده در فاکتور بعدی)
- هیچ bank refund صورت نمی‌گیرد
- نیازمند `CustomerFinancialAccount` model (target)

[OPEN-ISSUE: OI-05]
**Current Status:** لیست کامل سناریوهای credit/debit مشتری تعریف نشده.
**Question for Product Owner:** دقیقاً در چه سناریوهایی مشتری بستانکار یا بدهکار می‌شود؟

---

## Manual Adjustment

- Admin دستی مبلغی اضافه/کسر می‌کند
- دلیل الزامی
- Audit trail (created_by, approved_by)
- Current implementation exists: `TechnicianLedgerService.record_manual_settlement(direction=ADJUSTMENT_*)`

---

## Constraints

- Original Invoice never modified (R52, P09)
- All reversals are NEW ledger entries (P02)
- AdjustmentDocument references original invoice (audit trail)
- No deletion allowed (R51)

---

## وضعیت فعلی

| Component | Status |
|---|---|
| Manual adjustment (technician ledger) | ✅ `record_manual_settlement(ADJUSTMENT_*)` |
| Ledger immutability (no edit) | ✅ model enforcement |
| Source.REFUND defined | ✅ choice exists |
| RefundService implementation | ❌ Missing |
| AdjustmentDocument model | ❌ Missing — target |
| Customer credit/debit | ❌ Missing — blocked on OI-05, OI-06 |
| Gateway refund API | ❌ Missing — target |
