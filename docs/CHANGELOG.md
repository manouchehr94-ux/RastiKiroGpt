---
Title: Documentation Changelog
Layer: Entry
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# Documentation Changelog

---

## 2026-07-01 — Engineering Knowledge Base v2.0

**Type:** Major rebuild

Complete reorganization of the docs folder into a 13-layer Engineering Knowledge Base.

### New Folders Created

- `01_Human_Engineering/` — Developer onboarding and guides
- `02_AI_Operating_System/` — AI agent protocols (9 documents)
- `03_Architecture/` — Expanded from old `01_Architecture/` stubs
- `04_Business_Rules/` — Expanded from old `03_Business/` stubs
- `05_Workflows/` — New workflow documents
- `06_Quality_Assurance/` — QA and testing docs
- `09_Operations/` — Deployment and operations
- `10_Prompts/` — Reusable AI prompts
- `11_Project_Knowledge/` — Known risks, open questions, SOT policy

### New Documents Written

**AI Operating System (9 files):**
- `AI_AGENT_START_HERE.md` — Main AI entry point
- `AI_CONTEXT_MAP.md` — Task-to-docs mapping
- `AI_READING_ORDER.md` — Reading order by task type
- `AI_SAFE_CHANGE_PROTOCOL.md` — Step-by-step safe change procedure
- `AI_CODE_CHANGE_RULES.md` — Non-negotiable code change rules
- `AI_VERIFICATION_PROTOCOL.md` — How to verify changes
- `AI_HANDOFF_PROTOCOL.md` — Session handoff procedure
- `AI_LIMITATIONS.md` — When to inspect code vs trust docs
- `AI_PROMPT_USAGE_GUIDE.md` — How to use the prompt library

**Architecture (6 files expanded from stubs):**
- `SYSTEM_ARCHITECTURE.md` (expanded from 16-line stub)
- `DJANGO_APP_ARCHITECTURE.md` (new)
- `MULTI_TENANCY.md` (expanded from 21-line stub)
- `PERMISSIONS.md` (expanded from 26-line stub with P0-1 detail)
- `SERVICE_LAYER.md` (expanded from 21-line stub)
- `TEMPLATE_ARCHITECTURE.md` (new)

**Business Rules (9 files expanded/created):**
- `ORDER_RULES.md` (expanded from 33-line stub)
- `INVOICE_RULES.md` (expanded from 13-line stub)
- `PAYMENT_RULES.md` (new comprehensive)
- `TECHNICIAN_RULES.md` (new)
- `PAYOUT_RULES.md` (new)
- `CUSTOMER_RULES.md` (new)
- `COMPANY_RULES.md` (expanded)
- `NOTIFICATION_RULES.md` (new)
- `SMS_RULES.md` (new)

**Workflows (4 files):**
- `ORDER_LIFECYCLE.md` — With Mermaid state machine
- `INVOICE_PAYMENT_FLOW.md` — With Mermaid flowcharts
- `CANCELLATION_FLOW.md`
- `NOTIFICATION_FLOW.md`

**Quality Assurance (3 files):**
- `PRODUCTION_READINESS_CHECKLIST.md`
- `TEST_STRATEGY.md`
- `AI_VERIFICATION_CHECKLIST.md`

**Project Knowledge (3 files):**
- `KNOWN_RISKS.md` — All P0-P5 bugs with file:line references
- `SOURCE_OF_TRUTH.md` — Policy document
- `OPEN_QUESTIONS.md`

**Prompt Library (2 files):**
- `AUDIT_PROMPTS.md`
- `IMPLEMENTATION_PROMPTS.md`

**Root level (4 files):**
- `START_HERE.md`
- `DOCS_INDEX.md`
- `DOCUMENTATION_STATUS.md`
- `CHANGELOG.md`

**ADR section (2 files):**
- `ADR_INDEX.md`
- `07_ADR/README.md`

### Preserved (Not Changed)

- `07_ADR/ADR-001` through `ADR-008` — All ADRs preserved exactly
- `08_Site_Map/` — All 10 site map files preserved (created 2026-07-01)
- `99_AUDIT_2026_06_30/` — Full audit preserved (11 files)
- `00_Project/GLOSSARY.md` — Preserved
- `00_Project/TERMINOLOGY.md` — Preserved
- `00_Project/PROJECT_SCOPE.md` — Preserved

---

## 2026-07-01 — Site Map v1.0

Complete site map package created:
- 238 URL patterns documented
- 199+ templates mapped
- 5 security/navigation risks identified
- Navigation gap analysis and redesign proposals

---

## 2026-06-30 — Technical Audit v1.0

Full technical audit completed:
- 7 critical bugs identified
- Architecture scored (9/10 multi-tenancy, 8/10 order lifecycle)
- 1242 tests confirmed
- Production readiness gap analysis

---

## Prior to 2026-06-30

- RDOS v1.0 documentation system created (original docs structure)
- ADRs 001-008 written
- Phase 1-3 completed (foundation, payment, accounting)
