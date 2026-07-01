# SKILL.md — Rasti Service AI Development Entry Point

**Version:** EKB v1.0 (Engineering Knowledge Base)
**Status:** Active
**Primary rule:** Read the required documents before touching code.

This file is the entry point for Claude Code, ChatGPT, or any AI agent working on this repository. It is intentionally short. Detailed rules live under `docs/`.

> **For full AI operating instructions, read:** `docs/02_AI_Operating_System/AI_AGENT_START_HERE.md`

---

## 1. Source-of-Truth Order

When documents appear to conflict, use this order:

1. `docs/07_ADR/*` — accepted architecture decisions (binding)
2. `docs/04_Business_Rules/*` — business rules per entity
3. `docs/03_Architecture/*` — technical architecture rules
4. `docs/02_AI_Operating_System/*` — AI development workflow and protocols
5. Code and tests — current implementation evidence, not authority over business rules
6. `docs/00_Project/*` — glossary, terminology, scope, and context

If a conflict remains after applying this hierarchy, stop and report it. Do not guess.

---

## 2. Project Identity

Rasti Service is a multi-tenant Django SaaS platform for Iranian service-dispatch companies.

Rasti Service is **not** the service seller. Tenant companies sell services to their customers. Rasti Service provides software and may provide payment infrastructure only under the approved architecture.

Every order, invoice, customer, technician, payment, SMS, report, ledger, and setting belongs to exactly one tenant company unless explicitly marked as platform-level.

---

## 3. Non-Negotiable Rules

1. Always scope tenant data by `company`.
2. Never use `float` for money. Use `Decimal`.
3. Never bypass the service layer for business state changes.
4. Never rewrite unrelated code.
5. Never weaken or delete tests to make a change pass.
6. Never hard-delete financial data.
7. Never trust payment callback alone; provider verify is required.
8. Ambiguous or expired payments must go to `NEEDS_RECONCILIATION`, not blindly `FAILED`.
9. Ledger entries are immutable; reverse with a new entry.
10. Company admins must not activate online payment mode.
11. Platform commission is allowed only when all commission conditions are satisfied.
12. Stop if permission, tenant isolation, payment state, or money flow is unclear.

---

## 4. Payment and Commission Rule

Platform commission is created only when **all** of these are true:

1. Company payment mode is `platform_gateway` on `CompanyPaymentSettings`.
2. Payment exists and is verified `PAID`.
3. Payment gateway exists and `PaymentGateway.owner_type == platform`.
4. `CompanyFinancialPolicy.platform_fee_percent > 0`.

No platform commission for cash, card-to-card, manual admin payment, company-owned gateway, discounts, customer credits, failed payments, cancelled payments, or reconciliation cases.

During Phase 1, `CompanyPaymentSettings` may not exist yet. Phase 1 may add only the minimal `PaymentGateway.owner_type` field and defensive fee guards. Full mode enforcement belongs to Phase 2.

---

## 5. Canonical Models

- `Order` is the core operational object.
- `Invoice` is the bill issued by the tenant company/technician.
- `Payment` records payment attempts and verified outcomes.
- `PaymentGateway` is the target canonical gateway model.
- `CompanyPaymentSettings` is the source of truth for online payment activation and mode.
- `CompanyFinancialPolicy` is the source of truth for payout strategy, split rules, discount policy, and platform fee percent.
- `TechnicianLedgerEntry` and `CompanyPlatformFeeEntry` are immutable ledgers.

Legacy gateway models must not receive new business logic:

- `apps.platform_core.models.CompanyPaymentGatewaySetting`
- `apps.platform_core.models.PlatformPaymentGatewaySetting`

They may be read only during migration/consolidation tasks.

---

## 6. Required Start Sequence

At the beginning of every Claude Code session:

1. Read this `SKILL.md`.
2. Read `docs/README.md`.
3. Read `docs/02_AI_Operating_System/AI_AGENT_START_HERE.md`.
4. Read `docs/02_AI_Operating_System/AI_CODE_CHANGE_RULES.md`.
5. Read `docs/11_Project_Knowledge/KNOWN_CONSTRAINTS.md`.
6. Read the ADRs relevant to the task (`docs/07_ADR/`).
7. Read business and architecture documents relevant to the task.
8. Inspect related code and tests before planning.
9. Produce a plan and present it.
10. Wait for approval before implementation unless the user explicitly permits execution.

---

## 7. File Change Limit

Default maximum for one implementation task: **5 files changed**.

If more than 5 files are required, stop and ask for approval with a file-by-file reason.

Documentation-only tasks may exceed this limit only when the task explicitly asks to update documentation structure.

---

## 8. Testing Rule

Every business, payment, invoice, order, permission, or financial change requires tests.

For financial changes:

- Use real database test objects.
- Do not mock ledger services.
- Test all relevant payment modes.
- Test idempotency.
- Test tenant isolation if data access changes.

---

## 9. Migration Rule

No migration unless the task explicitly permits it.

Allowed production migrations must be additive and safe:

- Add table
- Add nullable field
- Add field with safe default
- Add index

Destructive migrations require a separate plan and approval.

---

## 10. Reporting Rule

Every task report must include:

1. Files changed
2. Files intentionally not changed
3. Migrations created or not created
4. Tests added/updated
5. Commands run
6. Test results
7. Risks
8. Out-of-scope items
9. Next recommended task

---

## 11. Freeze Status

RDOS v1.0 is the stable documentation baseline. After this freeze, architecture changes require a new ADR or an update to an existing ADR.





### Autonomous Execution

After a task has been approved by the user, Claude has authorization to:

- create files
- modify files
- create tests
- modify tests
- run tests
- run migrations (only if the task allows migrations)
- inspect code
- search the repository
- execute implementation steps

Do not ask for intermediate confirmations.

Follow:

`docs/02_AI_Operating_System/AI_SAFE_CHANGE_PROTOCOL.md`

Stop only if a documented Stop Condition is encountered.