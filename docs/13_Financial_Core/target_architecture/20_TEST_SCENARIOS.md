# 20 — سناریوهای تست (Test Scenarios)

**Version:** v1.0 — Draft — Pending Clarification

---

## Happy Path Scenarios

### HP-01: Online Payment Full Cycle
1. Order → DONE
2. Technician creates invoice with service + goods items
3. Invoice → ISSUED (wage % snapshotted)
4. Customer pays online (platform gateway)
5. PSP callback → verify → PAID
6. Settlement freeze (settled_* fields)
7. TechnicianLedgerEntry CREDIT created
8. CompanyPlatformFeeEntry DEBIT created
9. PaymentSplitSnapshot created
10. **Verify:** balance, amounts, immutability

### HP-02: Cash Payment Full Cycle
1. Order → DONE → Invoice ISSUED
2. Admin records cash payment
3. Invoice → PAID (settlement freeze)
4. TechnicianLedgerEntry CREDIT (source=cash_from_customer)
5. NO platform fee created
6. **Verify:** no CompanyPlatformFeeEntry

### HP-03: Technician Collects Cash
1. Order → DONE → Invoice ISSUED
2. Technician records cash collection (metadata.technician_id)
3. CREDIT (wage) + DEBIT (total amount collected)
4. Technician balance goes negative (owes company)
5. Admin settles manually (DEBIT manual_settlement)
6. **Verify:** balance returns to 0

### HP-04: Direct Shaparak Split
1. Company policy: SPLIT_WITH_TECHNICIAN
2. Technician: shaba_verified=True, sub_merchant_id set
3. Customer pays online (platform gateway)
4. PaymentSplitSnapshot: should_split=True
5. DEBIT direct_gateway_settlement created
6. **Verify:** technician_direct_amount matches ledger DEBIT

### HP-05: Discount Code Application
1. Customer enters discount code during payment
2. campaign_discount_amount set on invoice
3. Settlement: discount allocated per policy
4. **Verify:** settled_campaign_discount_policy correct, shares sum to total

---

## Edge Case Scenarios

### EC-01: Missing Technician IBAN (R21)
1. payout_strategy = SPLIT_WITH_TECHNICIAN
2. Technician shaba_verified = False
3. Payment verified
4. **Expected:** PaymentSplitSnapshot.should_split = False, reason = "technician_not_verified"
5. **Expected:** technician_ledger_amount = wage (company owes)
6. **Verify:** no DEBIT direct_gateway_settlement

### EC-02: Partial Payment Attempt (R47)
1. Invoice total = 5,000,000
2. PSP returns verified_amount = 4,500,000
3. **Expected:** Payment → NEEDS_RECONCILIATION
4. **Expected:** Invoice stays ISSUED (not PAID)
5. **Verify:** amount mismatch logged

### EC-03: Expired Payment
1. Payment created at T
2. No callback for 31 minutes
3. Callback arrives at T+31
4. **Expected:** Payment → NEEDS_RECONCILIATION
5. **Verify:** invoice unchanged

### EC-04: Duplicate Callback (Idempotency)
1. Payment verified → PAID
2. Second callback with same reference_id
3. **Expected:** return True, "Already verified"
4. **Verify:** no duplicate ledger entries

### EC-05: Invoice Cancellation Race
1. Technician requests cancellation (PENDING)
2. Meanwhile, customer pays (Invoice → PAID)
3. Admin tries to approve cancellation
4. **Expected:** ValueError "فاکتور پرداخت شده قابل لغو نیست"
5. **Verify:** invoice stays PAID, cancellation request → must be rejected

### EC-06: Concurrent Invoice Creation
1. Two requests: create invoice for same order simultaneously
2. First request acquires lock, creates invoice
3. Second request hits lock, waits, then finds existing
4. **Expected:** only one active invoice exists
5. **Verify:** DB constraint unique_active_invoice_per_order

### EC-07: Financial Backfill Recovery
1. TechnicianLedgerService fails during mark_paid
2. FinancialBackfillTask created (technician_ledger)
3. process_financial_backfill runs
4. create_invoice_entries called again (idempotent)
5. **Expected:** entry created, task → RESOLVED

### EC-08: Platform Fee Conditions Not Met
1. Payment via company_gateway (not platform)
2. **Expected:** no CompanyPlatformFeeEntry created
3. **Verify:** ADR-003 4-condition gate

### EC-09: Zero Wage (No Applicable Items)
1. Invoice with only goods items
2. Technician goods_wage_percent = 0
3. **Expected:** settled_technician_wage = 0
4. **Expected:** no TechnicianLedgerEntry created (wage=0 guard)

### EC-10: Policy Change After Invoice Issued
1. Invoice ISSUED with wage % snapshot = 40%
2. Admin changes technician wage % to 50%
3. Customer pays invoice
4. **Expected:** settlement uses 40% (snapshot), not 50% (current)
5. **Verify:** P08 forward-only policy

---

## Discount Edge Cases

### EC-11: Discount Exceeds Technician Share
1. technician_gross_share = 1,000,000
2. extra_discount = 1,500,000
3. policy = TECHNICIAN
4. **Expected:** tech_absorbed = 1,500,000, but final_wage = max(0, 1M - 1.5M) = 0
5. **Verify:** no negative wage

### EC-12: All Discount Policies
For same invoice, verify all 4 policies produce correct split:
- COMPANY: tech=0, comp=full
- TECHNICIAN: tech=full, comp=0
- HALF_HALF: tech=half, comp=half
- PROPORTIONAL: tech=proportional to gross share
