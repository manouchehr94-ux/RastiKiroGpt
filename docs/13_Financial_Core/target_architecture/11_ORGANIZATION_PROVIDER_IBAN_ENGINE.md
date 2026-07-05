# 11 — موتور مدیریت شبا (Organization & Provider IBAN Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R13–R15, R18–R21

---

## Organization IBAN (R13–R15)

### Model: CompanyMerchantProfile (موجود)

| Field | Purpose |
|---|---|
| `shaba_number` | شماره شبا شرکت (IR + 24 رقم) |
| `bank_name` | نام بانک |
| `account_holder_name` | نام صاحب حساب |
| `bank_card_number` | شماره کارت (masked in display) |
| `status` | lifecycle: NOT_SUBMITTED → SUBMITTED → APPROVED |

### Verification Flow

```
1. Company Admin submits KYC info + IBAN
   → CompanyMerchantProfile(status=SUBMITTED)

2. Platform Owner reviews at /owner-platform/merchant-profiles/
   → status = UNDER_REVIEW

3. Platform Owner approves
   → status = APPROVED
   → Company may now activate online payment (separate step)

4. Company requests changes after approval
   → CompanyMerchantProfileChangeRequest created
   → Platform Owner reviews change request
```

### Rules Enforcement

| Rule | Implementation |
|---|---|
| R13 — No IBAN → No payment | `CompanyPaymentEligibilityService.is_gateway_enabled()` |
| R14 — Approval by Platform only | `CompanyMerchantProfile.reviewed_by` = platform user |
| R15 — One active account | OneToOneField(Company). Change = re-approval via ChangeRequest |

---

## Provider IBAN (R18–R21)

### Model: Technician (موجود)

| Field | Purpose |
|---|---|
| `shaba_number` | شماره شبا تکنسین |
| `shaba_verified` | Boolean — آیا شرکت تأیید کرده |
| `shaba_verified_at` | تاریخ تأیید |
| `sub_merchant_id` | شناسه پذیرنده فرعی Shaparak |
| `financial_verification_status` | NOT_SUBMITTED/PENDING/VERIFIED/REJECTED |
| `verified_by` | FK to CompanyUser who verified |

### Verification Flow

```
1. Company Admin registers IBAN for technician
   → Technician.shaba_number = "IR..."
   → financial_verification_status = PENDING

2. Company Admin verifies (R19 — Org responsibility, NOT platform)
   → shaba_verified = True
   → financial_verification_status = VERIFIED
   → shaba_verified_at = now()
   → verified_by = admin user

3. Platform assigns sub_merchant_id (for Shaparak split)
   → sub_merchant_id = "SM-XXX"
```

### Rules Enforcement

| Rule | Implementation |
|---|---|
| R18 — Org registers IBAN per Provider | `Technician.shaba_number` per company |
| R19 — Org verifies (not Platform) | `verified_by` = CompanyUser within same company |
| R20 — Direct settlement only when Org enables | `payout_strategy=SPLIT_WITH_TECHNICIAN` + `shaba_verified=True` + `sub_merchant_id` present |
| R21 — No IBAN → share goes to Org | `PaymentSplitDecisionService`: if not verified → reason="technician_not_verified" → technician_ledger_amount (company owes) |

---

## R21 — No Indefinite Suspension

هنگامی که تکنسین شبا ندارد:
- سهم مالی تکنسین **به شرکت منتقل می‌شود** (CREDIT in technician ledger)
- شرکت مسئول پرداخت دستی به تکنسین (cash/bank/card-to-card)
- مبلغ **نباید** بدون مالک بماند

Implementation:
```python
# PaymentSplitDecisionService.compute():
if not tech_verified or not tech_sub_merchant_id:
    technician_direct_amount = 0      # no Shaparak split
    technician_ledger_amount = tech_wage  # company OWES technician
    reason = "technician_not_verified"
```

تکنسین CREDIT دریافت می‌کند → company balance positive → admin باید manual settle کند.

---

## وضعیت پیاده‌سازی

| Component | Status |
|---|---|
| Organization IBAN model | ✅ CompanyMerchantProfile |
| Organization IBAN verification flow | ✅ Platform Owner approval |
| Organization change request | ✅ CompanyMerchantProfileChangeRequest |
| Provider IBAN model | ✅ Technician.shaba_number |
| Provider verification by Org | ✅ shaba_verified + verified_by |
| No IBAN → fallback to Org | ✅ PaymentSplitDecisionService logic |
| Payment blocked without Org IBAN | ✅ CompanyPaymentEligibilityService |
