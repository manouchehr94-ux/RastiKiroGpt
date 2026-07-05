# 05 — تحلیل شکاف (Gap Analysis)

**تاریخ ممیزی:** 2026-07-05
**مرجع:** Locked Business Rules R01–R56 + Open Issues OI-01–OI-10

---

## Classification Legend

| Code | Meaning |
|---|---|
| ✅ IMPLEMENTED | پیاده‌سازی کامل |
| 🟡 PARTIAL | پیاده‌سازی ناقص |
| ❌ MISSING | پیاده‌سازی ناموجود |
| ⚠️ INCORRECT | پیاده‌سازی ناصحیح |
| 🔧 TECH_DEBT | بدهی فنی |
| 📈 SCALABILITY | محدودیت مقیاس‌پذیری آینده |

---

## Section 5.1 — Money Ownership & Legal Roles

| Rule | Status | یافته |
|---|---|---|
| **R01** — Legal custody of funds belongs to Platform until settlement | 🟡 PARTIAL | Platform-First Collection model پیاده‌سازی شده (`PaymentGateway.owner_type=platform`). اما مدل Escrow صریح وجود ندارد — مفهوم «مالکیت قانونی» فقط ضمنی است. |
| **R02** — Payment appears to be to Organization from Customer perspective | ✅ IMPLEMENTED | فاکتور به نام شرکت صادر می‌شود (`Invoice.company`). UI عمومی فاکتور فقط اطلاعات شرکت نمایش می‌دهد. |
| **R03** — Invoice must be issued in Organization name | ✅ IMPLEMENTED | `Invoice` همیشه `company` FK دارد. `footer_text` default: «مسئولیت فاکتور بر عهده ارائه‌دهنده خدمت» |
| **R04** — Payment receipt shows Platform business name | ✅ IMPLEMENTED | `PaymentGateway.owner_type=platform` → merchant پلتفرم در Shaparak |
| **R05** — Platform receives only commission | ✅ IMPLEMENTED | `CompanyPlatformFeeEntry` فقط platform_fee ثبت می‌کند. Platform مالک تجاری نیست. |

---

## Section 5.2 — Organization Model

| Rule | Status | یافته |
|---|---|---|
| **R06** — Each Organization is independent | ✅ IMPLEMENTED | `Company` model مستقل. Multi-tenant isolation. |
| **R07** — Each Org may have its own financial policies | ✅ IMPLEMENTED | `CompanyFinancialPolicy` — OneToOne per company |
| **R08** — Platform may define different commission rates per Org | ✅ IMPLEMENTED | `CompanyFinancialPolicy.platform_fee_percent` — per company |
| **R09** — Commission calculated on total invoice amount | ✅ IMPLEMENTED | `PlatformFeeService.record_invoice_fee()` uses `invoice.total_amount × fee_pct` |
| **R10** — Commission on cash configurable, default: only online | 🟡 PARTIAL | Default: no commission on cash (manual payments). اما فیلد قابل پیکربندی صریح برای on/off کارمزد نقدی وجود ندارد. در کد فقط بررسی `gateway.owner_type == PLATFORM` انجام می‌شود و cash/manual اصلاً به این شرط نمی‌رسد. برای فعال‌سازی cash commission، باید فیلد جدید اضافه شود. |

---

## Section 5.3 — Online Payment & Money Flow

| Rule | Status | یافته |
|---|---|---|
| **R11** — Platform-First Collection | ✅ IMPLEMENTED | تمام payments ابتدا به gateway پلتفرم می‌روند (وقتی mode=platform_gateway) |
| **R12** — Three configurable collection models (A/B/C) | 🟡 PARTIAL | Model A (Platform→Settlement→Org) پایه پیاده‌سازی شده. Model C (split with technician) via `PaymentSplitDecisionService`. Model B (Platform retains commission, rest to Org) ضمنی است. اما UI مدیریت صریح سه مدل وجود ندارد — فقط `payout_strategy` (direct_to_company / split_with_technician). |
| **R13** — No approved IBAN → no online payment | ✅ IMPLEMENTED | `CompanyPaymentEligibilityService.is_gateway_enabled()` بررسی KYC + merchant profile approval |
| **R14** — Org IBAN approval by Platform Owner only | ✅ IMPLEMENTED | `CompanyMerchantProfile.reviewed_by` — فقط platform owner approve می‌کند |
| **R15** — One active settlement bank account per Org | ✅ IMPLEMENTED | `CompanyMerchantProfile.shaba_number` — یک شبا. تغییر نیاز به re-approval (change request flow). |

---

## Section 5.4 — Provider (Technician)

