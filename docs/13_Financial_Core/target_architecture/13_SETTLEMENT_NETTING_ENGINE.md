# 13 — موتور تسویه و Net Settlement (Settlement & Netting Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R41–R45, Section 3.6

---

## اصل: دو لایه تسویه مستقل (P07)

### Layer 1: Platform ↔ Organization
- پیکربندی: Platform Owner
- واحد: فاکتور (R45)
- هدف: انتقال سهم شرکت + تسویه بدهی کارمزد

### Layer 2: Organization ↔ Provider
- پیکربندی: Organization Admin
- واحد: فاکتور (R45)
- هدف: پرداخت سهم تکنسین

---

## Net Position Settlement (Section 3.6)

تسویه per-invoice انجام نمی‌شود. در عوض:

```
Net Position = SUM(all receivables) - SUM(all payables) in a period
```

### مثال Layer 1:

```
دوره: هفته اول تیر ماه
شرکت الف:
  - فاکتور 1: total=10M, commission=500K → platform owes 9.5M
  - فاکتور 2: total=8M, commission=400K → platform owes 7.6M
  - فاکتور 3: total=5M, commission=250K → platform owes 4.75M

Net Position: platform owes company الف = 21.85M
Settlement: ONE bank transfer of 21.85M (not 3 separate)
```

**مزایا:**
- کاهش تعداد تراکنش‌های بانکی
- کاهش هزینه
- Automatic netting

---

## مدل‌های Target

### OrganizationSettlementConfig (جدید)

```python
class OrganizationSettlementConfig(CompanyOwnedModel):
    class Frequency(TextChoices):
        IMMEDIATE = "immediate"     # بلافاصله
        DAILY = "daily"             # روزانه
        TWO_DAY = "two_day"         # هر ۲ روز
        WEEKLY = "weekly"           # هفتگی
        MANUAL = "manual"           # دستی

    frequency = CharField(choices=Frequency, default=Frequency.MANUAL)
    delay_hours = PositiveIntegerField(default=0)
    minimum_amount_rial = PositiveBigIntegerField(default=0)
    auto_approve = BooleanField(default=True)  # R44
```

### SettlementBatch (جدید)

```python
class SettlementBatch(CompanyOwnedModel):
    class Level(TextChoices):
        PLATFORM_TO_ORG = "platform_to_org"
        ORG_TO_PROVIDER = "org_to_provider"

    class Status(TextChoices):
        CALCULATING = "calculating"
        READY = "ready"
        EXECUTING = "executing"
        COMPLETED = "completed"
        FAILED = "failed"

    level = CharField(choices=Level)
    status = CharField(choices=Status)
    period_start = DateTimeField()
    period_end = DateTimeField()
    net_amount_rial = BigIntegerField()
    items_count = PositiveIntegerField(default=0)
    executed_at = DateTimeField(null=True)
    bank_reference = CharField(max_length=200, blank=True)
    failure_reason = TextField(blank=True)
    created_by = ForeignKey(CompanyUser, null=True)
```

### SettlementItem (جدید)

```python
class SettlementItem(CompanyOwnedModel):
    batch = ForeignKey(SettlementBatch, related_name="items")
    invoice = ForeignKey(Invoice)
    ledger_entry = ForeignKey(TechnicianLedgerEntry, null=True)  # Layer 2
    platform_fee_entry = ForeignKey(CompanyPlatformFeeEntry, null=True)  # Layer 1
    amount_rial = BigIntegerField()
```

---

## Automation (R43, R44)

```
management command: process_settlements

1. For each company with auto settlement config:
   a. Calculate net position for current period
   b. Create SettlementBatch(status=CALCULATING)
   c. Aggregate invoices into SettlementItems
   d. If auto_approve (R44): status → READY → EXECUTING
   e. Execute bank transfer (future integration)
   f. status → COMPLETED
   g. Create CREDIT entry in CompanyPlatformFeeEntry (Layer 1)
      OR DEBIT entry in TechnicianLedgerEntry (Layer 2)
```

---

## Layer 2: Organization ↔ Provider

**Current (موجود):** `record_manual_settlement()` — admin ثبت دستی

**Target extension:**
- `TechnicianSettlementConfig` per company (frequency configurable by Org — R42)
- Batch settlement: aggregate technician balance → create batch → mark settled
- حفظ manual settlement existing (backward-compatible)

---

## Cash Settlement (R39)

تسویه نقدی بین شرکت و تکنسین:
- مستقیماً توسط شرکت (نقد/بانک/کارت‌به‌کارت)
- پلتفرم فقط ثبت و track می‌کند
- `record_manual_settlement(direction=COMPANY_PAID_TECHNICIAN)` → existing

---

## وضعیت فعلی

| Component | Status |
|---|---|
| Layer 2 manual settlement | ✅ `record_manual_settlement()` |
| Layer 2 direct Shaparak | ✅ `TechnicianDirectSettlementService` |
| Layer 1 platform fee tracking | ✅ `CompanyPlatformFeeEntry` |
| Layer 1 batch settlement | ❌ Missing — target |
| Settlement timing config (R41) | ❌ Missing — target |
| Automated processing (R43) | ❌ Missing — target |
| Net position calculation | ❌ Missing — target |
