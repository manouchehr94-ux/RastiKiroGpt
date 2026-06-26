# ADR-003 — Payment Architecture

## Status

Accepted

## Decisions

- `PaymentGateway` is canonical target gateway model.
- Gateway has `owner_type = company/platform`.
- Platform commission only for verified platform-owned gateway payment.
- Ambiguous payment goes to `NEEDS_RECONCILIATION`.
