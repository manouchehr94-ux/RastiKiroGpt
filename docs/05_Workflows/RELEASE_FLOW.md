---
Title: Release Flow
Layer: Workflows
Audience: Human + DevOps
Status: Active
Last Verified: 2026-07-01
Verified Against: 05_Deployment/RELEASE_PROCESS.md, 02_Development_System/RELEASE_CHECKLIST.md
Source of Truth: Mixed
Depends On: []
Related Documents: ../09_Operations/ROLLBACK.md, ../09_Operations/BACKUP.md, ../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md
Reusable Across Projects: Partially
---

# Release Flow

Step-by-step procedure for deploying a release to production.

---

## Pre-Release Requirements

Before starting a release:

- [ ] All P0 bugs resolved (see [../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md](../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md))
- [ ] All targeted tests passing: `python manage.py test --verbosity=1`
- [ ] No uncommitted changes: `git status` should be clean
- [ ] Migrations reviewed: `python manage.py showmigrations` — all migrations are correct
- [ ] Rollback plan documented (answer the 4 questions from [../09_Operations/ROLLBACK.md](../09_Operations/ROLLBACK.md))

---

## Release Steps

### Step 1 — Prepare

```bash
git status                          # Must be clean
git log --oneline -5                # Note the current HEAD
python manage.py check --deploy     # No errors allowed
```

### Step 2 — Backup

```bash
# Take full database backup
pg_dump -U <user> <dbname> > backup_$(date +%Y%m%d_%H%M%S).sql
```

See [../09_Operations/BACKUP.md](../09_Operations/BACKUP.md).

### Step 3 — Apply Migrations

```bash
python manage.py migrate            # Apply pending migrations
python manage.py showmigrations     # Verify all applied
```

### Step 4 — Deploy Code

```bash
git pull                            # Pull latest code
pip install -r requirements.txt     # Update dependencies if needed
python manage.py collectstatic --noinput  # Collect static files
```

Restart application server (Gunicorn/uWSGI).

### Step 5 — Verify

```bash
python manage.py check              # Should pass cleanly
```

Test critical flows:
- [ ] Admin login at `/login/`
- [ ] Platform owner login at `/login/`
- [ ] View order list at `/<code>/admin/orders/`
- [ ] Technician login and order view at `/<code>/tech/`
- [ ] Public invoice view at `/<code>/invoices/<id>/` (use a test invoice)

### Step 6 — Monitor (First 30 Minutes)

Check:
- Error monitoring for 500s
- Payment callback endpoint responding
- SMS queue not backing up
- `NEEDS_RECONCILIATION` count unchanged (no new payment issues)

### Step 7 — Confirm or Rollback

If no issues after 30 minutes: release confirmed.
If issues detected: execute rollback per [../09_Operations/ROLLBACK.md](../09_Operations/ROLLBACK.md).

---

## Smoke Checklist (Quick Validation)

- [ ] Admin login works
- [ ] Order list loads for admin
- [ ] Technician login works
- [ ] Technician order list loads
- [ ] Public invoice view accessible
- [ ] No 500 errors in logs
- [ ] Multi-tenant: Admin from company A cannot access company B

---

## Development Workflow (AI + Human)

1. Product Owner reports issue or feature request
2. AI writes structured implementation request
3. AI reads repo → audits → proposes solution
4. Human reviews audit and approves
5. AI implements approved scope only
6. AI runs tests and reports
7. Human performs manual QA
8. Human approves → feature committed
9. Scheduled release per this document
