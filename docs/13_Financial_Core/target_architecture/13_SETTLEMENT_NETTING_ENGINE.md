# 13 — موتور تسویه و Net Settlement (Settlement & Netting Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R41–R45, Section 3.6, P07

---

## Layer 1: Platform ↔ Organization Flow

### Overview
Platform holds customer funds (escrow). After invoices are PAID and eligible
for distribution, funds must be transferred from Platform to Organization.


### Data Flow

```
1. Invoice PAID → CompanyPlatformFeeEntry DEBIT created (commission owed)
2. EscrowRecord created → status DISTRIBUTED
3. SettlementCalculationService runs for period:
   a. Sum all invoice.total_amount for PAID invoices in period
   b. Subtract platform_fee (already retained)
   c. Subtract technician_direct_amount (already paid via Shaparak)
   d. Remaining = organization_share (net payable to company)
4. SettlementBatch created (level=PLATFORM_TO_ORG, net_amount_rial)
5. SettlementExecutionService:
   a. Initiates bank transfer to CompanyMerchantProfile.shaba_number
   b. Records bank_reference
   c. status → COMPLETED
   d. Creates CompanyPlatformFeeEntry CREDIT (if netting reduces balance)
6. EscrowRecord status → SETTLED
```

### Net Position Calculation

```
Net Position (Platform owes Organization) =
    SUM(invoice.total_amount for PAID invoices in period
        WHERE payment.gateway.owner_type = PLATFORM)
  - SUM(CompanyPlatformFeeEntry.amount_rial WHERE entry_type=DEBIT in period)
  - SUM(PaymentSplitSnapshot.technician_direct_amount
        WHERE should_split=True in period)
```

**Simplified:** Platform owes = total collected - commission retained - amount already split to technician.

### Configuration

```python
# CompanyFinancialPolicy fields (target):
settlement_frequency = "daily"  # choices: immediate, daily, two_day, weekly, manual
settlement_delay_hours = 24     # delay after invoice PAID before eligible
```

### Trigger

- `process_settlements` management command (cron: every hour or per frequency)
- Manual trigger via Platform Owner admin panel

---

## Layer 2: Organization ↔ Provider Flow

### Overview
Organization owes technicians their wage share. Settlement transfers this debt
to actual payment (bank transfer, cash, card-to-card).

### Data Flow

```
1. Invoice PAID → TechnicianLedgerEntry CREDIT created (company owes technician)
2. Balance = SUM(credits) - SUM(debits) > 0 → company owes
3. Settlement options:
   a. Automated: SettlementBatch(level=ORG_TO_PROVIDER) calculates net per technician
   b. Manual: Admin uses technician_settlement view (existing)
   c. Direct Shaparak split: DEBIT created automatically (existing)
4. SettlementExecutionService (for automated):
   a. Bank transfer to Technician.shaba_number
   b. Creates TechnicianLedgerEntry DEBIT (source=manual_settlement)
   c. Batch status → COMPLETED
```

### Existing Implementation

Currently only manual + direct split exist:
- `apps/payouts/views.py:technician_settlement()`: Admin records manual settlement
- `apps/payouts/services.py:TechnicianLedgerService.record_manual_settlement()`: Creates DEBIT entry
- `apps/payouts/services_direct_settlement.py:TechnicianDirectSettlementService.post_for_payment()`:
  Automatic DEBIT for Shaparak split

### Target Extension

Add automated batch processing configured per Organization (R42).

---

## Net Position Formula

### Layer 1 (Platform → Organization)

```
NET_POSITION_L1(company, period) =
    Σ(invoice.total_amount)                     -- all PAID invoices in period (platform gateway)
  − Σ(CompanyPlatformFeeEntry.amount_rial)      -- commission already retained
  − Σ(PaymentSplitSnapshot.technician_direct_amount WHERE should_split=True)
                                                 -- already paid to technician via PSP
```

### Layer 2 (Organization → Provider)

