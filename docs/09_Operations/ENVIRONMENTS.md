---
Title: Environments
Layer: Operations
Audience: Human + DevOps
Status: Active
Last Verified: 2026-07-01
Verified Against: config/settings/, 99_AUDIT_2026_06_30/08_PRODUCTION_READINESS_GAP_ANALYSIS.md
Source of Truth: Code
Depends On: []
Related Documents: DEPLOYMENT.md
Reusable Across Projects: No
---

# Environments

---

## Environment Configuration Files

| File | Purpose |
|---|---|
| `config/settings/base.py` | Base settings for all environments |
| `config/settings/development.py` | Local development overrides |
| `config/settings/production.py` | Production overrides |

Select environment via `DJANGO_SETTINGS_MODULE` environment variable.

---

## Critical Settings per Environment

### Development

```python
DEBUG = True
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", ...}}
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
```

### Production

```python
DEBUG = False
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", ...}}
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # Must be set
```

**Warning (P0-4):** `config/settings/base.py:19` currently has `ALLOWED_HOSTS = ["*"]` active. If `DJANGO_ALLOWED_HOSTS` environment variable is not set in production, the setting becomes `[""]` which rejects all requests.

---

## Required Environment Variables (Production)

| Variable | Required | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Django secret key |
| `DJANGO_SETTINGS_MODULE` | Yes | `config.settings.production` |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated allowed hosts |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `DJANGO_DEBUG` | No | Default: False in production |

Additional variables for SMS provider, payment gateway, email — Needs Verification in `config/settings/production.py`.

---

## Staging Environment

A staging environment should mirror production for:
- Testing payment gateway integration with real PSP sandbox
- Verifying SMS sending before enabling in production
- Manual QA of the full order lifecycle

**Note:** Staging environment does not exist as of 2026-07-01. Setting one up is recommended before first production deployment.
