# 02 — تحلیل گردش‌کار مالی (Financial Workflow Analysis)

**تاریخ ممیزی:** 2026-07-05

---

## 1. Invoice Lifecycle

### Trigger
- تکنسین: سفارش به وضعیت DONE می‌رسد → تکنسین فاکتور ایجاد می‌کند
- ادمین: از پنل ادمین فاکتور ایجاد می‌کند

### State Transitions
```
DRAFT → ISSUED → PAID
DRAFT → CANCELLED
ISSUED → CANCELLED (via CancellationRequest)
```

### Validation
- فقط سفارش‌های DONE قابل فاکتور هستند
- فقط یک فاکتور فعال (DRAFT یا ISSUED) در هر لحظه برای هر سفارش
- مبلغ فاکتور باید بزرگتر از صفر باشد برای صدور
- فاکتور PAID قابل تغییر نیست

### Permissions
- COMPANY_ADMIN، COMPANY_STAFF: ایجاد، ویرایش، صدور، لغو
- TECHNICIAN: ایجاد فاکتور برای سفارش‌های خودش، درخواست لغو

### Notifications
- `INVOICE_CREATED` → اطلاع به admin (in-app)
- `INVOICE_ISSUED_CUSTOMER` → اطلاع به مشتری (SMS + in-app)
- `INVOICE_PAID_CUSTOMER` → اطلاع به مشتری (SMS + in-app)
- `INVOICE_CANCELLED` → اطلاع به مشتری (in-app)

### Financial Impact
- ISSUED: هیچ تأثیر مالی ندارد (فقط wage percentages فریز می‌شوند)
- PAID: Settlement freeze + TechnicianLedgerEntry CREDIT + CompanyPlatformFeeEntry (شرایط خاص) + PaymentSplitSnapshot

---

## 2. Payment Lifecycle (Online)

### Trigger
- مشتری دکمه «پرداخت» را در صفحه فاکتور کلیک می‌کند

### State Transitions
```
INITIATED → PENDING → PAID
INITIATED → PENDING → FAILED
INITIATED → PENDING → NEEDS_RECONCILIATION
INITIATED → CANCELLED
```

### Validation
- فاکتور باید ISSUED باشد
- CompanyPaymentSettings.payment_mode ≠ disabled
- CompanyPaymentSettings.gateway_activation_status == active
- KYC eligibility check (CompanyMerchantProfile)
- مبلغ verify شده باید با مبلغ Payment مطابقت داشته باشد
- Payment نباید expired باشد (30 دقیقه timeout)

### Permissions
- مشتری: شروع پرداخت (public URL)
- پلتفرم: مدیریت NEEDS_RECONCILIATION

### Notifications
- `PAYMENT_STARTED` → admin (in-app)
- `PAYMENT_SUCCESS_CUSTOMER` → مشتری (SMS + in-app)
- `PAYMENT_SUCCESS_ADMIN` → admin (in-app)
- `PAYMENT_SUCCESS_OPERATOR` → اپراتور (in-app)
- `PAYMENT_FAILED_CUSTOMER` → مشتری (SMS + in-app)

### Financial Impact
- PAID: Invoice → PAID، Settlement freeze، Technician CREDIT، Platform Fee DEBIT (if applicable)، PaymentSplitSnapshot، Direct Gateway Settlement DEBIT (if split)

---

## 3. Manual/Cash Payment Lifecycle

### Trigger
- ادمین شرکت پرداخت نقدی/دستی ثبت می‌کند

### State Transitions
- Invoice: ISSUED → PAID (بدون PSP)

### Validation
- فاکتور باید ISSUED باشد

### Financial Impact
- Invoice settlement freeze
- TechnicianLedgerEntry CREDIT (source: cash_from_customer یا manual_payment)
- اگر تکنسین نقدی دریافت کرده: DEBIT cash_from_customer (کل مبلغ فاکتور)
- هیچ Platform Commission ایجاد نمی‌شود

---

## 4. Technician Wage Posting (Order Completion)

