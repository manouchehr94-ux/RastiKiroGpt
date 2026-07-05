# 03 — تحلیل مدل‌های مالی (Financial Model Analysis)

**تاریخ ممیزی:** 2026-07-05

---

## 1. Invoice (`apps/invoices/models.py`)

### Purpose
سند مالی رسمی صادره برای مشتری. واحد اصلی تسویه مالی.

### Relationships
- `order` → Order (FK, nullable — standalone invoices ممکن)
- `customer` → Customer (FK, nullable)
- `created_by` → User (FK)
- `items` ← InvoiceItem (reverse FK)
- `payments` ← Payment (reverse FK)
- `ledger_entries` ← TechnicianLedgerEntry (reverse FK)
- `platform_fee_entries` ← CompanyPlatformFeeEntry (reverse FK)
- `split_snapshots` ← PaymentSplitSnapshot (reverse FK)
- `backfill_tasks` ← FinancialBackfillTask (reverse FK)
- `cancellation_requests` ← InvoiceCancellationRequest (reverse FK)

### Lifecycle
DRAFT → ISSUED → PAID / CANCELLED

### Ownership
Organization (Company) — فاکتور به نام شرکت صادر می‌شود.

### Dependencies
- `InvoiceCounter` برای شماره‌گذاری اتمیک
- `CompanyFinancialPolicy` برای محاسبه settlement
- `services_wage` برای محاسبه سهم تکنسین

### Extension Points
- فیلدهای `settled_*` قابل افزایش بدون تغییر ساختار
- `InvoiceItem.RowType` قابل گسترش (choices)

---

## 2. InvoiceItem (`apps/invoices/models.py`)

### Purpose
یک ردیف از فاکتور. شامل نوع خدمت/کالا/ایاب‌وذهاب.

### Relationships
- `invoice` → Invoice (FK, CASCADE)

### RowType Choices
- `service` — اجرت خدمات
- `goods` — کالا / قطعه
- `travel` — ایاب و ذهاب

### Lifecycle
ایجاد با فاکتور → حذف و بازسازی هنگام ویرایش (bulk replace) → freeze هنگام PAID

### Ownership
Organization (via Invoice.company)

### Properties
- `gross_price` = quantity × unit_price
- `net_price` = gross_price - discount_amount

---

## 3. Payment (`apps/payments/models.py`)

### Purpose
رکورد تراکنش پرداخت. اثبات حرکت فیزیکی پول.

### Relationships
- `invoice` → Invoice (FK, nullable)
- `gateway` → PaymentGateway (FK, nullable)
- `attempts` ← PaymentAttempt (reverse FK)
- `split_snapshot` ← PaymentSplitSnapshot (OneToOne reverse)
- `ledger_entries` ← TechnicianLedgerEntry (reverse FK)
- `platform_fee_entries` ← CompanyPlatformFeeEntry (reverse FK)
- `backfill_tasks` ← FinancialBackfillTask (reverse FK)

### Lifecycle
INITIATED → PENDING → PAID / FAILED / NEEDS_RECONCILIATION / CANCELLED

### Ownership
Organization (Company)

---

## 4. PaymentGateway (`apps/payments/models.py`)

### Purpose
پیکربندی درگاه پرداخت هر شرکت.

### Key Fields
- `owner_type`: company / platform — تعیین‌کننده اعمال کارمزد پلتفرم
- `gateway_type`: zarinpal, idpay, nextpay, fake, manual
- `is_default`, `is_active`

### Constraints
- UNIQUE (company, gateway_type)

---

## 5. TechnicianLedgerEntry (`apps/payouts/models.py`)

### Purpose
دفترکل تغییرناپذیر تکنسین. تمام حقوق و تسویه‌های مالی.

### Relationships
- `technician` → Technician (FK, PROTECT)
- `invoice` → Invoice (FK, nullable)
- `payment` → Payment (FK, nullable)
- `order` → Order (FK, nullable)
- `created_by` → CompanyUser (FK, nullable)

### EntryType
- `credit` — بستانکار (شرکت بدهکار تکنسین)
- `debit` — بدهکار (تکنسین بدهکار شرکت / تسویه شده)

### Source Choices
- `online_gateway` — پرداخت آنلاین
- `cash_from_customer` — نقدی از مشتری
- `manual_payment` — پرداخت دستی
- `manual_settlement` — تسویه دستی
- `direct_gateway_settlement` — تسویه مستقیم شاپرک
- `adjustment` — تعدیل
- `refund` — بازگشت وجه
- `technician_service_wage` — اجرت خدمت

### Immutability
- `delete()` → PermissionError
- `save()` → بررسی عدم تغییر amount_rial و balance_after

