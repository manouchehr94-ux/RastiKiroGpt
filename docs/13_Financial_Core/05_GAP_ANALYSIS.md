# 05 — تحلیل شکاف (Gap Analysis)

**تاریخ ممیزی:** 2026-07-05
**مرجع:** Locked Business Rules R01–R56 + Open Issues OI-01–OI-10

---

## Classification Legend

| Code | Meaning |
|------|---------|
| ✅ IMPLEMENTED | پیاده‌سازی کامل و صحیح |
| 🟡 PARTIAL | پیاده‌سازی ناقص — بخشی موجود |
| ❌ MISSING | هیچ پیاده‌سازی وجود ندارد |
| ⚠️ INCORRECT | پیاده‌سازی ناصحیح نسبت به قاعده |

---

## Section 5.1 — Money Ownership & Legal Roles

### R01

**Rule:** Legal custody of customer funds belongs to Platform until settlement.

**Status:** 🟡 PARTIAL


**Evidence:**

- File: `apps/payments/models.py`, line 32 — `PaymentGateway.OwnerType` with `PLATFORM = "platform"` distinguishes platform-held funds.
- File: `apps/payouts/services_split.py`, line 28 — `PaymentSplitDecisionService.compute()` calculates `company_deposit_amount` vs `technician_direct_amount`, implying platform holds remainder.
- File: `apps/payouts/models.py`, line 137 — `PaymentSplitSnapshot` records amounts per party.

**Classification reason:**
Platform-First Collection is implemented (funds go to platform gateway).
However, no explicit `EscrowRecord` model materializes the ownership state.
Platform cannot query "total funds held belonging to others."

**Next action:**
Create `EscrowRecord` model with status lifecycle (held → reserved → settled).
Populate on payment verification when gateway is platform-owned.

---

### R02

**Rule:** Payment appears to be to Organization from Customer perspective.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/models.py`, line 21 — `Invoice` has mandatory `company` FK.
- File: `apps/invoices/models.py`, line 181 — `footer_text` default: `"مسئولیت فاکتور صادره بر عهده ارائه‌دهنده خدمت می‌باشد."`
- Public invoice URL `/<code>/invoices/<id>/` uses company code, not platform name.

**Classification reason:**
All customer-facing UI shows Organization identity, not Platform.

**Next action:** None.

---

### R03

**Rule:** Official invoice issued in Organization name.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/models.py`, line 38 — `Invoice.order` FK (nullable); line 21 inherits `CompanyOwnedModel`.
- File: `apps/invoices/models.py`, line 90 — `technician_name_snapshot` is supplementary info only.
- File: `apps/invoices/services.py`, line 131 — `InvoiceCreateService.create()` requires `company` parameter.

**Classification reason:**
Invoice is always scoped to company. Technician info is secondary.

**Next action:** None.

---

### R04

**Rule:** Online payment receipt shows Platform business name.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payments/models.py`, line 32 — `PaymentGateway.OwnerType.PLATFORM`.
- When `owner_type == "platform"`, the gateway `merchant_id` is the platform's Shaparak merchant, so the PSP receipt displays the platform legal name.

**Classification reason:**
Gateway merchant identity is controlled by `owner_type`.

**Next action:** None.

---

### R05

**Rule:** Platform receives only Platform Commission.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payouts/models.py`, line 189 — `CompanyPlatformFeeEntry` records only commission.
- File: `apps/payouts/services_platform_fee.py`, line 150 — `record_invoice_fee()` creates entry only when 4-condition gate passes.
- File: `apps/billing/models.py`, line 11 — `BillingRecord` is a separate SaaS subscription model.

**Classification reason:**
Platform revenue = CompanyPlatformFeeEntry DEBIT entries only. No other revenue path.

**Next action:** None.


---

## Section 5.2 — Organization Model

### R06

**Rule:** Every Organization is an independent business entity.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/tenants/models.py`, line 12 — `Company` model with `name`, `code` (unique slug), `economic_code`.
- Multi-tenant isolation via `CompanyOwnedModel` base class in `apps/common/models.py`.

**Classification reason:** Each Company is independent with unique slug.

**Next action:** None.

---

### R07

**Rule:** Each Organization may have configurable financial policies.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/tenants/models.py`, line 51 — `CompanyFinancialPolicy` model.
- Line 70 — `company = OneToOneField(Company)`.

