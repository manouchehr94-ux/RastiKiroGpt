---
Title: Source of Truth Policy
Layer: Project Knowledge
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: ADR
Depends On: []
Related Documents: ../07_ADR/ADR_INDEX.md
Reusable Across Projects: Partially
---

# Source of Truth Policy

Defines what is authoritative for each type of project knowledge.

---

## Rule Table

| What you need to know | Source of truth | Notes |
|---|---|---|
| Current implementation | **The code** (`apps/`) | Always verify in code |
| Accepted architectural decisions | **ADRs** (`07_ADR/`) | ADRs are binding |
| Intended business behavior | **Business rule docs** (`04_Business_Rules/`) | Verify in code — docs may be behind |
| Navigation and URL structure | **Site Map** (`08_Site_Map/01_URL_INVENTORY.md`) | Valid as of 2026-07-01 |
| Known bugs | **KNOWN_RISKS.md** (`11_Project_Knowledge/`) | Keep updated as bugs are fixed |
| Current tests | **Test files** (`apps/*/tests/`) | Test output is authoritative |
| Database schema | **Migrations** (`apps/*/migrations/`) | Not the models (which may be ahead of migrations) |

---

## Rules

### Rule 1 — Code Beats Docs

If documentation says X and code does Y, **code is correct**.

Mark the conflict clearly:
```
> **Note:** This doc says X but code currently does Y at [file:line].
> The doc needs to be updated. Do not trust this section until verified.
```

### Rule 2 — ADRs Are Binding

Once an ADR is accepted, its decision is binding unless a new ADR supersedes it.

Do not change code in a way that violates an accepted ADR without creating a new superseding ADR.

### Rule 3 — Docs with "Needs Verification" Are Not Authoritative

Any section marked "Needs Verification" must be verified in code before trusting.

### Rule 4 — Site Map Has an Expiry Date

The site map was verified on **2026-07-01**. URL patterns change over time. Always check against `config/urls.py` if the URL matters for a production decision.

### Rule 5 — AI Docs Are Operating Instructions, Not Proof

The AI Operating System docs (`02_AI_Operating_System/`) describe how agents should work. They are not proof that any feature is implemented correctly. Always verify implementation in code.

---

## When Docs and Code Conflict

1. Trust the code
2. Mark the conflicting doc section as "Needs Update"
3. If the behavior looks like a bug, add it to `KNOWN_RISKS.md`
4. If the code behavior is intentional but different from docs, update the docs

---

## Documentation Maintenance Responsibility

- After fixing a P0 bug → update `KNOWN_RISKS.md` (mark as fixed)
- After adding a URL → update `08_Site_Map/01_URL_INVENTORY.md`
- After changing a business rule → update `04_Business_Rules/`
- After making an architectural decision → create or update an ADR
- After changing permissions → update `03_Architecture/PERMISSIONS.md`
