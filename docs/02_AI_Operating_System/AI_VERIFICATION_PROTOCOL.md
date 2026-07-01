---
Title: AI Verification Protocol
Layer: AI Operating System
Audience: AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code
Reusable Across Projects: Partially
---

# AI Verification Protocol

How an AI agent verifies that a change is complete and correct.

---

## After Every Code Change

### Step 1 — Static Checks

```bash
python manage.py check --deploy
python manage.py check
```

These catch:
- Missing migrations
- Model integrity issues
- Settings errors

### Step 2 — Targeted Tests

Run tests for the specific app changed:

```bash
python manage.py test apps.<changed_app> --verbosity=2
```

For financial changes, also run:
```bash
python manage.py test apps.payments apps.invoices apps.payouts --verbosity=2
```

### Step 3 — Regression Tests

For changes to shared infrastructure (middleware, permissions, base models):
```bash
python manage.py test --verbosity=1
```

Verify: total test count stays at 1242 (or higher). Do not accept a lower test count.

---

## Verification Checklist for Specific Change Types

### Permission / Security Change

- [ ] View has correct decorator (`@require_tenant_role` or `@require_platform_owner`)
- [ ] Tests cover unauthorized access (should return 302 or 403)
- [ ] Tests cover cross-company access (should return 403 or 404)
- [ ] No other view in the same file lost its decorator

### Order Status Change

- [ ] Status value matches `OrderStatus` choices in `apps/orders/models.py`
- [ ] Transition is valid in the status machine
- [ ] `OrderStatusLog` entry is created
- [ ] Relevant notifications are triggered (or deliberately skipped)
- [ ] Test covers the transition

### Financial Change

- [ ] `transaction.atomic` wraps the operation
- [ ] `select_for_update()` used where parallel execution is possible
- [ ] No `float` — only `Decimal`
- [ ] Idempotency key prevents double-processing
- [ ] Existing ledger entries are not modified
- [ ] Tests run and pass

### URL / Routing Change

- [ ] URL added to the correct `urls*.py` file
- [ ] `name=` parameter is set
- [ ] `app_name` namespace matches existing convention
- [ ] URL is added to `08_Site_Map/01_URL_INVENTORY.md`
- [ ] Template path is correct

### Template Change

- [ ] Template extends the correct layout (`base_dashboard.html` or a `layouts/` file)
- [ ] Role-conditional blocks are correct
- [ ] RTL layout is preserved
- [ ] No hardcoded text that should be translatable
- [ ] Template is in the correct folder for its role

---

## How to Verify a Known Bug Is Fixed

For P0-1 (`admin_operator_list` missing decorator):
```python
# Verify in apps/tenants/views_admin.py at line 2125:
# Should see @require_tenant_role("COMPANY_ADMIN") before the def
```
Test:
```bash
python manage.py test apps.tenants --verbosity=2 --tag=permissions
```

For P0-2 (JWT logout broken):
1. Verify `rest_framework_simplejwt.token_blacklist` in `INSTALLED_APPS`
2. Verify migration `python manage.py showmigrations token_blacklist`
3. Test logout API endpoint returns 205 and token is rejected afterward

---

## Reporting Verification Results

Every task report must include:

```
## Verification

- [ ] manage.py check: PASS / FAIL
- [ ] Targeted tests: PASS (N tests) / FAIL (error)
- [ ] Full suite: PASS (1242 tests) / SKIPPED (reason)
- [ ] Manual QA: DONE / NEEDED (steps)
```
