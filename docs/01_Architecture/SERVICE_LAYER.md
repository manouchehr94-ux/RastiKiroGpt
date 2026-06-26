# Service Layer Rules

## Services own business logic

Views should call services. Templates should not contain business rules.

## Before changing a service

1. Search all callers.
2. Read related tests.
3. Understand transaction boundaries.
4. Preserve idempotency.
5. Add tests before changing risky behavior.

## Financial services

Financial services must use:
- `transaction.atomic`
- row locking where double-processing is possible
- deterministic idempotency keys
- Decimal only
