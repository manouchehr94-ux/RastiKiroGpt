# Payment Architecture Pointer

This file is intentionally short.

Authoritative payment decisions live in:

1. `docs/07_ADR/ADR-002-CompanyPaymentSettings.md`
2. `docs/07_ADR/ADR-003-Payment-Architecture.md`
3. `docs/07_ADR/ADR-004-Ledger-Discipline.md`
4. `docs/03_Business/PAYMENT_RULES.md`
5. `docs/03_Business/INVOICE_RULES.md`

Summary:

- `CompanyPaymentSettings` owns payment activation and mode.
- `CompanyFinancialPolicy` owns financial policy.
- `PaymentGateway` is the target canonical gateway model.
- `PaymentGateway.owner_type` distinguishes company-owned vs platform-owned gateways.
- Platform commission is allowed only for verified paid platform-owned gateway payments and only when all commission conditions are true.
- Ambiguous payment outcomes go to `NEEDS_RECONCILIATION`.
- Ledger entries are immutable.

Legacy gateway models:

- `CompanyPaymentGatewaySetting`
- `PlatformPaymentGatewaySetting`

Do not add new payment-flow logic to legacy models.
