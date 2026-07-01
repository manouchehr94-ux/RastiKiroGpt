---
Title: Audit Prompts
Layer: Prompt Library
Audience: AI + Human
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Depends On: []
Related Documents: IMPLEMENTATION_PROMPTS.md, ../02_AI_Operating_System/AI_PROMPT_USAGE_GUIDE.md
Reusable Across Projects: Partially
---

# Audit Prompts

Reusable prompts for technical audits.

---

## Prompt: Security Permission Audit

```
Perform a security audit of the permission system for [AREA].

Project: Rasti SaaS — Django 5.1.3
Path: D:\SaaSprojectService\Rasti chekFinal 10 tir

Context:
- Read docs/03_Architecture/PERMISSIONS.md first
- Known bug P0-1: admin_operator_list at apps/tenants/views_admin.py:2125 is missing @require_tenant_role
- @require_tenant_role is defined in apps/accounts/permissions.py

Audit scope:
- Read apps/[APP_NAME]/views*.py
- For each view function, verify it has @require_tenant_role or @require_platform_owner
- For each view, verify it scopes all queries by company=request.company
- List any views missing permission checks

Output format:
| View Name | File:Line | Has Decorator? | Queries Scoped? | Risk |
```

---

## Prompt: Multi-Tenant Isolation Audit

```
Audit multi-tenant data isolation in [APP_NAME].

Project: Rasti SaaS — Django 5.1.3
Path: D:\SaaSprojectService\Rasti chekFinal 10 tir

Context:
- Read docs/03_Architecture/MULTI_TENANCY.md first
- All company-owned models must use company= filter in every query
- Forbidden pattern: Order.objects.get(id=pk) without company=

Audit scope:
- Read apps/[APP_NAME]/views*.py
- Read apps/[APP_NAME]/services.py
- Search for ORM queries missing company= filter
- Verify callback lookups use company + reference together

Report:
- Files checked
- Violations found (file:line + the problematic query)
- Compliant patterns found
- Risk assessment
```

---

## Prompt: Financial Code Audit

```
Audit the financial code in [APP_NAME/SERVICE].

Project: Rasti SaaS — Django 5.1.3
Path: D:\SaaSprojectService\Rasti chekFinal 10 tir

Context:
- Read docs/04_Business_Rules/PAYMENT_RULES.md first
- Read docs/07_ADR/ADR-004-Ledger-Discipline.md first
- All financial code must use: transaction.atomic, select_for_update(), Decimal, idempotency keys
- TechnicianLedgerEntry must never be modified — only new reversing entries

Audit scope:
- Read apps/[APP_NAME]/services.py
- Check: are all monetary calculations using Decimal?
- Check: is transaction.atomic used?
- Check: is select_for_update() used where race conditions are possible?
- Check: are idempotency keys present?
- Check: are ledger entries ever edited (UPDATE) vs created (INSERT)?

Report:
- Files checked
- Violations found (file:line)
- Compliant patterns
- Risk assessment
```

---

## Prompt: Test Coverage Gap Analysis

```
Analyze test coverage gaps in [APP_NAME].

Project: Rasti SaaS — Django 5.1.3
Path: D:\SaaSprojectService\Rasti chekFinal 10 tir

Context:
- Read docs/06_Quality_Assurance/TEST_STRATEGY.md first
- Total tests: ~1242 as of 2026-06-30
- Known gaps: multi-tenant isolation tests, notification trigger tests, API tests

Analysis scope:
- Read apps/[APP_NAME]/tests/
- Read apps/[APP_NAME]/services.py and views.py
- Identify service methods with no corresponding test
- Identify permission checks with no test for unauthorized access
- Identify status transitions with no test

Report:
- Tested behaviors (with test file references)
- Untested behaviors (with risk assessment)
- Recommended new tests (with test code examples)
```
