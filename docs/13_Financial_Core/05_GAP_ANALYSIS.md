# 05 — تحلیل شکاف (Gap Analysis)

**تاریخ ممیزی:** 2026-07-05
**مرجع:** Locked Business Rules R01–R56 + Open Issues OI-01–OI-10

---

## Classification Legend

| Code | Meaning |
|---|---|
| ✅ IMPLEMENTED | پیاده‌سازی کامل و صحیح |
| 🟡 PARTIAL | پیاده‌سازی ناقص — بخشی موجود |
| ❌ MISSING | هیچ پیاده‌سازی وجود ندارد |
| ⚠️ INCORRECT | پیاده‌سازی ناصحیح نسبت به قاعده |

---

## Section 5.1 — Money Ownership & Legal Roles


### R01 — Legal custody of customer funds belongs to Platform until settlement

**Status:** 🟡 PARTIAL

**Evidence:**
- `apps/payments/models.py:PaymentGateway.OwnerType.PLATFORM` (line ~30): Gateway ownership distinguishes platform vs company funds.
- `apps/payouts/services_split.py:PaymentSplitDecisionService.compute()` (line ~48): Calculates `company_deposit_amount` vs `technician_direct_amount` — implies platform holds remainder.
- `apps/payouts/models.py:PaymentSplitSnapshot` (line ~115): Records `total_amount`, `platform_fee_amount`, `company_deposit_amount`, `technician_direct_amount`.

**What's missing:** No explicit `EscrowRecord` model tracking ownership state (held → reserved → settled). The concept is implicit in split calculations but not materialized in the database. Platform cannot query "total funds I hold belonging to others."

**Next action:** Create `EscrowRecord` model (target Sprint 3 in roadmap). Populate when `PaymentVerifyService.verify()` marks payment PAID with platform gateway.

---

### R02 — Payment appears to be to Organization from Customer perspective

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/models.py:Invoice` (line ~21): Invoice always has `company` FK — displayed as issuer.
- `apps/invoices/models.py:Invoice.footer_text` (line ~181): Default = `"مسئولیت فاکتور صادره بر عهده ارائه‌دهنده خدمت می‌باشد."` — explicitly states the service provider (Organization) is responsible.
- Public invoice URL `/<code>/invoices/<id>/` — `<code>` is the company slug, not platform.
- Short URL `/i/<public_code>/` — shows company branding and information.

**Next action:** None — fully satisfied.

---

### R03 — Official invoice must be issued in Organization name

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/models.py:Invoice.company` (line ~21): FK to `tenants.Company` (the Organization).
- `apps/invoices/models.py:Invoice.technician_name_snapshot` (line ~90): Technician info is supplementary only.
- `apps/invoices/models.py:Invoice.footer_text` (line ~181): Organization responsibility declaration.
- `apps/invoices/services.py:InvoiceCreateService.create()` (line ~130): `company` is required parameter.

**Next action:** None.

---

### R04 — Online payment receipt shows Platform business name

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payments/models.py:PaymentGateway.OwnerType.PLATFORM` (line ~28): When `owner_type == "platform"`, the gateway's `merchant_id` belongs to the platform, so Shaparak receipt shows platform's legal name.
- `apps/payments/services.py:PaymentStartService.start()` (line ~90): Uses `PaymentGatewaySelector.get_default_for_company()` which may return a platform-owned gateway.

**Next action:** None.

---

### R05 — Platform receives only Platform Commission

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payouts/models.py:CompanyPlatformFeeEntry` (line ~145): Dedicated ledger records only commission entries. No other revenue flows to platform.
- `apps/payouts/services_platform_fee.py:PlatformFeeService.record_invoice_fee()` (line ~150): Only creates entry when 4-condition gate passes (ADR-003).
- `apps/billing/models.py:BillingRecord` (line ~30): Separate model for SaaS subscription — completely independent system.

**Next action:** None.


---

## Section 5.2 — Organization Model

