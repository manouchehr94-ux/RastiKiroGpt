# ADR-008 — Financial Recovery Policy

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Platform Team  
**Supersedes:** —  
**Superseded by:** —  
**Related:** ADR-004, ADR-006, ADR-007

---

## Context

Financial writes in this platform are distributed across multiple services and may fail
for many reasons: network timeouts, DB errors, application exceptions, or concurrent
race conditions. Because ledger entries are immutable and payment status transitions are
final, a failed write cannot be retried naively — it must be retried idempotently.

This ADR records the complete recovery policy that governs all financial retry logic.

---

## Decision

All financial write failures are handled by the `FinancialBackfillTask` system.
The policy below is binding for all current and future financial services.

---

## Recovery Flow

```
Primary write attempt
      │
      ├──► SUCCESS ──────────────────────► Done
      │
      └──► FAILURE (any Exception)
              │
              ▼
      FinancialBackfillTask created
      (status=PENDING, task_type, company, invoice, payment)
              │
              ▼
      FinancialBackfillService.process_pending()
      (run by management command or cron)
              │
              ├──► Retry succeeds ──────► Task: RESOLVED
              │
              └──► Retry fails ──────────► Task: stays PENDING
                                           attempts counter incremented
                                           error_message updated
                                           (manual intervention required)
```

---

## Task Types

| `task_type` | Failed write | Retry handler |
|---|---|---|
| `technician_ledger` | `TechnicianLedgerService.create_invoice_entries()` | `_retry_technician_ledger()` |
| `platform_fee` | `PlatformFeeService.record_invoice_fee()` | `_retry_platform_fee()` |
| `payment_split_snapshot` | `PaymentSplitDecisionService.create_snapshot()` | `_retry_payment_split_snapshot()` |
| `direct_gateway_settlement` | `TechnicianDirectSettlementService.post_for_payment()` | `_retry_direct_gateway_settlement()` |

---

## Idempotency Rules

Every retry handler relies on the idempotency guarantees of the underlying service.
A handler may be called any number of times and must produce the same result:

| Service | Idempotency mechanism |
|---|---|
| `TechnicianLedgerService._write_entry()` | DB UNIQUE constraint on `idempotency_key` + `IntegrityError` recovery (savepoint) |
| `PlatformFeeService._write_entry()` | DB UNIQUE constraint on `idempotency_key` |
| `PaymentSplitDecisionService.create_snapshot()` | `OneToOneField` on `payment` + code-level filter check |
| `TechnicianDirectSettlementService.post_for_payment()` | `idempotency_key = direct_gateway_settlement:payment:{id}` |

**Rule:** A retry handler must NEVER check "has this already been done?" at the handler
level. It must call the service unconditionally and let the service's own idempotency
mechanism handle the duplicate.

---

## Deduplication of Backfill Tasks

At most one PENDING or PROCESSING task may exist per `(company, task_type, invoice)`.

`FinancialBackfillService.create_task()` enforces this via `select_for_update()` on the
existing task row before inserting. Concurrent callers are serialized; the second caller
receives the existing task without creating a duplicate.

**Key:** The deduplication key is `(company, task_type, invoice)`, NOT `(company, task_type, payment)`.
All payment-level tasks have `invoice=payment.invoice`, which satisfies this key.

---

## Cascade Recovery

Some task types have a dependency:  
`direct_gateway_settlement` requires `payment_split_snapshot` to exist first (the settlement
DEBIT reads `PaymentSplitSnapshot.technician_direct_amount`).

`_retry_direct_gateway_settlement()` handles this by checking for the snapshot and
creating it if missing before attempting the settlement:

```python
snapshot = PaymentSplitSnapshot.objects.filter(payment=payment).first()
if snapshot is None:
    PaymentSplitDecisionService.create_snapshot(payment, fresh_invoice)
TechnicianDirectSettlementService.post_for_payment(payment)
```

This means a single `DIRECT_GATEWAY_SETTLEMENT` task can recover from a cascaded failure
where both snapshot creation AND settlement failed.

---

## Transaction Isolation

Each task is processed in its own `transaction.atomic()` block inside `_process_one()`.

- On **success**: the task is marked RESOLVED within the same transaction. The ledger
  write and the RESOLVED status are atomic.
- On **failure**: the transaction rolls back. A separate `transaction.atomic()` block
  records the failure (increments `attempts`, stores `error_message`). The task remains
  PENDING for the next run.

This two-phase approach ensures that a ledger write that partially succeeds is never
paired with a RESOLVED task status unless both committed together.

---

## Backfill Processing

```
management command: python manage.py process_financial_backfill
service:            FinancialBackfillService.process_pending(limit=100)
```

The command processes up to `limit` PENDING tasks in `created_at` order. Each task
runs in isolation. A failure on task N does not affect task N+1.

**Recommended schedule:** Run every 5 minutes in production (cron or Celery beat).

---

## Manual Intervention Criteria

A task requires manual intervention when:

1. `attempts` exceeds a threshold (suggested: 5 attempts) with no resolution.
2. `error_message` indicates a data integrity issue (e.g., missing invoice, missing technician).
3. `task_type = direct_gateway_settlement` with `attempts > 3` — the PSP may have already
   settled, making the DEBIT amount no longer verifiable without external reconciliation.

**Manual intervention procedure:**
1. Inspect the task: `FinancialBackfillTask.objects.get(pk=task_id)`.
2. Inspect the linked payment / invoice / split snapshot.
3. If the write already succeeded (e.g., ledger entry exists), mark the task RESOLVED manually.
4. If the write genuinely failed and cannot be retried, create an ADJUSTMENT entry with
   a human-readable reason per ADR-004.
5. Never delete a `FinancialBackfillTask`. Mark it RESOLVED or FAILED only.

---

## What Is NOT Covered by This Policy

| Scenario | Status |
|---|---|
| `FinancialBackfillTask` creation fails (double failure) | Logged at CRITICAL; requires manual monitoring alert |
| Retry handler raises after many attempts | Task stays PENDING; no automatic escalation in V1 |
| Concurrent balance_after race on first technician write | Deferred — see Technical Debt section |
| Enterprise retry queue (Celery, SQS) | Deferred — see Technical Debt section |
| Reconciliation of PSP-level splits against ledger | Deferred — see Technical Debt section |

---

## Deferred Technical Debt

The following improvements are intentionally deferred. They are **not bugs** — the
current system is correct and self-healing for V1 scale.

### 1. Financial Account Lock Layer

**What:** A per-technician lock row that serialises all concurrent ledger writes,
preventing the brief window in which two concurrent writers can both pass the
idempotency check and compute `balance_after` independently.

**Why deferred:** V1 write volumes are low (ledger writes happen at invoice payment
time, not at request time). The existing `select_for_update()[:1]` on the last ledger
row serialises the non-empty case correctly. The empty-table case produces a wrong
`balance_after` snapshot but `get_balance()` (SUM) remains correct.

**When to implement:** When concurrent ledger writes to the same technician are
observed in production logs, or when the platform supports real-time payouts.

### 2. Enterprise Concurrency Strategy

**What:** Move from `select_for_update()` row-level locks to an optimistic concurrency
model (version counter + retry loop) to support high-throughput ledger writes without
serialisation bottlenecks.

**Why deferred:** Not needed at V1 scale. Row-level locking on a per-technician basis
is correct and safe for the current write frequency.

### 3. PostgreSQL Concurrency Integration Tests

**What:** Real multi-threaded tests that exercise concurrent `_write_entry()` calls
against a live PostgreSQL instance to verify that `balance_after` is never wrong in
practice.

**Why deferred:** Test environment uses SQLite in-memory, which serialises writes at
the database level, masking the race. Setting up a PostgreSQL test environment and
threading infrastructure is out of scope for V1.

**When to implement:** Before any migration to real-time or high-frequency ledger writes.

### 4. Large-Scale Reconciliation Optimisation

**What:** Batch reconciliation of `FinancialBackfillTask` rows against the PSP settlement
report, with automatic RESOLVED/escalation logic and a reconciliation audit table.

**Why deferred:** V1 manual intervention is sufficient. The reconciliation view
(`gateway_reconciliation`) provides admin visibility into `PaymentSplitSnapshot` rows.

### 5. Automatic Escalation / Alerting

**What:** After N failed retries, automatically create a platform notification or
Slack/email alert for the ops team.

**Why deferred:** V1 teams are small; manual log monitoring is acceptable. Implement
before the platform scales beyond ~10 tenants or 100 payments/day.

---

## Consequences

### Positive

- Payment callback latency is unaffected by ledger failures: all financial side effects
  are non-blocking in `PaymentVerifyService.verify()`.
- Every failed financial write has a recoverable audit trail.
- Retry handlers are simple: they call idempotent services unconditionally.
- The system is self-healing for all common failure modes (transient DB errors, timeouts).

### Negative / Trade-offs

- Recovery relies on a management command being scheduled. If the command is not run,
  PENDING tasks accumulate silently. Monitoring is required.
- Two-phase commit (task creation + original write) is not atomic: if the original write
  succeeds but task creation fails, we get a CRITICAL log but no backfill task. This
  double-failure window is acceptable for V1.

---

## References

- `apps/payouts/models.py` — `FinancialBackfillTask`
- `apps/payouts/services_backfill.py` — `FinancialBackfillService`
- `apps/invoices/services.py` — `InvoiceMarkPaidService` (creates `technician_ledger` and `platform_fee` tasks)
- `apps/payments/services.py` — `PaymentVerifyService` (creates `payment_split_snapshot` and `direct_gateway_settlement` tasks)
- `apps/payouts/services.py` — `TechnicianLedgerService._write_entry()` (TASK-011A-FIX-2 savepoint)
- `docs/07_ADR/ADR-004-Ledger-Discipline.md`
- `docs/07_ADR/ADR-007-Financial-Event-Timeline.md`
- `docs/07_ADR/FINANCIAL_ARCHITECTURE_INDEX.md`
