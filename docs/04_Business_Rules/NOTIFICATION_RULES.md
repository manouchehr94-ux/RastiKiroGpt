---
Title: Notification Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/notifications/catalog.py, apps/notifications/services.py
Source of Truth: Code
Depends On: []
Related Documents: SMS_RULES.md, ../05_Workflows/NOTIFICATION_FLOW.md
Reusable Across Projects: No
---

# Notification Business Rules

---

## Notification System Design

Rasti has an in-app notification system separate from SMS.

Notifications are:
- Per-company configurable (each company can enable/disable specific events)
- Role-targeted (admin gets different notifications than technician)
- Stored in the database and shown in the UI

---

## Notification Event Catalog

19 notification event types are defined in `apps/notifications/catalog.py`.

**Known issue:** Not all 19 events are triggered in the codebase. As of the 2026-06-30 audit:
- Events that ARE triggered: Needs Verification (inspect catalog.py and grep for event keys)
- Events that are DEFINED but may not be triggered include:
  - `order_cancelled`
  - `order_rescheduled`
  - `order_cancel_requested_customer`

---

## Notification Roles

Each notification event targets a specific role:
- Admin/Operator sees: new requests, cancellation requests, payment confirmations
- Technician sees: new order assignment, order cancellation
- Customer sees: (currently no dedicated notification system — Phase 24 removed customer panel)

---

## Per-Company Configuration

Companies can configure which notification events generate:
1. In-app notification
2. SMS message

Configuration at: `/<code>/admin/settings/notifications/` and `/<code>/admin/communication-settings/`

---

## Notification Throttle

There is a throttle mechanism to prevent duplicate notifications (e.g., multiple status change notifications in quick succession).

**Known issue:** The throttle uses Django's cache backend, which is not configured for multi-worker production environments. In a multi-worker deployment, throttle state is not shared between workers.

---

## Payment Success Notification Keys

Payment success events use role-specific event keys (not a single shared key). This was fixed in a recent commit. If adding payment-related notifications, use the role-specific variant.
