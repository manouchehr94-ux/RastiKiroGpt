---
Title: Testing Guide
Layer: Human Engineering
Audience: Human Developer
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/*/tests/, 06_Quality_Assurance/TEST_STRATEGY.md
Source of Truth: Code
Depends On: LOCAL_DEVELOPMENT.md
Related Documents: ../06_Quality_Assurance/TEST_STRATEGY.md, ../06_Quality_Assurance/MANUAL_QA_CHECKLIST.md
Reusable Across Projects: No
---

# Testing Guide

---

## Running Tests

```powershell
# Run all 1242 tests
python manage.py test --verbosity=1

# Run with more detail
python manage.py test --verbosity=2

# Run tests for a specific app
python manage.py test apps.orders --verbosity=2

# Run a single test class
python manage.py test apps.orders.tests.test_order_flow.OrderFlowTests --verbosity=2

# Run a single test method
python manage.py test apps.orders.tests.test_order_flow.OrderFlowTests.test_order_creation --verbosity=2
```

---

## Before Submitting Any Change

Run tests for:
1. The app you changed
2. Any app that depends on what you changed

```powershell
# Changed orders app
python manage.py test apps.orders --verbosity=2

# Changed payments (which affects orders and invoices)
python manage.py test apps.payments apps.orders apps.invoices --verbosity=2
```

---

## Writing Tests

### Test Location
```
apps/<app_name>/tests/
    __init__.py
    test_<feature>.py
    test_<service>.py
```

### Test Class Pattern
```python
from django.test import TestCase
from apps.orders.models import Order
from apps.tenants.models import Company

class OrderCreationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            company_code='test',
        )

    def test_order_requires_company(self):
        # Arrange
        # Act
        # Assert
```

### Required for Financial Tests
All financial tests must verify:
1. Correct amount stored as `Decimal`
2. Platform commission only created under the 4 conditions
3. Ledger entries are created (not updated)
4. Idempotency (submitting twice does not create duplicate records)

### Required for Permission Tests
```python
def test_company_staff_cannot_access_other_company_orders(self):
    # Create two companies and test cross-tenant access returns 404
```

---

## Test Categories

| Category | What it Tests | Example |
|---|---|---|
| Unit | Single function/method | `test_calculate_wage_amount` |
| Integration | View + service + model | `test_order_creation_flow` |
| Permission | Auth + role enforcement | `test_technician_cannot_access_admin` |
| Multi-tenant | Tenant isolation | `test_company_a_order_not_in_company_b` |
| Financial | Money + ledger rules | `test_platform_commission_not_created_for_cash` |
| Regression | Known bug does not recur | `test_payment_callback_without_verify_stays_pending` |

---

## Coverage Gaps (Known)

- Multi-tenant isolation tests are missing for many views
- Cross-company data access is not systematically tested
- P0-1 and P0-2 do not yet have regression tests
- See [../06_Quality_Assurance/REGRESSION_TEST_PLAN.md](../06_Quality_Assurance/REGRESSION_TEST_PLAN.md) for priority list

---

## Test Database

Tests run against a test database (auto-created by Django). Do not use production or development credentials in tests.

```python
# This is safe — Django creates a test_<dbname> automatically
# Never do: connect to production DB in tests
```
