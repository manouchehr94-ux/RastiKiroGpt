# Financial Core — Final Production Readiness Audit

**Date:** 2026-06-28  
**Author:** Architecture Review (CTO Perspective)  
**Scope:** All financial subsystems implemented through TASK-012A  
**Status:** Final — read-only record

---

## 1. Executive Summary

**Maturity Rating: Production Ready with Conditions**

The Financial Core is not a prototype. The immutable ledger design, snapshot-driven
amounts, idempotency keys, and backfill recovery system reflect genuine engineering
discipline — not scaffolding that will need to be replaced later. The architecture
decisions recorded in ADR-004 through ADR-008 are sound and internally consistent.

However, three conditions must be met before real customer money flows through this
system:

1. **The `FinancialBackfillService` cron job must be verified as running** and monitored
   in the production environment. The entire recovery model depends on it.
2. **An alert must exist** when a `FinancialBackfillTask` exceeds 3 attempts without
   resolution. Without it, silent ledger failures are invisible to operators.
3. **An end-to-end test of the complete payment flow** (not unit tests — a real Shaparak
   sandbox payment) must be run and verified in the target production environment
   before the first paying customer.

If these three conditions are satisfied, the Financial Core is suitable for production
at V1 scale (single-digit tenants, low payment volume). Nothing in the remaining
technical debt prevents correct operation at this scale.

---

## 2. Components Implemented

| Subsystem | Responsibility |
|---|---|
| `TechnicianLedgerEntry` | Immutable per-event record of all technician earnings and settlements. The system of record. |
| `CompanyPlatformFeeEntry` | Immutable per-invoice record of platform fees accrued by each tenant. |
| `PaymentSplitSnapshot` | Immutable audit record of the split routing decision made at payment verification time. Frozen at the exact moment of the PSP call. |
| `FinancialBackfillTask` | Retry queue for failed financial writes. Tracks status, attempts, error messages, and resolution. |
| `TechnicianLedgerService` | All ledger writes. Enforces idempotency via unique `idempotency_key` + savepoint IntegrityError recovery. |
| `TechnicianWagePostingService` | Posts a `technician_service_wage` CREDIT when an order is marked DONE. Reads rate at completion time; rate changes do not affect past entries. |
| `TechnicianDirectSettlementService` | Posts a `direct_gateway_settlement` DEBIT when Shaparak wires money directly to the technician. Amount sourced exclusively from `PaymentSplitSnapshot`. |
| `InvoiceMarkPaidService` | Orchestrates events 4–6 of the financial timeline (settlement freeze, invoice CREDIT, platform fee DEBIT). |
| `PaymentVerifyService` | Orchestrates events 7–8 (split snapshot creation, direct settlement DEBIT). Non-blocking for both. |
| `PlatformFeeService` | Platform fee writes. Idempotent via `idempotency_key` unique constraint. |
| `PaymentSplitDecisionService` | Computes split decision and creates the immutable `PaymentSplitSnapshot`. |
| `InvoiceSettlementService` | Freezes `settled_*` fields on the invoice at payment time. These are the authoritative source for all invoice-linked CREDIT entries. |
| `FinancialBackfillService` | Processes PENDING backfill tasks. Each task runs in an isolated transaction. Cascade recovery handles dependent failures. |
| `TechnicianStatementService` | Pure read-only projection of ledger rows into a human-readable statement. No writes. |
| Statement UI (HTML/Print/PDF/CSV) | Read-only views. PDF via WeasyPrint. CSV with UTF-8 BOM for Persian Excel compatibility. |
| Gateway Reconciliation view | Read-only admin view of `PaymentSplitSnapshot` rows for manual PSP reconciliation. |
| `TechnicianServiceRate` | Fixed rial wage per technician per order item definition. Wage rate model for Phase 1. |

---

## 3. Architecture Strengths

### 3.1 Immutable Ledger Design

The `TechnicianLedgerEntry.save()` override raises `PermissionError` if `amount_rial` or
`balance_after` is mutated after creation. `delete()` is permanently disabled. This is
enforced at the Django model layer, not merely by convention. A future developer cannot
accidentally corrupt the ledger by writing `entry.amount_rial = x; entry.save()` — they
will receive an explicit error.

