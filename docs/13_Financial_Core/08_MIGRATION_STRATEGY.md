# 08 — استراتژی مهاجرت (Migration Strategy)

**تاریخ ممیزی:** 2026-07-05

---

## اصول حاکم

1. **هیچ refactoring مخرب انجام نشود** — مدل‌ها و سرویس‌های موجود حفظ شوند
2. **هیچ migration غیرضروری ایجاد نشود** — فقط migration‌های backward-compatible
3. **سازگاری کامل به عقب** — تمام API‌ها و viewهای موجود بدون تغییر عمل کنند
4. **حداقل ریسک production** — هر phase به صورت مستقل قابل deploy
5. **حداکثر بازاستفاده** — از implementation موجود به عنوان foundation
6. **تکامل تدریجی** — نه بازطراحی

---

## Phase 0: Foundation (بدون تغییر کد production)

| Action | نوع | ریسک |
|---|---|---|
| ایجاد `docs/13_Financial_Core/` (همین ممیزی) | Documentation | صفر |
| ایجاد Target Architecture docs | Documentation | صفر |
| رفع OI-01 تا OI-10 با Product Owner | Decision | صفر |

---

## Phase 1: Missing Pieces — Low Risk Extensions

هدف: پر کردن gap‌های ساده بدون تغییر مدل‌های موجود.

### 1.1 Rounding Discount (R29)
- اضافه کردن فیلد `rounding_discount_enabled` و `max_rounding_discount_rial` به `CompanyFinancialPolicy`
- Migration: nullable fields with defaults → backward-compatible
- تغییر: `InvoiceSettlementService` برای اعمال rounding

### 1.2 Cash Commission Toggle (R10, R38)
- اضافه کردن فیلد `commission_on_cash_enabled` به `CompanyFinancialPolicy`
- Default: False (حفظ رفتار فعلی)
- تغییر: `InvoiceMarkPaidService` — بررسی فیلد جدید برای cash paths

### 1.3 Card-to-Card Channel (R40)
- اضافه کردن choice جدید به `Payment.metadata` schema یا `PaymentGateway.GatewayType`
- Approach: `GatewayType.CARD_TO_CARD = "card_to_card"` + manual gateway
- Migration: Alter field choices → zero-downtime

### 1.4 Audit Log for Policy Changes (R50)
- نصب `django-auditlog` یا custom signal-based logger
- Track: CompanyFinancialPolicy, CompanyPaymentSettings changes
- Migration: new table → no existing data touched

---

## Phase 2: Settlement Engine — Medium Complexity

هدف: پیاده‌سازی automated settlement (R41-R44).

### 2.1 Settlement Configuration Model
```python
class OrganizationSettlementConfig(CompanyOwnedModel):
    settlement_frequency = CharField(choices=["immediate", "daily", "weekly"])
    settlement_delay_hours = PositiveIntegerField(default=0)
```
- Migration: new table → backward-compatible
- Existing manual settlement continues to work

### 2.2 Settlement Batch Model
```python
class SettlementBatch(CompanyOwnedModel):
    period_start / period_end
    net_amount (computed from ledger entries in period)
    status: pending → processing → completed / failed
```

### 2.3 Settlement Execution Service
- Reads `CompanyPlatformFeeEntry` balance → calculates net position
- Creates batch → executes bank transfer (future integration)
- Records credit entry on `CompanyPlatformFeeEntry`

### 2.4 Technician Settlement Automation
- `TechnicianSettlementConfig` per company
- Automated batch settlement based on frequency
- Fallback: existing `record_manual_settlement` unchanged

---

## Phase 3: Escrow & Ownership Tracking — High Value

هدف: مدل صریح مالکیت پول (R01, Section 3.2).

### 3.1 EscrowRecord Model
```python
class EscrowRecord(CompanyOwnedModel):
    payment = FK(Payment)
    invoice = FK(Invoice)
    status: held → reserved → released → settled
    amount_rial
    released_at
```
- ایجاد by PaymentVerifyService after PAID
- Transition by SettlementBatch

### 3.2 Money Ownership State Machine
- Event-driven transitions
- All existing services continue to work
- EscrowRecord is **additive** — does not replace existing Payment/Invoice status

---

## Phase 4: Refund Engine

هدف: مکانیزم بازپرداخت (R46, OI-05, OI-06, OI-07).

### 4.1 RefundRequest Model
### 4.2 RefundService (orchestrates ledger reversals)
### 4.3 Customer Credit/Debit Model
- **باید بعد از resolve شدن OI-05, OI-06, OI-07 پیاده‌سازی شود**

---

## Phase 5: Reporting & KPI

هدف: گزارش‌های مالی جامع (R53-R56).

### 5.1 Provider Liability Report (R53)
- Query: TechnicianLedgerEntry WHERE balance < 0 per company
- View: existing admin panel extension

### 5.2 Platform Commission Report (R54)
- Query: CompanyPlatformFeeEntry aggregation
- View: platform_owner panel

### 5.3 Settlement Status Report (R55)
- Depends on Phase 2 (Settlement Batch model)

### 5.4 KPI Dashboard (R56)
- **باید بعد از resolve شدن OI-09 پیاده‌سازی شود**

---

## ماتریس وابستگی Phase‌ها

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3
                │                      │
                └──→ Phase 5.1/5.2     └──→ Phase 4 (requires OI resolution)
                                             │
                                             └──→ Phase 5.3/5.4
```

---

## قوانین مهاجرت Database

| Phase | Migration Type | Risk |
|---|---|---|
| 1 | ADD COLUMN (nullable/default) | Zero-downtime |
| 2 | CREATE TABLE | Zero-downtime |
| 3 | CREATE TABLE | Zero-downtime |
| 4 | CREATE TABLE | Zero-downtime |
| 5 | No schema change (queries only) | Zero-risk |

**هیچ ALTER COLUMN، DROP TABLE، یا data migration مخرب در هیچ فاز وجود ندارد.**