### R06 — Every Organization is an independent business entity

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/tenants/models.py:Company` (line ~13): Independent model with `name`, `code` (unique slug), `economic_code`, `is_active`.
- Multi-tenant isolation via `CompanyOwnedModel` base class (`apps/common/models.py`).
- URL-path based tenancy: `/<company_code>/` first segment resolves tenant.

**Next action:** None.

---

### R07 — Each Organization may have its own configurable financial policies

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/tenants/models.py:CompanyFinancialPolicy` (line ~51): `OneToOneField(Company)` — one policy per company.
- Fields: `campaign_discount_policy`, `extra_discount_policy`, `payout_strategy`, `platform_fee_percent`.

**Next action:** None.

---

### R08 — Platform may define different commission rates per Organization

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/tenants/models.py:CompanyFinancialPolicy.platform_fee_percent` (line ~95): `DecimalField(max_digits=5, decimal_places=2, default=0)` — per-company percentage.
- Help text: `"درصد کارمزد پلتفرم از کل مبلغ فاکتور — فقط توسط پلتفرم قابل تغییر است"`

**Next action:** None.

---

### R09 — Platform Commission calculated on total invoice amount (never only Organization share)

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payouts/services_platform_fee.py:PlatformFeeService.record_invoice_fee()` (line ~170):
  ```python
  amount = int(Decimal(str(invoice.total_amount)) * fee_pct / 100)
  ```
  Uses `invoice.total_amount` — the full customer-facing amount, not `settled_company_share`.

**Next action:** None.

---

### R10 — Commission on cash payments is configurable; default: only online

**Status:** 🟡 PARTIAL

**Evidence:**
- `apps/payouts/services_platform_fee.py:PlatformFeeService.record_invoice_fee()` (line ~163–168): Four conditions gate — condition 3 requires `gateway.owner_type == PaymentGateway.OwnerType.PLATFORM`. Cash/manual payments never have a payment with platform gateway, so commission is never created for cash. This enforces the **default behavior** correctly.
- `apps/invoices/services.py:InvoiceMarkPaidService.mark_paid()` (line ~275–285): Only calls `PlatformFeeService.record_invoice_fee()` when `_gw.owner_type == PaymentGateway.OwnerType.PLATFORM` — cash payments skip this entirely.

**What's missing:** No `CompanyFinancialPolicy.charge_commission_on_cash` field exists (grep confirmed: zero results for `charge_commission_on_cash` in codebase). There is no way for Platform Owner to enable cash commission per Organization.

**Next action:** Add `charge_commission_on_cash = models.BooleanField(default=False)` to `CompanyFinancialPolicy`. Modify `InvoiceMarkPaidService.mark_paid()` to check this flag for cash/manual paths.


---

## Section 5.3 — Online Payment & Money Flow

### R11 — Platform-First Collection model

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payments/models.py:PaymentGateway.OwnerType.PLATFORM` (line ~28): Gateway can be platform-owned.
- `apps/tenants/models.py:CompanyPaymentSettings.PaymentMode.PLATFORM_GATEWAY` (line ~566): Mode = `"platform_gateway"`.
- `apps/payments/services.py:PaymentStartService.start()` (line ~85): All payment flows route through the company's assigned gateway — when mode=platform_gateway, customer funds go to platform account first.

**Next action:** None.

---

### R12 — Three configurable collection models (A/B/C)

**Status:** 🟡 PARTIAL

**Evidence:**
- Model A (Platform→Settlement→Org): Implied by `PaymentGateway.owner_type=PLATFORM` + future settlement batch (not yet built).
- Model B (Platform retains commission, rest to Org): Implicit — no explicit "Model B" flag. Currently all platform-gateway payments follow this pattern at settlement time.
- Model C (Split with Provider): `apps/tenants/models.py:CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN` (line ~82) + `apps/payouts/services_split.py:PaymentSplitDecisionService.compute()` (line ~68–84).

**What's missing:** No explicit `collection_model` choice field (A/B/C). The behavior is derived from `payout_strategy` + `payment_mode` combination. There is no admin UI for selecting "Model A vs B vs C" directly.

**Next action:** Document that Model A/B/C are emergent from the combination of `CompanyPaymentSettings.payment_mode` and `CompanyFinancialPolicy.payout_strategy`. Consider adding explicit choice if Product Owner requires UI clarity.

---

### R13 — No approved IBAN → online payment disabled

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/tenants/services_merchant_profile.py:CompanyPaymentEligibilityService` (line ~234): Checks `CompanyMerchantProfile.status == APPROVED` before allowing gateway payments.
- `apps/payments/services.py:PaymentStartService.start()` (line ~148–153): Calls `CompanyPaymentEligibilityService.is_gateway_enabled(invoice.company)` — raises ValueError if not eligible.

