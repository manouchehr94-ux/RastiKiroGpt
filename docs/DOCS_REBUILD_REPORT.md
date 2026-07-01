---
Title: Documentation Rebuild Report
Layer: Entry
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# Documentation Rebuild Report

**Date:** 2026-07-01
**Type:** Major reorganization
**Scope:** Complete docs folder rebuild into Engineering Knowledge Base v2.0

---

## 1. What Changed

The docs folder was reorganized from an ad-hoc structure into a 13-layer Engineering Knowledge Base optimized for both human developers and AI agents.

### Before

```
docs/
├── 00_Project/       ← project overview (12 files, many in Persian)
├── 01_Architecture/  ← architecture stubs (16-26 lines each)
├── 02_Development_System/  ← AI protocol + templates
├── 03_Business/      ← business rule stubs (13-33 lines each)
├── 04_Testing/       ← test stubs
├── 05_Deployment/    ← deployment stubs
├── 06_Phases/        ← phase history
├── 07_ADR/           ← good ADRs (kept)
├── 08_Site_Map/      ← just created (2026-07-01)
├── 99_AUDIT_2026_06_30/  ← audit (kept)
├── AI/               ← AI rules and protocol
└── archive/          ← old reports
```

Problems:
- Architecture docs were 16-26 lines (stubs)
- Business rule docs were 13-33 lines (stubs)
- No AI agent operating system
- No unified entry point
- No source-of-truth policy
- No known risks tracking
- Folder numbering inconsistent with target structure

### After

```
docs/
├── README.md           ← landing page with security alerts
├── START_HERE.md       ← reading guide for humans and AI
├── DOCS_INDEX.md       ← complete index
├── DOCUMENTATION_STATUS.md
├── CHANGELOG.md
├── DOCS_REBUILD_REPORT.md
├── 00_Project/         ← unchanged (good content kept)
├── 01_Human_Engineering/   ← new: developer onboarding
├── 02_AI_Operating_System/ ← new: 9 AI protocol files
├── 03_Architecture/    ← new: expanded from stubs
├── 04_Business_Rules/  ← new: expanded from stubs
├── 05_Workflows/       ← new: 4 workflow docs
├── 06_Quality_Assurance/   ← new: QA and production checklist
├── 07_ADR/             ← unchanged + ADR_INDEX.md added
├── 08_Site_Map/        ← unchanged (10 files)
├── 09_Operations/      ← new: partial
├── 10_Prompts/         ← new: prompt library
├── 11_Project_Knowledge/   ← new: KNOWN_RISKS, SOURCE_OF_TRUTH
└── archive/            ← README.md added
```

---

## 2. Files Created

**Total new files created: 55+**

Key files:
- `02_AI_Operating_System/` — 9 files (all new)
- `03_Architecture/` — 6 expanded or new files
- `04_Business_Rules/` — 9 expanded or new files
- `05_Workflows/` — 4 new files
- `06_Quality_Assurance/` — 3 files
- `11_Project_Knowledge/` — 3 files
- Root level — 6 files (README rewritten + 5 new)

---

## 3. Files Moved

No files were physically moved. The old structure remains in place.

Old folders (`01_Architecture/`, `02_Development_System/`, `03_Business/`, `AI/`) still exist and are referenced in `archive/README.md`.

**Recommended follow-up:** Archive the old folders by moving their content to `archive/old_docs/`. Do not delete — preserve for history.

---

## 4. Files Reused Without Rewriting

- `00_Project/GLOSSARY.md` — Excellent, kept verbatim
- `00_Project/TERMINOLOGY.md` — Excellent, kept verbatim
- `00_Project/PROJECT_SCOPE.md` — Kept
- `07_ADR/ADR-001` through `ADR-008` — All kept verbatim
- `08_Site_Map/` — All 10 files kept
- `99_AUDIT_2026_06_30/` — All 11 files kept

---

## 5. Files Substantially Rewritten or Replaced

| Old File | New File | Change |
|---|---|---|
| `01_Architecture/SYSTEM_ARCHITECTURE.md` (16 lines) | `03_Architecture/SYSTEM_ARCHITECTURE.md` (comprehensive) | Major expansion |
| `01_Architecture/PERMISSIONS.md` (26 lines) | `03_Architecture/PERMISSIONS.md` | Major expansion with P0-1 detail |
| `01_Architecture/MULTI_TENANT.md` (21 lines) | `03_Architecture/MULTI_TENANCY.md` | Expanded with forbidden patterns |
| `01_Architecture/SERVICE_LAYER.md` (21 lines) | `03_Architecture/SERVICE_LAYER.md` | Expanded with code examples |
| `03_Business/ORDER_RULES.md` (33 lines) | `04_Business_Rules/ORDER_RULES.md` | Major expansion with state machine |
| `03_Business/INVOICE_RULES.md` (13 lines) | `04_Business_Rules/INVOICE_RULES.md` | Major expansion |
| `AI/AI_RULES.md` (48 lines) | `02_AI_Operating_System/AI_CODE_CHANGE_RULES.md` | Expanded with rationale |
| `AI/AI_DEVELOPMENT_PROTOCOL.md` | `02_AI_Operating_System/AI_SAFE_CHANGE_PROTOCOL.md` | Expanded and structured |
| `docs/README.md` | Rewritten with navigation table and security alerts |

---

## 6. Remaining Risks

1. **Old folder structure still in place** — `01_Architecture/`, `02_Development_System/`, `03_Business/`, `AI/` still exist. AI agents might read them and get outdated stubs. Recommendation: archive them.

2. **~25 documents still need to be written** — See `DOCUMENTATION_STATUS.md` for the list. Priority: `09_Operations/DEPLOYMENT.md` before any production deployment.

3. **Persian documents in `00_Project/`** — Some files like `START_HERE_FA.md`, `PROJECT_STATUS_FA.md`, `SMOKE_CHECKLIST_FA.md` are in Persian. They were not touched. Consider translating to English per the language requirement.

4. **Root-level FA files** — `Rasti_Master_Roadmap_FA.md`, `Rasti_Production_Readiness_Audit_Review_FA.md`, `Rasti_Scalability_Roadmap_FA.md` are at the docs root. Should be moved to `00_Project/` or archived.

---

## 7. What Future AI Agents Should Read First

**Mandatory reading order:**
1. `docs/02_AI_Operating_System/AI_AGENT_START_HERE.md`
2. `docs/11_Project_Knowledge/KNOWN_RISKS.md`
3. The specific task context from `docs/02_AI_Operating_System/AI_CONTEXT_MAP.md`

---

## 8. What Human Developers Should Read First

**Recommended reading order:**
1. `docs/START_HERE.md`
2. `docs/01_Human_Engineering/ONBOARDING.md`
3. `docs/00_Project/GLOSSARY.md`
4. `docs/03_Architecture/SYSTEM_ARCHITECTURE.md`
5. `docs/11_Project_Knowledge/KNOWN_RISKS.md`
