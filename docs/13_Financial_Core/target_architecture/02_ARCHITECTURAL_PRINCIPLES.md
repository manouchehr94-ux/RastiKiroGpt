# 02 — اصول معماری (Architectural Principles P01–P10)

**Version:** v1.0 — Draft — Pending Clarification

---

## P01 — جداسازی حرکت پول از معنای پول

**اصل:** یک تراکنش پرداخت موفق فقط اثبات می‌کند که پول جابجا شده. تعیین نمی‌کند چه کسی مالک است.

**مثال RastiSaas:**
- `Payment` (status=PAID) = حرکت فیزیکی پول
- `InvoiceSettlementService.settle()` = تعیین مالکیت (settled_technician_wage, settled_company_share)
- `TechnicianLedgerEntry` = ثبت حق مالکیت تکنسین
- `CompanyPlatformFeeEntry` = ثبت حق پلتفرم

**وضعیت در کد:** ✅ رعایت شده — `Payment` مستقل از `TechnicianLedgerEntry` و `CompanyPlatformFeeEntry`

---

## P02 — تمامیت مالی Append-Only

**اصل:** هیچ رکورد مالی پس از ایجاد قابل ویرایش یا حذف نیست.

**مثال RastiSaas:**
```python
# TechnicianLedgerEntry.delete() → PermissionError
# TechnicianLedgerEntry.save() → checks immutability of amount_rial, balance_after
```

اصلاح خطا: یک ADJUSTMENT entry جدید ایجاد می‌شود — نه تغییر entry قبلی.

**وضعیت در کد:** ✅ رعایت شده — ADR-004، model-level enforcement

---

## P03 — سیاست‌ها خارج از منطق تجاری

**اصل:** قواعد تجاری هرگز hardcode نمی‌شوند. از Financial Policy Engine بارگذاری می‌شوند.

**مثال RastiSaas:**
- `CompanyFinancialPolicy.platform_fee_percent` — نرخ کارمزد per company
- `CompanyFinancialPolicy.campaign_discount_policy` — سیاست تخفیف
- `CompanyFinancialPolicy.payout_strategy` — استراتژی تسویه

**وضعیت در کد:** ✅ رعایت شده — `CompanyFinancialPolicy` model + `get_or_create` pattern

---

## P04 — Financial Party مستقل از User Identity

**اصل:** یک حساب کاربری و یک هویت مالی مفاهیم متفاوتی هستند.

**مثال RastiSaas:**
```
تکنسین حسن
    ├── شرکت الف: Technician(id=10, company=A) → ledger مجزا
    └── شرکت ب: Technician(id=25, company=B) → ledger مجزا
```

هرچند هر دو User یکسان هستند، اما Financial Party‌های مستقل با ledger balance جداگانه.

**وضعیت در کد:** ✅ رعایت شده — `Technician` per `CompanyUser` per `Company` (R17)

---

## P05 — پلتفرم به عنوان Escrow Holder

**اصل:** پلتفرم فروشنده نیست. پول در نگهداری موقت (escrow) پلتفرم است تا تسویه. فقط کارمزد پلتفرم درآمد پلتفرم است.

**مثال RastiSaas:**
- کل وجه مشتری → به حساب پلتفرم (gateway owner_type=platform)
- `platform_fee_amount` → درآمد پلتفرم
- `company_deposit_amount` + `technician_direct_amount` → escrow (بدهی پلتفرم)

**وضعیت در کد:** 🟡 ضمنی — `PaymentSplitSnapshot` محاسبه می‌کند. اما مدل `EscrowRecord` صریح وجود ندارد.

---

## P06 — واحد تسویه: فاکتور

**اصل:** هر تسویه‌ای که شامل پلتفرم باشد باید به فاکتور reference داشته باشد — نه سفارش.

**مثال RastiSaas:**
- `TechnicianLedgerEntry.invoice` — FK to Invoice
- `CompanyPlatformFeeEntry.invoice` — FK to Invoice
- `PaymentSplitSnapshot.invoice` — FK to Invoice

**وضعیت در کد:** ✅ رعایت شده — تمام financial entries به Invoice reference دارند (R45)

---

## P07 — دو لایه تسویه مستقل

**اصل:** تسویه در دو سطح کاملاً مستقل رخ می‌دهد:

### لایه 1: Platform ↔ Organization
- پیکربندی: فقط توسط Platform Owner
- مرجع: `CompanyPlatformFeeEntry`, `SettlementBatch` (target)

### لایه 2: Organization ↔ Provider
- پیکربندی: فقط توسط Organization
- مرجع: `TechnicianLedgerEntry`, `record_manual_settlement`

**وضعیت در کد:** ✅ مفهومی رعایت شده — دو ledger جداگانه. اما automation فقط لایه 2 (دستی) پوشش می‌دهد.

---

## P08 — تغییرات سیاست فقط رو به جلو

**اصل:** تغییر سیاست‌ها هرگز اسناد تاریخی را تغییر نمی‌دهد.

**مثال RastiSaas:**
- `platform_fee_percent` تغییر می‌کند → فقط invoices آینده متأثر
- wage percentages در لحظه issue روی invoice فریز می‌شوند (`snapshot_wage_percentages_on_invoice`)
- settlement values در لحظه PAID فریز می‌شوند (`InvoiceSettlementService.settle()`)

**وضعیت در کد:** ✅ رعایت شده — R49، ADR-005

---

## P09 — فاکتور پرداخت‌شده تغییرناپذیر

**اصل:** فاکتور PAID قفل شده و هیچ فیلدی قابل تغییر نیست. هر اصلاح باید از طریق سند مالی جداگانه.

**مثال RastiSaas:**
```python
# Invoice.recalculate_totals():
if self.status == self.Status.PAID:
    raise ValueError("Cannot recalculate totals on PAID invoice")
```

**وضعیت در کد:** ✅ رعایت شده — R52. اما Credit Note / Debit Note model هنوز وجود ندارد (target: `14_REFUND_ADJUSTMENT_ENGINE.md`).

---

## P10 — هر تغییر وضعیت مالی Event-Driven

**اصل:** هر انتقال وضعیت مالی معنادار باید یک domain event publish کند.

**مثال RastiSaas:**

| Event | Trigger |
|---|---|
| `invoice_paid` | `InvoiceMarkPaidService.mark_paid()` |
| `payment_success_customer` | `PaymentVerifyService.verify()` |
| `commission_calculated` | `PlatformFeeService.record_invoice_fee()` — target |
| `escrow_reserved` | EscrowRecord creation — target |
| `settlement_completed` | SettlementBatch completion — target |
| `provider_iban_missing` | PaymentSplitDecisionService — when split blocked |
| `refund_issued` | RefundService — target |

**وضعیت در کد:** 🟡 جزئی — `notifications/event_catalog.py` شامل رویدادهای invoice/payment. اما financial-specific events (escrow, settlement, refund) هنوز ناموجود.
