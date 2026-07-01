---
Title: Review Prompts
Layer: Prompts
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: 02_Development_System/CODE_REVIEW_TEMPLATE.md, AI/PROMPTS/REVIEW_TEMPLATE.md
Source of Truth: Policy
Depends On: ../06_Quality_Assurance/MANUAL_QA_CHECKLIST.md
Related Documents: AUDIT_PROMPTS.md, DEBUGGING_PROMPTS.md
Reusable Across Projects: Partially
---

# Review Prompts

Prompts for code review, AI-assisted review, and structured human review of changes.

---

## Code Review Prompt (Full Review)

Use when reviewing a PR or a set of changed files.

```
Review this code change for the Rasti SaaS project. The project rules are:
- Multi-tenant Django SaaS; each company is isolated by company_code URL prefix
- All business logic lives in services.py files — never in views
- Money must use Decimal only (never float)
- Financial records (TechnicianLedgerEntry, CompanyPlatformFeeEntry) are immutable
- Permission decorators are required on every view: @require_tenant_role, @require_platform_owner, or @require_tenant_auth
- Platform commission entries are only created when: payment_mode=platform_gateway AND status=PAID AND owner_type=platform AND fee > 0

Files changed:
[paste file diffs here]

Review checklist:
1. SCOPE: Does this change do only what was requested?
2. CORRECTNESS: Is the business rule satisfied correctly?
3. MULTI-TENANCY: Are all queries company-scoped? No cross-tenant leakage?
4. MONEY SAFETY: Decimal only? No incorrect platform fee? Idempotent?
5. PERMISSIONS: Are all views properly protected with decorators?
6. TESTS: Are there new/updated tests? Was any regression test removed?
7. SERVICE LAYER: Does business logic stay in services.py?

Verdict: Approve / Request Changes / Block
```

---

## Quick Multi-Tenant Safety Check

Use when uncertain about a specific query or view.

```
Check this code for multi-tenant isolation issues. The company is injected via middleware as request.company.

Code:
[paste code]

Questions:
1. Does every queryset filter by company?
2. Is there any path where data from one company could appear in another company's response?
3. Does any URL parameter (like order_id) get validated against request.company?
```

---

## Financial Code Review Prompt

Use when reviewing anything that touches payments, ledger, invoices, or commissions.

```
Review this financial code change. Critical rules:
- TechnicianLedgerEntry and CompanyPlatformFeeEntry must NEVER be updated or deleted
- Platform commission (CompanyPlatformFeeEntry) is only created when ALL conditions are true:
  payment_mode = platform_gateway, status = PAID, owner_type = platform, fee > 0
- Payment is only marked PAID after PSP verify call succeeds
- Ambiguous payment results go to NEEDS_RECONCILIATION, never to FAILED
- Amount mismatches go to NEEDS_RECONCILIATION

Code:
[paste code]

Questions:
1. Are ledger entries created (not updated)?
2. Is the platform commission creation guarded by all 4 conditions?
3. Is the payment status set correctly for all PSP outcomes?
4. Is there any path that bypasses the verify step?
```

---

## Review Verdict Structure

Use this format when reporting review results:

```
## Review: [short description]

### Verdict: [APPROVED / REQUEST CHANGES / BLOCKED]

### Scope
[Did the change do only what was requested?]

### Issues Found
| Severity | Issue | File | Line |
|----------|-------|------|------|
| [CRITICAL/HIGH/MEDIUM/LOW] | [description] | [file] | [line] |

### Tests
[Were tests sufficient? Missing tests?]

### Actions Required
- [ ] [action if REQUEST CHANGES or BLOCKED]
```
