---
Title: Maintenance Guide
Layer: Human Engineering
Audience: Human Developer + DevOps
Status: Active
Last Verified: 2026-07-01
Verified Against: config/settings/, apps/*/models.py
Source of Truth: Mixed
Depends On: CONFIGURATION.md, LOCAL_DEVELOPMENT.md
Related Documents: ../09_Operations/MONITORING.md, ../09_Operations/BACKUP.md
Reusable Across Projects: Partially
---

# Maintenance Guide

Routine maintenance tasks for keeping the Rasti platform healthy.

---

## Regular Maintenance Tasks

### Daily
- [ ] Check `NEEDS_RECONCILIATION` payment count (Platform Owner task)
- [ ] Review error logs for 500s
- [ ] Check SMS credit balance for active companies

### Weekly
- [ ] Review `IN_PROGRESS` orders older than 48 hours
- [ ] Check database size and growth
- [ ] Verify backup completion

### Monthly
- [ ] Run `python manage.py check --deploy` against production config
- [ ] Review `KNOWN_RISKS.md` for any new risks
- [ ] Test rollback procedure in staging

---

## Database Maintenance

```bash
# Check database size
psql -U <user> -c "SELECT pg_size_pretty(pg_database_size('rasti_db'));"

# List table sizes (find largest tables)
psql -U <user> -d rasti_db -c "
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;"

# Analyze statistics (helps query planner)
psql -U <user> -d rasti_db -c "ANALYZE;"
```

---

## Log Rotation

Application logs should be rotated to prevent disk exhaustion. Configure in Nginx and the application server (Gunicorn).

```bash
# Logrotate example for Gunicorn log
/var/log/rasti/gunicorn.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

---

## SMS Credit Management

SMS credits are per-company. When credits run out:
- SMS notifications stop silently
- The system does not raise an error (H-2 bug — untriggered notification)
- Operators do not automatically receive an alert

Maintenance: Monitor credit balance weekly for active companies.

To check via admin panel: `/{code}/admin/settings/sms/` or equivalent.

---

## Clearing Expired Sessions

Django sessions accumulate in the database:

```bash
python manage.py clearsessions
```

Run weekly or monthly.

---

## Checking for Migration Drift

After any code changes that touch models:

```bash
python manage.py makemigrations --check
# Should output nothing if all model changes have migrations
```

If this outputs migration suggestions that are not committed, the model and migrations are out of sync — a critical deployment bug.

---

## Financial Data Audit

Monthly audit to verify financial integrity:

```python
# In Django shell
python manage.py shell

from apps.payouts.models import TechnicianLedgerEntry
from decimal import Decimal

# Check for any zero-amount entries (should not exist)
zero_entries = TechnicianLedgerEntry.objects.filter(amount=Decimal('0'))
print(f"Zero-amount entries: {zero_entries.count()}")

# Check for negative entries (should exist only as corrections)
negative_entries = TechnicianLedgerEntry.objects.filter(amount__lt=Decimal('0'))
print(f"Negative entries: {negative_entries.count()}")
```

Report anomalies to Platform Owner immediately.
