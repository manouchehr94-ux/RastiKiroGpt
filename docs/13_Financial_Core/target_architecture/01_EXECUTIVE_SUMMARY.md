# 01 — خلاصه اجرایی (Executive Summary)

**Version:** v1.0 — Draft — Pending Clarification

---

## پنج سؤال کلیدی مالی

هر تراکنش مالی در RastiSaas باید بتواند به این پنج سؤال پاسخ دهد:

---

### 1. چه مبلغی توافق شد؟ (What amount was agreed?)

فاکتور (`Invoice`) مرجع نهایی مبلغ توافقی است. مبلغ شامل:
- مجموع ردیف‌های خدمات (`service_total`)
- مجموع ردیف‌های کالا (`goods_total`)
- مجموع ردیف‌های ایاب‌وذهاب (`travel_total`)
- منهای تخفیفات ردیفی (`row_discount_amount`)
- منهای تخفیف مازاد (`extra_discount_amount`)
- منهای تخفیف کمپین (`campaign_discount_amount`)
- به‌اضافه مالیات (`tax_amount`)
= **`total_amount`** — مبلغ نهایی قابل پرداخت

**وضعیت فعلی:** ✅ پیاده‌سازی شده — `Invoice.total_amount` و `Invoice.recalculate_totals()`

---

### 2. چه کسی پرداخت کرد؟ (Who paid?)

مشتری (`Customer`) پرداخت‌کننده نهایی است. اثبات پرداخت:
- پرداخت آنلاین: `Payment.status == PAID` + `Payment.tracking_code`
- پرداخت نقدی: ثبت توسط ادمین شرکت (metadata.method = cash)
- کارت‌به‌کارت: ثبت توسط ادمین (metadata.method = card_to_card)

**وضعیت فعلی:** ✅ پیاده‌سازی شده — `Payment` model + `PaymentVerifyService`

---

### 3. مالکیت اقتصادی پول نزد چه کسی است؟ (Who economically owns the money?)

**قبل از تسویه:** پلتفرم — به عنوان Escrow Holder (نه مالک)
**بعد از تسویه:** هر طرف سهم خود را دریافت کرده

مالکیت باید در هر لحظه قابل تفکیک باشد:
- سهم پلتفرم (Commission) = `platform_fee_amount`
- سهم شرکت = `company_deposit_amount`
- سهم تکنسین = `technician_direct_amount` یا `technician_ledger_amount`

**وضعیت فعلی:** 🟡 جزئی — `PaymentSplitSnapshot` محاسبه می‌کند اما مدل Escrow صریح ندارد. (Gap: RISK-03)

---

### 4. هر طرف مستحق چه مبلغی است؟ (Who is entitled to what amount?)

سند تخصیص کمیسیون (`Commission Allocation Document`) = فیلدهای `settled_*` روی Invoice:
- `settled_technician_wage` — سهم تکنسین
- `settled_company_share` — سهم شرکت
- `settled_technician_absorbed_discount` — تخفیف جذب‌شده توسط تکنسین
- `settled_company_absorbed_discount` — تخفیف جذب‌شده توسط شرکت

**وضعیت فعلی:** ✅ پیاده‌سازی شده — `InvoiceSettlementService.settle()` تمام مقادیر را فریز می‌کند

---

### 5. چه چیزی تسویه شده، بازپرداخت شده، یا باقی مانده؟ (What has been settled, refunded, or remains outstanding?)

- **تسویه‌شده:** `TechnicianLedgerEntry` entries (DEBIT = settled)
- **بازپرداخت:** هنوز پیاده‌سازی نشده (Gap: RISK-01)
- **باقی‌مانده:** `TechnicianLedgerService.get_balance()` = SUM(credits) - SUM(debits)

| Financial Party | موجودی بدهکاری | مرجع |
|---|---|---|
| Platform → Organization | `CompanyPlatformFeeEntry` balance | `PlatformFeeService.get_balance()` |
| Organization → Technician | `TechnicianLedgerEntry` balance | `TechnicianLedgerService.get_balance()` |
| Customer → Organization | Invoice status (PAID = settled, ISSUED = outstanding) | `Invoice.status` |

**وضعیت فعلی:** 🟡 جزئی — Technician balance tracking ✅. Platform fee balance ✅. اما settlement batching/netting ❌ و refund ❌.

---

## ارتباط با ممیزی موجود

این سند بر اساس یافته‌های `docs/13_Financial_Core/05_GAP_ANALYSIS.md` تنظیم شده:
- 30 قاعده fully implemented → foundation قوی
- 12 قاعده partially implemented → نیاز به extension
- 8 قاعده missing → نیاز به development جدید

**Readiness Score:** 62/100 — foundation بالغ، اما settlement automation، escrow، و refund هنوز ناموجود.
