---
Title: AI Prompt Usage Guide
Layer: AI Operating System
Audience: AI + Human
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: Partially
---

# AI Prompt Usage Guide

How to use the prompt library in `docs/10_Prompts/`.

---

## When to Use Prompts

Prompts in `10_Prompts/` are starting templates. They are not complete task definitions.

Use a prompt when:
- Starting a new audit session
- Starting a new feature implementation
- Starting a code review
- Debugging an issue
- Creating documentation

---

## How to Adapt a Prompt

Every prompt must be adapted for the specific task:

1. Replace `[APP_NAME]` with the actual app name (e.g., `orders`, `payments`)
2. Replace `[TASK_DESCRIPTION]` with the specific task
3. Add the specific file paths involved
4. Add the specific ADRs relevant to the task
5. Add the specific test commands for the app

---

## Required Prompt Context (for AI agents starting fresh)

When giving a prompt to a new AI agent, always include:

```
PROJECT: Rasti SaaS — Django 5.1.3, Python 3.11.9, PostgreSQL
PATH: D:\SaaSprojectService\Rasti chekFinal 10 tir
DOCS: Read docs/02_AI_Operating_System/AI_AGENT_START_HERE.md first
RULES:
- Never weaken multi-tenant isolation
- Business logic only in services.py
- Decimal only for financial values
- @require_tenant_role decorator on all admin views
```

---

## Prompt Categories

| File | Use for |
|---|---|
| `AUDIT_PROMPTS.md` | Running a technical audit of a specific area |
| `IMPLEMENTATION_PROMPTS.md` | Implementing a specific feature or fix |
| `REVIEW_PROMPTS.md` | Reviewing code changes |
| `DEBUGGING_PROMPTS.md` | Diagnosing a specific bug |
| `DOCUMENTATION_PROMPTS.md` | Writing or updating documentation |
| `RELEASE_PROMPTS.md` | Preparing a release or deployment |

---

## The Development Workflow (Human + AI)

This project uses a structured human-AI workflow:

1. **Human (Product Owner)** — Reports issue or feature request
2. **AI Agent (Architect role)** — Writes structured implementation request/prompt
3. **AI Agent (Implementation role)** — Reads repo, audits, proposes solution
4. **Human review** — Approves or revises the proposal
5. **AI Agent** — Implements approved scope only
6. **AI Agent** — Runs tests, reports results
7. **Human** — Performs manual QA, approves or rejects

**The "No-Code-First Rule":** For Critical or High severity issues, audit and report before implementing. Wait for human approval.
