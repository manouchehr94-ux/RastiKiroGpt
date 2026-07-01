---
Title: Start Here — Reading Guide
Layer: Entry
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# Start Here

This is the reading guide for the Rasti Engineering Knowledge Base.

---

## If you are a human developer

**New to the project?** Read in this order:

1. [00_Project/PROJECT_OVERVIEW.md](00_Project/PROJECT_OVERVIEW.md) — What is Rasti?
2. [00_Project/GLOSSARY.md](00_Project/GLOSSARY.md) — Business terms
3. [01_Human_Engineering/ONBOARDING.md](01_Human_Engineering/ONBOARDING.md) — How to set up
4. [01_Human_Engineering/REPOSITORY_STRUCTURE.md](01_Human_Engineering/REPOSITORY_STRUCTURE.md) — Where is everything?
5. [03_Architecture/SYSTEM_ARCHITECTURE.md](03_Architecture/SYSTEM_ARCHITECTURE.md) — How it works

**Starting a task?**

- Order task → [04_Business_Rules/ORDER_RULES.md](04_Business_Rules/ORDER_RULES.md) + [05_Workflows/ORDER_LIFECYCLE.md](05_Workflows/ORDER_LIFECYCLE.md)
- Security task → [03_Architecture/PERMISSIONS.md](03_Architecture/PERMISSIONS.md)
- Payment task → [04_Business_Rules/PAYMENT_RULES.md](04_Business_Rules/PAYMENT_RULES.md) + [07_ADR/ADR-003-Payment-Architecture.md](07_ADR/ADR-003-Payment-Architecture.md)
- Navigation/URL task → [08_Site_Map/01_URL_INVENTORY.md](08_Site_Map/01_URL_INVENTORY.md)

---

## If you are an AI agent

**Read this first and only:**

→ [02_AI_Operating_System/AI_AGENT_START_HERE.md](02_AI_Operating_System/AI_AGENT_START_HERE.md)

That document tells you exactly:
- What to read for each task type
- What you must verify in code before trusting docs
- What you must never do
- How to hand off context to the next session

**Do not skip it.**

---

## Source of Truth Policy

| What you need to know | Source of truth |
|---|---|
| Current implementation | The code (`apps/`) |
| Architectural decisions | [07_ADR/](07_ADR/) |
| Business intent | [04_Business_Rules/](04_Business_Rules/) (if verified) |
| Navigation/routing | [08_Site_Map/01_URL_INVENTORY.md](08_Site_Map/01_URL_INVENTORY.md) (as of 2026-07-01) |
| Known bugs | [11_Project_Knowledge/KNOWN_RISKS.md](11_Project_Knowledge/KNOWN_RISKS.md) |
| Open questions | [11_Project_Knowledge/OPEN_QUESTIONS.md](11_Project_Knowledge/OPEN_QUESTIONS.md) |

**Rule: If docs and code conflict, trust the code. Mark the conflict in the doc.**

---

## What this project is NOT

- It is not an e-commerce platform.
- It is not a marketplace.
- The platform owner is not a merchant — tenant companies are.
- Customers pay the tenant company, not Rasti Service directly.
- "Billing" (`apps/billing/`) is a stub — SaaS subscription logic is not implemented.
