---
Title: Operations — README
Layer: Operations
Audience: Human + DevOps
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# 09 — Operations

Deployment, backup, monitoring, and operational guides.

---

## Files in This Folder

| File | Purpose | Status |
|---|---|---|
| [ENVIRONMENTS.md](ENVIRONMENTS.md) | Environment config, required env vars | Active |
| [DEPLOYMENT.md](DEPLOYMENT.md) | How to deploy to production | Active |
| [BACKUP.md](BACKUP.md) | Database and media backup procedures | Active |
| [ROLLBACK.md](ROLLBACK.md) | How to roll back a deployment | Active |
| [MONITORING.md](MONITORING.md) | What to monitor in production | Active |
| [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) | Security checklist and incident response | Active |

---

## Reading Order

Before first deployment, read in this order:
1. [ENVIRONMENTS.md](ENVIRONMENTS.md) — environment setup
2. [BACKUP.md](BACKUP.md) — backup before deployment
3. [DEPLOYMENT.md](DEPLOYMENT.md) — deployment steps
4. [MONITORING.md](MONITORING.md) — what to watch after deployment
5. [ROLLBACK.md](ROLLBACK.md) — if something goes wrong
6. [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) — security checklist

---

## Related Documents

- [../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md](../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md) — must pass before deploying
- [../05_Workflows/RELEASE_FLOW.md](../05_Workflows/RELEASE_FLOW.md) — end-to-end release procedure
- [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md) — P0 bugs to fix first

---

## Maintenance Notes

Update `ENVIRONMENTS.md` when new environment variables are added. Update `BACKUP.md` when backup procedures change. Never delete rollback procedures — add new ones.

**Before first production deployment:** Read [../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md](../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md) and fix all P0 issues first.
