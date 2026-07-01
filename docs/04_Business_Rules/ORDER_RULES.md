---
Title: Order Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/orders/models.py, apps/orders/services.py, apps/tenants/services.py
Source of Truth: Code
Depends On: []
Related Documents: ../05_Workflows/ORDER_LIFECYCLE.md, ../07_ADR/ADR-007-Financial-Event-Timeline.md
Reusable Across Projects: No
---

# Order Business Rules

---

## What is an Order?

An Order is the core operational object. It represents a service job after creation or approval. Every Order belongs to exactly one Company and may have one active Technician.

See [../00_Project/GLOSSARY.md](../00_Project/GLOSSARY.md) for the full definition.

---

## Order Status Machine

Status labels (Persian, as shown in UI):

| Code | Persian Label | English Meaning |
|---|---|---|
| `PENDING_REVIEW` | در انتظار تایید اپراتور | Public request awaiting operator approval |
| `NEW` | جدید | Approved, no technician yet |
| `WAITING` | در انتظار انجام خدمت | Technician assigned, awaiting acceptance |
| `IN_PROGRESS` | در حال انجام خدمت | Technician accepted, work in progress |
| `DONE` | انجام شده | Work completed |
| `CANCEL_REQUESTED` | درخواست لغو | Cancellation requested (by customer or admin) |
| `CANCELLED` | لغو شده | Order cancelled |

---

## Valid Status Transitions

```
PENDING_REVIEW → NEW              (operator approves public request)
NEW → WAITING                     (technician assigned)
NEW → CANCELLED                   (admin cancels)
WAITING → IN_PROGRESS             (technician accepts)
WAITING → NEW                     (technician removed / reassigned)
WAITING → CANCEL_REQUESTED        (cancellation requested)
IN_PROGRESS → DONE                (technician completes)
IN_PROGRESS → CANCEL_REQUESTED    (cancellation requested)
CANCEL_REQUESTED → CANCELLED      (admin approves cancellation)
CANCEL_REQUESTED → IN_PROGRESS    (cancellation rejected, work resumes)
```

Terminal states (no further transitions): `DONE`, `CANCELLED`

---

## Order Creation Paths

### Path 1 — Public Service Request

1. Customer fills form at `/<code>/request/`
2. `ServiceRequest` record created
3. `Order` created with status `PENDING_REVIEW`
4. Operator reviews at `/<code>/admin/requests/`
5. Operator approves → Order status becomes `NEW`

### Path 2 — Direct Admin / Phone Order

Admin creates order directly at `/<code>/admin/orders/create/`:
- If no technician assigned: status = `NEW`
- If technician assigned at creation: status = `WAITING`

---

## Technician Assignment Rules

- One active technician per order at any time
- Assigning a technician moves order from `NEW` → `WAITING`
- Removing a technician moves order back to `NEW`
- Technician accepts → `IN_PROGRESS`
- Technician cannot be assigned to `DONE` or `CANCELLED` orders

---

## Order Protection Rules

- Completed (`DONE`) orders must not be casually mutated
- Cancelled (`CANCELLED`) orders must not be casually mutated
- Only the platform owner or a specific admin action can modify terminal orders
- Order deletion is forbidden (use cancellation instead)

---

## Financial Events Triggered by Order

| Order Event | Financial Effect |
|---|---|
| Order status → `DONE` | Technician ledger entry eligible (if wage configured) |
| Invoice created for DONE order | Invoice issued |
| Invoice → `PAID` | Payment verified; platform commission created if applicable |
| Technician removed | Wage ledger entry for removed technician may be reversed |

See [../07_ADR/ADR-007-Financial-Event-Timeline.md](../07_ADR/ADR-007-Financial-Event-Timeline.md).

---

## Race Condition Protection

Order status transitions use database-level locking:
```python
order = Order.objects.select_for_update().get(id=order_id, company=company)
```

This prevents two simultaneous requests from both completing or cancelling the same order.

---

## Notification Events on Order

| Transition | Notification Triggered |
|---|---|
| `PENDING_REVIEW` → `NEW` | Needs Verification |
| `NEW` → `WAITING` | Tech notified of assignment |
| `WAITING` → `IN_PROGRESS` | Needs Verification |
| `IN_PROGRESS` → `DONE` | Admin/customer notified |
| → `CANCELLED` | Customer notified |

**Note:** 19 notification event types are defined in the catalog; not all are triggered. See [NOTIFICATION_RULES.md](NOTIFICATION_RULES.md).
