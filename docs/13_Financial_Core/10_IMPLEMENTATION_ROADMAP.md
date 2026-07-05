# 10 — نقشه راه پیاده‌سازی (Implementation Roadmap)

**تاریخ ممیزی:** 2026-07-05
**وضعیت:** Draft — Pending OI Resolution

---

## پیش‌شرط‌ها (قبل از هر implementation)

| # | Action | Owner | Blocker |
|---|---|---|---|
| 0.1 | Resolve OI-01 through OI-10 with Product Owner | Product Owner | — |
| 0.2 | Finalize this audit documentation | Engineering | — |
| 0.3 | Freeze Target Architecture docs | Engineering + PO | 0.1 |

---

## Sprint 1: Quick Wins (1-2 هفته)

**هدف:** پر کردن gap‌های ساده بدون ریسک

| Task | Rule | Type | Effort |
|---|---|---|---|
| Add `charge_commission_on_cash` field to CompanyFinancialPolicy | R10, R38 | Migration + logic | 2h |
| Add `rounding_discount_enabled` + `max_rounding_discount_rial` | R29 | Migration + logic | 3h |
| Add `card_to_card` to PaymentGateway.GatewayType choices | R40 | Migration | 1h |
| Install django-auditlog for financial policy models | R50 | Package + config | 4h |
| Add `ADDITIONAL_DISCOUNT` and `LOYALTY_DISCOUNT` to InvoiceItem.RowType | R23 | Migration | 1h |

**خروجی:** 5 gap‌ بسته، 0 risk جدید، backward-compatible

---

## Sprint 2: Settlement Foundation (2-3 هفته)

**هدف:** ساختار settlement batching

| Task | Rule | Type | Effort |
|---|---|---|---|
| Design + create `OrganizationSettlementConfig` model | R41 | New model | 4h |
| Design + create `SettlementBatch` + `SettlementItem` models | R41-R44 | New models | 8h |
| Implement `SettlementCalculationService` (net position) | R41-R44 | New service | 8h |
| Implement `SettlementExecutionService` (batch processing) | R43 | New service | 12h |
| Create management command `process_settlements` | R43 | Command | 4h |
| Admin UI: settlement config per company | R41 | View + template | 8h |
| Admin UI: settlement batch list + detail | R55 | View + template | 8h |

**خروجی:** Automated Platform↔Organization settlement. R41-R44 fully addressed.

---

## Sprint 3: Escrow Tracking (1-2 هفته)

**هدف:** explicit ownership tracking

| Task | Rule | Type | Effort |
|---|---|---|---|
| Design + create `EscrowRecord` model | P05, R01 | New model | 4h |
| Integrate with PaymentVerifyService (create on PAID) | R01 | Logic extension | 4h |
| Integrate with SettlementExecutionService (release on settle) | R01 | Logic extension | 4h |
| Platform Owner dashboard: escrow balance per company | R01 | View | 8h |
| State machine: held → reserved → released → settled → closed | Section 3.2 | Logic | 8h |

**خروجی:** Full money ownership visibility for Platform Owner.

---

## Sprint 4: Financial Alerting + Monitoring (1 هفته)

**هدف:** operational safety

| Task | Rule | Type | Effort |
|---|---|---|---|
| Add `FINANCIAL_BACKFILL_STUCK` event to notification catalog | ADR-008 | Config | 2h |
| Implement threshold check in `process_financial_backfill` | ADR-008 | Logic | 4h |
| Platform Owner notification on stuck tasks | ADR-008 | Integration | 4h |
| Dashboard: pending backfill tasks count | ADR-008 | View | 4h |

**خروجی:** No more silent financial failures.

---

## Sprint 5: Reporting — Phase 1 (2 هفته)

**هدف:** mandatory reports (R53-R55)

| Task | Rule | Type | Effort |
|---|---|---|---|
| Provider Liability Report (negative balance technicians) | R53 | View + query | 8h |
| Platform Commission Report (aggregated) | R54 | View + query | 8h |
| Settlement Status Report | R55 | View + query (depends Sprint 2) | 8h |
| Export (CSV/PDF) for all reports | R53-R55 | Feature | 8h |

**خروجی:** R53-R55 fully addressed.

---

## Sprint 6: Refund Engine (3-4 هفته) — BLOCKED on OI-07

**هدف:** complete refund lifecycle

**BLOCKER: OI-07 must be resolved first**

| Task | Rule | Type | Effort |
|---|---|---|---|
| Design RefundRequest model + status machine | OI-07 | Model | 8h |
| Implement RefundService (orchestration) | R46 | Service | 16h |
| Ledger reversals (tech wage ADJUSTMENT, platform fee CREDIT) | R46 | Logic | 12h |
| Gateway refund API integration | R46 | Integration | 8h |
| Customer credit balance (if OI-06 resolved) | OI-06 | Model + service | 16h |

---

## Sprint 7: KPI + Advanced Reporting — BLOCKED on OI-09, OI-10

**BLOCKER: OI-09 and OI-10 must be resolved first**

---

## Timeline Overview

```
Week 1-2:    Sprint 1 (Quick Wins)
Week 3-5:    Sprint 2 (Settlement Foundation)
Week 5-7:    Sprint 3 (Escrow) + Sprint 4 (Alerting)
Week 7-9:    Sprint 5 (Reporting Phase 1)
Week 9-13:   Sprint 6 (Refund — if OI-07 resolved)
Week 13+:    Sprint 7 (KPI — if OI-09/10 resolved)
```

---

## Definition of Done per Sprint

- [ ] All new models have migrations (backward-compatible)
- [ ] All new services have full test coverage
- [ ] Existing tests continue to pass
- [ ] Documentation updated
- [ ] No existing API/view broken
- [ ] ADR created if architectural decision made
