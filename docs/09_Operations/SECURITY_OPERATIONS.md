---
Title: Security Operations
Layer: Operations
Audience: Human + DevOps
Status: Active
Last Verified: 2026-07-01
Verified Against: 11_Project_Knowledge/KNOWN_RISKS.md, config/settings/production.py
Source of Truth: ADR + Policy
Depends On: ENVIRONMENTS.md
Related Documents: ../11_Project_Knowledge/KNOWN_RISKS.md, ../03_Architecture/PERMISSIONS.md
Reusable Across Projects: Partially
---

# Security Operations

---

## Critical Open Security Issues

These must be resolved before production launch:

| ID | Issue | File | Risk |
|---|---|---|---|
| P0-1 | `admin_operator_list` missing permission decorator | `apps/platform_core/views.py` | Any authenticated user can view operator list |
| P0-2 | JWT logout does not invalidate token | `apps/accounts/views.py` | Stolen tokens remain valid after logout |
| P0-3 | Hardcoded password "123456" | `apps/accounts/services.py` | New accounts created with known password |

See [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md) for fix instructions.

---

## Security Checks Before Deployment

- [ ] `python manage.py check --deploy` passes (catches common misconfigurations)
- [ ] `DEBUG = False` in production settings
- [ ] `SECRET_KEY` is random and not committed to git
- [ ] `ALLOWED_HOSTS` is not `['*']`
- [ ] Database credentials are from environment variables
- [ ] SMS API keys are from environment variables
- [ ] Payment gateway keys are from environment variables
- [ ] `CSRF_COOKIE_SECURE = True` (if HTTPS)
- [ ] `SESSION_COOKIE_SECURE = True` (if HTTPS)

---

## Django Security Settings (Production Required)

```python
# config/settings/production.py
DEBUG = False
SECRET_KEY = env('DJANGO_SECRET_KEY')
ALLOWED_HOSTS = ['your-domain.com']

# HTTPS settings (if deployed with HTTPS)
SECURE_SSL_REDIRECT = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

---

## Multi-Tenant Security Monitoring

Signs of cross-tenant access attempts (monitor error logs):
- 403 responses on URLs with another company's `company_code`
- 404 responses for object IDs that exist in another company
- Any spike in 403/404 on admin URLs

If a cross-tenant access attempt is detected:
1. Check which user and IP made the request
2. Check if the user had elevated access
3. Audit the affected company's data for unauthorized changes
4. Report to Platform Owner

---

## Incident Response

### Payment Incident
1. Check `NEEDS_RECONCILIATION` count
2. If suspicious: suspend payment processing temporarily
3. Audit all payments in the affected window
4. Create correcting ledger entries (never delete/edit existing)
5. Report to Platform Owner with full audit trail

### Permission Bypass Incident
1. Identify the request in logs (user, URL, timestamp)
2. Determine if data was accessed or modified
3. If modified: create correcting entries, do not delete
4. Fix the permission bug (add missing decorator)
5. Add regression test
6. Document in KNOWN_RISKS.md

### Credential Compromise
1. Rotate `SECRET_KEY` (invalidates all sessions)
2. Rotate database credentials
3. Rotate payment gateway credentials
4. Rotate SMS API credentials
5. Review access logs for unauthorized use

---

## Access Control Summary

| Role | Can Access |
|---|---|
| `PLATFORM_OWNER` | All companies, all data |
| `COMPANY_ADMIN` | Their company only |
| `COMPANY_STAFF` | Their company orders/customers |
| `TECHNICIAN` | Their assigned orders only |
| `CUSTOMER` | Their own orders/invoices |
| Anonymous | Public form, public invoice link |

Any violation of this table is a critical security bug.
