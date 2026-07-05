# 06 — تحلیل قابلیت بازاستفاده (Reuse Analysis)

**تاریخ ممیزی:** 2026-07-05

---

## مدل‌هایی که هرگز نباید جایگزین شوند

| Model | دلیل |
|---|---|
| `Invoice` | هسته مرکزی. 17 فیلد settled_* اضافه شده. migration history پیچیده. |
| `InvoiceItem` | ساختار RowType صحیح و کاربردی. |
| `Payment` | Status machine کامل و تست‌شده. |
| `PaymentGateway` | OwnerType distinction حیاتی برای commission logic. |
| `TechnicianLedgerEntry` | Immutability enforcement در model layer. تمام financial history در این جدول. |
| `CompanyPlatformFeeEntry` | همان الگوی ledger — هرگز replace نکنید. |
| `PaymentSplitSnapshot` | OneToOne immutable audit record. |
| `FinancialBackfillTask` | Recovery infrastructure — working correctly. |
| `TechnicianServiceRate` | Simple, correct, extensible (ADR-005). |
| `CompanyFinancialPolicy` | Central policy holder. |
| `CompanyPaymentSettings` | Payment mode authority. |
| `CompanyMerchantProfile` | KYC lifecycle — complex status machine. |

---

## سرویس‌هایی که هرگز نباید بازنویسی شوند

| Service | دلیل |
|---|---|
| `TechnicianLedgerService._write_entry()` | Idempotency + savepoint + select_for_update — battle-tested pattern |
| `TechnicianLedgerService.get_balance()` | Source of truth for balance — simple SUM |
| `TechnicianLedgerService.create_invoice_entries()` | Complex idempotent logic with cash detection |
| `PlatformFeeService._write_entry()` | Same proven ledger write pattern |
| `PlatformFeeService.record_invoice_fee()` | 4-condition gate from ADR-003 |
| `PaymentVerifyService.verify()` | Security-hardened (lock, expire, tamper detection) |
| `PaymentSplitDecisionService.compute()` | Pure calculation — easily testable |
| `InvoiceSettlementService.settle()` | Policy-aware freeze — critical for financial integrity |
| `FinancialBackfillService._process_one()` | Two-phase transaction pattern — correct |
| `TechnicianWagePostingService.post_for_order()` | Clean algorithm with missing-rate tolerance |
| `TechnicianStatementService.build()` | Pure read-only projection — safe |

---

## قواعد تجاری قابل بازاستفاده

| Rule | Location | وضعیت |
|---|---|---|
| Immutability enforcement | `TechnicianLedgerEntry.save()/delete()` | Production-ready |
| Idempotency key pattern | `_write_entry()` in both ledger services | Production-ready |
| 4-condition commission gate | `PlatformFeeService.record_invoice_fee()` | Production-ready (ADR-003) |
| Discount allocation algorithm | `_allocate_discount()` in services_wage | Complete with 4 policies |
| Category subtotal calculation | `_collect_category_totals()` | Correct implementation of R26 |
| Wage percentage snapshotting | `snapshot_wage_percentages_on_invoice()` | Forward-only policy compliance |
| Invoice duplicate guard | `InvoiceDuplicateGuard` | Race-safe with select_for_update |
| Payment expiration check | `_is_payment_expired()` | Security hardened |
| Cascade recovery | `_retry_direct_gateway_settlement()` | Handles missing snapshot |
| Settlement freeze completeness | `InvoiceSettlementService.settle()` | 17-field atomic freeze |

---

## تست‌های قابل حفظ

ممیزی نشان می‌دهد دایرکتوری `tests/` شامل 1242+ test است. تست‌های مالی مرتبط:

| Test File (expected) | Coverage |
|---|---|
| `test_task007a_financial_integrity.py` | CompanyPaymentSettings sync |
| `test_p_company_payment_settings.py` | Defaults, isolation, choices |
| تست‌های invoice/payment (if exist) | Lifecycle, validation |

**توصیه:** تمام تست‌های موجود مالی باید حفظ شوند. هر extension جدید باید backward-compatible باشد.

---

## Selectors قابل بازاستفاده

| Selector | Location |
|---|---|
| `InvoiceSelector.get_for_company()` | apps/invoices/selectors.py |
| `InvoiceSelector.get_for_customer()` | apps/invoices/selectors.py |
| `PaymentSelector.get_for_invoice()` | apps/payments/selectors.py |
| `PaymentGatewaySelector.get_default_for_company()` | apps/payments/selectors.py |
| `PaymentSelector.build_display_info()` | apps/payments/selectors.py |

---

## Utility Components قابل حفظ

| Utility | Location | کاربرد |
|---|---|---|
| `generate_invoice_number()` | apps/invoices/models.py | Concurrency-safe sequence |
| `_money()` helper | apps/invoices/services_wage.py | Decimal rounding |
| `_parse_statement_date()` | apps/payouts/views.py | Jalali date parsing |
| `build_invoice_snapshot_from_order()` | apps/invoices/services.py | Order→Invoice snapshot |
| `_resolve_discount_code_id()` | apps/payments/services.py | Discount code lookup |
| `_payment_collected_by_technician()` | apps/payouts/services.py | Cash detection from metadata |