| Rule | Status | یافته |
|---|---|---|
| **R16** — Provider must belong to Organization | ✅ IMPLEMENTED | `Technician` extends `CompanyOwnedModel` — همیشه یک company FK دارد |
| **R17** — Provider may work for multiple Orgs (separate accounts) | ✅ IMPLEMENTED | هر Technician یک `CompanyUser` مجزا دارد. ثبت‌نام جداگانه در هر شرکت. |
| **R18** — Each Org can register IBAN for each Provider | ✅ IMPLEMENTED | `Technician.shaba_number` — per-company technician model |
| **R19** — Provider IBAN verification is Org responsibility | ✅ IMPLEMENTED | `Technician.financial_verification_status` + `shaba_verified` — توسط company admin verify می‌شود |
| **R20** — Direct settlement to Provider only when Org enables | ✅ IMPLEMENTED | `CompanyFinancialPolicy.payout_strategy == SPLIT_WITH_TECHNICIAN` + technician verified |
| **R21** — No IBAN → share goes to Organization | ✅ IMPLEMENTED | `PaymentSplitDecisionService.compute()` → if not verified → `payout_strategy_is_direct_to_company` → technician_ledger_amount (company owes) |

---

## Section 5.5 — Invoice Line Structure

| Rule | Status | یافته |
|---|---|---|
| **R22** — Fixed line structure (type, description, qty, unit_price, discount, total) | ✅ IMPLEMENTED | `InvoiceItem` has all fields |
| **R23** — Mandatory line types: Product, Service, Transportation, Additional Discount, Loyalty Discount | 🟡 PARTIAL | `InvoiceItem.RowType` دارد: service, goods, travel. اما "Additional Discount" و "Loyalty Discount" به عنوان line type مجزا وجود ندارند — فقط `extra_discount_amount` و `campaign_discount_amount` در سطح فاکتور. |
| **R24** — Products and Services as separate lines | ✅ IMPLEMENTED | `RowType.SERVICE` و `RowType.GOODS` مجزا |
| **R25** — One Provider per Invoice | ✅ IMPLEMENTED | Invoice → Order → one Technician (FK) |
| **R26** — Commission allocation per category subtotal first | ✅ IMPLEMENTED | `_collect_category_totals()` → service_total, goods_total, travel_total → سپس wage |
| **R27** — Provider compensation by line type | ✅ IMPLEMENTED | `technician_service_wage_percent`, `goods_wage_percent`, `travel_wage_percent` — نرخ مجزا per type |

---

## Section 5.6 — Discounts

| Rule | Status | یافته |
|---|---|---|
| **R28** — Revenue sharing after all discounts | ✅ IMPLEMENTED | `_calculate_policy_aware_wage` بعد از row discounts، سپس discount allocation |
| **R29** — Rounding Discount configurable per Org | ❌ MISSING | هیچ مدل یا فیلدی برای «تخفیف رُند» (rounding discount) وجود ندارد. |
| **R30** — Discount Codes managed by Organization | ✅ IMPLEMENTED | `DiscountCampaign` و `DiscountCode` هر دو `CompanyOwnedModel` هستند |
| **R31** — Provider discount participation configurable | ✅ IMPLEMENTED | `CompanyFinancialPolicy.campaign_discount_policy` و `extra_discount_policy` — COMPANY/TECHNICIAN/HALF_HALF/PROPORTIONAL |

---

## Section 5.7 — Referral / Visitor

| Rule | Status | یافته |
|---|---|---|
| **R32** — No commission for introducing Organizations | ✅ IMPLEMENTED | هیچ referral commission پیاده‌سازی نشده |
| **R33** — Customer referrals reserved for future | ✅ IMPLEMENTED | هیچ پیاده‌سازی فعلی وجود ندارد (صحیح) |
| **R34** — Future: one-time only | N/A | آینده |
| **R35** — Future: deducted from Org share | N/A | آینده |
| **R36** — Referrer and Visitor are same role | N/A | آینده |

---

## Section 5.8 — Cash Payments

| Rule | Status | یافته |
|---|---|---|
| **R37** — Cash: legal ownership immediately to Org, but allocation doc still generated | ✅ IMPLEMENTED | Mark paid cash → settlement freeze + ledger entries ایجاد می‌شود |
| **R38** — Platform Commission on cash disabled by default, configurable per Org | 🟡 PARTIAL | Default disabled: صحیح. اما فیلد configurable مخصوص «فعال‌سازی commission بر نقدی» وجود ندارد. |
| **R39** — Cash settlement Org↔Provider done directly by Org | ✅ IMPLEMENTED | `record_manual_settlement` — admin ثبت می‌کند. Platform فقط track می‌کند. |
| **R40** — Card-to-Card as independent payment channel | ❌ MISSING | هیچ مدل مجزا برای «کارت به کارت» به عنوان payment channel مستقل وجود ندارد. فعلاً فقط metadata.method ممکن است. |

---

## Section 5.9 — Settlement

