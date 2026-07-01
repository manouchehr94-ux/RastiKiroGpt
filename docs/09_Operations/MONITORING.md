---
Title: Monitoring Guide
Layer: Operations
Audience: Human + DevOps
Status: Active
Last Verified: 2026-07-01
Verified Against: 05_Deployment/MONITORING.md
Source of Truth: Mixed
Depends On: ENVIRONMENTS.md
Related Documents: BACKUP.md
Reusable Across Projects: Partially
---

# Monitoring Guide

---

## Critical Metrics to Watch

### Payment Health

| Metric | Alert When |
|---|---|
| `NEEDS_RECONCILIATION` payment count | > 0 and not being reviewed |
| Payment failure rate | Spike (> 5% in 1 hour) |
| Payment callback errors | Any 5xx from callback handler |
| PSP verify endpoint errors | Any timeout or 5xx |

### Application Health

| Metric | Alert When |
|---|---|
| HTTP 500 errors | Any spike |
| HTTP 403 (permission denied) | Spike may indicate P0-1 exploitation |
| Slow queries (> 2s) | Dashboard/report queries |
| SMS send failures | > 10% failure rate |

### Business Health

| Metric | Check Daily |
|---|---|
| `NEEDS_RECONCILIATION` payments | Platform Owner must resolve these |
| SMS credit balance | Alert when below threshold |
| Orders stuck in `IN_PROGRESS` > 48h | May need admin attention |
| Failed notification deliveries | High count may indicate SMS credit issue |

---

## Log Locations

Needs Verification — check `config/settings/production.py` for logging configuration.

Expected log destinations:
- Application logs: stdout (if containerized) or `/var/log/rasti/`
- Error monitoring: Sentry (if configured)
- Access logs: web server (Nginx/Gunicorn)

---

## Key Log Events to Monitor

```
# Security events
"Permission denied" for admin URLs
"Cross-tenant access attempt"

# Financial events
"Payment NEEDS_RECONCILIATION"
"Platform commission created"
"Ledger entry created"

# SMS events
"SMS send failed"
"SMS credit insufficient"
```

---

## Health Check Endpoint

Needs Verification — check if a `/health/` endpoint exists.

If not, add one that verifies:
1. Database connection is live
2. Cache backend is reachable (if configured)
3. Returns 200 when healthy

---

## Pre-Launch Monitoring Checklist

- [ ] Error monitoring service configured (Sentry or equivalent)
- [ ] Database connection pool monitoring active
- [ ] `NEEDS_RECONCILIATION` payment dashboard visible to Platform Owner
- [ ] SMS credit alerts configured
- [ ] 500 error alerts configured
- [ ] Scheduled backup confirmed running
