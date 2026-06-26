# Master Prompt — Rasti Service

Use this at the start of every Claude Code session.

```text
You are working on Rasti Service, a Django multi-tenant SaaS for Iranian service-dispatch companies.

First read:
- SKILL.md
- docs/README.md
- docs/02_Development_System/CLAUDE_BEHAVIOR.md
- docs/02_Development_System/COMMON_MISTAKES.md
- docs/02_Development_System/TASK_TEMPLATE.md
- Relevant docs for the task

Rules:
- Do not guess.
- Do not rewrite unrelated code.
- Do not remove tests.
- Do not use float for money.
- Always preserve multi-tenant isolation.
- Read existing models/services/views/tests before editing.
- For financial/payment/invoice changes, write or update tests first.
- Make the smallest safe change.
- Report using REVIEW_TEMPLATE.md.
```
---

# Autonomous Execution

Before starting any implementation, read:

docs/02_Development_System/AUTONOMOUS_EXECUTION_POLICY.md

Once the user approves a task, you are authorized to perform all implementation steps within the approved scope without asking for intermediate confirmations.

Interrupt only if a Stop Condition defined in AUTONOMOUS_EXECUTION_POLICY.md is reached.