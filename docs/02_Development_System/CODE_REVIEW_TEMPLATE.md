# Code Review Template

## Scope

## Correctness

- [ ] Business rule satisfied
- [ ] Edge cases covered
- [ ] No unrelated changes

## Multi-tenancy

- [ ] Company scoped queries
- [ ] No cross-tenant leakage

## Money safety

- [ ] Decimal only
- [ ] No incorrect platform fee
- [ ] Idempotency preserved

## Tests

- [ ] New tests
- [ ] Regression tests
- [ ] No tests removed

## Verdict

Approve / Request changes / Block
