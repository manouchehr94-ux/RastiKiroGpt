---
Title: Developer Onboarding Guide
Layer: Human Engineering
Audience: Human
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code + Mixed
Depends On: []
Related Documents: LOCAL_DEVELOPMENT.md, REPOSITORY_STRUCTURE.md
Reusable Across Projects: No
---

# Developer Onboarding Guide

Welcome to the Rasti SaaS project. This guide helps new developers get up to speed.

---

## What is Rasti?

Rasti is a **multi-tenant SaaS platform** for field-service dispatch companies in Iran.

A "company" (tenant) signs up to use Rasti. Their customers request services, technicians fulfill them, and money flows through invoices and payments.

- **You build the platform** that companies use
- **Companies build their own service business** on top of the platform
- **Rasti is not the service seller** — the tenant company is

Read [../00_Project/GLOSSARY.md](../00_Project/GLOSSARY.md) for all key terms.

---

## Step 1 — Set Up Local Development

See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for environment setup.

Quick summary:
```bash
git clone <repo>
cd "Rasti chekFinal 10 tir"
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env      # Configure your local environment
python manage.py migrate
python manage.py runserver
```

---

## Step 2 — Understand the Architecture

Read in this order:
1. [../03_Architecture/SYSTEM_ARCHITECTURE.md](../03_Architecture/SYSTEM_ARCHITECTURE.md) — High-level overview
2. [../03_Architecture/MULTI_TENANCY.md](../03_Architecture/MULTI_TENANCY.md) — Most important design principle
3. [../03_Architecture/PERMISSIONS.md](../03_Architecture/PERMISSIONS.md) — How access control works
4. [../03_Architecture/SERVICE_LAYER.md](../03_Architecture/SERVICE_LAYER.md) — Where to put business logic

---

## Step 3 — Understand the Business Domain

Read:
- [../00_Project/GLOSSARY.md](../00_Project/GLOSSARY.md) — What terms mean
- [../04_Business_Rules/ORDER_RULES.md](../04_Business_Rules/ORDER_RULES.md) — Core order lifecycle
- [../04_Business_Rules/PAYMENT_RULES.md](../04_Business_Rules/PAYMENT_RULES.md) — Financial rules

---

## Step 4 — Know the Critical Bugs

Read [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md).

There are **5 P0 bugs** that must not be made worse:
- P0-1: Missing permission decorator on operator management view
- P0-2: JWT logout broken
- P0-3: Hardcoded default password in production code
- P0-4: `ALLOWED_HOSTS = ["*"]` in base settings
- P0-5: API customer creation crashes at runtime

Do not accidentally change these files without understanding the bug first.

---

## Step 5 — Run Tests

```bash
python manage.py test --verbosity=1
```

Should report: 1242 tests, 0 failures, 0 errors (approximately).

---

## Step 6 — Explore the URL Structure

The project has 238 URL patterns. The site map docs will help:
- [../08_Site_Map/README.md](../08_Site_Map/README.md) — Overview
- [../08_Site_Map/01_URL_INVENTORY.md](../08_Site_Map/01_URL_INVENTORY.md) — Every URL

---

## Key Things That Surprise New Developers

1. **All business logic is in `services.py`** — Never look for it in views
2. **Every query must include `company=`** — Never query by ID alone
3. **The `tenants` app is huge** — `views_admin.py` is 2000+ lines with 96 URL handlers
4. **Customer panel was removed in Phase 24** — `/<code>/customer/` redirects to public page
5. **`apps/billing/` is a stub** — SaaS subscription billing is not implemented
6. **SMS to technicians is disabled** — `if False` at `technician_notifications.py:147`
7. **Languages are mixed** — UI is Persian, code identifiers are English
8. **Persian UI labels must not change** — They are user contracts
