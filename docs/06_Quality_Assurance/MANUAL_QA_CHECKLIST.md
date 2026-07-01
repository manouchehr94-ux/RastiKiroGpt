---
Title: Manual QA Checklist
Layer: Quality Assurance
Audience: Human
Status: Active
Last Verified: 2026-07-01
Verified Against: 02_Development_System/TEST_CHECKLIST.md, 02_Development_System/RELEASE_CHECKLIST.md
Source of Truth: Mixed
Depends On: []
Related Documents: PRODUCTION_READINESS_CHECKLIST.md, ../05_Workflows/RELEASE_FLOW.md
Reusable Across Projects: No
---

# Manual QA Checklist

---

## Before Accepting Any Task (AI or Human)

- [ ] Targeted tests run: `python manage.py test apps.<changed_app> --verbosity=2`
- [ ] Existing related tests run and passing
- [ ] Negative cases tested (what happens if input is invalid?)
- [ ] Permission failures tested (what happens if wrong role tries to access?)
- [ ] Tenant isolation tested (can another company see this data?)
- [ ] Financial idempotency tested where relevant (what happens if submitted twice?)
- [ ] No tests were skipped or deleted to make the task pass

---

## Before Any Release

### Code Quality
- [ ] `python manage.py check --deploy` passes with no errors
- [ ] All tests pass: `python manage.py test --verbosity=1`
- [ ] Git status is clean: `git status` shows no uncommitted changes
- [ ] No `DEBUG = True` or test credentials in code going to production

### Flow Testing
- [ ] Order flow: public request → operator approval → technician assignment → completion
- [ ] Invoice flow: creation → customer view → payment initiation → PSP callback → PAID
- [ ] Payment safety: verify that callback alone does not mark payment as PAID
- [ ] SMS critical path: test that SMS is sent when configured (check SMS credit)
- [ ] Admin login and basic navigation

### Security Testing
- [ ] Admin login requires valid credentials
- [ ] Technician cannot access admin panel URLs
- [ ] Company A admin cannot access company B orders (test with direct URL)
- [ ] Public pages do not show admin sidebar
- [ ] Invoice public URL only shows ISSUED or PAID invoices

### Multi-Tenant Isolation Smoke Test
1. Login as admin of company A
2. Note the ID of any order in company A
3. Navigate to `/<company_b_code>/admin/orders/<company_a_order_id>/`
4. Should return 404 (not found)

---

## Payment-Specific QA

- [ ] PSP redirect works (correct URL format)
- [ ] Callback endpoint receives POST
- [ ] Payment is not marked PAID without PSP verify call
- [ ] Amount mismatch goes to `NEEDS_RECONCILIATION`
- [ ] Platform commission is NOT created for cash/manual payments

---

## Notification QA

- [ ] Key notifications appear in notification bell after trigger
- [ ] SMS is not sent when company SMS credit is zero
- [ ] Technician receives notification when assigned order

---

## After QA Passes

Confirm to the developer/AI agent:
```
QA: PASS
Tests: N tests, 0 failures
Manual check: [what was tested]
Ready to merge/deploy: YES
```

Or if failed:
```
QA: FAIL
Issue: [description]
File/URL: [where the problem is]
Expected: [what should happen]
Actual: [what happened]
```
