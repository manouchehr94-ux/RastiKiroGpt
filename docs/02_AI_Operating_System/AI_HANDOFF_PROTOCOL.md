---
Title: AI Handoff Protocol
Layer: AI Operating System
Audience: AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: Yes
---

# AI Handoff Protocol

How to start a new AI conversation without losing context.

---

## When Starting a New Session

1. Read [AI_AGENT_START_HERE.md](AI_AGENT_START_HERE.md) first — always
2. Read [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md) — check unresolved P0 issues
3. Check git log for recent changes: `git log --oneline -20`
4. If continuing a task, find the handoff note (check last commit message or ask user)

---

## When Ending a Session

Write a handoff note. Include:

```
## Session Handoff — [Date]

### Task in progress
[What was being worked on]

### Files changed
[List files with line numbers of key changes]

### What was NOT done
[What remains to be completed]

### Tests run
[Commands and results]

### Risks noticed
[Any issues seen during the session]

### Recommended next step
[What the next agent should do first]
```

If the session ends without finishing a task, save the handoff note to:
`docs/11_Project_Knowledge/HANDOFF_[DATE].md`

---

## Context Recovery Checklist

If you are picking up a task mid-stream:

- [ ] Read the last handoff note (if any)
- [ ] Read `git log --oneline -10` for recent commits
- [ ] Read `git diff HEAD~1` to see last change
- [ ] Re-read the relevant business rule docs
- [ ] Re-read the specific files being changed
- [ ] Confirm P0 bugs have not been accidentally changed

---

## What Not to Trust in a New Session

- Your memory of previous session conversations
- Docs marked "Needs Review" or "Draft"
- Site Map files older than 2 weeks (verify against `config/urls.py`)
- Any test result from a previous session (re-run before trusting)

---

## Sending Context to Another AI Model

When handing off to a different AI (ChatGPT, Cursor, Gemini, etc.):

Include in your initial prompt:
1. The text of [AI_AGENT_START_HERE.md](AI_AGENT_START_HERE.md)
2. The specific task description
3. The handoff note from the last session
4. The content of any files that will be changed

Do not assume another AI has project context.
