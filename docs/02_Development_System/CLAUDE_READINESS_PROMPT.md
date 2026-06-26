# Claude Readiness Prompt

Copy this into Claude before any implementation work:

```text
You are working inside:
D:\SaaSprojectService\Rasti chekFinal 5 tir

Do not code yet.

Read:
- SKILL.md
- docs/README.md
- docs/02_Development_System/MASTER_PROMPT.md
- docs/02_Development_System/CLAUDE_BEHAVIOR.md
- docs/02_Development_System/COMMON_MISTAKES.md
- docs/03_Business/PAYMENT_RULES.md
- docs/03_Business/INVOICE_RULES.md
- docs/03_Business/ORDER_RULES.md

Then produce a readiness report:
1. Documents found
2. Documents missing
3. Contradictions found
4. Rules you will follow
5. Whether you are ready for Task 001
6. No code changed
```
## Autonomous Execution

Read:

docs/02_Development_System/AUTONOMOUS_EXECUTION_POLICY.md

If the current task has been approved, execute all implementation steps autonomously.

Do not ask for confirmation to:

- create files
- modify files
- run tests
- inspect code
- search files
- continue implementation

Only interrupt if a Stop Condition occurs.