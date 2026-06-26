# Terminology — Official Names and Forbidden Names

**Version:** RDOS v1.0 Stable

Use these names consistently in code, tests, docs, UI labels, and prompts.

---

## Core Business Terms

### Order

- Persian: سفارش
- Canonical code name: `Order`
- API/path suggestion: `orders`
- Do not use: `Job`, `Ticket`, `WorkOrder`, `Task`
- Reason: Order is the core operational object in Rasti Service.

### Service Request

- Persian: درخواست خدمت
- Use when referring to initial public/customer request before operator approval.
- Do not confuse with `Order` after approval.

### Invoice

- Persian: فاکتور
- Canonical code name: `Invoice`
- Do not use: `Bill`, `Receipt`, `Factor`
- Reason: Invoice is the issued financial document for a tenant-company service.

### Payment

- Persian: پرداخت
- Canonical code name: `Payment`
- Use for online/recorded payment state and gateway verification.
- Do not use for invoice itself.

### Payment Attempt

- Persian: تلاش پرداخت
- Canonical code name: `PaymentAttempt`
- Use for provider initiation, callback, verify, retry, or failure records.

---

## Company and User Terms

### Tenant Company

- Persian: شرکت مستأجر / شرکت عضو پلتفرم
- Canonical code name: `Company`
- Do not use: `Merchant` as a replacement for company.
- Reason: Merchant profile is KYC/payment-specific; Company is the tenant entity.

### Customer

- Persian: مشتری
- Canonical code name: `Customer`
- The customer buys service from the tenant company, not from Rasti Service.

### Technician

- Persian: تکنسین / نیروی خدماتی
- Canonical code name: `Technician`
- One active technician per order unless a future ADR changes this.

### Platform Owner

- Persian: مالک پلتفرم / مدیر راستی سرویس
- Canonical concept: platform-level superuser/owner.
- Only this role can activate payment mode and approve certain KYC/payment operations.

---

## Payment Architecture Terms

### CompanyPaymentSettings

- Persian: تنظیمات پرداخت شرکت
- Canonical code name: `CompanyPaymentSettings`
- Purpose: Source of truth for payment activation and payment mode.
- Owns: `payment_mode`, activation audit fields, deactivation reason, activation status.
- Do not place payment mode on `CompanyFinancialPolicy`.

### payment_mode

- Persian: حالت پرداخت آنلاین
- Canonical field name: `payment_mode` or `online_payment_mode` only if existing code already uses it and an ADR permits it.
- Preferred for new model: `payment_mode`.
- Values: `disabled`, `company_gateway`, `platform_gateway`.
- Lives on: `CompanyPaymentSettings`.
- Do not treat it as a financial split policy.

### CompanyFinancialPolicy

- Persian: سیاست مالی شرکت
- Canonical code name: `CompanyFinancialPolicy`
- Purpose: Financial policies only.
- Owns: payout strategy, platform fee percent, discount absorption policy, wage/split policy.
- Does not own: payment activation, gateway activation, PSP credentials.

### PaymentGateway

- Persian: درگاه پرداخت
- Canonical code name: `PaymentGateway`
- Target canonical gateway model.
- Must include owner identity: `owner_type = company | platform`.

### owner_type

- Persian: نوع مالک درگاه
- Canonical field name: `owner_type`
- Values: `company`, `platform`.
- Do not use: `ownership`, `gateway_owner`, `gateway_type_owner` unless legacy code already has it.

### Platform Commission / Platform Fee

- Persian: کارمزد پلتفرم / کمیسیون راستی سرویس
- Canonical code name: `CompanyPlatformFeeEntry` for ledger entries.
- Created only under the full platform commission rule.

---

## Status Names

### Payment Status

Use canonical enum names:

- `INITIATED`
- `PENDING`
- `PAID`
- `FAILED`
- `CANCELLED`
- `NEEDS_RECONCILIATION`

Do not use: `UNKNOWN`, `UNCLEAR`, `WAITING_BANK` unless a future ADR adds them.

### Order Status Persian Labels

Use the approved Persian labels from `docs/03_Business/ORDER_RULES.md`.

---

## Naming Rules

- Use English for code identifiers.
- Use Persian for user-visible labels where the existing UI is Persian.
- Do not invent synonyms if a canonical term exists.
- If a new term is needed, add it here and reference the ADR or business rule that introduced it.
