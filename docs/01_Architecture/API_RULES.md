# API Rules

API implementation is future scope, but all future APIs must follow:

- company scoping
- explicit permission checks
- stable error codes
- no leaking internal IDs where public tokens are safer
- idempotency for payment-like actions
- audit logging for financial changes
