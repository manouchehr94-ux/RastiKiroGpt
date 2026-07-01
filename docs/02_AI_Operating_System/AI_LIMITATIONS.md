---
Title: AI Limitations — When to Inspect Code
Layer: AI Operating System
Audience: AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code
Reusable Across Projects: Partially
---

# AI Limitations

This document lists situations where an AI agent must inspect the current code rather than trusting documentation.

---

## Docs Cannot Be Trusted For

### 1. Current implementation status

Docs describe intended behavior. Code is what runs in production.

**Always verify in code:**
- Whether a decorator is actually applied to a view
- Whether a service method was actually added or removed
- Whether a migration was actually run
- Whether a field actually exists on a model
- Whether a template actually extends the expected layout

### 2. Site Map / URL accuracy

The site map docs were verified on 2026-07-01. Any URL change since then may not be reflected.

**Always verify** when adding or changing routes:
```bash
# Check what URLs exist
python manage.py show_urls | grep <pattern>
```

### 3. Test coverage

The test coverage map was generated from a snapshot. New code may not have tests.

**Always check:**
```bash
python manage.py test apps.<changed_app> --verbosity=2
```

### 4. Notification catalog

19 notification events are defined in the catalog. Not all are triggered. Before adding a new notification, verify the event key exists in `apps/notifications/catalog.py`.

### 5. Migration state

Never assume the database schema matches the models. Check:
```bash
python manage.py showmigrations <app_name>
python manage.py migrate --check
```

---

## Situations Requiring Code Inspection (Not Docs)

| Situation | File to inspect |
|---|---|
| Confirming a decorator signature | `apps/accounts/permissions.py` |
| Confirming order status values | `apps/orders/models.py` (choices) |
| Confirming payment status values | `apps/payments/models.py` (choices) |
| Confirming model fields | Relevant `apps/*/models.py` |
| Confirming service method exists | Relevant `apps/*/services.py` |
| Confirming URL namespace | Relevant `apps/*/urls*.py` |
| Confirming template exists | `templates/` folder |
| Confirming migration history | `apps/*/migrations/` |
| Confirming settings value | `config/settings/base.py` or `production.py` |

---

## Docs That Are Known to Need Verification

| Document | Why |
|---|---|
| `08_Site_Map/05_TEMPLATE_MAP.md` | Template map incomplete — some templates not yet mapped |
| `03_Architecture/DATABASE_MODEL.md` | Model fields may drift — always verify in code |
| `04_Business_Rules/PAYOUT_RULES.md` | Payout system partially implemented |
| `04_Business_Rules/COMPANY_RULES.md` | Subscription limits not enforced in code |

---

## When to Stop and Ask the User

Stop and ask the user if:
- You find a conflict between docs and code that affects the task
- You find a behavior in code that is undocumented and potentially intentional
- You are about to change financial, security, or permission logic
- You find a pattern you don't recognize and can't find in docs
- The task scope is larger than what was initially described
