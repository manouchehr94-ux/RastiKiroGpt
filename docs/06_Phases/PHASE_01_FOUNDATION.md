# Phase 01 — Foundation and Financial Safety

**Status:** Active phase  
**Goal:** Stabilize dangerous financial and architecture foundations without broad feature expansion.

---

## Phase 01 Principles

- No broad rewrites.
- No real PSP integration.
- No gateway model unification yet.
- No accounting expansion.
- Fix only safety issues that can corrupt financial records.
- Keep each task small and test-first.

---

## Phase 01 Tasks

### P1-T001 — Platform Fee Safety Fix

Goal: Stop creating platform fee entries for non-platform payments.

Scope includes:

- Add minimal `PaymentGateway.owner_type` field if missing.
- Add defensive guard in `PlatformFeeService`.
- Add defensive guard at the invoice mark-paid call site.
- Add tests for cash, manual, company-owned gateway, platform-owned gateway, and idempotency.

Scope excludes:

- `CompanyPaymentSettings` implementation.
- Gateway model unification.
- Real PSP implementation.
- Payment mode UI.
- Permission UI changes.

Reason: The system needs a way to distinguish company-owned vs platform-owned gateway before it can safely decide whether platform commission is allowed.

### P1-T002 — Payment Reconciliation Status Safety

Goal: Ambiguous/expired payments must go to `NEEDS_RECONCILIATION`, not blindly `FAILED`.

Scope includes:

- Add status if missing.
- Update expiration/verify ambiguous paths.
- Update reconciliation scans.
- Add tests.

### P1-T003 — Documentation Freeze Verification

Goal: Keep RDOS v1.0 stable and detect contradictions before implementation.

---

## Phase 01 Exit Criteria

Phase 01 is complete when:

- Platform fee cannot be created for cash/manual/company-gateway payments.
- Platform fee positive path still works for platform-owned verified paid payments.
- Ambiguous payments use `NEEDS_RECONCILIATION`.
- Existing payment, invoice, and cash tests pass.
- No more than the approved small model additions are made.
- RDOS v1.0 remains consistent after implementation reports.