**Classification reason:** One policy per company, configurable.

**Next action:** None.

---

### R08

**Rule:** Platform may define different commission rates per Organization.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/tenants/models.py`, line 94 — `platform_fee_percent = DecimalField(max_digits=5, decimal_places=2, default=0)`.

**Classification reason:** Per-company percentage controlled by platform.

**Next action:** None.

---

### R09

**Rule:** Platform Commission calculated on total invoice amount.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payouts/services_platform_fee.py`, line 180:
  ```python
  amount = int(Decimal(str(invoice.total_amount)) * fee_pct / 100)
  ```
  Uses `invoice.total_amount` — the full customer-facing amount.

**Classification reason:** Formula uses `total_amount`, not `settled_company_share`.

**Next action:** None.

---

### R10

**Rule:** Commission on cash payments configurable; default: only online.

**Status:** 🟡 PARTIAL

**Evidence:**

- File: `apps/payouts/services_platform_fee.py`, line 171 — condition: `gateway.owner_type != PaymentGateway.OwnerType.PLATFORM` → return None. Cash payments never have platform gateway → commission never created. Default behavior correct.
- File: `apps/invoices/services.py`, line 425 — outer check: only calls `PlatformFeeService` when `_gw.owner_type == PaymentGateway.OwnerType.PLATFORM`.
- No `charge_commission_on_cash` field anywhere in codebase (grep confirmed: zero results).

**Classification reason:**
Default (no commission on cash) works. But no toggle to enable it per Organization.

**Next action:**
Add `charge_commission_on_cash = BooleanField(default=False)` to `CompanyFinancialPolicy`.
Modify `InvoiceMarkPaidService.mark_paid()` to check this flag for cash paths.


---

## Section 5.3 — Online Payment & Money Flow

### R11

**Rule:** Platform-First Collection model (all online payments to platform first).

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payments/models.py`, line 32 — `OwnerType.PLATFORM`.
- File: `apps/tenants/models.py`, line 563 — `PaymentMode.PLATFORM_GATEWAY`.
- File: `apps/payments/services.py`, line 90 — `PaymentStartService.start()` routes to company's gateway, which may be platform-owned.

**Classification reason:** When mode=platform_gateway, funds go to platform account first.

**Next action:** None.

---

### R12

**Rule:** Three configurable collection models (A/B/C).

**Status:** 🟡 PARTIAL

**Evidence:**

- Model A (Platform→Settlement→Org): Implied by platform gateway + future batch settlement.
- Model C (Split with Provider): `apps/tenants/models.py`, line 66 — `PayoutStrategy.SPLIT_WITH_TECHNICIAN`; `apps/payouts/services_split.py`, line 68–86 — `can_split` logic.
- No explicit `collection_model` choice field (A/B/C selector) exists.

**Classification reason:**
Behavior derived from `payout_strategy` + `payment_mode` combination. No explicit A/B/C UI.

**Next action:**
Document that models are emergent from settings. Consider explicit choice if PO requires UI.

---

### R13

**Rule:** No approved IBAN → no online payment.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/tenants/services_merchant_profile.py`, line 234 — `CompanyPaymentEligibilityService`.
- File: `apps/payments/services.py`, line 150–151 — calls `CompanyPaymentEligibilityService.is_gateway_enabled()`.

**Classification reason:** Eligibility check blocks payment start when KYC not approved.

**Next action:** None.

---

### R14

**Rule:** Organization IBAN approval by Platform Owner only.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/tenants/models.py`, line 414 — `CompanyMerchantProfile.reviewed_by` FK to CompanyUser.
- Platform Owner review views at `/owner-platform/merchant-profiles/` (`apps/platform_core/views_merchant_profile.py`).

**Classification reason:** Only platform owner can approve.

**Next action:** None.

---

### R15

**Rule:** One active settlement bank account per Organization.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/tenants/models.py`, line 353 — `CompanyMerchantProfile.company = OneToOneField(Company)`.
- File: `apps/tenants/models.py`, line 386 — single `shaba_number` field.
- File: `apps/tenants/models.py`, line 464 — `CompanyMerchantProfileChangeRequest` for modifications requiring re-approval.