| Rule | Status | یافته |
|---|---|---|
| **R41** — Settlement timing Platform↔Org configurable per Org | ❌ MISSING | هیچ settlement timing configuration وجود ندارد. تسویه فوری یا دستی. |
| **R42** — Settlement timing Org↔Provider configured by Org | 🟡 PARTIAL | Admin دستی settlement ثبت می‌کند. اما هیچ automated timing وجود ندارد. |
| **R43** — Settlement Engine almost fully automatic | ❌ MISSING | Settlement کاملاً دستی است (manual_settlement via admin view). هیچ automatic batch settlement وجود ندارد. |
| **R44** — No manual approval normally required | 🟡 PARTIAL | Manual settlement بدون approval workflow ثبت می‌شود (صحیح). اما automated settlement اصلاً وجود ندارد. |
| **R45** — Settlement unit is Invoice, not Order | ✅ IMPLEMENTED | تمام ledger entries و platform fee entries به Invoice reference دارند |

---

## Section 5.10 — Financial Corrections & Controls

| Rule | Status | یافته |
|---|---|---|
| **R46** — Customer financial adjustments (creditor/debtor) | ❌ MISSING | هیچ مکانیزم Customer credit/debit وجود ندارد. |
| **R47** — Customer cannot pay less than total | ✅ IMPLEMENTED | `PaymentVerifyService`: amount mismatch → NEEDS_RECONCILIATION |
| **R48** — Only Admin/Operators with permission may modify policies | 🟡 PARTIAL | `@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")` برای settlement. platform_fee_percent فقط platform owner. اما permission matrix کامل documented نیست. |
| **R49** — Policy changes apply only to future invoices | ✅ IMPLEMENTED | Policy در لحظه settlement خوانده و snapshot می‌شود. invoiceهای قبلی تغییر نمی‌کنند. |
| **R50** — Every financial modification in Audit Log | 🟡 PARTIAL | Ledger entries خودشان audit trail هستند (append-only + metadata + created_by). اما audit log مستقل (who changed what policy when) وجود ندارد. |
| **R51** — No financial record may be deleted | ✅ IMPLEMENTED | `delete()` → PermissionError روی هر دو ledger |
| **R52** — Paid Invoices permanently locked | ✅ IMPLEMENTED | `recalculate_totals()` → ValueError if PAID. Settlement fields immutable after settled_at. |

---

## Section 5.11 — Reporting

| Rule | Status | یافته |
|---|---|---|
| **R53** — Provider liability report from Cash Payments mandatory | 🟡 PARTIAL | Balance قابل محاسبه از ledger (negative = technician owes). اما report صفحه مخصوص وجود ندارد. |
| **R54** — Complete Platform Commission Report | 🟡 PARTIAL | `CompanyPlatformFeeEntry` data موجود. اما report view مخصوص platform ناموجود یا orphan. |
| **R55** — Completed and pending Settlements report | ❌ MISSING | هیچ settlement batch/report مخصوص وجود ندارد (settlement دستی بدون batch). |
| **R56** — Most comprehensive reporting possible | ❌ MISSING | Report module (`apps/reports/`) فعلاً فقط DiscountCampaign و Report stub دارد. KPI catalog ناموجود. |

---

## Open Issues Assessment

| OI | Architectural Clue from Current Implementation |
|---|---|
| **OI-01** — Split Payment Capability | `PaymentSplitDecisionService` + `PaymentSplitSnapshot` نشان می‌دهد که split payment در سطح concept طراحی شده. `technician_direct_amount` و `sub_merchant_id` حاکی از قابلیت sub-merchant Shaparak. اما split واقعی هنوز TASK-010C (planned) است. |
| **OI-02** — Transportation Modeling | فعلاً `InvoiceItem.RowType.TRAVEL` — یک line type مجزا. نه field مستقل invoice. |
| **OI-03** — Discount Distribution | `CompanyFinancialPolicy` چهار policy (COMPANY/TECHNICIAN/HALF_HALF/PROPORTIONAL) دارد. extra و campaign جداگانه قابل پیکربندی. اما line discount و rounding discount policy نامشخص. |
| **OI-04** — Provider Debt Calculation | Balance = SUM(credits) - SUM(debits). Negative = technician owes. اما فرمول رسمی document نشده. |
| **OI-05** — Customer Financial Adjustments | هیچ پیاده‌سازی فعلی وجود ندارد. |
| **OI-06** — Customer Overpayment | `PaymentVerifyService`: amount mismatch → NEEDS_RECONCILIATION. Overpayment explicitly handled نیست. |
| **OI-07** — Refund Definitions | `TechnicianLedgerEntry.Source.REFUND` exists but **هیچ سرویس refund** پیاده‌سازی نشده. |
| **OI-08** — Policy Change Approval | فعلاً single-step: admin/platform changes immediately. No two-step approval. |
| **OI-09** — Financial KPI Catalog | `Report` model stub exists. No actual KPI implementation. |
| **OI-10** — Provider Reporting | `TechnicianStatementService` + export/pdf views exist. اما limited to ledger view. |

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
