# 09 — توصیه‌های معماری (Architectural Recommendations)

**تاریخ ممیزی:** 2026-07-05

---

## Priority 1 — Critical (Before Production Scale)

### REC-01: Refund Engine Design
**ریسک مرتبط:** RISK-01
**Rule Coverage:** R46, OI-05, OI-06, OI-07

**توصیه:**
- طراحی `RefundRequest` model با lifecycle: requested → approved → executed → settled
- سرویس `RefundExecutionService` که orchestrate می‌کند:
  - TechnicianLedgerEntry ADJUSTMENT (reverse wage)
  - CompanyPlatformFeeEntry CREDIT (reverse fee)
  - EscrowRecord status change
  - Payment gateway refund API call
- مکانیزم partial refund vs full refund
- **نیازمند resolve شدن OI-07 قبل از پیاده‌سازی**

### REC-02: Settlement Batch Engine
**ریسک مرتبط:** RISK-02
**Rule Coverage:** R41-R44

**توصیه:**
- مدل `SettlementBatch` + `SettlementItem`
- Configurable frequency per Organization (R41)
- Net Position calculation: aggregate platform_fee debits - credits per period
- Automatic execution via Celery/cron
- Admin override for manual trigger
- حفظ `record_manual_settlement` existing برای technician level (R42)

---

## Priority 2 — High (Before 10+ Tenants)

### REC-03: Explicit Escrow Model
**ریسک مرتبط:** RISK-03
**Rule Coverage:** R01, P05, Section 3.2, 3.5

**توصیه:**
- `EscrowRecord` additive model — per payment
- Track ownership states: held → reserved → eligible → distributed → settled
- Dashboard for Platform Owner: «total escrow balance across all organizations»
- Does NOT replace Payment/Invoice status — parallel tracking

### REC-04: Cash Commission Configuration
**ریسک مرتبط:** R10, R38 partial
**Rule Coverage:** R10, R38

**توصیه:**
- اضافه فیلد `charge_commission_on_cash` (BooleanField, default=False) به `CompanyFinancialPolicy`
- تغییر condition در `InvoiceMarkPaidService`:
  - اگر True: call `PlatformFeeService.record_invoice_fee()` حتی بدون online payment
  - Source: `CompanyPlatformFeeEntry.Source.CASH_INVOICE`
- **تغییر حداقلی — یک migration + یک condition**

### REC-05: Financial Alerting
**ریسک مرتبط:** RISK-06
**Rule Coverage:** ADR-008 recommended

**توصیه:**
- Notification event: `FINANCIAL_BACKFILL_STUCK` (attempts > 5)
- Platform Owner in-app notification
- Optional webhook/email integration
- Monitoring dashboard: pending tasks count

---

## Priority 3 — Medium

### REC-06: Card-to-Card Payment Channel
**Rule Coverage:** R40

**توصیه:**
- Choice جدید: `PaymentGateway.GatewayType.CARD_TO_CARD`
- Manual recording (مانند cash) اما با category مجزا
- Report separation: cash vs card-to-card vs online

### REC-07: Rounding Discount
**Rule Coverage:** R29

**توصیه:**
- فیلد `rounding_discount_amount` روی Invoice (max from policy)
- Validation: amount ≤ `CompanyFinancialPolicy.max_rounding_discount_rial`
- اعمال قبل از final total_amount calculation
- UI: checkbox «اعمال تخفیف رُند» در فرم فاکتور

### REC-08: Policy Change Audit Log
**Rule Coverage:** R50

**توصیه:**
- `django-auditlog` or custom middleware
- Track: CompanyFinancialPolicy, CompanyPaymentSettings, CompanyMerchantProfile changes
- Fields: who, when, old_value, new_value
- View: Platform Owner → audit trail page

### REC-09: Additional Invoice Line Types
**Rule Coverage:** R23

**توصیه:**
- اضافه کردن choices:
  - `ADDITIONAL_DISCOUNT = "additional_discount"` — تخفیف مازاد (ردیف منفی)
  - `LOYALTY_DISCOUNT = "loyalty_discount"` — تخفیف وفاداری
- Backward-compatible: existing service/goods/travel unchanged
- Wage calculation: discount types excluded from technician share

---

## Priority 4 — Future (After OI Resolution)

### REC-10: Customer Financial Party (OI-05, OI-06)
- مدل `CustomerFinancialAccount` — wallet/credit balance
- Overpayment → credit balance
- Refund → credit balance or bank return
- **منتظر تصمیم Product Owner**

### REC-11: Reporting KPI Engine (OI-09, OI-10)
- Aggregate views/materialized views
- Dashboard components
- **منتظر تعریف KPI catalog**

### REC-12: Event-Driven Architecture Extension
**Rule Coverage:** P10

**توصیه:**
- Django signals → domain events
- Future: message broker (Celery tasks or Redis streams)
- Event catalog extension: `escrow_reserved`, `settlement_batch_completed`, `refund_issued`
- Foundation exists in `notifications/event_catalog.py`

---

## Summary: Priority × Effort Matrix

| Recommendation | Priority | Effort | Dependencies |
|---|---|---|---|
| REC-01 Refund Engine | P1 | HIGH | OI-07 |
| REC-02 Settlement Batch | P1 | HIGH | None |
| REC-03 Escrow Model | P2 | MEDIUM | None |
| REC-04 Cash Commission | P2 | LOW | None |
| REC-05 Financial Alerting | P2 | LOW | None |
| REC-06 Card-to-Card | P3 | LOW | None |
| REC-07 Rounding Discount | P3 | LOW | None |
| REC-08 Audit Log | P3 | MEDIUM | None |
| REC-09 Line Types | P3 | LOW | None |
| REC-10 Customer Party | P4 | HIGH | OI-05, OI-06 |
| REC-11 KPI Engine | P4 | HIGH | OI-09, OI-10 |
| REC-12 Events Extension | P4 | MEDIUM | None |