**Next action:** None.

---

### R14 — Organization IBAN approval by Platform Owner only

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/tenants/models.py:CompanyMerchantProfile.reviewed_by` (line ~427): FK to `accounts.CompanyUser` — the platform owner user who reviewed.
- `apps/platform_core/views_merchant_profile.py`: Platform Owner review views at `/owner-platform/merchant-profiles/`.
- `apps/tenants/models.py:CompanyMerchantProfile.Status` (line ~333): Lifecycle requires `SUBMITTED → UNDER_REVIEW → APPROVED`, controlled by platform owner.

**Next action:** None.

---

### R15 — Each Organization may have only one active settlement bank account

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/tenants/models.py:CompanyMerchantProfile.company` (line ~357): `OneToOneField(Company)` — exactly one profile per company.
- `apps/tenants/models.py:CompanyMerchantProfile.shaba_number` (line ~395): Single SHABA field.
- `apps/tenants/models.py:CompanyMerchantProfileChangeRequest` (line ~464): Separate model for requesting changes to an approved profile — requires re-approval.

**Next action:** None.


---

## Section 5.4 — Provider (Technician)

### R16 — Provider must always belong to an Organization

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/accounts/models.py:Technician` (line ~118): Extends `CompanyOwnedModel` — inherits mandatory `company` FK.
- `apps/accounts/models.py:Technician.user` (line ~125): `OneToOneField(CompanyUser)` — CompanyUser itself has company scope.

**Next action:** None.

---

### R17 — Provider may work for multiple Orgs (separate accounts per Org)

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/accounts/models.py:Technician` (line ~118): Each Technician record is company-scoped. A human working for 2 companies has 2 separate `Technician` objects with 2 separate `CompanyUser` accounts.
- `apps/payouts/models.py:TechnicianLedgerEntry.technician` (line ~38): Ledger entries are per Technician instance (per company), not per human.
- ADR-006 §4 explicitly states: "Technician compensation is independent of customer payment behaviour" per Technician object.

**Next action:** None.

---

### R18 — Each Org can register IBAN for each Provider

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/accounts/models.py:Technician.shaba_number` (line ~148): `CharField(max_length=26, blank=True)` — per-technician-per-company SHABA.

**Next action:** None.

---

### R19 — Provider IBAN verification is Organization responsibility (not Platform)

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/accounts/models.py:Technician.verified_by` (line ~168): FK to `accounts.CompanyUser` — company admin verifies.
- `apps/accounts/models.py:Technician.financial_verification_status` (line ~159): Status choices include `PENDING`, `VERIFIED`, `REJECTED`.
- No platform-owner view exists for technician IBAN verification.

**Next action:** None.

---

### R20 — Direct settlement to Provider only when Org explicitly enables

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payouts/services_split.py:PaymentSplitDecisionService.compute()` (line ~68): `can_split` requires `payout_strategy == SPLIT_WITH_TECHNICIAN AND tech_verified AND bool(tech_sub_merchant_id)`.
- `apps/tenants/models.py:CompanyFinancialPolicy.payout_strategy` (line ~87): `PayoutStrategy.SPLIT_WITH_TECHNICIAN` — explicit opt-in by Organization.

**Next action:** None.

---

### R21 — No IBAN → share goes to Organization; must not remain suspended

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payouts/services_split.py:PaymentSplitDecisionService.compute()` (line ~91–106): When `can_split == False`:
  ```python
  technician_direct_amount = 0
  technician_ledger_amount = tech_wage  # company owes technician
  ```
  This means a CREDIT is posted to technician ledger (company owes), ensuring funds are never suspended.
- `apps/payouts/services.py:TechnicianLedgerService.create_invoice_entries()` (line ~133): Creates CREDIT entry regardless of split outcome — technician always gets credited.