This design makes the ledger tamper-proof against both bugs and intentional manipulation.
It is the correct foundation for an accounting system at any scale.

### 3.2 Business-Event-Driven Amounts

Every ledger entry reads its amount from the **authoritative snapshot of its triggering
event** — never from another ledger entry. The explicit anti-pattern ban in ADR-006 §7
prevents a class of subtle financial bugs that commonly appear in ledger systems: "read
the CREDIT amount to determine the DEBIT amount." Here, the CREDIT and DEBIT amounts are
independently derived and happen to agree in the common case — but they would not agree
if derived from different versions of the same fact.

### 3.3 Snapshot Architecture

Three immutable snapshots freeze financial facts at the exact moment they become known:
- `invoice.settled_technician_wage` — frozen by `InvoiceSettlementService.settle()`
- `PaymentSplitSnapshot` — frozen at payment verification
- `TechnicianLedgerEntry.metadata` — frozen at posting time

This means the ledger remains correct even if underlying master data changes after the
fact (rate changes, policy changes, technician deactivation).

### 3.4 Idempotency at Every Layer

Idempotency is enforced at three independent levels:
1. **Code level:** `exists()` pre-check before every `create()`
2. **Database level:** `UNIQUE` constraint on `idempotency_key`
3. **Savepoint level:** `IntegrityError` caught and recovered without aborting the outer
   transaction

All deterministic keys are derived from business identifiers (`invoice.id`, `payment.id`,
`order.id`), not from UUIDs. This means a retry after a crash produces the same key and
hits the idempotency check cleanly.

### 3.5 Non-Blocking Financial Side Effects

`PaymentVerifyService.verify()` marks the payment PAID regardless of what happens in the
ledger or fee writes. The try/except blocks are non-blocking: a ledger failure produces a
backfill task but never rolls back the payment status. This is the correct behaviour for
a PSP callback — the gateway has already processed the payment; the customer has paid.

### 3.6 Cascade Recovery in Backfill

`_retry_direct_gateway_settlement()` creates the split snapshot if it is missing before
attempting the settlement. This handles the cascade failure case (both snapshot creation
and settlement failed at verify time) with a single DIRECT_GATEWAY_SETTLEMENT task rather
than requiring two separate retry tasks in the correct sequence.

### 3.7 Tenant Isolation

Every financial model inherits from `CompanyOwnedModel` and carries a `company` FK.
All queries are scoped by `company`. There is no cross-tenant data access pattern in any
financial service. Tenant isolation is structural, not convention-based.

### 3.8 Ledger / Statement Separation

The `TechnicianStatementService` is explicitly read-only. The statement is a projection
over ledger rows — it does not write, and it does not determine amounts. This means the
accounting model can evolve (new sources, adjustment entries, restatements) independently
of what the technician sees on their statement.

### 3.9 Test Architecture

Tests are organized per task and per concern (integrity, idempotency, backfill, direct
settlement, statement). The test helpers (`_company()`, `_technician()`, `_snapshot()`)
are consistent across test files. New financial tests can be written by following
established patterns without understanding the full codebase.

### 3.10 ADR Documentation Quality

ADR-004 through ADR-008 form a coherent body of knowledge. ADR-006 contains executable
rules (anti-pattern code samples), not just policy statements. FINANCIAL_ARCHITECTURE_INDEX.md
provides a 22-question quick-reference table. A new developer joining the team can
understand the financial architecture from documentation alone, without reading service
code first.

---

## 4. Remaining Risks

### RISK-F1 — balance_after Race on Empty Technician Ledger

