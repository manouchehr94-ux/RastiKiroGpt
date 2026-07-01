---
Title: Rollback Procedures
Layer: Operations
Audience: Human + DevOps
Status: Active
Last Verified: 2026-07-01
Verified Against: 05_Deployment/ROLLBACK.md
Source of Truth: Mixed
Depends On: ENVIRONMENTS.md, BACKUP.md
Related Documents: DEPLOYMENT.md
Reusable Across Projects: Partially
---

# Rollback Procedures

---

## Pre-Deployment Questions (Answer Before Deploying)

Every release must answer:
1. Can the code change be reverted? (git revert / git checkout)
2. Can the migration be reversed safely? (check `migrations/0XXX_xxx.py` `reverse_sql`)
3. Is the data migration destructive? (column removal, data deletion, type change)
4. What is the manual recovery plan if rollback fails?

If any answer is "no" or "unknown" — escalate before deploying.

---

## Code Rollback

```bash
# Identify the last good commit
git log --oneline -10

# Revert to last good state
git checkout <good-commit-hash>
# OR
git revert HEAD  # Creates a revert commit (safer for production)

# Restart application
```

---

## Migration Rollback

```bash
# List migrations for the app
python manage.py showmigrations <app_name>

# Roll back one migration
python manage.py migrate <app_name> <previous-migration-number>

# Example: roll back orders app to migration 0015
python manage.py migrate orders 0015
```

**Warning:** Rolling back migrations that affect financial data must be done with extreme care. Always have a database backup before attempting migration rollback.

---

## Full Rollback Procedure

1. Stop the application server (prevent new requests)
2. Take a backup of current state (even if corrupted — for forensics)
3. Restore database from pre-deployment backup
4. Roll back code to previous git commit
5. Confirm migration state matches restored database
6. Restart application server
7. Test critical flows (login, order list, payment callback)
8. Report what failed and why

---

## Financial Data During Rollback

If a deployment created incorrect financial records (ledger entries, commissions):
- Do NOT rollback the financial records by deleting them
- Create reversing entries to correct the balance
- Keep the incorrect entries for audit purposes
- Document the incident in `11_Project_Knowledge/KNOWN_RISKS.md`

See [../07_ADR/ADR-004-Ledger-Discipline.md](../07_ADR/ADR-004-Ledger-Discipline.md).

---

## Irreversible Migrations

If a migration is irreversible (column deleted, data migrated and source dropped):
- Document it explicitly before deploying
- Ensure rollback plan covers data recovery from backup
- Require DBA approval before running in production
