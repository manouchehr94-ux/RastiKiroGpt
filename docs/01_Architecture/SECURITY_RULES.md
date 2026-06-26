# Security Rules

## Secrets

- Never log API keys, merchant secrets, tokens, or raw gateway credentials.
- Use masked display for merchant IDs.
- KYC files must not be publicly guessable.

## Payments

- Callback is not trusted.
- Provider verify is required.
- Signature validation required for real PSPs.
- Amount mismatch goes to `NEEDS_RECONCILIATION`.

## Permissions

Company admins cannot activate online payment mode.
Platform owner controls gateway activation and payment mode.