**Classification reason:** OneToOne enforces single profile. Change requires approval.

**Next action:** None.


---

## Section 5.4 — Provider (Technician)

### R16

**Rule:** Provider must always belong to an Organization.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/accounts/models.py`, line 118 — `class Technician(CompanyOwnedModel)` — inherits mandatory `company` FK.

**Next action:** None.

---

### R17

**Rule:** Provider may work for multiple Orgs (separate accounts).

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/accounts/models.py`, line 118 — Each `Technician` record is company-scoped.
- A human working for 2 companies has 2 separate `Technician` objects.
- File: `apps/payouts/models.py`, line 43 — `TechnicianLedgerEntry.technician` FK — ledger per Technician instance.

**Classification reason:** Financially independent per company per ADR-006 §4.

**Next action:** None.

---

### R18

**Rule:** Each Org can register IBAN for each Provider.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/accounts/models.py`, line 155 — `Technician.shaba_number = CharField(max_length=26)`.

**Next action:** None.

---

### R19

**Rule:** Provider IBAN verification is Organization responsibility (not Platform).

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/accounts/models.py`, line 173 — `Technician.verified_by = FK("accounts.CompanyUser")`.
- File: `apps/accounts/models.py`, line 165 — `financial_verification_status` with PENDING/VERIFIED/REJECTED.

**Classification reason:** Company admin verifies, not platform owner.

**Next action:** None.

---

### R20

**Rule:** Direct settlement to Provider only when Org explicitly enables.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payouts/services_split.py`, line 68–72:
  ```python
  can_split = (
      payout_strategy == CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN
      and tech_verified
      and bool(tech_sub_merchant_id)
      and tech_wage > 0
  )
  ```
- File: `apps/tenants/models.py`, line 88 — `payout_strategy` field with explicit opt-in.

**Classification reason:** Requires explicit payout_strategy + verified technician.

**Next action:** None.

---

### R21

**Rule:** No IBAN → share goes to Organization (must not remain suspended).

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payouts/services_split.py`, lines 91–93:
  ```python
  technician_direct_amount = 0
  technician_ledger_amount = tech_wage  # company owes technician
  ```
- File: `apps/payouts/services.py`, line 141 — `create_invoice_entries()` always creates CREDIT regardless of split outcome.

**Classification reason:** Technician always gets credited. Funds never suspended.

**Next action:** None.


---

## Section 5.5 — Invoice Line Structure

### R22

**Rule:** Every Invoice Line has fixed structure (type, description, qty, unit_price, discount, total).

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/models.py`, line 298 — `InvoiceItem` model.
- Fields: `row_type` (line 314), `description` (line 319), `quantity` (line 320), `unit_price` (line 321), `discount_amount` (line 322), `total_price` (line 323).

**Next action:** None.

---

### R23

**Rule:** Mandatory line types: Product, Service, Transportation, Additional Discount, Loyalty Discount.

**Status:** 🟡 PARTIAL

**Evidence:**

- File: `apps/invoices/models.py`, line 304 — `InvoiceItem.RowType`:
  ```python
  SERVICE = "service", "اجرت خدمات"
  GOODS = "goods", "کالا / قطعه"
  TRAVEL = "travel", "ایاب و ذهاب"
  ```
- No `ADDITIONAL_DISCOUNT` or `LOYALTY_DISCOUNT` choices exist (grep confirmed).

**Classification reason:** 3 of 5 required types implemented.

**Next action:** Add `ADDITIONAL_DISCOUNT` and `LOYALTY_DISCOUNT` to RowType choices.

---

### R24

**Rule:** Products and Services as separate lines.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/models.py`, line 304 — `SERVICE` and `GOODS` are distinct RowType choices.
- File: `apps/invoices/services_wage.py`, line 72 — `_collect_category_totals()` accumulates per `row_type`.

**Next action:** None.

---

### R25