```
NET_POSITION_L2(company, technician, period) =
    TechnicianLedgerService.get_balance(company, technician)
    -- i.e., SUM(credits) - SUM(debits) for entries in period
    -- Positive = company still owes technician
```

**Netting benefit:** Instead of settling each invoice separately, aggregate per period.
Example: 10 invoices × 10M rial each → 1 bank transfer of 100M minus fees.

---

## Batch Creation Algorithm

```python
class SettlementCalculationService:

    @staticmethod
    def create_batch_for_company(company, level, period_start, period_end):
        """
        Algorithm:
        1. Lock: acquire advisory lock per company to prevent concurrent batch creation
        2. Eligibility: find all PAID invoices in [period_start, period_end]
           that are NOT already in any SettlementBatch
        3. Filter: only invoices where paid_at + settlement_delay_hours <= now()
        4. Compute net position per formula above
        5. Create SettlementBatch(status=CALCULATING)
        6. Create SettlementItem per eligible invoice
        7. Update batch: net_amount_rial, items_count, total_credits, total_debits
        8. batch.status = READY
        9. If auto_approve (R44): proceed to execution immediately
        """
        pass

    @staticmethod
    def _find_eligible_invoices(company, period_start, period_end, delay_hours):
        """
        SELECT invoice.*
        FROM invoices_invoice invoice
        LEFT JOIN payouts_settlementitem si ON si.invoice_id = invoice.id
        WHERE invoice.company_id = {company.id}
          AND invoice.status = 'paid'
          AND invoice.paid_at >= {period_start}
          AND invoice.paid_at <= {period_end}
          AND invoice.paid_at + interval '{delay_hours} hours' <= NOW()
          AND si.id IS NULL  -- not already in a batch
        """
        pass
```


---

## Settlement Item Selection Rules

### Inclusion Criteria (Layer 1)
1. Invoice.status == PAID
2. Invoice.paid_at within batch period
3. Invoice.paid_at + delay_hours <= now()
4. Invoice has a Payment with gateway.owner_type == PLATFORM
5. Invoice is NOT already referenced by any SettlementItem in a non-FAILED batch

### Inclusion Criteria (Layer 2)
1. TechnicianLedgerEntry exists with entry_type=CREDIT, created_at in period
2. Corresponding technician has positive balance (company owes)
3. Entry is NOT already referenced by any SettlementItem in a non-FAILED batch
4. Technician.shaba_number is not empty (for automated payout)

### Exclusion Criteria (both layers)
- Invoices with pending AdjustmentDocument (DRAFT/PENDING_APPROVAL)
- Invoices with PENDING FinancialBackfillTask
- Invoices where EscrowRecord.status != DISTRIBUTED (not yet eligible)

---

## Idempotency Rules

### Batch Creation Idempotency
- Advisory lock per (company, level) prevents concurrent batch creation
- `_find_eligible_invoices` LEFT JOIN exclusion ensures no invoice appears in multiple batches
- If `create_batch_for_company()` is called twice for same period:
  - Second call finds zero eligible invoices → creates empty batch → skipped

### Item Assignment Idempotency
- SettlementItem has no UNIQUE constraint on invoice.
  (An invoice could theoretically be in a FAILED batch,
  then be reassigned to a new batch.)
- Selection query filters `si.id IS NULL` only for non-FAILED batches
- A FAILED batch's items are "released" — eligible for re-inclusion in next batch

### Execution Idempotency
- `SettlementExecutionService` checks batch.status == READY before executing
- If status is already COMPLETED or EXECUTING: no-op return
- Bank reference is recorded atomically with status → COMPLETED

---

## Failure and Retry Handling

### Batch Calculation Failure
```
create_batch_for_company() raises Exception
  → transaction rolls back
  → no SettlementBatch or SettlementItem created
  → next cron run will retry from scratch
  → idempotent: same invoices will be found again
```

