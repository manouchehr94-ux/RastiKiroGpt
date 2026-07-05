# 18 — الزامات گزارش‌گیری (Reporting Requirements)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R53–R56

---

## R53 — گزارش بدهی تکنسین از پرداخت نقدی (اجباری)

**هدف:** نمایش تکنسین‌هایی که وجه نقد مشتری را دریافت کرده و هنوز به شرکت تحویل نداده‌اند.

**Query Logic:**
```sql
SELECT technician_id, 
       SUM(CASE WHEN entry_type='debit' AND source='cash_from_customer' THEN amount_rial ELSE 0 END) as cash_collected,
       SUM(CASE WHEN entry_type='debit' AND source='manual_settlement' THEN amount_rial ELSE 0 END) as settled,
       get_balance(company, technician) as current_balance
FROM technician_ledger_entry
WHERE company = X
GROUP BY technician_id
HAVING get_balance < 0  -- technician owes company
```

**Output:**
| تکنسین | نقد دریافتی | تسویه‌شده | مانده بدهی |
|---|---|---|---|

**Implementation Status:** 🟡 Data exists in ledger. Dedicated report view missing.

---

## R54 — گزارش کامل کارمزد پلتفرم (اجباری)

**هدف:** مجموع کارمزد تعلق‌گرفته و تسویه‌شده per company.

**Query Logic:**
```sql
SELECT company_id,
       SUM(CASE WHEN entry_type='debit' THEN amount_rial ELSE 0 END) as total_fees_accrued,
       SUM(CASE WHEN entry_type='credit' THEN amount_rial ELSE 0 END) as total_fees_settled,
       get_balance(company) as outstanding_balance
FROM company_platform_fee_entry
GROUP BY company_id
```

**Output:**
| شرکت | کارمزد تعلق‌گرفته | تسویه‌شده | مانده |
|---|---|---|---|

**Filters:** date range, company, status

**Implementation Status:** 🟡 `PlatformFeeService.get_balance()` exists. Aggregated report view missing.

---

## R55 — گزارش تسویه‌های انجام‌شده و در انتظار (اجباری)

**هدف:** وضعیت settlement batches.

**Output (target):**
| Batch # | شرکت | نوع | مبلغ خالص | وضعیت | تاریخ |
|---|---|---|---|---|---|

**Depends on:** SettlementBatch model (target Sprint 2)

**Implementation Status:** ❌ Missing — requires settlement engine first.

---

## R56 — جامع‌ترین گزارش مالی ممکن

[OPEN-ISSUE: OI-09]
**Current Status:** Platform Owner «جامع‌ترین گزارش‌گیری» درخواست کرده اما KPI catalog مشخص نیست.
**Question for Product Owner:** کدام KPIهای مالی الزامی هستند؟

[OPEN-ISSUE: OI-10]
**Current Status:** الزامات گزارش‌گیری تکنسین مشخص نشده.
**Question for Product Owner:** دقیقاً کدام گزارش‌ها باید به تکنسین نمایش داده شود؟

---

## KPI‌های پیشنهادی (Pending PO Approval)

### Platform Level
- Total GMV (Gross Merchandise Value) per period
- Total platform commission earned
- Average commission rate
- Total escrow balance
- Settlement velocity (time from PAID to SETTLED)
- Failed financial tasks count
- NEEDS_RECONCILIATION count

### Organization Level
- Revenue per period
- Invoice count (paid/issued/cancelled)
- Average invoice amount
- Technician payout ratio
- Discount utilization rate
- Outstanding technician balance
- Platform fee outstanding

### Provider Level (OI-10)
- Total earnings per period
- Cash collected vs settled
- Outstanding balance (owed or owing)
- Service rate summary
- Statement export

---

## Existing Report Infrastructure

| Component | Status |
|---|---|
| `apps/reports/models.Report` | Stub — not used for financial |
| Technician statement (view) | ✅ `technician_statement` view |
| Technician export (CSV/PDF) | ✅ views exist |
| Platform fee entries list | ✅ `PlatformFeeService.list_entries()` |
| Financial preview per invoice | ✅ `InvoiceFinancialPreviewService` |
| Dashboard KPIs | ❌ Missing |
| Aggregated reports | ❌ Missing |
