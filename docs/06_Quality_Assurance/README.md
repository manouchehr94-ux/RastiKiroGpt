---
Title: Quality Assurance — README
Layer: Quality Assurance
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Mixed
Reusable Across Projects: No
---

# 06 — Quality Assurance

Testing, QA, and production readiness documentation.

---

## Files in This Folder

| File | Purpose | Status |
|---|---|---|
| [PRODUCTION_READINESS_CHECKLIST.md](PRODUCTION_READINESS_CHECKLIST.md) | P0 bugs, infrastructure, launch checklist | Active |
| [TEST_STRATEGY.md](TEST_STRATEGY.md) | Test approach, types, examples | Active |
| [AI_VERIFICATION_CHECKLIST.md](AI_VERIFICATION_CHECKLIST.md) | Checklist for AI agents after making changes | Active |
| [MANUAL_QA_CHECKLIST.md](MANUAL_QA_CHECKLIST.md) | Manual testing steps for key flows | Active |
| [REGRESSION_TEST_PLAN.md](REGRESSION_TEST_PLAN.md) | Regression test plan and naming conventions | Active |

---

## Reading Order

1. [PRODUCTION_READINESS_CHECKLIST.md](PRODUCTION_READINESS_CHECKLIST.md) — read first; shows current P0 bugs
2. [TEST_STRATEGY.md](TEST_STRATEGY.md) — test philosophy and how to run tests
3. [MANUAL_QA_CHECKLIST.md](MANUAL_QA_CHECKLIST.md) — before any release
4. [REGRESSION_TEST_PLAN.md](REGRESSION_TEST_PLAN.md) — when fixing bugs
5. [AI_VERIFICATION_CHECKLIST.md](AI_VERIFICATION_CHECKLIST.md) — for AI agents after any change

---

## Current Test Status

- **1242 tests** as of 2026-06-30
- Run: `python manage.py test --verbosity=1`
- Strong: order lifecycle, financial logic
- Weak: multi-tenant isolation, API endpoints, notification triggering

---

## Related Documents

- [../11_Project_Knowledge/KNOWN_RISKS.md](../11_Project_Knowledge/KNOWN_RISKS.md) — P0 bug details
- [../01_Human_Engineering/TESTING_GUIDE.md](../01_Human_Engineering/TESTING_GUIDE.md) — developer testing guide
- [../05_Workflows/RELEASE_FLOW.md](../05_Workflows/RELEASE_FLOW.md) — release process

---

## Maintenance Notes

Update `PRODUCTION_READINESS_CHECKLIST.md` whenever a P0 bug is fixed or discovered. Update `REGRESSION_TEST_PLAN.md` when a new bug pattern is found. Do not remove checklist items — mark them DONE instead.
