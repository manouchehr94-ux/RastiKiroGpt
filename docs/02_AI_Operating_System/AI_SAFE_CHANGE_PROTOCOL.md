---
Title: AI Safe Change Protocol
Layer: AI Operating System
Audience: AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: ADR + Code
Reusable Across Projects: Partially
---

# AI Safe Change Protocol

This is the step-by-step protocol for making any code change safely.

---

## Step 1 — Read Docs First

Before touching code:
1. Open [AI_CONTEXT_MAP.md](AI_CONTEXT_MAP.md)
2. Find the task type
3. Read all listed docs for that task type
4. Read all listed ADRs for that task type

Do not skip this step even for "small" changes.

---

## Step 2 — Identify Source of Truth

Ask: "What is the authoritative source for this behavior?"

| Source | When it applies |
|---|---|
| The code | Current implementation |
| ADRs | Accepted architectural decisions |
| Business rule docs | Intended behavior (verify in code) |
| Site map docs | Navigation/routing as of 2026-07-01 |
| Audit report | Known bugs (verify still true) |

If docs and code conflict, trust the code. Mark the conflict.

---

## Step 3 — Read the Specific Code

Read only the files you will change and their direct dependencies:
- The model(s) involved
- The service(s) involved
- The view(s) involved
- The test file(s) covering this area

Do not read the entire codebase.

---

## Step 4 — Confirm Scope

Before writing code, state clearly:
- "I will change: [list of files and what changes]"
- "I will NOT change: [list of related things that are out of scope]"
- "Risks: [list potential side effects]"

For Critical or High severity changes, stop here and wait for confirmation.

---

## Step 5 — Make the Change

- Make the narrowest possible change
- Do not clean up unrelated code
- Do not rename anything outside scope
- Do not add abstractions not required by the task

---

## Step 6 — Update Docs If Needed

If the change affects:
- A business rule → update `04_Business_Rules/`
- A URL → update `08_Site_Map/01_URL_INVENTORY.md`
- A permission → update `03_Architecture/PERMISSIONS.md`
- An architectural decision → create or update an ADR in `07_ADR/`
- A known risk → update `11_Project_Knowledge/KNOWN_RISKS.md`

---

## Step 7 — Run Targeted Tests

```bash
# Run tests for the app you changed
python manage.py test apps.<app_name> --verbosity=2

# Run related tests
python manage.py test apps.orders apps.payments --verbosity=2

# Full suite (only if scope is broad)
python manage.py test --verbosity=1
```

---

## Step 8 — Report

Your implementation report must include:
- Files changed (with line numbers)
- Tests run (command + result)
- Risks from the change
- What was NOT changed (but is related)
- Manual QA steps needed

---

## Fast Track (Documentation-Only Tasks)

For tasks that only touch `docs/`:
1. Read relevant existing docs
2. Make changes
3. Verify no broken links
4. Report what was changed and why

---

## Emergency Protocol (P0 Bug Fix)

For critical security bugs (P0-1 through P0-5):
1. Read the specific file and line noted in [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md)
2. Confirm the bug still exists in current code
3. Make the minimum fix
4. Run the full test suite
5. Report with a security-focused summary
