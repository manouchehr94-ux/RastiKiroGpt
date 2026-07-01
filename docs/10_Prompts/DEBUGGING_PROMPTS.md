---
Title: Debugging Prompts
Layer: Prompts
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: 02_Development_System/BUG_REPORT_TEMPLATE.md, AI/PROMPTS/BUG_FIX_TEMPLATE.md
Source of Truth: Policy
Depends On: []
Related Documents: REVIEW_PROMPTS.md, ../11_Project_Knowledge/KNOWN_RISKS.md
Reusable Across Projects: Partially
---

# Debugging Prompts

Prompts and templates for reporting, investigating, and fixing bugs.

---

## Bug Report Template

Use when filing a new bug or reporting an issue to an AI agent.

```
## Bug Report

**Title:** [short description]
**Severity:** Critical / High / Medium / Low
**Date:** [date]

**Who is affected:**
[which role, which flow, which company type]

**Reproduction steps:**
1. 
2. 
3. 

**Expected behavior:**
[what should happen]

**Actual behavior:**
[what actually happens]

**Error message or log output:**
[paste error, traceback, or log if available]

**Suspected root cause:**
[if known]

**Related files:**
[list files if known]

**Risk of fix:**
[High (financial code, permissions) / Medium / Low]

**Tests required:**
[what tests should be added/changed]
```

---

## AI Bug Fix Prompt

Use when asking an AI agent to fix a specific bug.

```
Fix this bug in the Rasti SaaS project.

Bug description:
[paste bug report]

Constraints — read before starting:
1. Fix ONLY the bug described. Do not refactor unrelated code.
2. Do not change more than 5 files without asking first.
3. Do not remove or weaken any existing tests.
4. Do not create Django migrations unless explicitly permitted.
5. If the fix requires changes to financial code, list the changes and ask before implementing.
6. All money must stay as Decimal — never float.
7. Multi-tenant isolation must be preserved — all querysets must filter by company.
8. If you find additional bugs while investigating, report them separately.

After fixing:
1. Show the complete diff
2. Show which tests cover the fix
3. State the regression test you added
4. Flag any uncertainty as "Needs Verification"
```

---

## Diagnostic Prompt (When Bug Cause Is Unknown)

Use to ask an AI to investigate without implementing a fix yet.

```
Investigate this problem in the Rasti SaaS project without making any changes.

Problem description:
[describe the symptom]

Files to investigate:
[list files or app name]

I need:
1. Root cause hypothesis
2. Exact file and line number where the problem originates
3. Which other files are affected
4. What test would reproduce this bug
5. Risk level: is this a financial, security, or low-risk issue?

Do NOT implement a fix yet. Report findings only.
```

---

## Known P0 Bugs Reference

Before investigating a new bug, check if it is already a known P0:

| ID | Description | File | Quick Check |
|---|---|---|---|
| P0-1 | `admin_operator_list` missing permission decorator | `apps/platform_core/views.py` | Check decorator on view |
| P0-2 | JWT logout does not invalidate token | `apps/accounts/views.py` | Check logout view |
| P0-3 | Hardcoded password "123456" | `apps/accounts/services.py` | Search for "123456" |
| P0-4 | Platform commission on non-platform payments | `apps/payments/services.py` | Check commission logic |
| P0-5 | `Customer.name` field crash in API | `apps/customers/serializers.py` | Check field mapping |

See full details in [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md).
