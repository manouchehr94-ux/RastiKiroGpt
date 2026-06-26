# Architect Review Checklist

A change cannot be accepted if any required item is NO.

## General

- [ ] Smallest safe change?
- [ ] No unrelated refactor?
- [ ] Existing pattern followed?

## Multi-tenant

- [ ] All queries scoped?
- [ ] Permissions checked?

## Financial

- [ ] Decimal only?
- [ ] Transaction boundaries correct?
- [ ] Idempotency preserved?
- [ ] Ledger immutable?
- [ ] Payment callback verified?

## Tests

- [ ] Tests added/updated?
- [ ] Existing tests pass?
- [ ] Failure case tested?

## Migration

- [ ] Additive?
- [ ] Backward compatible?
- [ ] Rollback plan?

## Documentation

- [ ] Docs updated if business rule changed?
