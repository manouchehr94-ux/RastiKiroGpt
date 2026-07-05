# VERSION

---

## v1.0 — Draft — Pending Clarification

**Release Date:** 2026-07-05
**Status:** Draft — Pending Clarification
**Freeze Status:** NOT FROZEN

---

## Why Not Frozen

This document package **cannot** be marked as Frozen until all ten Open Issues (OI-01 through OI-10) have been resolved by the Product Owner.

See `22_FREEZE_CHECKLIST.md` for complete conditions.

---

## Document Package Contents

| # | File | Status |
|---|---|---|
| 00 | README.md | ✅ Complete |
| 01 | EXECUTIVE_SUMMARY.md | ✅ Complete |
| 02 | ARCHITECTURAL_PRINCIPLES.md | ✅ Complete |
| 03 | BUSINESS_RULES.md | ✅ Complete |
| 04 | DOMAIN_MODEL.md | ✅ Complete |
| 05 | MONEY_OWNERSHIP_LIFECYCLE.md | ✅ Complete |
| 06 | INVOICE_LINE_ENGINE.md | ✅ Complete |
| 07 | COMMISSION_ALLOCATION_ENGINE.md | ✅ Complete (OI-03 marked) |
| 08 | PAYMENT_COLLECTION_ENGINE.md | ✅ Complete (OI-01 marked) |
| 09 | ESCROW_ENGINE.md | ✅ Complete |
| 10 | FINANCIAL_POLICY_ENGINE.md | ✅ Complete (OI-08 marked) |
| 11 | ORGANIZATION_PROVIDER_IBAN_ENGINE.md | ✅ Complete |
| 12 | LEDGER_ENGINE.md | ✅ Complete |
| 13 | SETTLEMENT_NETTING_ENGINE.md | ✅ Complete |
| 14 | REFUND_ADJUSTMENT_ENGINE.md | ✅ Complete (OI-05, OI-06, OI-07 marked) |
| 15 | REFERRAL_VISITOR_ENGINE.md | ✅ Complete (extension point) |
| 16 | FINANCIAL_EVENT_CATALOG.md | ✅ Complete |
| 17 | PERMISSION_MATRIX.md | ✅ Complete |
| 18 | REPORTING_REQUIREMENTS.md | ✅ Complete (OI-09, OI-10 marked) |
| 19 | DATA_MODEL.md | ✅ Complete |
| 20 | TEST_SCENARIOS.md | ✅ Complete |
| 21 | OPEN_ISSUES_REGISTER.md | ✅ Complete |
| 22 | FREEZE_CHECKLIST.md | ✅ Complete |
| — | VERSION.md | ✅ This file |

---

## Version History

| Version | Date | Description |
|---|---|---|
| v1.0-draft | 2026-07-05 | Initial target architecture documentation based on code audit |

---

## Grounding

Every design decision in this document package is grounded in:
1. **Existing Code Audit:** `docs/13_Financial_Core/01-11_*.md`
2. **Locked Business Rules:** R01–R56 (Section 5 of the prompt)
3. **Open Issues:** OI-01–OI-10 (Section 6 of the prompt)
4. **Architectural Principles:** P01–P10 (Section 4 of the prompt)
5. **Existing ADRs:** ADR-002 through ADR-008

No design decision was made independently of the existing implementation audit.
