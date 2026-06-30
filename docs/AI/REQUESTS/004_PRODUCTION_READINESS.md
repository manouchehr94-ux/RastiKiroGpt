# Request 004 — Production Readiness Audit

Priority: High  
Mode: Audit first

---

## Goal

Review project readiness for real production deployment.

Assume future growth:

- many companies
- many users
- many orders
- many invoices
- many notifications
- large financial data

---

## Inspect

- settings
- security
- ALLOWED_HOSTS
- DEBUG
- database
- static/media
- logging
- monitoring
- Redis readiness
- Celery readiness
- PgBouncer / connection pooling
- backup
- health checks
- deployment docs

---

## Output

- critical blockers
- high risks
- medium risks
- safe-to-delay items
- production readiness roadmap
- no code changes unless explicitly approved
