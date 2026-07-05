# 04 — تحلیل سرویس‌های مالی (Financial Service Analysis)

**تاریخ ممیزی:** 2026-07-05

---

## 1. InvoiceCreateService

**فایل:** `apps/invoices/services.py`

| | |
|---|---|
| Inputs | company, customer, order, items, notes, tax_amount, discount_amount, created_by, snapshots |
| Outputs | Invoice (DRAFT) |
| Responsibilities | تولید شماره فاکتور اتمیک، ایجاد فاکتور و آیتم‌ها، محاسبه مجدد totals |
| Side Effects | InvoiceCounter increment, InvoiceItem bulk create |

---

## 2. InvoiceIssueService

**فایل:** `apps/invoices/services.py`

| | |
|---|---|
| Inputs | invoice (DRAFT) |
| Outputs | Invoice (ISSUED) |
| Responsibilities | اعتبارسنجی مبلغ > 0، snapshot wage percentages، تغییر وضعیت |
| Side Effects | فریز `technician_*_wage_percent_snapshot`، notification signal triggered |

---

## 3. InvoiceMarkPaidService

**فایل:** `apps/invoices/services.py`

| | |
|---|---|
| Inputs | invoice (ISSUED), payment (optional), payment_method, payment_reference, discount_code_id |
| Outputs | Invoice (PAID) |
| Responsibilities | قفل invoice (select_for_update)، فراخوانی settlement، ایجاد ledger entries، platform fee |
| Side Effects | InvoiceSettlementService.settle()، TechnicianLedgerService.create_invoice_entries()، PlatformFeeService.record_invoice_fee() (شرایطی)، FinancialBackfillTask on failure |

**این سرویس مرکز ثقل کل هسته مالی است.**

---

## 4. InvoiceSettlementService

**فایل:** `apps/invoices/services_settlement.py`

| | |
|---|---|
| Inputs | invoice, payment_method, payment_reference, discount_code_id |
| Outputs | Invoice (با فیلدهای settled_* فریز شده) |
| Responsibilities | اجرای محاسبه policy-aware wage، فریز تمام مقادیر مالی |
| Side Effects | نوشتن 17 فیلد settled_* روی Invoice |

---

## 5. TechnicianLedgerService

**فایل:** `apps/payouts/services.py`

| | |
|---|---|
| Inputs (create_credit/debit) | company, technician, source, amount_rial, idempotency_key, ... |
| Outputs | TechnicianLedgerEntry or None (idempotency hit) |
| Responsibilities | محاسبه balance_after، نوشتن entry اتمیک |
| Side Effects | select_for_update روی آخرین entry (lock)، savepoint برای race condition |

| | |
|---|---|
| Inputs (create_invoice_entries) | invoice, payment |
| Outputs | list[TechnicianLedgerEntry] |
| Responsibilities | CREDIT wage + DEBIT cash (اگر تکنسین نقدی گرفت) |

| | |
|---|---|
| Inputs (record_manual_settlement) | company, technician, amount_rial, direction, reference, ... |
| Outputs | TechnicianLedgerEntry |
| Responsibilities | ثبت تسویه دستی (COMPANY_PAID_TECHNICIAN / TECHNICIAN_PAID_COMPANY / ADJUSTMENT) |

| | |
|---|---|
| Inputs (get_balance) | company, technician |
| Outputs | int (balance in rial) |
| Responsibilities | SUM(credits) - SUM(debits) — مرجع واقعی balance |

---

## 6. PlatformFeeService

**فایل:** `apps/payouts/services_platform_fee.py`

| | |
|---|---|
| Inputs (record_invoice_fee) | invoice, payment, source, created_by |
| Outputs | CompanyPlatformFeeEntry or None |
| Responsibilities | اعتبارسنجی 4 شرط ADR-003، محاسبه fee، نوشتن DEBIT entry |
| Side Effects | PlatformFeeRecordingFailed exception on failure |

| | |
|---|---|
| Inputs (record_manual_credit) | company, amount_rial, description, idempotency_key |
| Outputs | CompanyPlatformFeeEntry |
| Responsibilities | ثبت CREDIT (تسویه کارمزد توسط شرکت) |

