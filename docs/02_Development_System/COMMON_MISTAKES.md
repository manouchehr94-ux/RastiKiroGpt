# Common Mistakes — Do Not Repeat

**Version:** RDOS v1.0 Stable

---

## Code Mistakes

1. Using `float` for money.
2. Querying tenant data without `company` scope.
3. Updating business state directly in views instead of services.
4. Creating invoices with `Invoice.objects.create()` instead of service/factory patterns.
5. Editing ledger entries instead of creating reversal entries.
6. Weakening tests to make a change pass.
7. Refactoring unrelated code during a bug fix.
8. Changing more than 5 files without approval.
9. Creating migrations when the task did not permit migrations.
10. Treating payment callback as proof of payment.
11. Marking ambiguous payments as `FAILED` instead of `NEEDS_RECONCILIATION`.
12. Creating platform fee entries for cash/manual/company-gateway payments.

---

## Gateway Mistakes

Do not add new payment-flow logic to these legacy/transitional models:

- `apps.platform_core.models.CompanyPaymentGatewaySetting`
- `apps.platform_core.models.PlatformPaymentGatewaySetting`

Target canonical model:

- `apps.payments.models.PaymentGateway`

Legacy models may be read only during migration/consolidation tasks approved in Phase 2.

---

## Documentation Mistakes

1. Adding a new rule without updating the relevant source-of-truth document.
2. Changing architecture without ADR.
3. Using synonyms not listed in `TERMINOLOGY.md`.
4. Leaving phase boundaries ambiguous.
5. Hiding unresolved questions inside implementation code.
