---
Title: Release Prompts
Layer: Prompts
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: 05_Workflows/RELEASE_FLOW.md, 02_Development_System/RELEASE_CHECKLIST.md
Source of Truth: Policy
Depends On: []
Related Documents: ../05_Workflows/RELEASE_FLOW.md, ../09_Operations/ROLLBACK.md
Reusable Across Projects: Partially
---

# Release Prompts

Prompts for preparing and verifying releases.

---

## Pre-Release Readiness Check Prompt

Use before starting a release to verify the project is ready.

```
Check if the Rasti project is ready for release. 

Run these checks and report the result of each:
1. `python manage.py test --verbosity=1` — all tests must pass
2. `python manage.py check --deploy` — no errors allowed
3. `git status` — must be clean (no uncommitted changes)
4. `python manage.py showmigrations` — all migrations applied

Also verify:
- Are there any P0 bugs still unresolved? (check 11_Project_Knowledge/KNOWN_RISKS.md)
- Are there any migrations that have not been tested in staging?
- Is there a database backup ready?

Report format:
- Tests: PASS/FAIL (N tests, N failures)
- Deployment check: PASS/FAIL (list any errors)
- Git status: CLEAN/DIRTY
- P0 bugs: N open (list them)
- Release readiness: READY/NOT READY

If NOT READY, list exactly what must be done before proceeding.
```

---

## Migration Pre-Flight Prompt

Use before running migrations in production.

```
Review the pending migrations before I run them in production.

Show me:
python manage.py showmigrations | grep '\[ \]'

For each unmigrated migration, I need to know:
1. What does this migration do? (schema change, data migration, both?)
2. Is it reversible? (`python manage.py migrate <app> <previous>`)
3. Is it destructive? (deletes columns, drops data)
4. What is the risk level? (Low/Medium/High)
5. What is the rollback plan if this migration causes errors?

Do NOT run the migrations — analysis only.
```

---

## Post-Release Verification Prompt

Use immediately after deployment to verify the release is good.

```
Verify the release of the Rasti project is successful.

Smoke test checklist — test each URL and report status (200/error):
1. `GET /login/` — should return 200
2. `GET /{company_code}/admin/` — should return 200 (logged in as COMPANY_ADMIN)
3. `GET /{company_code}/admin/orders/` — should return 200
4. `GET /{company_code}/tech/` — should return 200 (logged in as TECHNICIAN)
5. `GET /{company_code}/invoices/{test_invoice_id}/` — should return 200

Also check:
- No 500 errors in the log in the last 5 minutes
- `NEEDS_RECONCILIATION` payment count is same as before deployment
- Application server (Gunicorn) is running without errors

Report: RELEASE CONFIRMED or ROLLBACK NEEDED
If rollback needed: state exactly which check failed and what the error was.
```

---

## Rollback Decision Prompt

Use when a release is failing and you need to decide whether to rollback.

```
A release is showing problems. I need to decide: rollback or fix forward?

Problem description:
[describe what is broken]

Error messages or logs:
[paste relevant logs]

Context:
- Time since deployment: [X minutes]
- Users affected: [estimate]
- Revenue impact: [payment processing broken? YES/NO]
- Financial data affected: [YES/NO]

Help me decide:
1. Is this a critical data integrity issue? (YES = immediate rollback)
2. Is payment processing affected? (YES = immediate rollback)
3. Can this be fixed with a quick code change? (YES = fix forward)
4. How long would the fix take? (>30 min = consider rollback)

Recommendation: ROLLBACK NOW / FIX FORWARD / WAIT AND MONITOR
Reason: [why]
Next step: [what to do immediately]
```
