---
Title: Company (Tenant) Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/tenants/models.py, apps/platform_core/views.py
Source of Truth: Code
Depends On: []
Related Documents: ../03_Architecture/MULTI_TENANCY.md, ../07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md
Reusable Across Projects: No
---

# Company (Tenant) Business Rules

---

## What is a Tenant Company?

A company that subscribes to Rasti Service and uses it to manage customers, orders, technicians, invoices, payments, SMS, and reports.

The tenant company owns the customer relationship and service liability. Rasti Service is the SaaS infrastructure provider, not the service seller.

See [../07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md](../07_ADR/ADR-001-Rasti-Is-SaaS-Provider.md).

---

## Company Registration

Public registration form at `/register/` (or public routes).

Registration flow:
1. Company fills registration form
2. Platform Owner reviews and activates the company
3. Company Admin receives login credentials

---

## Company Activation and Deactivation

- Only Platform Owner can activate/deactivate a company
- Deactivated company: all tenant URLs return 404 (middleware blocks access)
- Deactivation does not delete data

---

## Company Subscription (SaaS Billing)

**Status: STUB — Not Implemented**

`apps/billing/services.py` contains only a 6-line stub. SaaS subscription logic (subscription plans, plan limits, billing cycles) is NOT implemented.

Defined but not enforced:
- Maximum technicians per subscription
- Maximum users per subscription
- Maximum orders per period

---

## Company Settings (Managed by Company Admin)

Company Admin manages at `/<code>/admin/settings/`:
- Company information and branding
- Custom order fields
- Service categories and items
- Operator users
- Payment gateway and KYC profile
- SMS templates and notification events
- Communication event settings

---

## Company Brandings and Public Page

Each company has a public-facing page at `/<code>/` with:
- Company logo/branding
- Service request form (if enabled by admin)
- Contact information

---

## Service Request Form Enable/Disable

The public service request form at `/<code>/request/` can be enabled or disabled per company via `CompanySettings.is_request_form_enabled`. When disabled, the form shows a "not available" message.

---

## Company Code

- The `company_code` (slug) is the URL identifier for the company
- It is assigned at registration and cannot be changed without URL impact
- It appears in all tenant URLs: `/<company_code>/admin/`, etc.
