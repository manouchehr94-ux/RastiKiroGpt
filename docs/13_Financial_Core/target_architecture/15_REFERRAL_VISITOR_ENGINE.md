# 15 — موتور ارجاع (Referral / Visitor Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R32–R36
**Status:** Future Extension Point — NOT for current implementation

---

## وضعیت فعلی

مطابق R32 و R33:
- هیچ کمیسیون ارجاع فعلاً پیاده‌سازی نشده
- هیچ کمیسیون معرفی مشتری فعلاً پیاده‌سازی نشده
- این **عمداً** صحیح است

---

## قواعد آینده (وقتی فعال شود)

### R34 — کمیسیون فقط یک‌بار
- اولین فاکتور پرداخت‌شده مشتری معرفی‌شده → کمیسیون
- فاکتورهای بعدی → هیچ کمیسیون اضافی

### R35 — کسر از سهم شرکت
- کمیسیون ارجاع از سهم Organization کسر
- هرگز از کارمزد Platform کسر نمی‌شود
- هرگز از سهم Provider کسر نمی‌شود

### R36 — معرف مشتری = بازدیدکننده
- این دو مفهوم یکی هستند — نه نقش‌های جداگانه

---

## Extension Point Architecture (طراحی آینده)

```python
# Target model (NOT FOR IMPLEMENTATION NOW)
class ReferralCommission(CompanyOwnedModel):
    referrer = ForeignKey("accounts.CompanyUser")
    referred_customer = ForeignKey("accounts.Customer")
    triggered_invoice = ForeignKey("invoices.Invoice")
    commission_amount_rial = PositiveBigIntegerField()
    deducted_from = CharField()  # always "organization_share"
    status = CharField()  # pending → paid
    paid_at = DateTimeField(null=True)
```

**Integration point:** `InvoiceSettlementService.settle()` — after calculating company_share, deduct referral commission before final share.

---

## Architectural Decisions

1. هیچ کدی برای referral در V1 نوشته نمی‌شود
2. Extension point: `InvoiceSettlementService` قبلاً policy-driven است → اضافه کردن referral policy در آینده بدون تغییر ساختار ممکن
3. اگر در آینده فعال شود:
   - migration: new table (zero-downtime)
   - logic: new step in settlement calculation
   - no existing code breaks