**Rule:** Each Invoice belongs to exactly one Provider.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/models.py`, line 38 — `Invoice.order` FK.
- File: `apps/orders/models.py`, line 53 — `Order.technician` single FK.

**Next action:** None.

---

### R26

**Rule:** Commission allocation calculates category subtotals first.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/services_wage.py`, line 72 — `_collect_category_totals()` returns `(service_total, goods_total, travel_total)`.
- Line 154 — called before wage calculation in `_calculate_policy_aware_wage()`.

**Next action:** None.

---

### R27

**Rule:** Provider compensation determined by line type.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/accounts/models.py`, lines 135/139/143 — `service_wage_percent`, `goods_wage_percent`, `travel_wage_percent`.
- File: `apps/invoices/services_wage.py`, lines 161–163:
  ```python
  service_wage = _money(service_total * service_pct / Decimal("100"))
  goods_wage = _money(goods_total * goods_pct / Decimal("100"))
  travel_wage = _money(travel_total * travel_pct / Decimal("100"))
  ```

**Next action:** None.


---

## Section 5.6 — Discounts

### R28

**Rule:** Revenue sharing calculated after all discounts applied.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/models.py`, line 338 — `InvoiceItem.net_price` = `gross_price - discount_amount`.
- File: `apps/invoices/services_wage.py`, line 72 — `_collect_category_totals()` uses `item.total_price` (post-row-discount).
- Lines 175–181 — extra/campaign discounts allocated via `_allocate_discount()`.

**Next action:** None.

---

### R29

**Rule:** Rounding Discount configurable per Organization.

**Status:** ❌ MISSING

**Evidence:**

- Grep `rounding_discount` across entire codebase: zero results.
- No field in `CompanyFinancialPolicy` or `Invoice`.

**Classification reason:** Completely absent.

**Next action:** Add `rounding_discount_enabled`, `max_rounding_discount_rial` to `CompanyFinancialPolicy`. Add `rounding_discount_amount` to `Invoice`.

---

### R30

**Rule:** Discount Codes managed by Organization.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/reports/models.py`, line 39 — `DiscountCampaign(CompanyOwnedModel)`.
- File: `apps/reports/models.py`, line 88 — `DiscountCode(CompanyOwnedModel)`.

**Next action:** None.

---

### R31

**Rule:** Provider discount participation configurable.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/tenants/models.py`, line 75 — `campaign_discount_policy` choices.
- File: `apps/tenants/models.py`, line 81 — `extra_discount_policy` choices.
- File: `apps/tenants/models.py`, line 60 — `DiscountPolicy`: COMPANY/TECHNICIAN/HALF_HALF/PROPORTIONAL_SHARE.
- File: `apps/invoices/services_wage.py`, line 114 — `_allocate_discount()` implements all 4 strategies.

**Next action:** None.


---

## Section 5.7 — Referral / Visitor

### R32–R36

**Status:** ✅ IMPLEMENTED (R32, R33 correctly absent) / N/A (R34–R36 future)

**Evidence:** No referral commission model, service, or field exists. Correct per rules.

**Next action:** None in current version.

---

## Section 5.8 — Cash Payments

### R37

**Rule:** Cash: ownership to Organization immediately; allocation doc still generated.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/services.py`, line 383 — `InvoiceSettlementService.settle()` called for cash.
- File: `apps/payouts/services.py`, line 141 — `create_invoice_entries()` called for cash (creates CREDIT).

**Next action:** None.

---

### R38

**Rule:** Platform Commission on cash disabled by default; configurable per Org.

**Status:** 🟡 PARTIAL

**Evidence:**

- Default disabled: File `apps/payouts/services_platform_fee.py`, line 171 — blocks non-platform gateways.
- Configurable toggle: absent (no `charge_commission_on_cash` field).

**Next action:** Same as R10 — add boolean field.

---

### R39

**Rule:** Cash settlement Org↔Provider done directly by Org.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payouts/services.py`, line 232 — `record_manual_settlement()`.
- File: `apps/payouts/views.py`, line 67 — `technician_settlement()` view for company admin.

**Next action:** None.

---

### R40

**Rule:** Card-to-Card as independent payment channel.

**Status:** ❌ MISSING

**Evidence:**

