# Autonomous Execution Policy (RDOS v1.0)

This policy defines which actions Claude Code may perform without asking for confirmation.

---

# Default Rule

Claude should execute all actions required to complete an approved task.

Do not ask for confirmation between individual steps unless a Stop Condition is reached.

An approved task is considered authorization to perform all required implementation work within the approved scope.

---

# Automatically Allowed

Claude may without asking:

- create new source files
- modify existing files
- delete temporary files
- create test files
- modify test files
- run unit tests
- run integration tests
- run pytest
- run Django tests
- run formatting tools
- run linting
- run static analysis
- run type checking
- inspect database schema
- inspect migrations
- read any project file
- search entire repository
- refactor within approved scope
- add comments
- update documentation

---

# Automatically Allowed Migrations

Claude may create migrations only if:

- migration was explicitly approved in the task
OR
- MASTER_PROMPT explicitly allows migrations.

Otherwise migration creation must stop.

---

# Automatically Allowed Commands

Claude may execute:

python manage.py test

pytest

python manage.py makemigrations

python manage.py migrate

python manage.py check

python manage.py showmigrations

coverage

ruff

black

isort

mypy

whenever required.

---

# Never Ask About

Do NOT ask:

"Should I create this file?"

"Should I modify this file?"

"Should I run tests?"

"Should I run migrations?"

"Should I inspect more files?"

"Should I continue?"

Once a task is approved these are already approved.

---

# Stop Conditions

Only stop if one of these occurs:

- more than approved file limit
- destructive migration
- data loss risk
- architecture contradiction
- documentation contradiction
- security concern
- multi-tenant isolation risk
- permission ambiguity
- business rule ambiguity
- external dependency required
- missing credentials
- irreversible operation

Only then ask the user.

---

# Principle

Minimize interruptions.

Maximize autonomous execution.

Only interrupt when human decision is actually required.