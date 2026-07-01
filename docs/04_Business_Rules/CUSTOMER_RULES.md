---
Title: Customer Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/tenants/views.py, apps/invoices/views.py, apps/payments/urls.py
Source of Truth: Code
Depends On: []
Related Documents: INVOICE_RULES.md, PAYMENT_RULES.md
Reusable Across Projects: No
---

# Customer Business Rules

---

## What is a Customer?

The person or business receiving service from a tenant company. The customer pays the tenant company, not Rasti Service directly.

See [../00_Project/GLOSSARY.md](../00_Project/GLOSSARY.md).

---

## Customer Role

A Customer is a user with role `CUSTOMER`. They belong to exactly one company.

---

## Customer Access

After login (`/login/?company=<code>`), customers are redirected to `/<code>/invoices/`.

Accessible pages:
- `/<code>/invoices/` — list of own invoices
- `/<code>/invoices/<id>/` — invoice detail
- `/<code>/invoices/<id>/pay/` — initiate payment
- `/<code>/payments/` — payment history

---

## Customer Dashboard Status

**Phase 24 Change:** The customer dashboard at `/<code>/customer/` was removed in Phase 24.

Current behavior:
- Navigating to `/<code>/customer/` redirects to the public company page (`/<code>/`)
- The template `dashboard/customer_home.html` still exists but is not directly accessible
- Customers are directed to `/<code>/invoices/` after login

This is intentional but creates a poor user experience. Redesign is recommended (see [../08_Site_Map/07_RECOMMENDED_NAVIGATION_REDESIGN.md](../08_Site_Map/07_RECOMMENDED_NAVIGATION_REDESIGN.md)).

---

## Customer Registration

Customers are registered by company admins or via the public service request form. Self-registration via portal is Needs Verification.

---

## Customer Identification in API

**Known Bug (P0-5):**
`apps/api/views.py:311` attempts `Customer.objects.create(name=...)` but `Customer` model does not have a `name` field — it has `first_name` and `last_name`. This causes a `TypeError` at runtime in the API customer creation endpoint.
