---
Title: Project Knowledge — README
Layer: Project Knowledge
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# 11 — Project Knowledge

Non-obvious facts, constraints, risks, and open questions about the Rasti project.

---

## Files in This Folder

| File | Contents | Status |
|---|---|---|
| [KNOWN_RISKS.md](KNOWN_RISKS.md) | All known bugs and risks with severity and status | Active |
| [SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md) | What is authoritative for each type of knowledge | Active |
| [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) | Product and technical questions needing decisions | Active |
| [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md) | Development principles and non-negotiable constraints | Active |

---

## Reading Order

1. [KNOWN_RISKS.md](KNOWN_RISKS.md) — read first; 5 P0 bugs that must not be worsened
2. [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md) — non-negotiable rules for all development
3. [SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md) — what to trust when docs conflict
4. [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) — decisions pending

---

## Related Documents

- [../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md](../06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md) — detailed P0 fix checklist
- [../07_ADR/](../07_ADR/) — binding architectural decisions
- [../02_AI_Operating_System/AI_CODE_CHANGE_RULES.md](../02_AI_Operating_System/AI_CODE_CHANGE_RULES.md) — AI-specific constraints

---

## Maintenance Notes

- When a P0 bug is fixed → update [KNOWN_RISKS.md](KNOWN_RISKS.md)
- When a product decision is made → update [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)
- When docs and code conflict → update [SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md)
- When a new architectural constraint is discovered → update [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md)