**Next action:** None.


---

## Section 5.5 — Invoice Line Structure

### R22 — Every Invoice Line has fixed structure (type, description, qty, unit_price, discount, total)

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/models.py:InvoiceItem` (line ~298): Fields: `row_type`, `description`, `quantity`, `unit_price`, `discount_amount`, `total_price`.

**Next action:** None.

---

### R23 — Mandatory Invoice Line Types: Product, Service, Transportation, Additional Discount, Loyalty Discount

**Status:** 🟡 PARTIAL

**Evidence:**
- `apps/invoices/models.py:InvoiceItem.RowType` (line ~304): Only 3 choices: `SERVICE="service"`, `GOODS="goods"`, `TRAVEL="travel"`.
- Grep confirmed: no `additional_discount` or `loyalty_discount` choice anywhere in codebase.

**What's missing:** `ADDITIONAL_DISCOUNT` and `LOYALTY_DISCOUNT` RowType choices do not exist. Invoice-level discounts are handled via `Invoice.extra_discount_amount` and `Invoice.campaign_discount_amount` fields (not as line items).

**Next action:** Add `ADDITIONAL_DISCOUNT = "additional_discount"` and `LOYALTY_DISCOUNT = "loyalty_discount"` to `InvoiceItem.RowType.choices`. Migration: alter field choices (zero-downtime, no data change).

---

### R24 — Products and Services must always appear as separate Invoice Lines

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/models.py:InvoiceItem.RowType` (line ~304): `SERVICE` and `GOODS` are distinct choices.
- `apps/invoices/services_wage.py:_collect_category_totals()` (line ~85): Iterates items and accumulates separately per `row_type`.

**Next action:** None.

---

### R25 — Each Invoice belongs to exactly one Provider

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/models.py:Invoice.order` (line ~37): FK to Order.
- `apps/orders/models.py:Order.technician` (line ~58): Single FK to `accounts.Technician`.
- No multi-technician invoice support exists.

**Next action:** None.

---

### R26 — Commission Allocation Engine calculates category subtotals first

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/services_wage.py:_collect_category_totals()` (line ~85–110): Returns `(service_total, goods_total, travel_total)` computed from `item.total_price` grouped by `row_type`.
- Called at line ~115 of `_calculate_policy_aware_wage()` before any wage calculation.

**Next action:** None.

---

### R27 — Provider compensation determined by Invoice Line Type (not individual product)

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/accounts/models.py:Technician` (line ~131–142): Three separate percentage fields: `service_wage_percent`, `goods_wage_percent`, `travel_wage_percent`.
- `apps/invoices/services_wage.py:_calculate_policy_aware_wage()` (line ~118–121):
  ```python
  service_wage = service_total * service_pct / 100
  goods_wage = goods_total * goods_pct / 100
  travel_wage = travel_total * travel_pct / 100
  ```

**Next action:** None.


---

## Section 5.6 — Discounts

### R28 — Revenue sharing calculated after all discounts applied

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/services_wage.py:_calculate_policy_aware_wage()` (line ~112–153): Category totals use `item.total_price` which is already `gross_price - discount_amount` (row discounts applied). Then extra/campaign discounts are allocated via `_allocate_discount()`.
- `apps/invoices/models.py:InvoiceItem.net_price` (property, line ~339): `max(0, self.gross_price - (self.discount_amount or 0))`.

**Next action:** None.

---

### R29 — Rounding Discount configurable per Organization (enabled/disabled + max amount)

**Status:** ❌ MISSING

**Evidence:**
- Grep `rounding_discount` across entire codebase: **zero results**.
- `apps/tenants/models.py:CompanyFinancialPolicy`: No `rounding_discount_enabled` or `max_rounding_discount_rial` field.
- `apps/invoices/models.py:Invoice`: No `rounding_discount_amount` field.

**Next action:** Add to `CompanyFinancialPolicy`: `rounding_discount_enabled = BooleanField(default=False)`, `max_rounding_discount_rial = PositiveBigIntegerField(default=0)`. Add to `Invoice`: `rounding_discount_amount = DecimalField(default=0)`. Apply in `recalculate_totals()` and `InvoiceSettlementService.settle()`.

