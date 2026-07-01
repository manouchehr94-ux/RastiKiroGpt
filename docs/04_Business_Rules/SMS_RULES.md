---
Title: SMS Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/sms/models.py, apps/sms/services.py, apps/orders/technician_notifications.py
Source of Truth: Code
Depends On: []
Related Documents: NOTIFICATION_RULES.md
Reusable Across Projects: No
---

# SMS Business Rules

---

## SMS Architecture

Each company has its own SMS wallet (credit) and SMS configuration:
- SMS credit balance stored per company
- Credit must be checked before sending
- SMS sending uses a configurable provider (per platform or per company)

---

## SMS Credit Rules

- Company must have sufficient credit to send SMS
- Credit is deducted per message sent
- Platform Owner manages company SMS credit at `/owner-platform/sms-billing/`
- Company Admin views SMS wallet at `/<code>/admin/sms-credit/`

---

## SMS Template System

Companies can define custom SMS templates for notification events.

Templates are managed at:
- `/<code>/admin/sms/templates/` — company-level templates
- `/owner-platform/sms-template-requests/` — template change requests (NOT in sidebar — orphan page)

**Known issue:** Platform-level SMS (subscription alerts, credit warnings) always uses plain fallback text instead of the configured templates. The template system is defined but not used for platform messages.

---

## Technician SMS Notifications

**Critical Bug (permanently disabled):**

`apps/orders/technician_notifications.py:147`:
```python
if False and send_sms and notification_settings.send_sms_on_new_order:
```

This `if False` condition permanently disables SMS notifications to technicians for new order assignments, regardless of company settings. This is a bug, not an intentional feature flag.

**Resolution needed:** Remove `if False and` to restore normal behavior. Test thoroughly before doing so.

---

## SMS Admin Management (Company Level)

SMS management for company admins at `/<code>/admin/sms/`:
- Outbox: `/<code>/admin/sms/outbox/` — sent messages
- Inbox: `/<code>/admin/sms/inbox/` — received messages (if inbound is configured)
- Templates: `/<code>/admin/sms/templates/`
- Diagnostics: `/<code>/admin/sms/diagnostics/`
- Bulk retry: `/<code>/admin/sms/outbox/bulk-retry/` (no rate limit — risk of provider abuse)

---

## SMS for Platform (Platform Owner Level)

SMS operations for Platform Owner at `/owner-platform/`:
- SMS billing: `/owner-platform/sms-billing/`
- Platform SMS outbox: `/owner-platform/sms/outbox/`
- Provider settings: `/owner-platform/sms/provider/`
- Message types: `/owner-platform/sms/message-types/`