### Trigger
- `OrderCompleteService.complete()` — سفارش به DONE تغییر وضعیت می‌دهد

### State Transitions
- یک CREDIT entry در TechnicianLedgerEntry ایجاد می‌شود

### Validation
- سفارش باید technician داشته باشد
- آیتم‌های سفارش با `kind=NUMBER` و `is_technician_wage_applicable=True`
- برای هر آیتم، `TechnicianServiceRate` فعال باید موجود باشد (اختیاری — missing rate فقط warning)

### Financial Impact
- یک CREDIT entry با source=`technician_service_wage`
- Amount = sum(quantity × fixed_wage_rial)
- مستقل از رفتار پرداخت مشتری

---

## 5. Platform Commission Lifecycle

### Trigger
- `InvoiceMarkPaidService.mark_paid()` — فقط برای پرداخت‌های online از gateway پلتفرم

### Conditions (ALL required)
1. `CompanyPaymentSettings.payment_mode == "platform_gateway"`
2. `Payment.status == "paid"`
3. `PaymentGateway.owner_type == "platform"`
4. `CompanyFinancialPolicy.platform_fee_percent > 0`

### Financial Impact
- یک DEBIT entry در `CompanyPlatformFeeEntry`
- Amount = invoice.total_amount × platform_fee_percent / 100

---

## 6. Direct Shaparak Settlement

### Trigger
- `PaymentVerifyService.verify()` — بعد از PAID شدن payment

### Conditions
- `PaymentSplitSnapshot.should_split_with_technician == True`
- `snapshot.technician_direct_amount > 0`
- `gateway.owner_type == PLATFORM`
- technician verified + has sub_merchant_id

### Financial Impact
- یک DEBIT entry با source=`direct_gateway_settlement`
- Amount = `PaymentSplitSnapshot.technician_direct_amount`

---

## 7. Manual Technician Settlement

### Trigger
- ادمین شرکت از صفحه `technician_settlement` تسویه ثبت می‌کند

### Directions
- COMPANY_PAID_TECHNICIAN → DEBIT (balance کاهش)
- TECHNICIAN_PAID_COMPANY → CREDIT (balance افزایش)
- ADJUSTMENT_CREDIT / ADJUSTMENT_DEBIT

### Financial Impact
- یک entry جدید در TechnicianLedgerEntry
- Idempotency via form token

---

## 8. Invoice Cancellation Flow

### Trigger
- تکنسین درخواست لغو می‌دهد (InvoiceCancellationRequestService.request)
- ادمین تأیید یا رد می‌کند

### State Transitions
```
CancellationRequest: PENDING → APPROVED / REJECTED
Invoice (on approve): DRAFT/ISSUED → CANCELLED
```

### Validation
- فقط DRAFT یا ISSUED (نه PAID)
- فقط یک درخواست PENDING در هر لحظه
- اگر فاکتور در فاصله PAID شود، approve رد می‌شود

### Financial Impact
- هیچ اثر مالی مستقیم ندارد (فاکتور PAID نشده بود)
- اما اگر آیتم‌های order-completion wage قبلاً post شده باشند، آن entries باقی می‌مانند (مستقل از invoice)

---

## 9. Financial Recovery Flow

### Trigger
- شکست هر یک از نوشتارهای مالی در events 5-8 (ADR-007)

### State Transitions
```
FinancialBackfillTask: PENDING → PROCESSING → RESOLVED
FinancialBackfillTask: PENDING → PROCESSING → (rollback) → PENDING (attempts++)
```

### Processing
- `process_financial_backfill` management command
- هر task در transaction جداگانه
- Cascade recovery: direct_gateway_settlement می‌تواند split snapshot را هم بسازد

---

## 10. Discount Code Application Flow

### Trigger
- مشتری کد تخفیف وارد می‌کند هنگام پرداخت

### Financial Impact
- `campaign_discount_amount` روی Invoice ثبت می‌شود
- در Settlement، مطابق policy تخفیف بین تکنسین و شرکت تقسیم می‌شود
- `settled_discount_code_id` فریز می‌شود
