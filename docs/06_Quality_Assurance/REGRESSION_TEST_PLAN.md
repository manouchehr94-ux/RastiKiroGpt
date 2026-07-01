---
Title: Regression Test Plan
Layer: Quality Assurance
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: 04_Testing/REGRESSION_TEST_RULES.md, apps/*/tests/
Source of Truth: Code + Policy
Depends On: TEST_STRATEGY.md
Related Documents: TEST_COVERAGE_MAP.md
Reusable Across Projects: Partially
---

# Regression Test Plan

---

## Regression Test Policy

> Every fixed bug must have a regression test.
> A regression test ensures the same bug never reappears silently.

**Rules:**
1. The regression test name must describe the original bug and the correct behavior
2. Never remove a regression test without explicit architectural reason documented in an ADR
3. Regression tests live in the test file for the relevant app

---

## Naming Convention

```python
def test_<bug_description>_returns_<expected_behavior>(self):
    # Test that verifies the bug does not recur

# Examples:
def test_payment_callback_without_verify_does_not_mark_paid(self):
def test_company_a_order_not_accessible_from_company_b_url(self):
def test_technician_cannot_access_admin_operator_list(self):
```

---

## Priority Areas for Regression Tests

### P0 Bug Regressions (Write these when P0s are fixed)

| Bug | Test to Write |
|---|---|
| P0-1: `admin_operator_list` missing decorator | `test_operator_list_requires_company_admin_role` |
| P0-2: JWT logout broken | `test_jwt_token_invalid_after_logout` |
| P0-3: Hardcoded "123456" | `test_default_password_not_accepted_in_production` |
| P0-5: `Customer.name` crash | `test_api_customer_create_uses_first_and_last_name` |

### Financial Regression Tests (Already should exist — verify coverage)

- Payment callback without verify does not mark payment PAID
- Duplicate payment callback does not create duplicate commission
- Platform commission not created for company-gateway payments
- Platform commission not created for cash/manual payments
- Ledger entries are not updated — only new entries created

### Multi-Tenant Isolation Regression Tests (Missing — priority)

- Company A cannot access Company B's orders via direct URL
- Company A cannot access Company B's invoices via direct URL
- Company A's admin cannot manage Company B's operators
- Technician from Company A cannot see Company B's available orders

---

## Running Regression Tests

```bash
# Run all regression tests (they should be in the normal test suite)
python manage.py test --verbosity=2

# Run tests for a specific bug fix
python manage.py test apps.payments.tests.test_payment_regression --verbosity=2
```

---

## When a Bug Is Reported

1. Write a failing test that reproduces the bug
2. Fix the bug
3. Confirm the test now passes
4. Keep the test in the suite permanently

This is "test-first" regression. The test proves the bug existed and proves the fix works.