**Classification:** High  
**Description:** When two concurrent callers both write the first ledger entry for a
brand-new technician, neither can lock a "last row" (there are no rows yet). Both compute
`balance_after` independently from `get_balance()` → 0. Both create entries. The second
entry has a wrong `balance_after` snapshot. `get_balance()` (SUM) remains correct; only
the per-row running-balance display is affected.  
**Impact:** The technician statement shows an incorrect running balance for the first
entry. Reconciliation by summing all entries gives the correct total, but the
statement is confusing.  
**Likelihood:** Low at V1 scale. Requires truly simultaneous concurrent first-writes for
a brand-new technician (e.g., an invoice payment and an order completion landing at
the same millisecond). Highly unlikely in a low-volume environment.  
**Mitigation:** Implement Financial Account Lock Layer (per-technician lock row) as
described in ADR-008 Technical Debt §1. Not required before V1 launch.

---

### RISK-F2 — No PostgreSQL Concurrency Testing

**Classification:** High  
**Description:** All tests run against SQLite in-memory. SQLite serialises all writes at
the database level, masking any concurrency issue that would manifest in PostgreSQL with
row-level locking. The `select_for_update()[:1]` strategy has not been exercised under
real concurrent writes.  
**Impact:** A concurrency bug that is invisible in tests but visible in production
(PostgreSQL with real concurrent HTTP requests) could produce incorrect `balance_after`
values or missed idempotency recoveries.  
**Likelihood:** Medium. The logic for the non-empty table case is sound (both writers
lock the same last row; one waits). The empty-table case is RISK-F1.  
**Mitigation:** Before scaling beyond a handful of tenants, run a PostgreSQL-based
concurrency integration test suite with threading. This is a prerequisite for RISK-F1
resolution.

---

### RISK-F3 — No Automatic Alerting on Backfill Task Accumulation

**Classification:** High  
**Description:** If `FinancialBackfillService.process_pending()` fails repeatedly (e.g.,
cron not scheduled, or a systematic ledger write failure), PENDING tasks accumulate
silently. There is no alert, email, or dashboard notification.  
**Impact:** Ledger entries that failed during payment verification may remain missing for
days without anyone noticing. A technician's statement would show an incorrect balance
and no one in the ops team would know why.  
**Likelihood:** Medium. Cron misconfiguration is a common production deployment failure.  
**Mitigation (P0 — required before first paying customer):** Add a monitoring check that
alerts when `FinancialBackfillTask.objects.filter(status="pending", attempts__gte=3)`
is non-empty. A daily digest to the ops channel is the minimum viable alert.

---

### RISK-F4 — FinancialBackfillService Depends on Unverified Cron

**Classification:** High  
**Description:** The entire recovery model depends on `process_pending()` being invoked
on a schedule. There is no confirmation in the codebase that this cron job exists and is
running in the production environment. The management command exists; the scheduling does
not.  
**Impact:** Without the cron, all backfill tasks remain PENDING indefinitely. A single
transient DB failure at payment time leaves the ledger permanently wrong.  
**Likelihood:** Certain to fail without explicit deployment verification.  
**Mitigation (P0):** Document the required cron entry in the deployment checklist.
Verify it before onboarding the first paying customer. Prefer a managed task scheduler
(Celery Beat, systemd timer, or cloud scheduler) over raw crontab.

---

### RISK-F5 — WeasyPrint PDF Generation Performance and Memory

**Classification:** Medium  
**Description:** PDF generation via `WeasyPrint v62.3` runs synchronously in the HTTP
request-response cycle. For a technician with hundreds of ledger entries, the HTML
template may be large; WeasyPrint may consume significant memory and take several
seconds to render.  
**Impact:** Slow or failed PDF responses for active technicians. If the PDF request
times out, the technician sees a 500 error with no fallback.  
**Likelihood:** Low at V1 scale (few entries per technician). Increases as platform
matures.  
**Mitigation:** Add a statement date-range filter to the PDF view to limit the number of
rows. For scale, move PDF generation to a background task with a download link.

---

### RISK-F6 — record_manual_settlement UUID Fallback is Non-Idempotent

