# ADR-005 — Technician Service Pricing

**Status:** Accepted  
**Date:** 2026-06-27  
**Deciders:** Platform Team  
**Supersedes:** —  
**Superseded by:** —

---

## Context

The platform must compensate technicians based on the service units they complete per order.
The initial requirement is a fixed rial amount per countable order item (e.g., "نصب پکیج = 4,000,000 ریال").

Before building UI and order-completion posting logic, a model was introduced:
`TechnicianServiceRate` in `apps/payouts/models.py`.

This ADR records the current scope, the deliberate design constraints applied in Phase 1,
and the approved direction for future extension.

---

## Current Model — TechnicianServiceRate

```
TechnicianServiceRate(CompanyOwnedModel)
  - company          FK → tenants.Company
  - technician       FK → accounts.Technician
  - item_definition  FK → orders.OrderItemDefinition  (kind=NUMBER only)
  - fixed_wage_rial  PositiveBigIntegerField
  - is_active        BooleanField (default=True)
  - created_at / updated_at  (inherited)
```

**Constraints enforced at model layer:**

- `unique_tech_rate_per_item`: one rate per `(company, technician, item_definition)`
- `tech_rate_wage_non_negative`: `fixed_wage_rial >= 0`
- `clean()`: rejects cross-company FK references, non-NUMBER item kinds, and active rates on inactive item definitions

---

## Current Scope

This model covers exactly one pricing mode in Phase 1:

- **Pricing type:** fixed rial amount per unit
- **Unit of measurement:** `OrderItemDefinition.value_number` captured on the order
- **Eligible items:** only `OrderItemDefinition.kind = NUMBER`
- **Rate granularity:** per technician per item definition
- **Rate timing:** rate is read at order completion time
- **Rate isolation:** after a wage ledger entry is posted, the rate can change freely without affecting past entries
- **Non-eligible items:** MONEY, TEXT, BOOL item definitions cannot have a wage rate

The model does **not** yet cover:

- Percentage-based compensation per item
- Formula-based pricing
- Effective date ranges on rates
- Historical audit trail of rate changes per technician
- Rate tiers or volume discounts

---

## Decision

**Keep the model as-is. Do not extend in this phase.**

The decision is to ship `TechnicianServiceRate` with the minimum fields required to support Phase 1:
fixed wages on order completion. No additional columns will be added until at least one of the
following triggers is met:

1. UI for technician rate management is built and a second pricing type is requested by a real tenant.
2. A compliance requirement demands a historical record of rate changes.
3. The posting logic for order completion is deployed and produces support requests about edge cases
   that the current model cannot handle.

**Model name is final for this codebase generation.** No rename planned.

---

## Future Direction (Approved, Not Yet Scheduled)

When Phase 2 is triggered, the model will be extended with the following fields.
All additions must be backward-compatible migrations (nullable or with defaults):

### Pricing type

```python
class PricingType(models.TextChoices):
    FIXED   = "fixed",   "مبلغ ثابت"
    PERCENT = "percent", "درصد از مبلغ سفارش"
    FORMULA = "formula", "فرمول سفارشی"

pricing_type = models.CharField(
    max_length=10,
    choices=PricingType.choices,
    default=PricingType.FIXED,
)
```

The `FORMULA` type will store an expression in a `formula` TextField and be evaluated
server-side by a sandboxed evaluator. No `eval()` or user-controlled code execution.

### Effective date range

```python
effective_from = models.DateField(null=True, blank=True)
effective_to   = models.DateField(null=True, blank=True)
```

When set, the system picks the rate whose `effective_from <= order.completed_at.date() <= effective_to`.
If multiple rates are valid, the most recently effective one wins.
When not set (current behavior), the active rate is always used.

### Audit trail

```python
created_by = models.ForeignKey(
    "accounts.CompanyUser",
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name="created_service_rates",
)
notes = models.TextField(blank=True)
```

### Historical snapshot on posting

When an order is completed and wages are posted to `TechnicianLedgerEntry`, the rate
snapshot (amount and pricing_type) will be stored in the ledger entry's `metadata` field:

```json
{
  "rate_id": 42,
  "pricing_type": "fixed",
  "fixed_wage_rial": 4000000,
  "snapshotted_at": "2026-06-27T10:30:00Z"
}
```

This snapshot makes the ledger entry self-contained. Even if the rate row is later
deactivated or updated, the ledger entry records exactly what was applied.

### Invariant: completed orders are immutable

Regardless of extension, the following rule is non-negotiable:

> Changing a rate after an order is completed must never alter any previously posted
> ledger entry. Old entries are corrected only by a new ADJUSTMENT entry per ADR-004.

This rule is enforced by design: wage posting reads the current rate at completion time
and writes `amount_rial` + metadata snapshot into the immutable `TechnicianLedgerEntry`.
No FK from `TechnicianLedgerEntry` to `TechnicianServiceRate` is introduced to prevent
cascade side effects.

---

## Consequences

### Positive

- **Simple now.** No unused columns in the schema. No migration surface for features that
  are not yet needed. Technician rate setup (UI and service layer) can ship quickly.

- **Migration-safe later.** All planned future fields are nullable or carry defaults.
  Adding them requires no data backfill and no downtime on the existing table.

- **No breaking change now.** The Phase 1 posting service (`TechnicianWagePostingService`)
  reads only `fixed_wage_rial` and `is_active`. Future `pricing_type` field will default
  to `FIXED`, making the posting service forward-compatible without a code change at
  the time of migration.

- **Ledger integrity preserved.** Because the snapshot is written into `metadata` at
  posting time, the rate history is implicit in the ledger — there is no need for a
  separate rate-history table in Phase 1.

### Negative / Trade-offs

- **No rate history in Phase 1.** If a tenant asks "what rate was applied on order #42?",
  the answer is visible only after Phase 2 snapshot metadata is in place. For Phase 1,
  the only answer is the ledger entry description field.

- **Effective date range is not enforceable in Phase 1.** If a company changes a rate
  mid-month, all future completions use the new rate immediately, with no way to pin
  older orders to the old rate. This is accepted as a Phase 1 limitation.

- **Single active rate per item per technician.** The unique constraint
  `unique_tech_rate_per_item` prevents storing both a current and a future rate
  simultaneously. Until effective date ranges are added, rate rollback requires
  a manual update.

---

## References

- `apps/payouts/models.py` — `TechnicianServiceRate`
- `apps/orders/models.py` — `OrderItemDefinition`, `OrderItemValue`
- `docs/07_ADR/ADR-004-Ledger-Discipline.md` — immutability rules for ledger entries
- `docs/03_Business/ACCOUNTING_RULES.md` — technician wage rules
- TASK-010A-1 — initial implementation commit `db49151`
- TASK-010B — order completion wage posting (planned)
