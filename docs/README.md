# Rasti Service Documentation Index — RDOS v1.0

This folder is the source of truth for Rasti Service architecture, business rules, AI-agent behaviour, testing, deployment, and phase planning.

---

## Read Order for AI Agents

1. `SKILL.md`
2. `docs/README.md`
3. `docs/01_Architecture/ARCHITECTURE_INDEX.md`
4. Relevant ADRs under `docs/07_ADR/`
5. Relevant business rules under `docs/03_Business/`
6. Relevant architecture rules under `docs/01_Architecture/`
7. Development workflow files under `docs/02_Development_System/`
8. Code and tests

---

## Folder Map

| Folder | Purpose |
|---|---|
| `00_Project` | Vision, scope, glossary, naming, terminology |
| `01_Architecture` | Technical architecture, domain model, database, security, permissions |
| `02_Development_System` | Claude behaviour, prompts, task/review templates, checklists |
| `03_Business` | Business rules for orders, invoices, payments, customers, companies, technicians, SMS |
| `04_Testing` | Test strategy and test rules |
| `05_Deployment` | Backup, release, rollback, monitoring |
| `06_Phases` | Implementation phases and roadmap |
| `07_ADR` | Architecture Decision Records |

---

## Source-of-Truth Priority

When rules conflict:

1. ADRs win over all other documents.
2. Business rules win over architecture details.
3. Architecture rules win over development workflow documents.
4. Development workflow documents define process, not business truth.
5. Code shows current implementation; it may be wrong.
6. Project glossary and terminology clarify language, not architecture decisions.

If a conflict cannot be resolved, stop and report it.

---

## RDOS v1.0 Freeze Rule

RDOS v1.0 is considered stable after these documents are applied. Future changes must be tracked using ADRs and changelog entries.