**Classification:** Medium  
**Description:** `TechnicianLedgerService.record_manual_settlement()` generates a random
UUID as the idempotency key if no explicit key is provided. The view correctly passes an
explicit token from the form, so the HTTP-level case is idempotent. However, any
programmatic caller that calls the service without an explicit key will generate a new
UUID on each call — making retry-on-failure non-idempotent.  
**Impact:** A programmatic double-call to `record_manual_settlement()` without an
explicit key creates two ledger entries. This could arise from a future management
command or API endpoint that retries on failure.  
**Likelihood:** Low today (no programmatic callers exist). Increases as the platform adds
API endpoints or management commands.  
**Mitigation:** Make `idempotency_key` a required parameter (remove the UUID fallback) in
a future refactor. Callers must provide a deterministic key.

---

### RISK-F7 — get_balance() Full Table SUM Per Call

**Classification:** Medium  
**Description:** `TechnicianLedgerService.get_balance()` computes the balance with a
full `SUM(amount_rial)` over all ledger entries for a technician, split into separate
credit and debit aggregates. For a technician with thousands of entries, this is two
full-table aggregation queries per call. It is called inside `_write_entry()` on every
ledger write and inside every statement view.  
**Impact:** Slow statement rendering and slow ledger writes for high-activity technicians.  
**Likelihood:** Low at V1 scale (few entries per technician). Medium at one year of use.  
**Mitigation:** Add a `balance_after` read path (take the last row's `balance_after` as
the current balance instead of SUM) once the Financial Account Lock ensures correct
ordering. Alternatively, introduce a `TechnicianLedgerBalance` denormalization row
(per-technician running total, updated atomically on each write).

---

### RISK-F8 — PaymentCallbackService Nested select_for_update

**Classification:** Low  
**Description:** `PaymentCallbackService.handle_callback()` acquires a `select_for_update`
lock on the payment row, then calls `PaymentVerifyService.verify()` which also acquires
`select_for_update` on the same row. In Django with PostgreSQL, locking a row twice in
the same transaction is idempotent (the existing lock is reused). In SQLite, the
behaviour differs. This double-lock is harmless in practice but misleading.  
**Impact:** No functional impact. Risk of confusion for developers reading the code.  
**Likelihood:** Irrelevant to production behaviour.  
**Mitigation:** Refactor `verify()` to accept a pre-locked payment instance rather than
re-locking. Low priority.

---

### RISK-F9 — No Automated PSP Reconciliation

**Classification:** Low  
**Description:** There is no automated comparison between the platform ledger and the
Shaparak/PSP settlement report. The gateway reconciliation view shows `PaymentSplitSnapshot`
rows but does not import or compare against the actual PSP settlement file.  
**Impact:** If a direct gateway settlement DEBIT is posted in the ledger but Shaparak
actually did not settle (PSP error), the discrepancy is invisible until manual review.  
**Likelihood:** Low (PSP errors are rare). Medium as payment volume grows.  
**Mitigation:** Build an automated reconciliation import in a future phase. For V1, the
gateway reconciliation view and the `direct_gateway_settlement` DEBIT idempotency key
provide sufficient auditability.

---

### RISK-F10 — No Rate Limiting on Financial Write Views

**Classification:** Low  
**Description:** The `record_manual_settlement` view has no rate limiting. A company
admin could submit the settlement form rapidly (or programmatically) and generate many
ledger entries. The idempotency token prevents duplicates for a single form submission,
but a user who opens a fresh form (new GET → new token) each time can create unlimited
settlement entries.  
**Impact:** Ledger pollution. No financial fraud risk (only company admins have access).
Difficult to detect without monitoring.  
**Likelihood:** Low (requires malicious or buggy admin user).  
**Mitigation:** Add a per-user, per-technician rate limit on the settlement endpoint (e.g.,
10 submissions per minute). Low priority for V1.

---

## 5. Technical Debt

All items in this section are **deferred by design, not bugs**. The system is correct
within the stated constraints. These items represent known limitations that are acceptable
for V1.

