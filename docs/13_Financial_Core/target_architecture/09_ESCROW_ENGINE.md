# 09 — موتور Escrow پلتفرم (Platform Escrow Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R01–R05, Section 3.5

---

## اصل: پلتفرم Escrow Holder است، نه فروشنده (P05)

وجوه در حساب پلتفرم = Escrow (بدهی) + Commission (درآمد)

فقط `platform_fee_amount` درآمد پلتفرم است. بقیه escrow.

---

## مدل EscrowRecord (Target — جدید)

```python
class EscrowRecord(CompanyOwnedModel):
    class Status(TextChoices):
        HELD = "held"
        RESERVED = "reserved"
        ELIGIBLE = "eligible"
        DISTRIBUTED = "distributed"
        PENDING_SETTLEMENT = "pending_settlement"
        SETTLED = "settled"
        CLOSED = "closed"

    payment = OneToOneField(Payment, related_name="escrow_record")
    invoice = ForeignKey(Invoice, related_name="escrow_records")
    amount_rial = PositiveBigIntegerField()
    platform_commission_rial = PositiveBigIntegerField(default=0)
    organization_share_rial = PositiveBigIntegerField(default=0)
    provider_share_rial = PositiveBigIntegerField(default=0)
    status = CharField(max_length=25, choices=Status, default=Status.HELD)
    held_at = DateTimeField(auto_now_add=True)
    distributed_at = DateTimeField(null=True)
    settled_at = DateTimeField(null=True)
    closed_at = DateTimeField(null=True)
    settlement_batch = ForeignKey("SettlementBatch", null=True, blank=True)
```

---

## State Transitions

| From | To | Trigger | Service |
|---|---|---|---|
| — | HELD | Payment verified (gateway=platform) | PaymentVerifyService |
| HELD | RESERVED | Invoice marked PAID | InvoiceMarkPaidService |
| RESERVED | DISTRIBUTED | Settlement service calculates shares | InvoiceSettlementService |
| DISTRIBUTED | PENDING_SETTLEMENT | SettlementBatch created | SettlementEngine |
| PENDING_SETTLEMENT | SETTLED | Bank transfer confirmed | SettlementExecutionService |
| SETTLED | CLOSED | No outstanding adjustments | periodic check |

---

## Escrow Balance Query

```sql
SELECT
    SUM(amount_rial) - SUM(platform_commission_rial) AS total_escrow_liability
FROM escrow_record
WHERE status NOT IN ('settled', 'closed')
```

این query به Platform Owner نشان می‌دهد: «چقدر پول دیگران نزد ماست.»

---

## Cash Payments و Escrow

برای پرداخت نقدی (R37)، **هیچ EscrowRecord ایجاد نمی‌شود** — پول هرگز escrow پلتفرم نبوده.

---

## ارتباط با مدل‌های موجود

| Existing Model | Relation to Escrow |
|---|---|
| `PaymentSplitSnapshot` | مبالغ split محاسبه‌شده → populate `organization_share_rial` و `provider_share_rial` |
| `CompanyPlatformFeeEntry` | platform commission tracked separately → populate `platform_commission_rial` |
| `TechnicianLedgerEntry` | provider payment tracked → trigger SETTLED transition |

**EscrowRecord additive است — جایگزین هیچ مدل موجودی نمی‌شود.**

---

## وضعیت فعلی (Audit Finding)

- Escrow مفهومی ضمنی: پول در حساب پلتفرم نگهداری می‌شود
- هیچ explicit tracking مالکیت وجود ندارد
- Platform Owner نمی‌تواند «total escrow liability» ببیند
- **RISK-03:** شناسایی‌شده در ممیزی
