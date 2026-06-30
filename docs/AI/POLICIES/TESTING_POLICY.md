# Testing Policy

Every implementation must be tested.

---

## Minimum

```bash
python manage.py check
```

Run related tests.

---

## Bug Fix

Add regression test when possible.

---

## Critical Area

Run broader suite for:

- payments
- invoices
- notifications
- tenant isolation
- permissions

---

## Forbidden

Do not delete tests.

Do not disable failing tests.

Do not claim success without test output.
