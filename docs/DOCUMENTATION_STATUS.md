---
Title: Documentation Status
Layer: Entry
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# Documentation Status

Current status of the Engineering Knowledge Base as of 2026-07-01.

---

## Rebuild Summary

The docs folder was rebuilt on 2026-07-01 from the original scattered docs into a 13-layer Engineering Knowledge Base.

See [DOCS_REBUILD_REPORT.md](DOCS_REBUILD_REPORT.md) for the full rebuild log.

---

## Layer Status

| Layer | Folder | Status | Coverage |
|---|---|---|---|
| Entry | Root `docs/` | ✅ Active | Complete |
| Human Engineering | `01_Human_Engineering/` | ✅ Active | Core files present |
| AI Operating System | `02_AI_Operating_System/` | ✅ Active | All 9 docs present |
| Architecture | `03_Architecture/` | ✅ Active | 6 of 11 docs complete |
| Business Rules | `04_Business_Rules/` | ✅ Active | 9 of 10 docs complete |
| Workflows | `05_Workflows/` | ✅ Active | 4 of 9 docs complete |
| Quality Assurance | `06_Quality_Assurance/` | ✅ Active | Core docs present |
| ADR | `07_ADR/` | ✅ Active | 8 ADRs + index |
| Site Map | `08_Site_Map/` | ✅ Active | 10 files, 238 URLs documented |
| Operations | `09_Operations/` | 🟡 Partial | 2 of 6 docs present |
| Prompts | `10_Prompts/` | 🟡 Partial | 2 of 6 docs present |
| Project Knowledge | `11_Project_Knowledge/` | ✅ Active | Core docs present |
| Archive | `archive/` | ✅ Active | README present |

---

## Files That Need to Be Written

### 01_Human_Engineering/ (Priority: Medium)
- `LOCAL_DEVELOPMENT.md` — Step-by-step local setup
- `APPLICATION_MAP.md` — Visual dependency map
- `DJANGO_ARCHITECTURE.md` — Django-specific notes
- `CONFIGURATION.md` — All environment variables
- `TESTING_GUIDE.md` — Test runner guide
- `DEPLOYMENT_GUIDE.md` — Deployment steps
- `MAINTENANCE_GUIDE.md` — Ongoing maintenance

### 03_Architecture/ (Priority: Medium)
- `DATABASE_MODEL.md` — Model relationships and fields
- `DOMAIN_MODEL.md` — Business domain entities
- `API_ARCHITECTURE.md` — REST API structure
- `INTEGRATION_MAP.md` — External integrations

### 04_Business_Rules/ (Priority: Low)
- `SERVICE_CATEGORY_RULES.md` — Service categories and items

### 05_Workflows/ (Priority: Medium)
- `PUBLIC_REQUEST_FLOW.md` — From form to order
- `OPERATOR_REVIEW_FLOW.md` — Operator review steps
- `TECHNICIAN_FLOW.md` — Technician daily workflow
- `RELEASE_FLOW.md` — Release process
- `DOCUMENTATION_UPDATE_FLOW.md` — How to update docs

### 06_Quality_Assurance/ (Priority: Medium)
- `TEST_COVERAGE_MAP.md` — Per-app test coverage
- `MANUAL_QA_CHECKLIST.md` — Manual testing steps
- `REGRESSION_TEST_PLAN.md` — Regression plan

### 09_Operations/ (Priority: High — needed before deployment)
- `DEPLOYMENT.md` — Deployment steps
- `BACKUP.md` — Backup procedures
- `ROLLBACK.md` — Rollback procedures
- `MONITORING.md` — What to monitor
- `SECURITY_OPERATIONS.md` — Security operations

### 10_Prompts/ (Priority: Low)
- `REVIEW_PROMPTS.md`
- `DEBUGGING_PROMPTS.md`
- `DOCUMENTATION_PROMPTS.md`
- `RELEASE_PROMPTS.md`

### 11_Project_Knowledge/ (Priority: Low)
- `KNOWN_CONSTRAINTS.md`
- `DECISION_LOG.md`

---

## Verified Documents (Based on Code Reading)

The following documents were written or verified against the actual codebase:

- ✅ `08_Site_Map/01_URL_INVENTORY.md` — 238 URLs verified against 21 url files
- ✅ `03_Architecture/PERMISSIONS.md` — Verified against `apps/accounts/permissions.py`
- ✅ `03_Architecture/MULTI_TENANCY.md` — Verified against `apps/tenants/middleware.py`
- ✅ `11_Project_Knowledge/KNOWN_RISKS.md` — Verified against code (each bug has file:line)
- ✅ `07_ADR/` — All 8 ADRs pre-existed and are authoritative

---

## Not Yet Verified (Needs Code Review)

- `04_Business_Rules/NOTIFICATION_RULES.md` — Catalog completeness needs verification
- `04_Business_Rules/PAYOUT_RULES.md` — Ledger entry types need verification
- `05_Workflows/CANCELLATION_FLOW.md` — `return-to-cycle` view behavior needs verification
