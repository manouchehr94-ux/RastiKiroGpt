# 07 — تحلیل ریسک (Risk Analysis)

**تاریخ ممیزی:** 2026-07-05

---

## ریسک‌های بحرانی (Critical)

### RISK-01: عدم وجود مکانیزم Refund

**شدت:** CRITICAL
**وضعیت:** `TechnicianLedgerEntry.Source.REFUND` تعریف شده اما **هیچ سرویس refund** پیاده‌سازی نشده.

**Impact:**
- اگر مشتری درخواست بازپرداخت کند، هیچ مسیر سیستماتیک وجود ندارد
- Settlement entries قبلاً freeze شده‌اند — reverse کردن آن‌ها فقط با adjustment entries ممکن است
- Platform fee charged → باید credit entry ساخته شود → سرویسی برای این orchestration نیست

**Mitigation:** طراحی Refund Engine قبل از production scale.

---

### RISK-02: عدم وجود Settlement Batching / Netting

**شدت:** HIGH
**وضعیت:** هر تسویه Platform↔Organization دستی و per-invoice است. هیچ Net Position calculation وجود ندارد.

**Impact:**
- در مقیاس بالا، تعداد تراکنش‌های بانکی بسیار زیاد می‌شود
- هزینه‌های بانکی غیرضروری
- پلتفرم مجبور به tracking دستی «چقدر به هر شرکت بدهکارم»

**Mitigation:** پیاده‌سازی Settlement Batch Engine (R41-R44).

---

### RISK-03: عدم وجود مدل Escrow صریح

**شدت:** HIGH
**وضعیت:** پول مشتری به حساب پلتفرم واریز می‌شود اما **هیچ مدل صریحی** ownership lifecycle و escrow status track نمی‌کند.

**Impact:**
- از نظر حسابداری، موجودی حساب پلتفرم = مجموع escrow + commission خود پلتفرم — قابل تفکیک نیست
- گزارش‌گیری «چقدر escrow داریم» غیرممکن
- Risk حقوقی: اثبات اینکه funds مربوط به شرکت‌ها هستند

**Mitigation:** مدل EscrowRecord per payment/invoice.

---

## ریسک‌های مهم (High)

### RISK-04: Race Condition در balance_after (Documented)

**شدت:** MEDIUM (documented in ADR-008)
**وضعیت:** `_write_entry()` از `select_for_update()[:1]` استفاده می‌کند. اما اگر ledger خالی باشد، lock نمی‌شود.

**Impact:**
- First ledger entry for a new technician: potential incorrect balance_after
- `get_balance()` (SUM) همیشه صحیح است — balance_after فقط cache/display

**Mitigation:** Financial Account Lock Layer (deferred per ADR-008).

---

### RISK-05: عدم وجود Audit Log مستقل

**شدت:** MEDIUM
**وضعیت:** Ledger entries خودشان audit trail هستند. اما تغییرات policy، activation status، و configuration فاقد audit log هستند.

**Impact:**
- «چه کسی platform_fee_percent را تغییر داد؟» → قابل ردیابی نیست
- «چه کسی payment mode را suspend کرد؟» → قابل ردیابی نیست

**Mitigation:** Django audit trail (django-auditlog یا custom).

---

### RISK-06: FinancialBackfillTask بدون Alerting

**شدت:** MEDIUM
**وضعیت:** تسک‌های PENDING بدون automatic escalation تجمیع می‌شوند (documented in ADR-008).

**Impact:**
- اگر management command اجرا نشود، پول در limbo می‌ماند
- بدون notification به platform owner

**Mitigation:** Monitoring + alerting before scale (per ADR-008 recommendation).

---

### RISK-07: عدم وجود Card-to-Card Channel

**شدت:** MEDIUM
**وضعیت:** R40 می‌گوید «کارت به کارت باید channel مستقل باشد» — فعلاً فقط "cash" یا "manual" metadata.

**Impact:**
- گزارش‌گیری دقیق «چقدر کارت به کارت» ممکن نیست
- خلط با نقدی در آمار

**Mitigation:** اضافه کردن payment channel مجزا (model level).

---

## ریسک‌های متوسط (Medium)

### RISK-08: عدم وجود Customer Financial Party

**شدت:** MEDIUM (آینده)
**وضعیت:** مشتری فقط invoices و payments دارد. هیچ wallet، credit balance، یا debtor/creditor model ندارد.

**Impact:** R46 (customer adjustments) غیرممکن بدون این مدل.

---

### RISK-09: Single-Entry Ledger

**شدت:** LOW (per ADR-004 — intentional for V1)
**وضعیت:** «Single-entry with double-entry discipline.» Balance ≠ stored value — SUM recomputation required.

**Impact:**
- در مقیاس بالا، SUM queries ممکن است کند شوند
- Reconciliation دستی‌تر از true double-entry

**Mitigation:** Materialized balance views یا periodic reconciliation (ADR-004 direction).

---

### RISK-10: عدم پشتیبانی از Partial Payment

**شدت:** LOW
**وضعیت:** `payment.amount != invoice.total_amount` → ValueError. مشتری باید exactly total بپردازد.

**Impact:** R47 رعایت شده (مشتری نمی‌تواند کمتر بپردازد). اما partial payment یا installments غیرممکن.

---

## خلاصه ریسک‌ها

| Severity | Count |
|---|---|
| CRITICAL | 1 |
| HIGH | 2 |
| MEDIUM | 7 |
| LOW | 2 |
| **Total** | **12** |
