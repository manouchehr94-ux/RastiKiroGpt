---
Title: AI Operating System — README
Layer: AI Operating System
Audience: AI + Human
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# 02 — AI Operating System

This folder contains operating instructions for AI agents working on the Rasti project.

**Start here:** [AI_AGENT_START_HERE.md](AI_AGENT_START_HERE.md)

---

## Files in This Folder

| File | Purpose |
|---|---|
| [AI_AGENT_START_HERE.md](AI_AGENT_START_HERE.md) | First document any AI agent must read |
| [AI_CONTEXT_MAP.md](AI_CONTEXT_MAP.md) | Maps task types to documents and code |
| [AI_READING_ORDER.md](AI_READING_ORDER.md) | Reading order by task type |
| [AI_SAFE_CHANGE_PROTOCOL.md](AI_SAFE_CHANGE_PROTOCOL.md) | Step-by-step safe change procedure |
| [AI_CODE_CHANGE_RULES.md](AI_CODE_CHANGE_RULES.md) | Non-negotiable rules for code changes |
| [AI_VERIFICATION_PROTOCOL.md](AI_VERIFICATION_PROTOCOL.md) | How to verify changes are correct |
| [AI_HANDOFF_PROTOCOL.md](AI_HANDOFF_PROTOCOL.md) | How to hand off context between sessions |
| [AI_LIMITATIONS.md](AI_LIMITATIONS.md) | When to inspect code instead of trusting docs |
| [AI_PROMPT_USAGE_GUIDE.md](AI_PROMPT_USAGE_GUIDE.md) | How to use the prompt library |

---

## Reading Order

All AI agents must read in this order:
1. [AI_AGENT_START_HERE.md](AI_AGENT_START_HERE.md) — mandatory first read
2. [AI_CODE_CHANGE_RULES.md](AI_CODE_CHANGE_RULES.md) — 10 non-negotiable rules
3. [AI_SAFE_CHANGE_PROTOCOL.md](AI_SAFE_CHANGE_PROTOCOL.md) — 8-step change procedure

Then read what is relevant to the task:
- [AI_CONTEXT_MAP.md](AI_CONTEXT_MAP.md) — which docs to read for which task type
- [AI_READING_ORDER.md](AI_READING_ORDER.md) — ordered reading lists by task type
- [AI_VERIFICATION_PROTOCOL.md](AI_VERIFICATION_PROTOCOL.md) — post-change verification
- [AI_LIMITATIONS.md](AI_LIMITATIONS.md) — when to inspect code instead of trusting docs
- [AI_HANDOFF_PROTOCOL.md](AI_HANDOFF_PROTOCOL.md) — session start/end procedures
- [AI_PROMPT_USAGE_GUIDE.md](AI_PROMPT_USAGE_GUIDE.md) — how to use the prompt library

---

## Related Documents

- [../10_Prompts/](../10_Prompts/) — prompt library used by AI agents
- [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md) — P0 bugs AI agents must know
- [../11_Project_Knowledge/KNOWN_CONSTRAINTS.md](../11_Project_Knowledge/KNOWN_CONSTRAINTS.md) — constraints AI agents must respect
- [../00_Project/SKILL.md](../00_Project/SKILL.md) — repo-root AI entry point

---

## Maintenance Notes

Update these documents when the development protocol changes (new rules, new verification steps, new handoff requirements). Do not update AI rules in response to a single task — only when a pattern emerges that needs to be codified.

---

## Design Principle

Docs tell an AI agent what the project intends.
Code tells an AI agent what the project actually does.
When they conflict, **trust the code, mark the conflict in the doc**.