---

## 7. PaymentSplitDecisionService

**فایل:** `apps/payouts/services_split.py`

| | |
|---|---|
| Inputs (compute) | invoice, payment |
| Outputs | dict (split decision) |
| Responsibilities | محاسبه تسهیم: آیا شاپرک مستقیم به تکنسین واریز کند؟ |
| Side Effects | هیچ (pure calculation) |

| | |
|---|---|
| Inputs (create_snapshot) | payment, invoice |
| Outputs | PaymentSplitSnapshot or None |
| Responsibilities | ایجاد snapshot تغییرناپذیر — idempotent |

---

## 8. TechnicianDirectSettlementService

**فایل:** `apps/payouts/services_direct_settlement.py`

| | |
|---|---|
| Inputs | payment |
| Outputs | list (0 or 1 entry) |
| Responsibilities | بررسی 9 شرط applicability، ایجاد DEBIT entry |
| Side Effects | TechnicianLedgerEntry DEBIT with source=direct_gateway_settlement |

---

## 9. TechnicianWagePostingService

**فایل:** `apps/payouts/services_order_wages.py`

| | |
|---|---|
| Inputs | order (DONE) |
| Outputs | list (0 or 1 entry) |
| Responsibilities | محاسبه wage از TechnicianServiceRate × OrderItemValue.value_number |
| Side Effects | TechnicianLedgerEntry CREDIT with source=technician_service_wage + metadata snapshot |

---

## 10. TechnicianStatementService

**فایل:** `apps/payouts/services_statement.py`

| | |
|---|---|
| Inputs | technician, from_date, to_date |
| Outputs | dict (rows + summary) |
| Responsibilities | خواندن ledger entries، ترجمه source به فارسی، محاسبه summary |
| Side Effects | هیچ — خالص read-only |

---

## 11. FinancialBackfillService

**فایل:** `apps/payouts/services_backfill.py`

| | |
|---|---|
| Inputs (create_task) | company, task_type, invoice, payment, error_message |
| Outputs | (task, created: bool) |
| Responsibilities | ایجاد task بدون تکرار (deduplication per company+type+invoice) |

| | |
|---|---|
| Inputs (process_pending) | limit |
| Outputs | dict {resolved, failed, skipped} |
| Responsibilities | dispatch و retry هر task در transaction جداگانه |

---

## 12. PaymentStartService

**فایل:** `apps/payments/services.py`

| | |
|---|---|
| Inputs | invoice (ISSUED), callback_url, gateway (optional) |
| Outputs | (Payment, PaymentAttempt, redirect_url) |
| Responsibilities | KYC check، payment mode guard، gateway selection، redirect generation |
| Side Effects | Payment + PaymentAttempt creation |

---

## 13. PaymentVerifyService

**فایل:** `apps/payments/services.py`

| | |
|---|---|
| Inputs | payment (PENDING) |
| Outputs | (success: bool, message: str) |
| Responsibilities | Lock + expire check + PSP verify + amount tampering check + mark paid + financial events |
| Side Effects | Invoice PAID، ledger entries، split snapshot، direct settlement DEBIT، backfill tasks on failure |

---

## 14. InvoiceFinancialPreviewService

**فایل:** `apps/invoices/services_preview.py`

| | |
|---|---|
| Inputs | invoice |
| Outputs | dict (financial breakdown) |
| Responsibilities | محاسبه پیش‌نمایش بدون هیچ DB write |
| Side Effects | هیچ |

---

## 15. _calculate_policy_aware_wage

**فایل:** `apps/invoices/services_wage.py`

| | |
|---|---|
| Inputs | invoice, use_snapshot_percentages_only, campaign_policy, extra_policy |
| Outputs | dict (wage calculation result) |
| Responsibilities | محاسبه سهم تکنسین/شرکت با در نظر گرفتن policy تخفیف |
| Algorithm | category totals → wage percentages → gross shares → discount allocation → net shares |
