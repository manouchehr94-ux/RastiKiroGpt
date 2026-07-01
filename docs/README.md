---
Title: Rasti Engineering Knowledge Base
Layer: Entry
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: docs rebuild
Source of Truth: Mixed
Depends On: []
Related Documents: START_HERE.md, DOCS_INDEX.md
Reusable Across Projects: No
---

# Rasti Engineering Knowledge Base

**Project:** Rasti SaaS — Multi-Tenant Service Dispatch Platform
**Stack:** Django 5.1.3 · Python 3.11.9 · PostgreSQL · Tailwind CSS
**Date:** 2026-07-01

---

## What is this?

This folder is the single source of operational truth for the Rasti SaaS project.
It serves human developers, QA engineers, and AI coding agents equally.

---

## Quick Navigation

| You are... | Start here |
|---|---|
| New developer | [START_HERE.md](START_HERE.md) → [01_Human_Engineering/ONBOARDING.md](01_Human_Engineering/ONBOARDING.md) |
| AI agent (Claude, GPT, Cursor, etc.) | [02_AI_Operating_System/AI_AGENT_START_HERE.md](02_AI_Operating_System/AI_AGENT_START_HERE.md) |
| Reviewing architecture | [03_Architecture/SYSTEM_ARCHITECTURE.md](03_Architecture/SYSTEM_ARCHITECTURE.md) |
| Checking business rules | [04_Business_Rules/README.md](04_Business_Rules/README.md) |
| Reviewing security | [03_Architecture/PERMISSIONS.md](03_Architecture/PERMISSIONS.md) |
| Reviewing a workflow | [05_Workflows/README.md](05_Workflows/README.md) |
| Finding a URL or route | [08_Site_Map/01_URL_INVENTORY.md](08_Site_Map/01_URL_INVENTORY.md) |
| Checking a decision | [07_ADR/ADR_INDEX.md](07_ADR/ADR_INDEX.md) |
| Running QA | [06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md](06_Quality_Assurance/PRODUCTION_READINESS_CHECKLIST.md) |
| Checking known issues | [11_Project_Knowledge/KNOWN_RISKS.md](11_Project_Knowledge/KNOWN_RISKS.md) |

---

## Folder Structure

```
docs/
├── README.md                     ← You are here
├── START_HERE.md                 ← Reading guide for humans and AI
├── DOCS_INDEX.md                 ← Complete index of all documents
├── DOCUMENTATION_STATUS.md       ← Status of this documentation system
├── CHANGELOG.md                  ← Documentation changelog
├── VERSION.md                    ← EKB version record
│
├── 00_Project/                   ← Project overview, scope, glossary, terminology
├── 01_Human_Engineering/         ← Developer onboarding, local dev, testing, maintenance
├── 02_AI_Operating_System/       ← AI agent rules, protocols, context maps
├── 03_Architecture/              ← System design, multi-tenancy, permissions, service layer
├── 04_Business_Rules/            ← Domain rules per entity
├── 05_Workflows/                 ← End-to-end process flows with Mermaid diagrams
├── 06_Quality_Assurance/         ← Testing, QA checklists, production readiness
├── 07_ADR/                       ← Architecture Decision Records (binding)
├── 08_Site_Map/                  ← URL inventory and navigation maps (Persian)
├── 09_Operations/                ← Deployment, backup, monitoring, rollback, security
├── 10_Prompts/                   ← Reusable AI prompts by task category
├── 11_Project_Knowledge/         ← Known risks, constraints, open questions
├── 99_AUDIT_2026_06_30/          ← Technical audit snapshot (Persian, reference only)
└── archive/                      ← Superseded and historical documents
```

---

## Critical Security Alerts (Unresolved as of 2026-07-01)

| # | Issue | File | Severity |
|---|---|---|---|
| P0-1 | `admin_operator_list` missing `@require_tenant_role` | `apps/tenants/views_admin.py:2125` | CRITICAL |
| P0-2 | JWT logout does not invalidate token | `apps/api/auth_views.py:152` | CRITICAL |
| P0-3 | Hardcoded `"123456"` default password check in production login | `apps/accounts/views.py:58` | CRITICAL |
| P0-4 | `ALLOWED_HOSTS = ["*"]` active in base settings | `config/settings/base.py:19` | HIGH |
| P0-5 | `Customer.objects.create(name=...)` — field does not exist | `apps/api/views.py:311` | CRITICAL |

See [11_Project_Knowledge/KNOWN_RISKS.md](11_Project_Knowledge/KNOWN_RISKS.md) for full details.

---

## Read Order for AI Agents

1. `docs/00_Project/SKILL.md` — source-of-truth order and key rules
2. `docs/README.md` — this file
3. `docs/02_AI_Operating_System/AI_AGENT_START_HERE.md` — full AI operating instructions
4. `docs/02_AI_Operating_System/AI_CODE_CHANGE_RULES.md` — non-negotiable rules
5. Relevant ADRs under `docs/07_ADR/`
6. Relevant business rules under `docs/04_Business_Rules/`
7. Relevant architecture rules under `docs/03_Architecture/`
8. Code and tests

---

## Folder Map

| Folder | Purpose |
|---|---|
| `00_Project/` | Scope, glossary, terminology, project overview |
| `01_Human_Engineering/` | Developer onboarding, local dev, testing, maintenance |
| `02_AI_Operating_System/` | AI agent rules, protocols, context maps |
| `03_Architecture/` | System architecture, multi-tenancy, permissions, service layer |
| `04_Business_Rules/` | Business rules per entity (orders, payments, invoices, etc.) |
| `05_Workflows/` | End-to-end process flows with Mermaid diagrams |
| `06_Quality_Assurance/` | Test strategy, QA checklists, production readiness |
| `07_ADR/` | Architecture Decision Records (binding) |
| `08_Site_Map/` | URL inventory and navigation maps (Persian) |
| `09_Operations/` | Deployment, backup, monitoring, rollback, security |
| `10_Prompts/` | Reusable AI prompts by task category |
| `11_Project_Knowledge/` | Known risks, constraints, open questions, source of truth |
| `99_AUDIT_2026_06_30/` | Complete technical audit (point-in-time reference, Persian) |
| `archive/` | Superseded and historical documents |

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
