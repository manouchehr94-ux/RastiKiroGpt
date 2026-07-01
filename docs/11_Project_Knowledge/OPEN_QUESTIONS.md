---
Title: Open Questions
Layer: Project Knowledge
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Needs Verification
Depends On: []
Related Documents: KNOWN_RISKS.md
Reusable Across Projects: No
---

# Open Questions

Questions that need a product or technical decision before implementation.

---

## Product Questions

### Q1 — Customer Dashboard Plan

The customer dashboard (`/<code>/customer/`) was removed in Phase 24 and now redirects to the public company page. Is there a plan to restore it?

**Impact:** Customer UX is currently broken — customers see a marketing page after login instead of a dashboard.
**Decision needed from:** Product Owner
**See:** [../08_Site_Map/07_RECOMMENDED_NAVIGATION_REDESIGN.md](../08_Site_Map/07_RECOMMENDED_NAVIGATION_REDESIGN.md) Section 8 for redesign proposal

---

### Q2 — Technician SMS Enable/Disable Decision

Technician SMS for new order assignments is permanently disabled by `if False` in `apps/orders/technician_notifications.py:147`.

Is this intentional (i.e., SMS to technicians is not a supported feature) or a bug?

**Impact:** If enabled, will increase SMS credit consumption immediately.
**Decision needed from:** Product Owner

---

### Q3 — SaaS Billing Implementation Timeline

`apps/billing/` is a stub. When will SaaS subscription billing be implemented?

**Impact:** Companies can currently use the platform indefinitely without billing enforcement.

---

### Q4 — Orphan Pages Navigation

These pages exist but have no sidebar link:
- `/<code>/admin/financial-reports/summary/` (and 5 sub-pages)
- `/<code>/admin/payments/gateway-reconciliation/`
- `/owner-platform/technician-financial-verifications/`
- `/owner-platform/sms-template-requests/`
- `/owner-platform/password-reset-policy/`

Should these be added to sidebar navigation? Or are they intentionally "hidden" (admin-only, direct URL)?

---

## Technical Questions

### T1 — Subscription Limits Enforcement

Subscription limits (max technicians, max users, max orders per period) exist in the database but are not enforced in code. When should these be enforced?

---

### T2 — Cache Backend for Production

The notification throttle requires a shared cache backend in multi-worker deployments. What cache backend should be used in production (Redis, Memcached)?

---

### T3 — Payment Callback Race Condition

The payment callback URL is public. If a PSP sends multiple callbacks simultaneously (retry behavior), is there protection against creating duplicate platform commission entries?

**Note:** Service uses idempotency keys but this needs verification in `apps/payments/services.py`.

---

### T4 — Deprecated URLs

These URLs still work but appear deprecated:
- `/loginlogin/` and `/loginlogin/<path>` — legacy redirects
- `/<code>/login/` — redirects to unified login
- `/owner-platform/communication-templates/` — commented as deprecated in nav

Should these be removed (with proper redirects), or kept indefinitely for backwards compatibility?