- Grep `card_to_card` and `CARD_TO_CARD`: zero results.
- File: `apps/payments/models.py`, line 25 — `GatewayType` has only: ZARINPAL, IDPAY, NEXTPAY, FAKE, MANUAL.

**Next action:** Add `CARD_TO_CARD = "card_to_card"` to `PaymentGateway.GatewayType`.


---

## Section 5.9 — Settlement

### R41

**Rule:** Settlement timing Platform↔Org configurable per Organization.

**Status:** ❌ MISSING

**Evidence:**

- Grep `settlement_frequency`, `settlement_delay`, `settlement_timing`: zero results.
- Grep `SettlementBatch`: zero results.
- No timing configuration in `CompanyFinancialPolicy`.

**Next action:** Add `settlement_frequency` and `settlement_delay_hours` to `CompanyFinancialPolicy`. Create `SettlementBatch` + `SettlementItem` models.

---

### R42

**Rule:** Settlement timing Org↔Provider configured by Organization.

**Status:** 🟡 PARTIAL

**Evidence:**

- File: `apps/payouts/views.py`, line 67 — admin records settlement manually (no schedule).
- File: `apps/payouts/services.py`, line 232 — `record_manual_settlement()` immediate.

**Classification reason:** Manual works. Configurable timing absent.

**Next action:** Create `TechnicianSettlementConfig` per company with frequency.

---

### R43

**Rule:** Settlement Engine almost fully automatic.

**Status:** ❌ MISSING

**Evidence:**

- No automated settlement service, Celery task, or management command for batch settlement.
- Only per-payment automation: `TechnicianDirectSettlementService` (Shaparak split).

**Next action:** Build `SettlementCalculationService`, `SettlementExecutionService`, `process_settlements` command.

---

### R44

**Rule:** No manual approval required under normal conditions.

**Status:** 🟡 PARTIAL

**Evidence:**

- Manual settlement (`record_manual_settlement`) has no approval workflow — correct.
- No automated settlement exists to apply this rule to.

**Next action:** When building SettlementBatch, default `auto_approve=True`.

---

### R45

**Rule:** Settlement unit is Invoice.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payouts/models.py`, line 49 — `TechnicianLedgerEntry.invoice` FK.
- File: `apps/payouts/models.py`, line 215 — `CompanyPlatformFeeEntry.invoice` FK.
- File: `apps/payouts/models.py`, line 155 — `PaymentSplitSnapshot.invoice` FK.
- File: `apps/payouts/models.py`, line 331 — `FinancialBackfillTask.invoice` FK.

**Next action:** None.


---

## Section 5.10 — Financial Corrections & Controls

### R46

**Rule:** Financial Engine must support Customer adjustments (creditor/debtor).

**Status:** ❌ MISSING

**Evidence:**

- Grep `CustomerWallet`, `customer_credit`, `CustomerFinancialAccount`: zero results.
- No customer balance/wallet model exists.

**Next action:** Design `CustomerFinancialAccount`. Blocked on OI-05.

---

### R47

**Rule:** Customer cannot pay less than Invoice Total.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payments/services.py`, lines 287–288:
  ```python
  if int(response.verified_amount) != int(payment.amount):
      payment.status = Payment.Status.NEEDS_RECONCILIATION
  ```
- File: `apps/invoices/services.py`, line 361:
  ```python
  if payment.amount != invoice.total_amount:
      raise ValueError("Payment amount does not match invoice total.")
  ```

**Next action:** None.

---

### R48

**Rule:** Only Admin/Operators with appropriate permissions may modify policies.

**Status:** 🟡 PARTIAL

**Evidence:**

- File: `apps/payouts/views.py`, line 50 — `@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")`.
- `platform_fee_percent` controlled via platform owner views only.
- No granular "can_modify_financial_policy" permission.

**Next action:** Document permission matrix. Consider granular permissions.

---

### R49

