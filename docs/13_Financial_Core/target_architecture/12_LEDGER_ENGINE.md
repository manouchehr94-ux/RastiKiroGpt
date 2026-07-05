# 12 — موتور دفترکل (Immutable Ledger Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** Section 3.4, R51

---

## اصل: Append-Only (P02)

هر رویداد مالی یک Ledger entry ایجاد می‌کند. Entries:
- هرگز ویرایش نمی‌شوند
- هرگز حذف نمی‌شوند
- اصلاحات = entry جدید ADJUSTMENT

---

## دو دفترکل موجود

### 1. TechnicianLedgerEntry (Organization ↔ Provider)

**Convention:** CREDIT = شرکت بدهکار تکنسین. DEBIT = تکنسین بدهکار / تسویه شد.

| Source | Entry Type | When Created |
|---|---|---|
| `technician_service_wage` | CREDIT | Order completion (DONE) |
| `online_gateway` | CREDIT | Invoice paid online |
| `cash_from_customer` | CREDIT | Invoice paid cash (technician didn't collect) |
| `cash_from_customer` | DEBIT | Technician collected cash from customer |
| `manual_payment` | CREDIT | Admin recorded manual payment |
| `direct_gateway_settlement` | DEBIT | Shaparak paid technician directly |
| `manual_settlement` | DEBIT | Admin settled with technician |
| `adjustment` | CREDIT/DEBIT | Manual correction |
| `refund` | CREDIT/DEBIT | Refund (target — not implemented) |

### 2. CompanyPlatformFeeEntry (Platform ↔ Organization)

**Convention:** DEBIT = شرکت بدهکار پلتفرم. CREDIT = تسویه شد.

| Source | Entry Type | When Created |
|---|---|---|
| `online_gateway` | DEBIT | Invoice paid via platform gateway |
| `cash_invoice` | DEBIT | Cash invoice (if commission enabled) |
| `manual_adjustment` | DEBIT/CREDIT | Manual correction |
| `platform_fee_settlement` | CREDIT | Company paid platform fee |
| `refund` | CREDIT | Refund reverses fee |

---

## Immutability Enforcement

```python
class TechnicianLedgerEntry(CompanyOwnedModel):
    def delete(self, *args, **kwargs):
        raise PermissionError("Immutable — cannot delete")

    def save(self, *args, **kwargs):
        if self.pk is not None:  # existing record
            original = TechnicianLedgerEntry.objects.filter(pk=self.pk).values(...)
            if original["amount_rial"] != self.amount_rial:
                raise PermissionError("amount_rial is immutable")
            if original["balance_after"] != self.balance_after:
                raise PermissionError("balance_after is immutable")
```

---

## Idempotency

هر entry یک `idempotency_key` (UNIQUE) دارد:

| Business Event | Key Pattern |
|---|---|
| Order wage | `technician_service_wage:order:{order.id}` |
| Invoice technician credit | `invoice:{invoice.id}:technician_credit` |
| Invoice cash debit | `invoice:{invoice.id}:cash_received_by_technician` |
| Direct settlement | `direct_gateway_settlement:payment:{payment.id}` |
| Platform fee | `platform_fee:invoice:{invoice.id}` |
| Manual settlement | `manual_settlement:{uuid}` |

---

## Balance Calculation

```python
# Authoritative balance (always recomputed from SUM):
TechnicianLedgerService.get_balance(company, technician):
    credits = SUM(amount_rial WHERE entry_type=CREDIT)
    debits  = SUM(amount_rial WHERE entry_type=DEBIT)
    return credits - debits
    # Positive = company owes technician
    # Negative = technician owes company
```

`balance_after` field = cached running balance (display/convenience). `get_balance()` = source of truth.

---

## Concurrency Control

```python
# Lock latest entry for this technician before writing:
list(
    TechnicianLedgerEntry.objects.select_for_update()
    .filter(company=company, technician=technician)
    .order_by("-id")[:1]
    .values_list("id", flat=True)
)
# Then compute balance_after and create new entry
```

**Known limitation (ADR-008):** first entry for a new technician has no row to lock. Balance SUM remains correct; `balance_after` field may be stale.

---

## Authoritative Source Rule (ADR-006 §7)

هر ledger entry مبلغ خود را از **snapshot مرجع** آن business event می‌خواند — هرگز از entry قبلی.

| Event | Amount Source |
|---|---|
| Order DONE | `OrderItemValue.value_number × TechnicianServiceRate.fixed_wage_rial` |
| Invoice paid | `invoice.settled_technician_wage` |
| Gateway split | `PaymentSplitSnapshot.technician_direct_amount` |
| Manual settlement | Amount entered by admin |

**Anti-pattern:** `prior_entry.amount_rial` → FORBIDDEN

---

## Single-Entry with Double-Entry Discipline (ADR-004)

فعلاً true double-entry نیست (هر entry یک‌طرفه). اما discipline:
- هر دو طرف cash movement اتمیک ثبت (invoice CREDIT + cash DEBIT)
- Immutability
- Idempotency
- No manual balance editing

**Target future:** وقتی scale بالا رفت → materialized balance views یا true double-entry upgrade.
