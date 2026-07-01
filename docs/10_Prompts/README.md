---
Title: Prompt Library — README
Layer: Prompt Library
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: Partially
---

# 10 — Prompt Library

Reusable prompts for common tasks in the Rasti project.

---

## Files in This Folder

| File | Use For | Status |
|---|---|---|
| [AUDIT_PROMPTS.md](AUDIT_PROMPTS.md) | Security audits, isolation audits, coverage analysis | Active |
| [IMPLEMENTATION_PROMPTS.md](IMPLEMENTATION_PROMPTS.md) | Bug fixes, new features, status transitions | Active |
| [REVIEW_PROMPTS.md](REVIEW_PROMPTS.md) | Code review — full, financial, multi-tenant | Active |
| [DEBUGGING_PROMPTS.md](DEBUGGING_PROMPTS.md) | Diagnosing and fixing bugs | Active |
| [RELEASE_PROMPTS.md](RELEASE_PROMPTS.md) | Release readiness, migration pre-flight, post-release | Active |

---

## Reading Order

There is no fixed reading order — use the prompt for the task at hand. Quick reference:
- Security/audit concern → [AUDIT_PROMPTS.md](AUDIT_PROMPTS.md)
- Bug to fix → [DEBUGGING_PROMPTS.md](DEBUGGING_PROMPTS.md) then [IMPLEMENTATION_PROMPTS.md](IMPLEMENTATION_PROMPTS.md)
- PR to review → [REVIEW_PROMPTS.md](REVIEW_PROMPTS.md)
- Preparing a release → [RELEASE_PROMPTS.md](RELEASE_PROMPTS.md)

---

## How to Use

Prompts are starting templates. Adapt them for the specific task by filling in:
- `[APP_NAME]` — the specific app
- `[TASK_DESCRIPTION]` — what needs to be done
- `[FILE:LINE]` — specific location

Always include the project path and reference to `AI_AGENT_START_HERE.md` when sending a prompt to a fresh AI agent.

See [../02_AI_Operating_System/AI_PROMPT_USAGE_GUIDE.md](../02_AI_Operating_System/AI_PROMPT_USAGE_GUIDE.md).

---

## Related Documents

- [../02_AI_Operating_System/AI_AGENT_START_HERE.md](../02_AI_Operating_System/AI_AGENT_START_HERE.md) — AI agent entry point
- [../02_AI_Operating_System/AI_PROMPT_USAGE_GUIDE.md](../02_AI_Operating_System/AI_PROMPT_USAGE_GUIDE.md) — how to use prompts effectively

---

## Maintenance Notes

Add new prompts only when a task pattern recurs frequently. Do not add single-use prompts. Merge overlapping prompts rather than creating variations.