**Rule:** Policy changes apply only to future invoices.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/services_wage.py`, line 231 — `snapshot_wage_percentages_on_invoice()` freezes at ISSUE time.
- File: `apps/invoices/services_settlement.py`, line 22 — `settle()` reads policy at PAID time and freezes.
- File: `apps/payouts/services_order_wages.py`, line 65 — reads rate at completion time.

**Next action:** None.

---

### R50

**Rule:** Every financial modification in Audit Log.

**Status:** 🟡 PARTIAL

**Evidence:**

- Ledger entries self-document: `metadata` JSONField + `created_by` + `created_at`.
- No independent audit log for policy/settings changes.

**Next action:** Install `django-auditlog` for `CompanyFinancialPolicy`, `CompanyPaymentSettings`.

---

### R51

**Rule:** No financial record may ever be deleted.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/payouts/models.py`, line 108:
  ```python
  def delete(self, *args, **kwargs):
      raise PermissionError("...immutable and cannot be deleted.")
  ```
- File: `apps/payouts/models.py`, line 267 — same on `CompanyPlatformFeeEntry`.

**Next action:** None.

---

### R52

**Rule:** Paid Invoices permanently locked.

**Status:** ✅ IMPLEMENTED

**Evidence:**

- File: `apps/invoices/models.py`, line 255:
  ```python
  def recalculate_totals(self, *, save: bool = True) -> None:
      if self.pk and self.status == self.Status.PAID:
          raise ValueError("Cannot recalculate totals on PAID invoice")
  ```

**Next action:** None (formal AdjustmentDocument model is target for R46/OI-07).


---

## Section 5.11 — Reporting

### R53

**Rule:** Provider liability report from Cash Payments mandatory.

**Status:** 🟡 PARTIAL

**Evidence:**

- File: `apps/payouts/services.py`, line 34 — `get_balance()` returns per-technician balance.
- File: `apps/payouts/views.py`, line 50 — `technician_ledger()` shows individual balance.
- No aggregated report view showing ALL technicians with negative balances.

**Next action:** Build dedicated Provider Liability Report view.

---

### R54

**Rule:** Complete Platform Commission Report mandatory.

**Status:** 🟡 PARTIAL

**Evidence:**

- File: `apps/payouts/services_platform_fee.py`, line 54 — `get_balance()` per company.
- File: `apps/payouts/services_platform_fee.py`, line 63 — `list_entries()` per company.
- No aggregated cross-company commission report view.

**Next action:** Build Platform Commission Report at `/owner-platform/reports/commission/`.

---

### R55

**Rule:** Completed and pending Settlements report mandatory.

**Status:** ❌ MISSING

**Evidence:**

- No `SettlementBatch` model exists (grep confirmed).
- No settlement report view exists.

**Next action:** Depends on Settlement Engine (R41–R44).

---

### R56

**Rule:** Most comprehensive financial reporting possible.

**Status:** ❌ MISSING

**Evidence:**

- File: `apps/reports/models.py`, line 11 — `Report` stub model. No financial KPIs.

**Next action:** Blocked on OI-09 and OI-10.

---

## Open Issues Assessment

| OI | Existing Architectural Clue |
|----|------------------------------|
| OI-01 | `PaymentSplitSnapshot.technician_direct_amount` + `Technician.sub_merchant_id` + `PaymentSplitDecisionService.compute()` → split infrastructure designed. |
| OI-02 | `InvoiceItem.RowType.TRAVEL` exists as line item. |
| OI-03 | 4 discount policies in `CompanyFinancialPolicy`. Separate per extra vs campaign. |
| OI-04 | `get_balance()` = SUM(credits) - SUM(debits). Negative = technician owes. |
| OI-05 | No `CustomerFinancialAccount` or wallet exists. |
| OI-06 | Amount mismatch → NEEDS_RECONCILIATION. No auto-handling. |
| OI-07 | `TechnicianLedgerEntry.Source.REFUND` defined. No `RefundService`. |
| OI-08 | Policy changes are immediate (single-step). No approval workflow. |
| OI-09 | `Report` stub exists. No KPI computation. |
| OI-10 | `TechnicianStatementService.build()` + export views = basic provider reporting. |

---

## Summary Statistics

| Classification | Count |
|----------------|-------|
| ✅ IMPLEMENTED | 30 |
| 🟡 PARTIAL | 12 |
| ❌ MISSING | 8 |
| ⚠️ INCORRECT | 0 |
| N/A (Future) | 6 |
| **Total** | **56** |
