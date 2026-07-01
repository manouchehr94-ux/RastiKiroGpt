---
Title: Backup Procedures
Layer: Operations
Audience: Human + DevOps
Status: Active
Last Verified: 2026-07-01
Verified Against: 05_Deployment/BACKUP.md
Source of Truth: Mixed
Depends On: ENVIRONMENTS.md
Related Documents: ROLLBACK.md
Reusable Across Projects: Partially
---

# Backup Procedures

---

## When to Take a Backup

**Mandatory:**
- Before every production deployment
- Before running migrations that affect financial data
- Before any bulk data operation
- Before any schema change to: `Order`, `Invoice`, `Payment`, `TechnicianLedgerEntry`, `CompanyPlatformFeeEntry`

**Recommended:**
- Daily scheduled backup (configure via cron or cloud provider)
- Before restoring from a backup (backup the current state first)

---

## What to Back Up

| Data | Priority | Notes |
|---|---|---|
| PostgreSQL database | CRITICAL | Full dump including all tables |
| Media files (KYC documents) | HIGH | If KYC files are stored locally |
| `.env` file | HIGH | Never commit to git |
| Migration state | MEDIUM | Document current migration head |

---

## Database Backup

```bash
# PostgreSQL full dump
pg_dump -U <db_user> -h <db_host> <db_name> > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed
pg_dump -U <db_user> -h <db_host> <db_name> | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

---

## Migration State Check

Before backup, record the current migration head:
```bash
python manage.py showmigrations --plan | grep "\[X\]" | tail -5
```

---

## Restore (Emergency)

```bash
# Stop application
# Restore database
psql -U <db_user> -h <db_host> <db_name> < backup_YYYYMMDD_HHMMSS.sql
# Run migrations if needed
python manage.py migrate
# Restart application
```

---

## Financial Data Protection

- Never delete financial records (`TechnicianLedgerEntry`, `CompanyPlatformFeeEntry`, `Payment`, `Invoice`)
- Financial records that are incorrect should be reversed via new entries (ADR-004)
- Backup validation: verify row counts of financial tables match expected after restore
