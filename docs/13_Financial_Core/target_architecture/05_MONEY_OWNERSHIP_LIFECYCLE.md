# 05 — چرخه مالکیت پول (Money Ownership Lifecycle)

**Version:** v1.0 — Draft — Pending Clarification

---

## State Machine

```
customer_paid ──→ held_in_platform_escrow ──→ reserved_for_invoice
                                                       │
                                                       ▼
                                          eligible_for_distribution
                                                       │
                                                       ▼
                                              policy_calculated
                                                       │
                                                       ▼
                                           distributed_by_policy
                                                       │
                                                       ▼
                                            pending_settlement
                                                       │
                                                       ▼
                                          settled_to_stakeholders
                                                       │
                                                       ▼
                                                    closed
```

---

## Mapping States to RastiSaas Events

### customer_paid
**Trigger:** `PaymentVerifyService.verify()` → Payment.status = PAID
**What happens:** PSP تأیید کرده که پول از حساب مشتری برداشته شده.
**Existing implementation:** ✅ `Payment(status=PAID, paid_at=now())`

---

### held_in_platform_escrow
**Trigger:** Payment verified + gateway.owner_type = PLATFORM
**What happens:** وجه فیزیکاً در حساب بانکی پلتفرم است. حقوقاً به ذینفعان تعلق دارد.
**Existing implementation:** 🟡 ضمنی (پول در حساب پلتفرم). Target: `EscrowRecord(status=HELD)`

---

### reserved_for_invoice
**Trigger:** `InvoiceMarkPaidService.mark_paid()` — Invoice.status = PAID
**What happens:** وجه به فاکتور خاصی تخصیص یافته.
**Existing implementation:** ✅ Invoice links to Payment. Target: `EscrowRecord(status=RESERVED)`

---

### eligible_for_distribution
**Trigger:** خدمت تکمیل شده (Order.status = DONE) + فاکتور PAID
**What happens:** شرایط عملیاتی برای توزیع مالی برآورده شده.
**Existing implementation:** ✅ در RastiSaas فعلی، settlement بلافاصله با PAID اتفاق می‌افتد (R37).
**Note:** در مدل‌های پیچیده‌تر (مثلاً delivery confirmation)، این state جداگانه خواهد بود.

---

### policy_calculated
**Trigger:** `InvoiceSettlementService.settle()`
**What happens:** تمام سیاست‌ها (commission, wage, discount allocation) اعمال شده.
**Existing implementation:** ✅ `_calculate_policy_aware_wage()` + policy freeze
**EscrowRecord target:** status = ELIGIBLE → run policies

---

### distributed_by_policy
**Trigger:** Settlement freeze complete (settled_* fields written)
**What happens:** حق مالی هر Financial Party مشخص شده:
- `settled_technician_wage` → سهم تکنسین
- `settled_company_share` → سهم شرکت
- `platform_fee_amount` → سهم پلتفرم
**Existing implementation:** ✅ `Invoice.settled_*` fields
**Target:** `EscrowRecord(status=DISTRIBUTED)`

---

### pending_settlement
**Trigger:** Ledger entries created + waiting for actual bank transfer
**What happens:** تخصیص محاسبه شده، منتظر انتقال واقعی.
**Existing implementation:** 🟡 `TechnicianLedgerEntry` CREDIT ایجاد شده اما debit (settlement) هنوز نه.
**Target:** `EscrowRecord(status=PENDING_SETTLEMENT)`, `SettlementBatch(status=PENDING)`

---

### settled_to_stakeholders
**Trigger:** Bank transfer executed OR direct Shaparak split OR manual settlement recorded
**What happens:** وجه واقعاً به ذینفعان منتقل شده.
**Existing implementation:**
- Direct split: ✅ `TechnicianDirectSettlementService` → DEBIT entry
- Manual: ✅ `record_manual_settlement()` → DEBIT entry
- Automated batch: ❌ Missing
**Target:** `EscrowRecord(status=SETTLED)`, `SettlementBatch(status=COMPLETED)`

---

### closed
**Trigger:** تمام stakeholders paid + no outstanding adjustments
**What happens:** فاکتور از نظر مالی بسته شده.
**Existing implementation:** ❌ Missing — هیچ explicit "closed" state وجود ندارد.
**Target:** `EscrowRecord(status=CLOSED)`

---

## Cash Payment Variant

برای پرداخت نقدی، lifecycle متفاوت است:

```
customer_paid_cash
       │
       ▼
ownership_at_organization (فوری — R37)
       │
       ▼
policy_calculated (Commission Allocation Doc ایجاد شده)
       │
       ▼
distributed_by_policy (settled_* فریز)
       │
       ▼
pending_org_provider_settlement (if technician collected cash)
       │
       ▼
settled (manual_settlement recorded)
       │
       ▼
closed
```

**تفاوت اصلی:** پول هرگز escrow پلتفرم نیست. مالکیت فوراً به شرکت تعلق دارد (R37).

---

## State Transition Rules

| From | To | Condition | Reversible? |
|---|---|---|---|
| customer_paid | held_in_platform_escrow | gateway.owner_type=PLATFORM | No (refund only) |
| held_in_platform_escrow | reserved_for_invoice | Invoice.status=PAID | No |
| reserved_for_invoice | eligible_for_distribution | Order.status=DONE (or immediate) | No |
| eligible_for_distribution | policy_calculated | Settlement service runs | No |
| policy_calculated | distributed_by_policy | settled_* written | No |
| distributed_by_policy | pending_settlement | Ledger entries created | No |
| pending_settlement | settled_to_stakeholders | Bank transfer confirmed | No |
| settled_to_stakeholders | closed | No outstanding adjustments | No |

**هیچ فاکتوری نمی‌تواند مستقیماً به closed برود بدون عبور از تمام states قبلی.**