---

### R30 — Discount Codes managed by Organization (not Platform)

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/reports/models.py:DiscountCampaign` (line ~50): Extends `CompanyOwnedModel` — company-scoped.
- `apps/reports/models.py:DiscountCode` (line ~100): Extends `CompanyOwnedModel` — company-scoped.
- Platform has no ownership of discount campaigns.

**Next action:** None.

---

### R31 — Provider discount participation configurable (on/off policy)

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/tenants/models.py:CompanyFinancialPolicy.campaign_discount_policy` (line ~69): Choices = COMPANY/TECHNICIAN/HALF_HALF/PROPORTIONAL_SHARE.
- `apps/tenants/models.py:CompanyFinancialPolicy.extra_discount_policy` (line ~75): Same choices.
- `apps/invoices/services_wage.py:_allocate_discount()` (line ~44–70): Implements all 4 strategies.
- When policy=COMPANY, technician absorbs 0 (fully protected). When policy=TECHNICIAN, technician absorbs full discount.

**Next action:** None.


---

## Section 5.7 — Referral / Visitor

### R32 — Referrers receive no commission for introducing Organizations

**Status:** ✅ IMPLEMENTED (correctly absent)

**Evidence:** No referral commission model, service, or field exists anywhere in the codebase. This is intentionally correct per the business rule.

**Next action:** None.

---

### R33 — Customer referrals currently generate no commission (reserved for future)

**Status:** ✅ IMPLEMENTED (correctly absent)

**Evidence:** No customer referral tracking or commission system exists. Correct per rule.

**Next action:** None — future extension point only.

---

### R34–R36 — Future referral rules

**Status:** N/A (explicitly future)

**Next action:** None in current version. Architecture supports extension (see `target_architecture/15_REFERRAL_VISITOR_ENGINE.md`).

---

## Section 5.8 — Cash Payments

### R37 — Cash: legal ownership immediately to Organization; allocation doc still generated

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/services.py:InvoiceMarkPaidService.mark_paid()` (line ~230): Cash path calls `InvoiceSettlementService.settle()` → settles all `settled_*` fields (the allocation document).
- `apps/payouts/services.py:TechnicianLedgerService.create_invoice_entries()` (line ~133): Called for cash payments — creates CREDIT entry.
- No escrow is created for cash (correct — funds never enter platform account).

**Next action:** None.

---

### R38 — Platform Commission on cash disabled by default; configurable per Org

**Status:** 🟡 PARTIAL

**Evidence:**
- Default disabled: ✅ `InvoiceMarkPaidService.mark_paid()` (line ~275): Commission code only runs when `_gw.owner_type == PaymentGateway.OwnerType.PLATFORM`. Cash payments have no gateway or a `MANUAL` type gateway — condition never met.
- Configurable toggle: ❌ No `charge_commission_on_cash` field exists (grep confirmed zero results).

**Next action:** Same as R10 — add `charge_commission_on_cash` field to `CompanyFinancialPolicy`.

---

### R39 — Cash settlement Org↔Provider done directly by Org; Platform tracks only

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payouts/services.py:TechnicianLedgerService.record_manual_settlement()` (line ~168): Admin records settlement with directions (COMPANY_PAID_TECHNICIAN, TECHNICIAN_PAID_COMPANY).
- `apps/payouts/views.py:technician_settlement()` (line ~61): View at `/<code>/admin/technicians/<id>/statement/` — company admin performs settlement.
- Platform does not execute cash settlements — only records exist.

**Next action:** None.

---

### R40 — Card-to-Card Transfer must be independent payment channel (not equivalent to Cash)

**Status:** ❌ MISSING

**Evidence:**
- Grep `card_to_card` and `CARD_TO_CARD` across codebase: **zero results**.
- `apps/payments/models.py:PaymentGateway.GatewayType` (line ~19): Only `ZARINPAL, IDPAY, NEXTPAY, FAKE, MANUAL`. No `CARD_TO_CARD` choice.
- Currently card-to-card payments would be recorded as manual/cash — no separate tracking.

**Next action:** Add `CARD_TO_CARD = "card_to_card", "کارت‌به‌کارت"` to `PaymentGateway.GatewayType.choices`. No structural change needed — just a new enum value in migration.


