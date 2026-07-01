---
Title: Test Strategy
Layer: Quality Assurance
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/*/tests/, 99_AUDIT_2026_06_30/05_TESTING_AUDIT.md
Source of Truth: Code + Audit
Depends On: []
Related Documents: TEST_COVERAGE_MAP.md
Reusable Across Projects: Partially
---

# Test Strategy

---

## Test Philosophy

- Tests are the behavioral guarantee of the system
- Business-critical logic must have integration tests, not just unit tests
- Financial and multi-tenant isolation tests are the highest priority
- Do not test framework internals — test business behavior

---

## Test Runner

```bash
# Full suite
python manage.py test --verbosity=1

# Specific app
python manage.py test apps.orders --verbosity=2

# Specific test file
python manage.py test apps.orders.tests.test_order_lifecycle --verbosity=2

# With coverage (if coverage.py installed)
coverage run manage.py test
coverage report
```

---

## Test Count (as of 2026-06-30)

**1242 tests total**

High-quality test areas:
- `apps/orders/tests/` — order lifecycle and status transitions
- `apps/payments/tests/` — payment verification and reconciliation
- `apps/payouts/tests/` — ledger and settlement
- `apps/invoices/tests/` — invoice creation and payment

Gap areas:
- Multi-tenant isolation tests (very few)
- Notification event triggering tests
- API endpoint tests
- Template rendering tests

---

## Test Types

### 1. Unit Tests

For pure logic functions (no database, no HTTP):
- Financial calculations
- Status machine validation
- Service helper functions

### 2. Integration Tests (Most Important)

For business flows that touch database:
- Order creation → status transition → completion
- Invoice creation → payment → ledger entries
- Technician assignment → acceptance → completion

Pattern:
```python
class TestOrderLifecycle(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="test", ...)
        self.admin = User.objects.create(role="COMPANY_ADMIN", company=self.company, ...)
        self.tech = User.objects.create(role="TECHNICIAN", company=self.company, ...)

    def test_order_status_transition_new_to_done(self):
        order = Order.objects.create(company=self.company, status="NEW", ...)
        # Assign tech → WAITING
        # Accept → IN_PROGRESS
        # Complete → DONE
        self.assertEqual(order.status, "DONE")
```

### 3. Permission Tests (Critical)

For every admin/protected view:
```python
def test_operator_list_requires_company_admin(self):
    # Login as TECHNICIAN
    self.client.force_login(self.technician)
    response = self.client.get(f"/{self.company.code}/admin/settings/operators/")
    # Should be 302 (redirect to login) or 403 (forbidden)
    self.assertIn(response.status_code, [302, 403])
```

### 4. Multi-Tenant Isolation Tests (Missing — Priority)

```python
def test_company_a_cannot_access_company_b_order(self):
    order_b = Order.objects.create(company=self.company_b, ...)
    self.client.force_login(self.admin_a)  # Admin from company A
    response = self.client.get(f"/{self.company_a.code}/admin/orders/{order_b.id}/")
    self.assertEqual(response.status_code, 404)
```

---

## What Not to Test

- Django ORM behavior (trust Django)
- Third-party library internals (trust the library)
- Pure HTML rendering without business logic
- Configuration values (test the behavior, not the config)

---

## Test Data Strategy

Use `TestCase.setUp()` for test data. Avoid:
- Fixtures (brittle, hard to maintain)
- Factory libraries (overkill for this project size)

Use factories only if the test data setup becomes unmanageable.

---

## CI/CD

Tests should run on every push. Currently: Needs Verification — check `.github/workflows/` or equivalent CI configuration.
