# Payment Rules

**Version:** RDOS v1.0 Stable

---

## 1. Business Position

Rasti Service is the SaaS provider, not the seller of the service. The customer pays the tenant company. Rasti Service may provide payment infrastructure only under approved payment mode and legal/PSP constraints.

---

## 2. Payment Modes

Payment mode belongs to `CompanyPaymentSettings`.

| Mode | Meaning | Platform commission |
|---|---|---|
| `disabled` | No online payment | Never |
| `company_gateway` | Tenant company uses its own PSP/gateway | Never |
| `platform_gateway` | Rasti Service/facilitator gateway | Possible if all conditions match |

All companies start with payment disabled.

Only platform owner can activate/deactivate payment mode.

---

## 3. Gateway Ownership

The target canonical gateway model is `PaymentGateway`.

Every gateway must identify:

- `owner_type = company`
- `owner_type = platform`

Company-owned gateway payments must never create platform commission.

Legacy gateway models must not receive new payment-flow logic:

- `CompanyPaymentGatewaySetting`
- `PlatformPaymentGatewaySetting`

---

## 4. Platform Commission Rule

Create `CompanyPlatformFeeEntry` only when all conditions are true:

1. Company payment mode is `platform_gateway`.
2. Payment exists and status is verified `PAID`.
3. Payment gateway exists and `owner_type == platform`.
4. `CompanyFinancialPolicy.platform_fee_percent > 0`.

Never create platform commission for:

- cash
- manual admin payment
- card-to-card
- company-owned gateway
- failed payment
- cancelled payment
- `NEEDS_RECONCILIATION`
- discounts
- customer credits

Phase 1 note: before `CompanyPaymentSettings` exists, implement the defensive gateway/payment guard first. Full mode enforcement is Phase 2.

---

## 5. Callback and Verify

Callback is only a signal. It is not proof.

A payment becomes `PAID` only after provider verify succeeds.

Required outcome rules:

- verified success → `PAID`
- provider-confirmed failure → `FAILED`
- expired, timeout, ambiguous, or amount mismatch → `NEEDS_RECONCILIATION`

`PaymentReconciliationService` is audit-only. It must not auto-settle.

---

## 6. One Invoice, One Customer Payment

V1 supports one customer payment per invoice. No partial customer payments and no multiple payers in V1.

---

## 7. Refunds and Credits

Automated refunds are not V1. Customer credit and discount are company-level concepts. Rasti Service does not fund or absorb them.