### Key Fields
- `amount_rial` — مبلغ (همیشه مثبت)
- `balance_after` — مانده بعد از این entry
- `idempotency_key` — UNIQUE، جلوگیری از تکرار
- `metadata` — JSONField با اطلاعات snapshot

---

## 6. CompanyPlatformFeeEntry (`apps/payouts/models.py`)

### Purpose
دفترکل کارمزد پلتفرم برای هر شرکت.

### EntryType
- `debit` — شرکت بدهکار پلتفرم (کارمزد تعلق گرفت)
- `credit` — تسویه شده (شرکت پرداخت کرد)

### Source Choices
- `cash_invoice`, `online_gateway`, `manual_adjustment`, `platform_fee_settlement`, `refund`

### Immutability
همان الگوی TechnicianLedgerEntry

---

## 7. PaymentSplitSnapshot (`apps/payouts/models.py`)

### Purpose
رکورد تغییرناپذیر تصمیم تسهیم پرداخت. مرجع مبلغ تسویه مستقیم.

### Relationships
- `payment` → Payment (OneToOne)
- `invoice` → Invoice (FK, nullable)

### Key Fields
- `total_amount`, `platform_fee_amount`, `company_deposit_amount`
- `technician_direct_amount`, `technician_ledger_amount`
- `should_split_with_technician` — آیا شاپرک مستقیماً به تکنسین واریز کرد؟
- `payout_strategy_snapshot`, `technician_verified_snapshot`, `platform_fee_percent_snapshot`

---

## 8. FinancialBackfillTask (`apps/payouts/models.py`)

### Purpose
ردیابی نوشتارهای مالی ناموفق که باید retry شوند.

### TaskType
- `technician_ledger`, `platform_fee`, `payment_split_snapshot`, `direct_gateway_settlement`

### Status
PENDING → PROCESSING → RESOLVED / FAILED

### Deduplication
حداکثر یک task فعال (PENDING/PROCESSING) به ازای (company, task_type, invoice)

---

## 9. TechnicianServiceRate (`apps/payouts/models.py`)

### Purpose
نرخ ثابت ریالی اجرت تکنسین به ازای هر واحد آیتم سفارش.

### Constraints
- UNIQUE (company, technician, item_definition)
- فقط آیتم‌های `kind=NUMBER`

### Lifecycle
ایجاد → فعال/غیرفعال → خوانده شده در لحظه order completion → snapshot در metadata

---

## 10. CompanyFinancialPolicy (`apps/tenants/models.py`)

### Purpose
سیاست مالی هر شرکت: تقسیم تخفیف، استراتژی پرداخت، کارمزد پلتفرم.

### Key Fields
- `campaign_discount_policy` — COMPANY / TECHNICIAN / HALF_HALF / PROPORTIONAL_SHARE
- `extra_discount_policy` — همان choices
- `payout_strategy` — DIRECT_TO_COMPANY / SPLIT_WITH_TECHNICIAN
- `platform_fee_percent` — درصد کارمزد پلتفرم

### Ownership
OneToOne with Company — فقط پلتفرم owner مجاز به تغییر platform_fee_percent

---

## 11. CompanyPaymentSettings (`apps/tenants/models.py`)

### Purpose
حالت پرداخت و وضعیت فعال‌سازی آنلاین هر شرکت.

### Key Fields
- `payment_mode`: disabled / company_gateway / platform_gateway
- `gateway_activation_status`: inactive / pending_review / active / suspended
- `is_online_payment_enabled` — computed on save

### Ownership
فقط Platform Owner مجاز به تغییر

---

## 12. CompanyMerchantProfile (`apps/tenants/models.py`)

### Purpose
اطلاعات KYC و بانکی شرکت — الزامی قبل از فعال‌سازی درگاه واقعی.

### Key Fields
- `status`: not_submitted / submitted / under_review / approved / rejected / change_requested
- `shaba_number` — شماره شبا شرکت
- `bank_name`, `account_holder_name`, `bank_card_number`
- مدارک هویتی (national_card_image، business_license_image)

### Lifecycle
NOT_SUBMITTED → SUBMITTED → UNDER_REVIEW → APPROVED / REJECTED

---

## 13. DiscountCode (`apps/reports/models.py`)

### Purpose
کد تخفیف یک‌بار مصرف اختصاص‌یافته به مشتری.

### Key Fields
- `code_hash` — hash کد (نه plaintext)
- `percent`, `max_discount_rial`, `expires_at`
- `used_invoice_id`, `used_discount_amount_rial`, `used_at`
- `status`: created / sms_queued / used / expired / cancelled

### Relationship to Invoice
- `used_invoice_id` → PositiveIntegerField (نه FK — audit stability)
- مورد استفاده در `_resolve_discount_code_id()` هنگام mark_paid
