---
Title: Implementation Prompts
Layer: Prompt Library
Audience: AI + Human
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: Partially
---

# Implementation Prompts

Reusable prompts for implementing specific features or fixes.

---

## Prompt: Fix a P0 Security Bug

```
Fix the following P0 security bug:

PROJECT: Rasti SaaS — Django 5.1.3
PATH: D:\SaaSprojectService\Rasti chekFinal 10 tir
DOCS: Read docs/02_AI_Operating_System/AI_AGENT_START_HERE.md first

BUG: [P0-X description from docs/11_Project_Knowledge/KNOWN_RISKS.md]
FILE: [file:line]

Steps:
1. Read the file and confirm the bug exists exactly as described
2. Make the minimum change to fix the bug
3. Do NOT change any other code
4. Run: python manage.py test apps.[affected_app] --verbosity=2
5. Report: files changed, tests run, result, manual QA steps
```

---

## Prompt: Add a New Notification Event

```
Add a new notification event for [TRIGGER].

PROJECT: Rasti SaaS — Django 5.1.3
PATH: D:\SaaSprojectService\Rasti chekFinal 10 tir
DOCS: Read docs/04_Business_Rules/NOTIFICATION_RULES.md first

Context:
- 19 events are defined in apps/notifications/catalog.py
- Check if the event key already exists before adding
- Notification must be configurable per company (check/use existing pattern)
- Do NOT send SMS without checking credit

Steps:
1. Read apps/notifications/catalog.py — find the event key
2. Read an existing notification trigger for the same app as a pattern
3. Add the notification trigger in the correct service
4. Write a test that verifies the notification is created
5. Run: python manage.py test apps.notifications apps.[affected_app]
6. Report: files changed, test result
```

---

## Prompt: Add a New Admin View

```
Add a new admin view for [FEATURE].

PROJECT: Rasti SaaS — Django 5.1.3
PATH: D:\SaaSprojectService\Rasti chekFinal 10 tir
DOCS: Read docs/02_AI_Operating_System/AI_AGENT_START_HERE.md first
DOCS: Read docs/03_Architecture/PERMISSIONS.md

Requirements:
- View URL: /<code>/admin/[path]/
- Access: COMPANY_ADMIN only (or: COMPANY_ADMIN + COMPANY_STAFF)
- Template: templates/tenants/[name].html
- Business logic: in apps/tenants/services.py or apps/[relevant_app]/services.py

Mandatory:
- Add @require_tenant_role("COMPANY_ADMIN") to the view
- All queries must include company=request.company
- Add URL to apps/tenants/urls.py under the admin URL patterns
- Add URL to docs/08_Site_Map/01_URL_INVENTORY.md

Report:
- Files changed (with line numbers)
- URL added (name=, path=)
- Tests written and run
```

---

## Prompt: Add a New Order Status Transition

```
Add a new order status transition: [FROM] → [TO].

PROJECT: Rasti SaaS — Django 5.1.3
PATH: D:\SaaSprojectService\Rasti chekFinal 10 tir
DOCS: Read docs/04_Business_Rules/ORDER_RULES.md first
DOCS: Read docs/05_Workflows/ORDER_LIFECYCLE.md first
ADR: Read docs/07_ADR/ADR-007-Financial-Event-Timeline.md if this triggers financial events

Steps:
1. Verify the transition is in the allowed list in ORDER_RULES.md
2. If not in the list, STOP and confirm with user before proceeding
3. Read apps/orders/services.py — find the existing pattern for status transitions
4. Add the new transition using select_for_update()
5. Create OrderStatusLog entry
6. Trigger appropriate notification (check catalog.py)
7. Write test for the transition
8. Run: python manage.py test apps.orders --verbosity=2
9. Update ORDER_RULES.md and ORDER_LIFECYCLE.md if the state machine changed
```