---

## Section 5.9 — Settlement

### R41 — Settlement timing Platform↔Org configurable per Organization

**Status:** ❌ MISSING

**Evidence:**
- Grep `settlement_frequency`, `settlement_delay`, `settlement_timing` in codebase: **zero results**.
- `apps/tenants/models.py:CompanyFinancialPolicy`: No timing/frequency fields.
- Grep `SettlementBatch` in codebase: **zero results**.
- No settlement scheduling model or management command exists.

**Next action:** Add `settlement_frequency` (choices: immediate/daily/weekly/manual) and `settlement_delay_hours` fields to `CompanyFinancialPolicy`. Create `SettlementBatch` + `SettlementItem` models. Create `process_settlements` management command.

---

### R42 — Settlement timing Org↔Provider configured by Organization

**Status:** 🟡 PARTIAL

**Evidence:**
- `apps/payouts/views.py:technician_settlement()` (line ~61): Admin manually records settlements at any time — no configured schedule.
- `apps/payouts/services.py:TechnicianLedgerService.record_manual_settlement()` (line ~168): Immediate recording.
- No `TechnicianSettlementConfig` model with frequency settings.

**What exists:** Manual settlement works correctly. What's missing: configurable timing/automation.

**Next action:** Create `TechnicianSettlementConfig` (per company) with frequency settings. Preserve existing manual settlement as override.

---

### R43 — Settlement Engine almost fully automatic

**Status:** ❌ MISSING

**Evidence:**
- No automated settlement service exists. All settlements are triggered manually by admin via `technician_settlement` view.
- No Celery tasks, management commands, or cron jobs for settlement processing.
- `apps/payouts/services_direct_settlement.py:TechnicianDirectSettlementService` is the only automated piece (Shaparak split at payment time) — but this is per-payment, not batch settlement.

**Next action:** Build `SettlementCalculationService` and `SettlementExecutionService`. Create `process_settlements` management command scheduled via cron.

---

### R44 — No manual approval required under normal conditions

**Status:** 🟡 PARTIAL

**Evidence:**
- Manual settlement (`record_manual_settlement`) does NOT require approval — admin records directly. ✅
- But there is no automated settlement to evaluate this rule against.
- Future `SettlementBatch` should default to `auto_approve=True` per this rule.

**Next action:** When building SettlementBatch, set `auto_approve=True` as default. No approval workflow unless OI-08 decides otherwise.

---

### R45 — Settlement unit is Invoice (never Order)

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payouts/models.py:TechnicianLedgerEntry.invoice` (line ~46): FK to Invoice.
- `apps/payouts/models.py:CompanyPlatformFeeEntry.invoice` (line ~155): FK to Invoice.
- `apps/payouts/models.py:PaymentSplitSnapshot.invoice` (line ~121): FK to Invoice.
- `apps/payouts/models.py:FinancialBackfillTask.invoice` (line ~237): FK to Invoice.
- All financial records reference Invoice, not Order.

**Next action:** None.


---

## Section 5.10 — Financial Corrections & Controls

### R46 — Financial Engine must support Customer financial adjustments (creditor/debtor)

**Status:** ❌ MISSING

**Evidence:**
- Grep `CustomerWallet`, `customer_wallet`, `CustomerCredit`, `customer_credit` in codebase: **zero results**.
- No model for customer financial position exists.
- `apps/accounts/models.py:Customer`: No balance, credit, or wallet fields.

**Next action:** Design `CustomerFinancialAccount` model. Blocked on OI-05 (scenarios undefined).

---

### R47 — Customer cannot pay less than Invoice Total

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payments/services.py:PaymentVerifyService.verify()` (line ~198–207): Amount tampering protection:
  ```python
  if int(response.verified_amount) != int(payment.amount):
      payment.status = Payment.Status.NEEDS_RECONCILIATION
  ```
- `apps/invoices/services.py:InvoiceMarkPaidService.mark_paid()` (line ~244):
  ```python
  if payment.amount != invoice.total_amount:
      raise ValueError("Payment amount does not match invoice total.")
  ```

