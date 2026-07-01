---
Title: Known Constraints and Development Principles
Layer: Project Knowledge
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: 00_Project/PROJECT_PRINCIPLES.md, 02_Development_System/COMMON_MISTAKES.md
Source of Truth: Policy (binding)
Depends On: []
Related Documents: KNOWN_RISKS.md, SOURCE_OF_TRUTH.md, ../02_AI_Operating_System/AI_CODE_CHANGE_RULES.md
Reusable Across Projects: No
---

# Known Constraints and Development Principles

These are the non-negotiable principles for working on the Rasti SaaS project. They apply to both human developers and AI agents. Violations have caused production bugs and financial data errors in the past.

---

## Development Principles (Binding)

1. **Correctness before speed.** A correct slow solution is always better than a fast incorrect one.
2. **Small safe changes before broad rewrites.** Never rewrite more than needed to fix the task.
3. **Service layer before view logic.** All business logic lives in `services.py`. Views are thin.
4. **Tests before risky changes.** If a change is risky, write the test first.
5. **Tenant isolation everywhere.** Every queryset must filter by company.
6. **Money logic must be deterministic and auditable.** Financial code has no side effects and no ambiguity.
7. **No hidden side effects in financial code.** A function that touches money must declare it in its name and docs.
8. **Every important decision must be documented.** If it's architectural, it needs an ADR.
9. **Production data must be protected.** Never run destructive migrations without a backup and rollback plan.
10. **If unsure, stop and report.** Silence on uncertainty is a bug.

---

## Code Constraints (Do Not Violate)

### Money
- Use `DecimalField` and `Decimal` only. Never `float`.
- Ledger entries (`TechnicianLedgerEntry`, `CompanyPlatformFeeEntry`) are never edited. Create new entries only.
- Platform commission is only created when ALL 4 conditions are true:
  - `payment_mode = platform_gateway`
  - `status = PAID`
  - `owner_type = platform`
  - `fee > 0`

### Multi-Tenancy
- Every queryset that touches tenant-owned models must filter by `company`.
- `company` is injected via `TenantMiddleware` as `request.company`.
- Cross-tenant data access is a critical security bug, not just a business logic error.

### Payments
- A payment is PAID only after the PSP verify call succeeds AND the returned amount matches.
- Amount mismatch → `NEEDS_RECONCILIATION` (not `FAILED`, not `PAID`).
- The callback endpoint alone must never set payment status to PAID.

### Permissions
- Every view requires one of: `@require_tenant_role`, `@require_platform_owner`, or `@require_tenant_auth`.
- No view should be publicly accessible unless it is explicitly a public view (e.g., invoice public view, public service request form).

### Gateway Models (Deprecated)
Do not add new payment-flow logic to these legacy models:
- `apps.platform_core.models.CompanyPaymentGatewaySetting`
- `apps.platform_core.models.PlatformPaymentGatewaySetting`

Canonical model: `apps.payments.models.PaymentGateway`

---

## Common Mistakes (Avoid These)

These have occurred before and must not repeat:

| Mistake | Rule |
|---|---|
| Using `float` for money | Always `Decimal` |
| Querying tenant data without `company` scope | Always filter by company |
| Business state changes directly in views | Always go through services |
| `Invoice.objects.create()` instead of factory | Use service/factory pattern |
| Editing ledger entries | Create reversals, never edit |
| Weakening tests to make a change pass | Never weaken tests |
| Refactoring unrelated code during a bug fix | Fix only the bug |
| Changing more than 5 files without approval | Escalate first |
| Creating migrations when not permitted | Ask before creating migrations |
| Treating payment callback as proof of payment | Verify with PSP first |
| Marking ambiguous payments as `FAILED` | Use `NEEDS_RECONCILIATION` |
| Creating platform fee for non-platform payments | Check all 4 conditions |

---

## Documentation Constraints

1. Adding a new rule without updating the relevant source-of-truth document.
2. Changing architecture without an ADR.
3. Using synonyms not listed in `TERMINOLOGY.md`.
4. Leaving phase boundaries ambiguous.
5. Hiding unresolved questions inside implementation code.

---

## Scope Constraint

> Never change more than what is necessary for the task.

- Bug fix: change only the buggy code + add regression test
- New feature: implement only what is specified + required tests
- Refactor: change only the structure, not the behavior
- Documentation: change only docs, never source code

See [../02_AI_Operating_System/AI_CODE_CHANGE_RULES.md](../02_AI_Operating_System/AI_CODE_CHANGE_RULES.md) for AI-specific rules.
