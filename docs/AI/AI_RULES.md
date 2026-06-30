# AI Rules

## Mandatory Rules

- Always understand before changing.
- Always inspect the current implementation.
- Always preserve existing correct architecture.
- Always respect multi-tenant isolation.
- Always explain WHY a change is needed.
- Always run tests before claiming completion.

---

## Forbidden Actions

Never:

- rewrite an entire module without approval
- remove tests
- disable tests
- create unnecessary migrations
- change unrelated files
- combine multiple issues
- modify financial logic casually
- expose public users to admin layout
- ignore security or tenant isolation
- claim completion without verification

---

## Output Rules

Every audit must include:

- files inspected
- root cause
- proposed solution
- risk
- tests required

Every implementation report must include:

- files changed
- tests run
- result
- commit hash
- risks
- manual QA steps