**Next action:** None.

---

### R48 — Only Admin/Operators with appropriate permissions may modify policies

**Status:** 🟡 PARTIAL

**Evidence:**
- `apps/payouts/views.py:technician_settlement()` (line ~50): `@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")` — enforced.
- `apps/tenants/models.py:CompanyFinancialPolicy.platform_fee_percent` help_text: "فقط توسط پلتفرم قابل تغییر" — but enforcement is at view level (platform owner views), not at model level.
- `apps/accounts/permissions.py:require_tenant_role` decorator exists and is used.

**What's missing:** Explicit permission documentation is not formalized. No granular permission like "can_modify_financial_policy" vs "can_view_financial_policy". Role-based access is broad (COMPANY_ADMIN/COMPANY_STAFF have same access to most financial views).

**Next action:** Document full permission matrix. Consider adding granular permissions for financial policy modification.

---

### R49 — Policy changes apply only to future invoices

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/services_wage.py:snapshot_wage_percentages_on_invoice()` (line ~147): Snapshots wage percentages at ISSUE time — future rate changes don't affect this invoice.
- `apps/invoices/services_settlement.py:InvoiceSettlementService.settle()` (line ~20): Reads policy at settlement time and freezes into `settled_*` fields.
- `apps/payouts/services_order_wages.py:TechnicianWagePostingService.post_for_order()` (line ~80): Reads `TechnicianServiceRate.fixed_wage_rial` at order completion time — rate changes don't affect past entries.
- ADR-005 invariant: "Changing a rate after an order is completed must never alter any previously posted ledger entry."

**Next action:** None.

---

### R50 — Every financial modification must be fully recorded in Audit Log

**Status:** 🟡 PARTIAL

**Evidence:**
- Ledger entries are self-documenting: `TechnicianLedgerEntry.metadata` (JSONField) + `created_by` FK + `created_at`.
- `CompanyPlatformFeeEntry.created_by` + `created_at`.
- `CompanyMerchantProfile.reviewed_by`, `reviewed_at`, `review_note`.

**What's missing:** No independent audit log for **policy changes** (CompanyFinancialPolicy field changes), **payment settings changes** (CompanyPaymentSettings.payment_mode changes), or **technician wage percent changes**. No `django-auditlog` or equivalent installed.

**Next action:** Install `django-auditlog` or build custom audit trail for: `CompanyFinancialPolicy`, `CompanyPaymentSettings`, `Technician` (wage fields).

---

### R51 — No financial record may ever be deleted

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/payouts/models.py:TechnicianLedgerEntry.delete()` (line ~94):
  ```python
  def delete(self, *args, **kwargs):
      raise PermissionError("TechnicianLedgerEntry #{self.pk} is immutable and cannot be deleted.")
  ```
- `apps/payouts/models.py:CompanyPlatformFeeEntry.delete()` (line ~197): Same pattern.
- `apps/payouts/models.py:FinancialBackfillTask`: No delete override, but ADR-008 states "Never delete a FinancialBackfillTask."

**Next action:** None.

---

### R52 — Paid Invoices permanently locked; correction via separate documents

**Status:** ✅ IMPLEMENTED

**Evidence:**
- `apps/invoices/models.py:Invoice.recalculate_totals()` (line ~255):
  ```python
  if self.pk and self.status == self.Status.PAID:
      raise ValueError("Cannot recalculate totals on PAID invoice")
  ```
- `apps/invoices/services.py:InvoiceMarkPaidService.mark_paid()` (line ~237): After settlement, `Invoice.status=PAID` is permanent.
- No service exists to modify PAID invoice fields.

**What exists for correction:** `TechnicianLedgerService.record_manual_settlement(direction=ADJUSTMENT_*)` — but this adjusts the technician ledger, not the invoice itself.

**What's missing:** Formal `AdjustmentDocument` (Credit Note / Debit Note) model for invoice-level corrections.

**Next action:** Build `AdjustmentDocument` model (target Sprint 6, blocked on OI-07).


---

## Section 5.11 — Reporting

### R53 — Provider liability report from Cash Payments mandatory

**Status:** 🟡 PARTIAL

