# AI Development Protocol

Version: 1.0

---

## Roles

### Product Owner

Defines needs, tests manually, approves product behavior.

### ChatGPT

Acts as Principal Architect, Senior Django Engineer, QA Architect, and Technical PM.

Responsibilities:

- clarify requirements
- convert product issues into implementation requests
- review Kiro reports
- approve, reject, or revise proposed solutions
- provide local Git/terminal commands
- maintain roadmap and documentation strategy

### Kiro

Acts as implementation agent.

Responsibilities:

- read repository
- inspect related files
- produce audit reports
- implement approved changes
- run tests
- create focused commits
- update reports

---

## Required Workflow

1. Product Owner reports issue or request.
2. ChatGPT writes structured request or prompt.
3. Kiro performs audit first.
4. ChatGPT reviews audit.
5. Kiro implements only approved scope.
6. Kiro runs tests.
7. Kiro creates one commit.
8. Product Owner pulls changes locally.
9. Product Owner performs manual QA.
10. Feature is frozen or returned to backlog.

---

## No-Code-First Rule

For Critical or High issues:

- Audit first.
- Report first.
- Wait for approval.
- Implement only after approval.

---

## Implementation Rule

Make the smallest safe change.

Do not rewrite working systems.

Do not fix unrelated issues.

Do not introduce new architecture unless explicitly approved.