### Execution Failure (bank transfer fails)
```
SettlementExecutionService.execute(batch) fails
  → batch.status = FAILED, failure_reason = error message
  → items are NOT deleted (audit trail)
  → items become re-eligible for next batch (selection query allows)
  → platform owner notified via financial_settlement_failed event
```

### Partial Execution (unlikely for single bank transfer)
```
If multi-transfer batch (future):
  → each SettlementItem tracks individual transfer status
  → batch status = PARTIAL (items have mixed COMPLETED/FAILED)
  → FAILED items eligible for retry batch
For V1: one bank transfer per batch → atomic success/failure.
```

### Retry Schedule
- Management command `process_settlements` runs per configured frequency
- FAILED batches are logged but not automatically retried (manual intervention)
- Platform Owner reviews at `/owner-platform/settlements/` and can trigger manual retry

---

## Events Emitted

| Event | Trigger | Recipient |
|---|---|---|
| `settlement_batch_created` | Batch status → READY | PLATFORM_OWNER, COMPANY_ADMIN |
| `settlement_batch_executing` | Batch status → EXECUTING | PLATFORM_OWNER |
| `settlement_completed` | Batch status → COMPLETED | COMPANY_ADMIN |
| `settlement_failed` | Batch status → FAILED | PLATFORM_OWNER |
| `provider_settlement_received` | Technician DEBIT created (Layer 2) | TECHNICIAN |

### Event Payload (target)

```python
{
    "event_key": "settlement_completed",
    "company_id": 42,
    "batch_id": 101,
    "level": "platform_to_org",
    "net_amount_rial": 85000000,
    "items_count": 12,
    "period_start": "2026-07-01T00:00:00Z",
    "period_end": "2026-07-07T23:59:59Z",
    "bank_reference": "TXN-2026-07-08-001",
    "timestamp": "2026-07-08T10:30:00Z",
}
```

---

## Reporting Impact

### Settlement Status Report (R55)

| Field | Source |
|---|---|
| Batch # | SettlementBatch.id |
| Company | SettlementBatch.company.name |
| Level | SettlementBatch.level |
| Period | period_start — period_end |
| Net Amount | SettlementBatch.net_amount_rial |
| Items | SettlementBatch.items_count |
| Status | SettlementBatch.status |
| Executed At | SettlementBatch.executed_at |
| Bank Ref | SettlementBatch.bank_reference |

### Platform Commission Report Integration (R54)

When a PLATFORM_TO_ORG batch COMPLETES:
- `CompanyPlatformFeeEntry` CREDIT is created (commission "settled")
- Commission report shows: total accrued - total settled = outstanding

### Provider Liability Report Integration (R53)

When an ORG_TO_PROVIDER batch COMPLETES:
- `TechnicianLedgerEntry` DEBIT is created per technician
- Liability report shows: updated balances per technician

---

## Existing vs Target

| Component | Existing | Target |
|---|---|---|
| Layer 2 manual settlement | ✅ `record_manual_settlement()` | Preserved (backward-compatible) |
| Layer 2 direct Shaparak | ✅ `TechnicianDirectSettlementService` | Preserved |
| Layer 1 fee tracking | ✅ `CompanyPlatformFeeEntry` DEBIT | Preserved |
| Layer 1 batch settlement | ❌ None | `SettlementBatch(level=PLATFORM_TO_ORG)` |
| Layer 2 batch settlement | ❌ None | `SettlementBatch(level=ORG_TO_PROVIDER)` |
| Settlement timing config | ❌ None | `CompanyFinancialPolicy.settlement_frequency` |
| Net position calculation | ❌ None | `SettlementCalculationService` |
| Automated execution | ❌ None | `process_settlements` command |
| Settlement reporting | ❌ None | Admin views on SettlementBatch |

---

## Cash Settlement (R39) — Not Batched

Cash settlement between Organization and Provider:
- Done directly by Organization (cash, bank transfer, card-to-card)
- Platform only **records** these via `record_manual_settlement()`
- NOT included in automated settlement batches
- Already implemented and working — no changes needed
