# ADR-004 — Ledger Discipline

## Status

Accepted

## Decision

Use single-entry ledger for V1, but with double-entry discipline:
- immutable entries
- idempotency keys
- both sides of cash movements recorded atomically
- no manual balance editing
