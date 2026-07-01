---
Title: Service Layer Architecture
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/orders/services.py, apps/payments/services.py, apps/tenants/services.py
Source of Truth: Code
Depends On: []
Related Documents: SYSTEM_ARCHITECTURE.md
Reusable Across Projects: Partially
---

# Service Layer Architecture

---

## Principle

All business logic lives in `services.py` files. Views are thin HTTP handlers.

```
View          → Receives HTTP request, validates inputs, calls service
Service       → Executes business logic, returns result
Model         → Data constraints only (validators, __str__, basic properties)
Template      → Presentation only, no business decisions
```

---

## Service Layer Rules

### 1 — Services own business decisions

Any decision that could change based on business rules goes in a service:
- Order status transitions
- Invoice creation and payment processing
- Platform fee calculation
- Notification triggering
- SMS sending decisions
- Technician assignment

### 2 — Services must not call views

Services are unaware of HTTP. They receive data objects, not request objects.

Exception: Services may receive `company` as a parameter (extracted from `request.company` by the view).

### 3 — Financial services have additional rules

```python
# Financial services must:
from django.db import transaction

@transaction.atomic
def process_payment(payment_id, company):
    payment = Payment.objects.select_for_update().get(id=payment_id, company=company)
    # ... use Decimal only, never float
    # ... create idempotency-keyed records
    # ... never modify existing ledger entries
```

- Use `transaction.atomic` wrapper
- Use `select_for_update()` where race conditions are possible
- Use `Decimal` for all monetary values — never `float`
- Use idempotency keys to prevent double-processing
- Treat `TechnicianLedgerEntry` as immutable (create reversing entries instead of editing)

---

## Service Files by App

| App | Service File | Key Responsibilities |
|---|---|---|
| `apps/orders/` | `services.py` | Order creation, status transitions, technician assignment |
| `apps/invoices/` | `services.py` | Invoice creation, status management |
| `apps/payments/` | `services.py` | Payment initiation, verification, reconciliation |
| `apps/payouts/` | `services.py` | Technician ledger entries, settlement |
| `apps/notifications/` | `services.py` | Notification creation and delivery |
| `apps/sms/` | `services.py` | SMS sending, credit management |
| `apps/tenants/` | `services.py` | Company operations, order from admin perspective |
| `apps/platform_core/` | `services.py` | Platform-level operations |

---

## Before Changing a Service

1. Read all callers (`grep` for function name)
2. Read related tests
3. Understand transaction boundaries
4. Preserve idempotency guarantees
5. Add tests before changing risky behavior

---

## Anti-Patterns to Avoid

```python
# WRONG — business logic in view
def order_complete_view(request, pk, **kwargs):
    order = Order.objects.get(id=pk, company=request.company)
    order.status = "DONE"  # ← business logic in view
    order.save()
    Notification.objects.create(...)  # ← side effect in view

# CORRECT — view calls service
def order_complete_view(request, pk, **kwargs):
    result = OrderService.complete_order(
        order_id=pk,
        company=request.company,
        completed_by=request.user
    )
    return redirect(...)
```

```python
# WRONG — float for money
fee = total_amount * 0.05  # ← float precision loss

# CORRECT — Decimal for money
from decimal import Decimal
fee = total_amount * Decimal("0.05")
```