| Item | Reason Deferred | Acceptable for V1? |
|---|---|---|
| Financial Account Lock Layer | V1 write volume is too low to cause the race in practice. Requires new model + migration. | Yes |
| PostgreSQL concurrency integration tests | Requires threading infra + PG test environment. Out of scope for V1. | Yes, with RISK-F2 acknowledged |
| Enterprise retry queue (Celery/SQS) | Management command is adequate for low volume. Celery adds operational complexity. | Yes |
| Large-scale reconciliation automation | PSP error rate is very low. Manual review via gateway reconciliation view suffices. | Yes |
| Automatic escalation on repeated backfill failures | Monitoring must be verified before launch. Simple query-based alert is P0. | No — alert required before launch |
| `record_manual_settlement` required idempotency_key | No programmatic callers today. UUID fallback only applies to future callers. | Yes |
| Balance optimization (last-row read instead of SUM) | Requires Financial Account Lock first. Low volume — SUM queries are fast. | Yes |
| Rate limiting on settlement views | Low risk with admin-only access. | Yes |
| Automated PSP settlement import | V1 volume is low; manual reconciliation is acceptable. | Yes |

---

## 6. Production Readiness Checklist

| Dimension | Score | Explanation |
|---|---|---|
| **Correctness** | 8/10 | Business logic is correct. Immutability, idempotency, snapshot amounts, and tenant scoping are all properly enforced. Minus 2 for the deferred `balance_after` race (RISK-F1) which may produce wrong running-balance snapshots in rare concurrent cases. |
| **Recoverability** | 8/10 | All financial write failures have a backfill path. Cascade recovery handles dependent failures. Minus 2 for the absence of automatic alerting when backfill tasks accumulate (RISK-F3) and the unverified cron scheduling (RISK-F4). |
| **Security** | 7/10 | Financial views are admin-only. Multi-tenant scoping is structural. Amount tampering is detected in `PaymentVerifyService`. Minus 3 for no rate limiting on financial write views, no audit log of who created which ledger entry (the `created_by` FK exists but is not always populated), and no 2FA requirement for high-value settlement actions. |
| **Maintainability** | 9/10 | Clear service layer, single-responsibility services, no ledger writes in views. ADR system enables confident change. Minus 1 for the double-lock in `PaymentCallbackService` and the UUID fallback in `record_manual_settlement`. |
| **Extensibility** | 9/10 | Adding a new ledger source requires only: a new `Source` choice, a new `TaskType`, a new handler in `_dispatch()`, and tests. No structural change needed. Minus 1 for `get_balance()` SUM which will need to be replaced at scale. |
| **Performance** | 5/10 | `get_balance()` is a full SUM per write and per statement view. WeasyPrint PDF is synchronous in the HTTP cycle. No caching layer. No pagination on `list_statement()` beyond a raw limit/offset. These are acceptable at V1 scale but will require attention early in growth. |
| **Testing** | 8/10 | Extensive unit and integration tests covering all happy paths, idempotency, backfill resolution, and regression. Minus 2 for the absence of PostgreSQL concurrency tests (RISK-F2) and the absence of a full end-to-end test of the Shaparak callback flow in a staging environment. |
| **Documentation** | 9/10 | ADR-004 through ADR-008 form a complete and internally consistent body of knowledge. FINANCIAL_ARCHITECTURE_INDEX.md is a high-quality entry point. Minus 1 for the absence of inline API documentation (no docstrings on most service methods beyond a one-liner). |
| **Multi-tenancy** | 9/10 | `CompanyOwnedModel` is used throughout. All financial queries are scoped by `company`. Statement and reconciliation views enforce tenant context via `request.company`. Minus 1 for no tenant-level rate limits on financial operations. |
| **Operational Readiness** | 5/10 | The most significant gap. No health check endpoint for financial services. No monitoring dashboard for `FinancialBackfillTask` status. No automatic alerting. No verified cron for `process_pending()`. No runbook for manual backfill intervention. These are not architectural flaws — they are deployment concerns — but they are real gaps. |

**Weighted average: ~7.7/10**

---

## 7. Recommendations Before First Paying Customer

These items are required before any real customer money flows through the system.

### P0.1 — Verify and Monitor FinancialBackfillService Cron

Add `process_financial_backfill` to the production cron or task scheduler. Set it to
run every 5 minutes. Add a monitoring check that alerts when the count of PENDING tasks
with `attempts >= 3` is non-zero. Document the runbook for manual intervention.

