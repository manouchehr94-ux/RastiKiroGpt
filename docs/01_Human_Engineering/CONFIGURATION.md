---
Title: Configuration Guide
Layer: Human Engineering
Audience: Human Developer + DevOps
Status: Needs Verification
Last Verified: 2026-07-01
Verified Against: config/settings/, 09_Operations/ENVIRONMENTS.md
Source of Truth: Code
Depends On: []
Related Documents: LOCAL_DEVELOPMENT.md, ../09_Operations/ENVIRONMENTS.md
Reusable Across Projects: No
---

# Configuration Guide

Configuration is managed through split Django settings files in `config/settings/`.

---

## Settings Files

| File | Purpose | Committed |
|---|---|---|
| `config/settings/base.py` | Shared settings for all environments | Yes |
| `config/settings/local.py` | Local developer overrides | No (gitignored) |
| `config/settings/production.py` | Production settings | Yes (no secrets) |
| `config/settings/staging.py` | Staging environment | Yes (if exists) |

---

## Setting the Active Settings Module

```powershell
# Windows PowerShell (local)
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"

# Linux/Mac (production server)
export DJANGO_SETTINGS_MODULE="config.settings.production"
```

Or in the WSGI/ASGI file: `config/wsgi.py` or via Gunicorn `--env` flag.

---

## Required Environment Variables

These must be set in the environment (never hardcode in settings files):

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key (long random string) |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | Database host (default: localhost) |
| `DB_PORT` | Database port (default: 5432) |
| `SMS_API_KEY` | SMS gateway API key |
| `PAYMENT_GATEWAY_KEY` | PSP merchant key |
| `PAYMENT_GATEWAY_SECRET` | PSP merchant secret |

Needs Verification — check `config/settings/production.py` for exact variable names.

---

## Company-Level Configuration

Each company has its own settings managed through the admin panel:

| Setting | Location | Purpose |
|---|---|---|
| Company name, code | `Company` model | Tenant identity |
| Service request form enabled | `Company.service_request_enabled` | Enable/disable public form |
| SMS credit | `CompanySMSCredit` | SMS sending quota |
| Payment gateway | `PaymentGateway` | PSP configuration per company |
| Financial policy | `CompanyFinancialPolicy` | Commission and wage rules |

---

## Feature Flags

The project does not currently have a formal feature flag system.

Provisional flags (managed in settings or code):
- Public service request form: controlled per-company in database
- SMS: controlled by credit balance and company settings
- Payment gateway: controlled per-company via `PaymentGateway` model

---

## Development vs Production Differences

| Setting | Development | Production |
|---|---|---|
| `DEBUG` | `True` | `False` (required) |
| `ALLOWED_HOSTS` | `['*']` or `['localhost']` | Specific domain(s) only |
| `DATABASE` | Local PostgreSQL | Remote PostgreSQL |
| `EMAIL_BACKEND` | Console backend | SMTP |
| `STATIC_FILES` | Django served | Nginx or CDN |
| `HTTPS` | No | Yes (with SECURE_ settings) |
