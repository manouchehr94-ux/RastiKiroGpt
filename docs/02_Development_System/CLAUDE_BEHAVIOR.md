# Claude Behavior Rules

## Required behavior

1. Read before editing.
2. Search before creating new names/classes/services.
3. Prefer existing patterns.
4. Make small changes.
5. Explain risk.
6. Stop on contradiction.
7. Ask only when code/docs cannot answer.
8. Report exactly what changed.

## Hard limits

- Do not modify more than 5 files without explicit permission unless the task demands it.
- Do not create migrations unless the task explicitly allows it.
- Do not run destructive commands.
- Do not perform broad refactors.
- Do not convert architecture without a separate plan.

## When to stop

Stop and report if:
- docs conflict with code
- migration would be destructive
- test setup is unclear
- payment behavior is ambiguous
- tenant isolation is uncertain
