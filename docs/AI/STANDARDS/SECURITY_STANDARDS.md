# Security Standards

## Multi-Tenant

No cross-company leakage.

Every tenant query must be scoped.

---

## Public Pages

Expose only public-safe data.

No admin chrome.

No internal links.

---

## Payments

Callback must be idempotent.

Payment amount and reference must be verified.

---

## Sensitive Files

KYC and private media must not be publicly accessible without authorization.