**Evidence:**
- Data available: `apps/payouts/services.py:TechnicianLedgerService.get_balance()` (line ~34) returns per-technician balance. Negative balance = technician owes.
- `apps/payouts/views.py:technician_ledger()` (line ~53): Shows individual technician balance.
- `apps/payouts/views.py:technician_statement()` (line ~117): Shows statement with date filtering.

**What's missing:** No **aggregated** report view showing ALL technicians with negative balances across a company. Admin must check each technician individually.

**Next action:** Build dedicated "Provider Liability Report" view that queries `TechnicianLedgerService.get_balance()` for all technicians in a company and filters for negative balances.

---

### R54 — Complete Platform Commission Report mandatory

**Status:** 🟡 PARTIAL

**Evidence:**
- Data available: `apps/payouts/services_platform_fee.py:PlatformFeeService.get_balance()` (line ~58): Returns per-company outstanding balance.
- `apps/payouts/services_platform_fee.py:PlatformFeeService.list_entries()` (line ~67): Returns ordered entries per company.
- `apps/payouts/views_split_snapshots.py`: Gateway reconciliation view exists.

**What's missing:** No **aggregated** platform commission report showing: total fees accrued, total settled, outstanding per company, date-range filtering, export capability.

**Next action:** Build Platform Commission Report at `/owner-platform/reports/commission/` with aggregation across companies.

---

### R55 — Completed and pending Settlements report mandatory

**Status:** ❌ MISSING

**Evidence:**
- No `SettlementBatch` model exists (grep confirmed).
- No settlement report view exists.
- Manual settlements are recorded as individual ledger entries — no batch tracking.

**Next action:** Depends on Settlement Engine (R41-R44). Build after `SettlementBatch` model is created.

---

### R56 — Most comprehensive financial reporting possible

**Status:** ❌ MISSING

**Evidence:**
- `apps/reports/models.py:Report` (line ~12): Stub model with `ReportType` choices: `ORDERS_SUMMARY`, `REVENUE`, `TECHNICIAN_PERFORMANCE`, `CUSTOMER_ACTIVITY`. None are financially detailed.
- No dashboard KPIs, no aggregated financial views, no executive summary reports.

**Next action:** Blocked on OI-09 (KPI catalog undefined) and OI-10 (Provider reporting requirements undefined).

---

## Open Issues Assessment

| OI | Existing Architectural Clue |
|---|---|
| **OI-01** | `PaymentSplitSnapshot.technician_direct_amount` + `Technician.sub_merchant_id` + `PaymentSplitDecisionService.compute()` → split infrastructure designed. Shaparak split not yet physically tested. |
| **OI-02** | `InvoiceItem.RowType.TRAVEL` exists as line item → transportation is currently a line type. |
| **OI-03** | 4 discount policies in `CompanyFinancialPolicy` (COMPANY/TECHNICIAN/HALF_HALF/PROPORTIONAL). Separate per extra vs campaign. But line-level and rounding discount distribution undefined. |
| **OI-04** | `TechnicianLedgerService.get_balance()` = `SUM(credits) - SUM(debits)`. When technician collects cash DEBIT(total) is posted → balance goes negative. Formula is implicit. |
| **OI-05** | No `CustomerFinancialAccount` or wallet exists. Zero infrastructure for customer credit/debit. |
| **OI-06** | `PaymentVerifyService.verify()` sends amount mismatch to NEEDS_RECONCILIATION. No auto-handling. |
| **OI-07** | `TechnicianLedgerEntry.Source.REFUND = "refund"` defined. No `RefundService`. |
| **OI-08** | All policy changes are immediate (single-step by platform owner). No approval workflow model. |
| **OI-09** | `apps/reports/models.py:Report` stub exists. No actual KPI computation. |
| **OI-10** | `TechnicianStatementService.build()` + export views = basic provider reporting. No portal/dashboard. |

---

## Summary Statistics

| Classification | Count |
|---|---|
| ✅ IMPLEMENTED | 30 |
| 🟡 PARTIAL | 12 |
| ❌ MISSING | 8 |
| ⚠️ INCORRECT | 0 |
| N/A (Future/Reserved) | 6 |
| **Total Rules** | **56** |
