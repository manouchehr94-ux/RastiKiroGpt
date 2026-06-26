# Logging and Audit

## Log

- security failures
- payment callback failures
- provider verify failures
- reconciliation mismatches
- permission denials for sensitive actions

## Do not log

- API secrets
- raw KYC document paths in public logs
- card data
- sensitive personal data unnecessarily

## Audit

Every financial state change must be reconstructable from:
- PaymentAttempt
- Invoice settled fields
- Ledger entries
- KYC review fields
- future FinancialAuditLog
