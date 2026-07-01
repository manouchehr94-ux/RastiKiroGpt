---
Title: Local Development Guide
Layer: Human Engineering
Audience: Human Developer
Status: Active
Last Verified: 2026-07-01
Verified Against: AI/WORKFLOWS/LOCAL_PULL_WORKFLOW.md, AI/POLICIES/GIT_WORKFLOW.md, codebase
Source of Truth: Mixed
Depends On: []
Related Documents: CONFIGURATION.md, ../06_Quality_Assurance/TEST_STRATEGY.md
Reusable Across Projects: No
---

# Local Development Guide

---

## Prerequisites

- Python 3.11.9
- PostgreSQL (running locally or via Docker)
- Git
- Tailwind CSS CLI (if modifying frontend styles)

---

## Initial Setup

```powershell
cd "D:\SaaSprojectService\Rasti chekFinal 10 tir"

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Check Django can see the project
python manage.py check
```

---

## Environment Configuration

The project uses split settings:
- `config/settings/base.py` — shared settings
- `config/settings/local.py` — local overrides (not committed)
- `config/settings/production.py` — production settings

Create `config/settings/local.py` with:
```python
from .base import *

DEBUG = True
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'rasti_db',
        'USER': 'rasti_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

Set `DJANGO_SETTINGS_MODULE`:
```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"
```

---

## Database Setup

```powershell
# Apply all migrations
python manage.py migrate

# Create superuser (platform owner)
python manage.py createsuperuser

# Verify migrations are all applied
python manage.py showmigrations
```

---

## Running the Dev Server

```powershell
python manage.py runserver
```

Access the platform at `http://localhost:8000/`.

To test multi-tenancy, create a company first via the platform admin panel, then access `http://localhost:8000/{company_code}/admin/`.

---

## After Pulling Changes

```powershell
git status  # Must be clean before pulling
git pull
python manage.py check
python manage.py migrate  # If new migrations
python manage.py test <related_tests>  # Run tests for changed apps
python manage.py runserver
```

If `git status` is not clean, do not pull. Stash or commit your local changes first.

---

## Running Tests

```powershell
# Run all tests (1242 tests)
python manage.py test --verbosity=1

# Run tests for a specific app
python manage.py test apps.orders --verbosity=2

# Run a single test
python manage.py test apps.orders.tests.TestOrderFlow.test_order_creation --verbosity=2
```

---

## Git Workflow

```powershell
# Before starting work
git status  # Ensure clean working tree
git pull    # Get latest

# After completing work
python manage.py test  # All tests must pass
git status             # Review what changed
git add <specific files>  # Add only the files changed for this task
git commit -m "fix: description of what was fixed"
```

**Rules:**
- Commit only work that is focused on the task
- Never commit with failing tests
- Never commit `DEBUG = True` or local credentials
- Review `git diff` before committing

---

## Common Dev Commands

```powershell
# Create migrations after model change
python manage.py makemigrations <app_name>

# Shell for debugging
python manage.py shell

# Check for Django configuration errors
python manage.py check --deploy

# Collect static files (needed after CSS/JS changes)
python manage.py collectstatic --noinput
```