### P0.2 — Deploy a Staging Environment with Real Shaparak Sandbox

Before onboarding any paying customer, perform a complete end-to-end test:
- Create an order → complete it → verify wage posting
- Issue an invoice → initiate payment via Shaparak sandbox → receive callback → verify all
  ledger entries (CREDIT + DEBIT + platform fee + split snapshot + direct settlement)
- Verify `get_balance()` returns the expected value
- Verify statement display

### P0.3 — Add a Financial Health Admin View

Create a simple admin view (or use Django Admin) showing:
- Count of PENDING `FinancialBackfillTask` rows
- Any tasks with `attempts >= 3` (requiring manual attention)
- Last run time of `process_pending()`

### P0.4 — Populate created_by on All Financial Entries

Currently `created_by` is populated only for manual settlements (view sets
`created_by=request.user`). For audit purposes, system-generated entries should carry a
system user or a `None` + `metadata.created_by_service` field indicating which service
created them.

### P0.5 — Document Manual Settlement Intervention Procedure

Write a 1-page operations runbook: how to identify a failed backfill task, how to
resolve it manually (including how to create an ADJUSTMENT entry via Django shell), and
when to escalate.

---

## 8. Recommendations Before Enterprise Scale

These items are not required for V1 but are required before significant scale.

### Enterprise.1 — Financial Account Lock Layer

Implement a `TechnicianLedgerBalance` model or per-technician advisory lock to serialize
all concurrent ledger writes. This eliminates RISK-F1 and enables the `balance_after`
optimization (read last row instead of SUM).

### Enterprise.2 — PostgreSQL Concurrency Integration Tests

Build a threaded test suite that runs concurrent `_write_entry()` calls against a real
PostgreSQL instance. Verify both the non-empty table (serialized via last-row lock) and
empty table cases.

### Enterprise.3 — Move PDF Generation to Background Job

Accept a PDF generation request, generate in background (Celery task), store in object
storage (S3/MinIO), return a download URL. Eliminate synchronous WeasyPrint calls from
the HTTP cycle.

### Enterprise.4 — Automated PSP Reconciliation Import

Build an import pipeline for Shaparak settlement reports (CSV or API). Automatically
match settled amounts against `PaymentSplitSnapshot.technician_direct_amount`. Flag
discrepancies for manual review.

### Enterprise.5 — Replace SUM-Based get_balance() with Denormalized Running Total

Replace the two-query SUM with a single read of a `TechnicianLedgerBalance.current_balance`
field maintained atomically during each write.

### Enterprise.6 — Enterprise Retry Queue

Replace the management-command cron with Celery Beat + Celery tasks. Each
`FinancialBackfillTask` becomes a Celery task with exponential backoff, dead-letter queue,
and Flower dashboard visibility.

---

## 9. Final Verdict

**The Financial Core is approved for production at V1 scale, subject to P0 conditions.**

As CTO, I would sign off on this architecture for the following reasons:

**Why I would approve:**
The fundamental design is correct and future-proof. The immutable ledger, snapshot-driven
amounts, and idempotency keys are not compromises — they are exactly what a financial
system needs. The recovery model is comprehensive: every known failure path has a retry
mechanism. The ADR documentation is the best-documented subsystem in the codebase. The
test suite covers the critical paths with deterministic, maintainable tests.

**Why I would attach conditions:**
The system's correctness depends on `FinancialBackfillService.process_pending()` running
reliably. Right now, that is an unverified assumption. An unmonitored cron failure would
mean ledger entries fail silently without any alert. No financial system should have
silent failures as an accepted operating mode.

**What I would not compromise on:**
The immutable ledger model is non-negotiable. The snapshot-driven amounts are
non-negotiable. The idempotency keys are non-negotiable. These design decisions protect
the financial integrity of the system under all future code changes and will not be
revisited.

**Summary:**
Three P0 items must be completed (cron verified, alert in place, staging E2E test done).
After those, this financial core is ready to handle real customer payments.
