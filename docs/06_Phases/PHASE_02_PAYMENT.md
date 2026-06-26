# Phase 02 — Payment Architecture Implementation

**Status:** Planned after Phase 01  
**Goal:** Implement explicit payment modes, gateway consolidation, permissions, and real-provider readiness.

---

## Phase 02 Principles

- Build on Phase 01 safety fixes.
- Do not re-add `PaymentGateway.owner_type` if Phase 01 already added it.
- Phase 02 owner-type work means management UI, permissions, selectors, and consolidation around the existing field.
- Payment mode activation belongs to `CompanyPaymentSettings`.
- Gateway consolidation must be planned and tested separately.

---

## Phase 02 Tasks

### P2-T001 — CompanyPaymentSettings

Goal: Add the canonical model for payment activation and payment mode.

Includes:

- `CompanyPaymentSettings`
- default mode `disabled`
- activation audit fields
- platform-owner-only activation service
- data migration creating one row per company

### P2-T002 — Payment Mode Enforcement

Goal: `PaymentStartService` must respect company payment mode.

Includes:

- disabled mode blocks online initiation
- company-gateway mode uses company-owned gateway
- platform-gateway mode uses platform-owned gateway and KYC rules

### P2-T003 — Gateway Model Consolidation

Goal: move payment-flow configuration to canonical `PaymentGateway`.

Includes:

- analyze legacy gateway models
- migrate data if needed
- update selectors/services
- prevent new logic on legacy models

Legacy models:

- `CompanyPaymentGatewaySetting`
- `PlatformPaymentGatewaySetting`

### P2-T004 — Gateway Activation Permissions

Goal: company admin cannot activate online payment or gateway status.

Includes:

- platform-owner-only activation
- company-admin submission/review separation
- tests

### P2-T005 — Callback Security

Goal: prepare for real PSP providers.

Includes:

- callback signature validation
- provider-specific verify rules
- spoofed callback tests

---

## Phase 02 Exit Criteria

Phase 02 is complete when:

- Payment mode is explicit and stored on `CompanyPaymentSettings`.
- Company admin cannot activate online payment.
- Gateway flow uses canonical `PaymentGateway` for new payment logic.
- Legacy gateway models are either migrated or clearly isolated.
- Callback signature validation is implemented for real providers or documented as provider-specific required work.
- Tests cover all three payment modes.
