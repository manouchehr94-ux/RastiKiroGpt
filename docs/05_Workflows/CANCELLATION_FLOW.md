---
Title: Cancellation Flow
Layer: Workflows
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/orders/models.py, apps/tenants/views_admin.py
Source of Truth: Code
Depends On: ../04_Business_Rules/ORDER_RULES.md
Related Documents: ORDER_LIFECYCLE.md
Reusable Across Projects: No
---

# Cancellation Flow

---

## Cancellation Request States

An order can only be cancelled through the `CANCEL_REQUESTED` state.

```
Any active state → CANCEL_REQUESTED → CANCELLED
                                    ↘ Back to IN_PROGRESS (if rejected)
```

Active states that can transition to CANCEL_REQUESTED:
- `WAITING`
- `IN_PROGRESS`

Orders in `NEW` or `PENDING_REVIEW` can be directly cancelled (no CANCEL_REQUESTED step).

---

## Cancellation Request Flow

```
Step 1: Customer or Admin requests cancellation
  → URL: /<code>/admin/orders/<id>/cancel-request/
  → Order → CANCEL_REQUESTED

Step 2: Admin reviews cancellation request
  → List at: /<code>/admin/orders/ (filtered by CANCEL_REQUESTED)

Step 3a: Admin approves cancellation
  → URL: /<code>/admin/orders/<id>/cancel-approve/
  → Order → CANCELLED

Step 3b: Admin rejects cancellation
  → URL: /<code>/admin/orders/<id>/cancel-reject/
  → Order → IN_PROGRESS (resumes)
```

---

## Return to Cycle

URL: `/<code>/admin/orders/<id>/return-to-cycle/`

This URL name is ambiguous — "return to cycle" likely means restoring an order back to the active workflow from CANCEL_REQUESTED. Needs Verification — inspect `apps/tenants/views_admin.py`.

---

## Terminal Cancellation

Once `CANCELLED`:
- Order cannot be reopened
- Technician ledger entries related to the order may be reversed
- Invoice (if any) should be voided

---

## Notification on Cancellation

When order is cancelled:
- Customer should be notified (event: `order_cancelled`)
- Technician should be notified

**Known issue:** `order_cancelled` notification event is defined in the catalog but may not be triggered. Needs Verification.
