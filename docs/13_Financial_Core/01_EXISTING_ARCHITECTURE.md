# 01 — معماری موجود هسته مالی (Existing Financial Core Architecture)

**تاریخ ممیزی:** 2026-07-05
**نسخه:** v1.0 — Audit Phase

---

## 1. مرز ماژول مالی

هسته مالی RastiSaas از لحظه ایجاد فاکتور (Invoice) تا ثبت تسویه (Settlement) و ایجاد رویدادهای مالی را پوشش می‌دهد. این هسته شامل اپلیکیشن‌های زیر است:

| Application | مسئولیت اصلی |
|---|---|
| `apps/invoices/` | مدل Invoice، InvoiceItem، InvoiceCancellationRequest — ایجاد، ویرایش، صدور، پرداخت، لغو فاکتور |
| `apps/payments/` | مدل Payment، PaymentGateway، PaymentAttempt — مدیریت تراکنش‌های پرداخت آنلاین |
| `apps/payouts/` | مدل TechnicianLedgerEntry، CompanyPlatformFeeEntry، PaymentSplitSnapshot، FinancialBackfillTask، TechnicianServiceRate — دفترکل تکنسین، کارمزد پلتفرم، تسویه مستقیم |
| `apps/reports/` | DiscountCampaign، DiscountCode — کمپین تخفیف و کد تخفیف |
| `apps/billing/` | BillingRecord — **فقط اشتراک SaaS (stub)** — جزو هسته مالی نیست |
| `apps/tenants/` | CompanyFinancialPolicy، CompanyPaymentSettings، CompanyMerchantProfile — سیاست‌های مالی و تنظیمات پرداخت هر شرکت |
| `apps/accounts/` | Technician (فیلدهای shaba، sub_merchant_id، verification) |
| `apps/notifications/` | event_catalog.py — رویدادهای مالی (INVOICE_PAID، PAYMENT_SUCCESS و غیره) |

---

## 2. لایه‌بندی معماری

پروژه از الگوی **Service Layer** استفاده می‌کند:

```
Views (thin) → Services (business logic) → Models (data + immutability) → Selectors (read)
```

**قوانین معماری:**
- منطق تجاری فقط در `services.py` قرار دارد
- ویوها thin هستند و فقط orchestration انجام می‌دهند
- خواندن داده‌ها از طریق `selectors.py`
- مدل‌ها فقط data integrity و immutability اعمال می‌کنند

---

## 3. الگوهای معماری موجود

### 3.1 Immutable Ledger Pattern
- `TechnicianLedgerEntry.delete()` → PermissionError
- `TechnicianLedgerEntry.save()` → بررسی تغییرناپذیری `amount_rial` و `balance_after`
- `CompanyPlatformFeeEntry` → همان الگو
- اصلاح خطا فقط با ADJUSTMENT entry جدید

### 3.2 Idempotency Key Pattern
- هر ledger entry یک `idempotency_key` یکتا دارد (UNIQUE constraint در DB)
- callback‌های تکراری gateway هیچ‌گاه ردیف تکراری ایجاد نمی‌کنند
- الگوی savepoint برای مدیریت race condition

### 3.3 Platform-First Collection
- تمام پرداخت‌های آنلاین ابتدا به حساب پلتفرم واریز می‌شوند
- تسویه بعداً انجام می‌شود (در حال حاضر فقط تسویه مستقیم Shaparak)

### 3.4 Invoice Settlement Freeze
- در لحظه PAID شدن، تمام فیلدهای `settled_*` روی Invoice فریز می‌شوند
- این snapshot منبع حقیقت برای تمام محاسبات بعدی (ledger entries، platform fee) است

### 3.5 Financial Backfill / Recovery
- `FinancialBackfillTask` برای بازیابی نوشتارهای مالی ناموفق
- چهار نوع task: technician_ledger, platform_fee, payment_split_snapshot, direct_gateway_settlement
- اجرا توسط management command: `process_financial_backfill`

### 3.6 Multi-Tenant Isolation
- تمام مدل‌های مالی از `CompanyOwnedModel` ارث‌بری می‌کنند
- هر کوئری باید `company` scope داشته باشد
- ایزولاسیون در لایه مدل و selector اعمال می‌شود

### 3.7 Snapshot at Decision Time
- `PaymentSplitSnapshot` — تصمیم تسهیم در لحظه verify فریز می‌شود
- Wage percentages روی Invoice در لحظه Issue فریز می‌شوند
- Settlement values در لحظه PAID فریز می‌شوند
- `TechnicianServiceRate` در لحظه order completion در metadata ثبت می‌شود

---

## 4. مستندات موجود

| سند | وضعیت |
|---|---|
| `docs/04_Business_Rules/PAYMENT_RULES.md` | فعال — تأیید‌شده علیه کد |
| `docs/04_Business_Rules/INVOICE_RULES.md` | فعال — تأیید‌شده علیه کد |
| `docs/04_Business_Rules/PAYOUT_RULES.md` | فعال — تأیید‌شده علیه کد |
| `docs/07_ADR/ADR-002-CompanyPaymentSettings.md` | پذیرفته‌شده |
| `docs/07_ADR/ADR-003-Payment-Architecture.md` | پذیرفته‌شده |
| `docs/07_ADR/ADR-004-Ledger-Discipline.md` | پذیرفته‌شده |
| `docs/07_ADR/ADR-005-Technician-Service-Pricing.md` | پذیرفته‌شده |
| `docs/07_ADR/ADR-006-Technician-Ledger-Statement-Architecture.md` | پذیرفته‌شده — جامع |
| `docs/07_ADR/ADR-007-Financial-Event-Timeline.md` | پذیرفته‌شده — جامع |
| `docs/07_ADR/ADR-008-Financial-Recovery-Policy.md` | پذیرفته‌شده — جامع |
| `docs/05_Workflows/INVOICE_PAYMENT_FLOW.md` | فعال |

### مستندات ناموجود (یافته ممیزی)
- سند Escrow Architecture → ناموجود
- سند Settlement Batching/Netting → ناموجود
- سند Refund Architecture → ناموجود
- سند Financial Party / Wallet → ناموجود
- سند Organization↔Platform Settlement → ناموجود
- سند Customer Financial Adjustments → ناموجود
- سند KPI/Reporting Architecture → ناموجود

---

## 5. Stack فنی

| مؤلفه | نسخه |
|---|---|
| Django | 5.1.3 |
| Python | 3.11.9 |
| Database | PostgreSQL |
| UI | Tailwind CSS، templates Django |
| PDF Export | WeasyPrint |
| CSV Export | UTF-8 BOM |
| Multi-tenancy | URL-path based (first segment = company code) |

---

## 6. شمای وابستگی بین ماژول‌ها

```
orders.Order ──→ invoices.Invoice ──→ payments.Payment
                       │                      │
                       ▼                      ▼
              payouts.TechnicianLedgerEntry   payouts.PaymentSplitSnapshot
              payouts.CompanyPlatformFeeEntry payouts.FinancialBackfillTask
                       │
                       ▼
              payouts.TechnicianServiceRate (via Order completion)

tenants.CompanyFinancialPolicy ──→ invoices.services_wage
tenants.CompanyPaymentSettings ──→ payments.services (guards)
tenants.CompanyMerchantProfile ──→ payments.services (KYC eligibility)
accounts.Technician            ──→ payouts (shaba, sub_merchant_id)
reports.DiscountCode           ──→ invoices.services (campaign_discount_amount)
notifications.event_catalog    ──→ invoice/payment status changes (signals)
```
