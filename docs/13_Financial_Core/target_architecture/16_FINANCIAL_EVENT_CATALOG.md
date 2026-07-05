# 16 — کاتالوگ رویدادهای مالی (Financial Event Catalog)

**Version:** v1.0 — Draft — Pending Clarification
**Principle:** P10 — Every Financial State Change is Event-Driven

---

## رویدادهای موجود (در `notifications/event_catalog.py`)

| Event Key | Trigger | Recipient |
|---|---|---|
| `INVOICE_CREATED` | فاکتور ایجاد شد | COMPANY_ADMIN |
| `INVOICE_ISSUED_CUSTOMER` | فاکتور صادر شد | CUSTOMER |
| `INVOICE_PAID_CUSTOMER` | فاکتور پرداخت شد | CUSTOMER |
| `INVOICE_CANCELLED` | فاکتور لغو شد | CUSTOMER |
| `PAYMENT_STARTED` | پرداخت شروع شد | COMPANY_ADMIN |
| `PAYMENT_SUCCESS_CUSTOMER` | پرداخت موفق | CUSTOMER |
| `PAYMENT_SUCCESS_ADMIN` | پرداخت موفق | COMPANY_ADMIN |
| `PAYMENT_SUCCESS_OPERATOR` | پرداخت موفق | OPERATOR |
| `PAYMENT_FAILED_CUSTOMER` | پرداخت ناموفق | CUSTOMER |

---

## رویدادهای Target (جدید — باید اضافه شوند)

### Escrow Events

| Event Key | Trigger | Recipient |
|---|---|---|
| `escrow_reserved` | Payment verified, escrow created | PLATFORM_OWNER |
| `escrow_released` | Settlement batch executed | PLATFORM_OWNER |

### Settlement Events

| Event Key | Trigger | Recipient |
|---|---|---|
| `settlement_batch_created` | Batch calculation complete | PLATFORM_OWNER, COMPANY_ADMIN |
| `settlement_batch_executing` | Bank transfer initiated | PLATFORM_OWNER |
| `settlement_completed` | Transfer confirmed | COMPANY_ADMIN |
| `settlement_failed` | Transfer failed | PLATFORM_OWNER |

### Commission Events

| Event Key | Trigger | Recipient |
|---|---|---|
| `commission_calculated` | Platform fee entry created | PLATFORM_OWNER |
| `commission_settlement_due` | Fee balance exceeds threshold | COMPANY_ADMIN |

### Provider Events

| Event Key | Trigger | Recipient |
|---|---|---|
| `provider_iban_missing` | Split blocked due to no IBAN | COMPANY_ADMIN |
| `provider_iban_verified` | Technician SHABA verified | TECHNICIAN |
| `provider_wage_posted` | Order completion wage CREDIT | TECHNICIAN |
| `provider_settlement_received` | Manual settlement DEBIT | TECHNICIAN |

### Refund Events

| Event Key | Trigger | Recipient |
|---|---|---|
| `refund_requested` | AdjustmentDocument created | COMPANY_ADMIN |
| `refund_approved` | AdjustmentDocument approved | CUSTOMER |
| `refund_issued` | Refund executed | CUSTOMER, COMPANY_ADMIN |

### Recovery Events

| Event Key | Trigger | Recipient |
|---|---|---|
| `financial_backfill_stuck` | Task attempts > threshold | PLATFORM_OWNER |
| `financial_backfill_resolved` | Task marked RESOLVED | PLATFORM_OWNER |

### Reconciliation Events

| Event Key | Trigger | Recipient |
|---|---|---|
| `payment_needs_reconciliation` | Ambiguous payment outcome | PLATFORM_OWNER |
| `reconciliation_resolved` | Manual resolution | PLATFORM_OWNER |

---

## Event Structure (Target)

```python
@dataclass
class FinancialEvent:
    event_key: str
    company_id: int
    invoice_id: int | None
    payment_id: int | None
    technician_id: int | None
    amount_rial: int | None
    timestamp: datetime
    metadata: dict
```

---

## Integration Points

| Consumer | Current | Target |
|---|---|---|
| In-app notifications | ✅ `apps/notifications/` | Extend with new events |
| SMS notifications | ✅ `apps/sms/` | Add templates for new events |
| Accounting system | ❌ | Future webhook/API |
| Analytics | ❌ | Future event stream |
| External APIs | ❌ | Future REST/webhook |

---

## Implementation Approach

Phase 1: اضافه کردن event keys به `EventKey` class و `EVENT_DEFINITIONS` dict
Phase 2: emit events from financial services (non-blocking)
Phase 3: external integrations (webhook, message broker)
