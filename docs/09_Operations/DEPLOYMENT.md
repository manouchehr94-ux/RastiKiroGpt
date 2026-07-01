---
Title: Deployment Guide
Layer: Operations
Audience: Human + DevOps
Status: Active
Last Verified: 2026-07-01
Verified Against: 05_Deployment/DEPLOYMENT_GUIDE.md, config/settings/production.py
Source of Truth: Code + Policy
Depends On: ENVIRONMENTS.md, BACKUP.md
Related Documents: ROLLBACK.md, MONITORING.md, ../05_Workflows/RELEASE_FLOW.md
Reusable Across Projects: Partially
---

# Deployment Guide

---

## Deployment Prerequisites

Before any deployment:
1. All tests pass: `python manage.py test --verbosity=1`
2. `python manage.py check --deploy` returns no errors
3. Database backup completed (see [BACKUP.md](BACKUP.md))
4. Rollback plan documented (see [ROLLBACK.md](ROLLBACK.md))
5. P0 bugs reviewed — no new critical bugs introduced

---

## Environment Overview

| Environment | Settings File | Purpose |
|---|---|---|
| Local | `config/settings/local.py` | Development |
| Staging | `config/settings/staging.py` | Pre-production testing |
| Production | `config/settings/production.py` | Live |

See [ENVIRONMENTS.md](ENVIRONMENTS.md) for required environment variables per environment.

---

## Production Server Requirements

Needs Verification — confirm with infrastructure:
- Web server: Nginx (recommended) proxying to Gunicorn
- Database: PostgreSQL 14+
- Python: 3.11.9
- Static files: Served by Nginx or object storage (S3/MinIO)
- Process manager: systemd or supervisor

---

## Deployment Steps

### 1. Backup
```bash
pg_dump -U <user> <dbname> > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Pull Code
```bash
git pull origin main
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 5. Apply Migrations
```bash
python manage.py showmigrations  # Verify what will run
python manage.py migrate
python manage.py showmigrations  # Verify all applied
```

### 6. Restart Application
```bash
# Systemd
sudo systemctl restart rasti

# Or Gunicorn directly
pkill -f gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --daemon
```

### 7. Verify
```bash
python manage.py check
curl http://localhost:8000/login/  # Should return 200
```

Follow the smoke checklist in [../05_Workflows/RELEASE_FLOW.md](../05_Workflows/RELEASE_FLOW.md).

---

## Critical Production Settings

```python
# config/settings/production.py must have:
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
SECRET_KEY = env('SECRET_KEY')  # From environment variable
DATABASES = {...}  # From environment variables
```

Never deploy with `DEBUG = True`.

---

## Post-Deployment Monitoring

For the first 30 minutes after deployment:
- Watch error logs for 500s
- Check `NEEDS_RECONCILIATION` payment count (should not increase)
- Monitor SMS send queue
- Verify technician panel loads

See [MONITORING.md](MONITORING.md).
