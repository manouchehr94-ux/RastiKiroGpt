---
Title: Engineering Knowledge Base — Version Record
Layer: Entry
Audience: Human + AI
Status: Active
Last Updated: 2026-07-01
---

# Engineering Knowledge Base — Version Record

---

## Current Version

**Engineering Knowledge Base v1.0**

Release date: 2026-07-01
Status: Released

---

## What v1.0 Includes

| Layer | Description | Doc Count |
|---|---|---|
| 00_Project | Scope, glossary, terminology, overview | 11 |
| 01_Human_Engineering | Developer onboarding, local dev, testing, maintenance | 6 |
| 02_AI_Operating_System | AI agent rules, protocols, context maps, handoff | 9 |
| 03_Architecture | System, multi-tenancy, permissions, service layer, database, domain, API | 9 |
| 04_Business_Rules | 9 business domains fully documented | 9 |
| 05_Workflows | 8 end-to-end process flows with Mermaid diagrams | 8 |
| 06_Quality_Assurance | Test strategy, manual QA, regression plan, readiness checklist | 5 |
| 07_ADR | 8 binding architecture decisions + index + template | 11 |
| 08_Site_Map | All 238 URL patterns in Persian | 10 |
| 09_Operations | Deployment, backup, monitoring, rollback, security | 6 |
| 10_Prompts | Audit, implementation, review, debugging, release prompts | 5 |
| 11_Project_Knowledge | Risks, constraints, source of truth, open questions | 4 |
| 99_AUDIT_2026_06_30 | Complete technical audit snapshot (Persian) | 12 |
| Root + reports | README, DOCS_INDEX, CHANGELOG, migration reports | 7 |
| **Total active docs** | | **112+** |

---

## Version History

| Version | Date | Description |
|---|---|---|
| v0.1 | 2026-06-30 | Initial technical audit (99_AUDIT_2026_06_30) |
| v0.5 | 2026-07-01 | Phase 2: Engineering Knowledge Base initial build (75+ new docs) |
| v0.9 | 2026-07-01 | Phase 3: Documentation migration and consolidation (archive old structure) |
| **v1.0** | **2026-07-01** | **Final standardization pass — EKB released** |

---

## What v1.0 Does NOT Include

These topics are documented as "Future scope" and will be addressed in v1.1+:
- Service category business rules (`04_Business_Rules/SERVICE_CATEGORY_RULES.md`)
- Test coverage map (`06_Quality_Assurance/TEST_COVERAGE_MAP.md`)
- Integration/external service map (`03_Architecture/INTEGRATION_MAP.md`)
- Application map for developers (`01_Human_Engineering/APPLICATION_MAP.md`)
- Developer onboarding first-week walkthrough
- Scalability roadmap (Persian version exists in `archive/superseded/`)

---

## Version Policy

- v1.x patches: Documentation corrections, link fixes, content verification updates
- v1.x minor: New documents added to cover "future scope" items
- v2.0: Only when the documentation architecture itself changes (would require new Phase)

---

## Maintenance Owner

Documentation maintenance is a shared responsibility:
- After fixing a P0 bug → update `11_Project_Knowledge/KNOWN_RISKS.md`
- After an architectural decision → create/update ADR in `07_ADR/`
- After a new URL or major feature → update `08_Site_Map/01_URL_INVENTORY.md`
- After a workflow change → update `05_Workflows/`
