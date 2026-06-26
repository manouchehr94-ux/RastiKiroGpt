# ADR-002 — CompanyPaymentSettings Owns Payment Activation

## Status

Accepted

## Decision

Use `CompanyPaymentSettings` for payment mode and activation audit.

`CompanyFinancialPolicy` remains for financial policy, splits, discounts, payout strategy, platform fee percent.

## Consequences

Clear permission boundary: platform owner controls payment activation.
