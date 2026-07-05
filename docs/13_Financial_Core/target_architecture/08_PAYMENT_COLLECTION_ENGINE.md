# 08 — موتور وصول پرداخت (Payment Collection Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R11–R15, R37–R40

---

## سه مدل وصول (R12)

### Model A — Platform → Settlement → Organization

```
Customer ──→ Platform Account ──→ Settlement Batch ──→ Organization Bank
                    │
                    └── Platform retains commission
```

**Use case:** حالت پیش‌فرض. پلتفرم وجه را دریافت و بعد تسویه می‌کند.
**Implementation:** ✅ `PaymentGateway.owner_type=PLATFORM` + `CompanyFinancialPolicy.payout_strategy=DIRECT_TO_COMPANY`

### Model B — Platform Retains Commission, Rest to Organization

```
Customer ──→ Platform Account ──→ (commission retained)
                    │
                    └── Remaining amount → Organization Bank (immediate or batched)
```

**Use case:** تسویه فوری/روزانه با کسر کارمزد.
**Implementation:** 🟡 ضمنی — نیاز به Settlement Engine (target Sprint 2)

### Model C — Platform Retains Commission, Split with Provider

```
Customer ──→ Platform Account ──→ (commission retained)
                    │
                    ├── Organization share → Organization Bank
                    └── Provider share → Provider Bank (Shaparak sub-merchant)
```

**Use case:** تسویه مستقیم Shaparak به تکنسین.
**Implementation:** ✅ `CompanyFinancialPolicy.payout_strategy=SPLIT_WITH_TECHNICIAN` + `PaymentSplitDecisionService`

---

## پرداخت آنلاین (Online Payment)

[OPEN-ISSUE: OI-01]

**Current Status:** معماری Platform-First Collection فعال. Split Payment در سطح concept طراحی شده (`PaymentSplitSnapshot`, `sub_merchant_id`). اما split واقعی Shaparak هنوز TASK-010C (planned).

**Question for Product Owner:** آیا PSP انتخاب‌شده (Shaparak) از Split Payment real-time بین چند ذینفع پشتیبانی می‌کند؟

---

### جریان پرداخت آنلاین (موجود)

```
1. Customer clicks Pay → PaymentStartService.start()
2. Guards: invoice ISSUED + payment mode active + KYC approved + gateway active
3. Payment(INITIATED) → PaymentAttempt → PSP redirect URL
4. Customer pays at gateway
5. Gateway callback → PaymentCallbackService.handle_callback()
6. PaymentVerifyService.verify():
   - Lock Payment (select_for_update)
   - Check expiration (30 min)
   - Call PSP verify endpoint
   - Check amount match (tampering protection)
   - Mark PAID
   - InvoiceMarkPaidService.mark_paid()
   - PaymentSplitDecisionService.create_snapshot()
   - TechnicianDirectSettlementService.post_for_payment()
```

---

## پرداخت نقدی (Cash Payment — R37)

```
1. Admin records cash at /<code>/admin/invoices/<id>/record-payment/
2. InvoiceMarkPaidService.mark_paid(payment_method="cash")
3. Settlement freeze (settled_* fields)
4. TechnicianLedgerEntry CREDIT (source: cash_from_customer or manual_payment)
5. If technician collected: DEBIT cash_from_customer (total invoice amount)
6. NO platform commission (R38 default)
```

**Legal ownership:** فوراً به شرکت (R37). Platform escrow اعمال نمی‌شود.

---

## پرداخت کارت‌به‌کارت (Card-to-Card — R40)

**Status:** ❌ Missing — target implementation

**Target Design:**
- `PaymentGateway.GatewayType.CARD_TO_CARD = "card_to_card"`
- Recording: مشابه cash (manual) — admin ثبت می‌کند
- Tracking: metadata.method = "card_to_card"
- Reporting: مجزا از cash — channel مستقل

**تفاوت با نقدی:**
- Card-to-card اثبات‌پذیر (bank transaction reference)
- Cash اثبات‌ناپذیر (فقط trust)
- Future: bank transfer هم channel مجزا خواهد بود

---

## Guards و KYC (R13–R15)

### R13 — No IBAN → No Online Payment

```python
# PaymentStartService.start():
CompanyPaymentEligibilityService.is_gateway_enabled(company)
# Checks: CompanyMerchantProfile.status == APPROVED
```

### R14 — IBAN Approval by Platform Only

```python
# CompanyMerchantProfile:
# status: NOT_SUBMITTED → SUBMITTED → UNDER_REVIEW → APPROVED
# reviewed_by: Platform Owner user
```

### R15 — One Active Bank Account

```python
# CompanyMerchantProfile: OneToOne with Company
# CompanyMerchantProfileChangeRequest: for modifications post-approval
```

---

## Security Measures (P8)

| Protection | Implementation |
|---|---|
| Duplicate callback prevention | `select_for_update()` on Payment |
| Payment expiration | 30-minute timeout → NEEDS_RECONCILIATION |
| Amount tampering | verified_amount ≠ payment.amount → NEEDS_RECONCILIATION |
| KYC enforcement | `CompanyPaymentEligibilityService` before payment start |
| Idempotent verification | Already PAID → return True immediately |

---

## NEEDS_RECONCILIATION Resolution

```
Payment enters NEEDS_RECONCILIATION when:
- Expired (> 30 min without verification)
- Amount mismatch (possible tampering)
- PSP ambiguous response

Resolution:
- Platform Owner reviews at /owner-platform/payments/operations/
- Manual mark as PAID or FAILED
```
