# 10 — موتور سیاست مالی (Financial Policy Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Principle:** P03 — Policies Outside Business Logic

---

## سیاست‌های قابل پیکربندی per Organization

### CompanyFinancialPolicy (موجود)

| Field | Type | Default | Controlled By |
|---|---|---|---|
| `platform_fee_percent` | Decimal(5,2) | 0 | Platform Owner only |
| `campaign_discount_policy` | Choice | COMPANY | Platform Owner |
| `extra_discount_policy` | Choice | TECHNICIAN | Platform Owner |
| `payout_strategy` | Choice | DIRECT_TO_COMPANY | Platform Owner |

### Target Extensions

| Field | Type | Default | Controlled By | Rule |
|---|---|---|---|---|
| `charge_commission_on_cash` | Boolean | False | Platform Owner | R10, R38 |
| `rounding_discount_enabled` | Boolean | False | Organization Admin | R29 |
| `max_rounding_discount_rial` | PositiveBigInteger | 0 | Organization Admin | R29 |
| `settlement_frequency` | Choice | manual | Platform Owner | R41 |
| `settlement_delay_hours` | PositiveInteger | 0 | Platform Owner | R41 |

---

### CompanyPaymentSettings (موجود)

| Field | Current | Controlled By |
|---|---|---|
| `payment_mode` | disabled/company_gateway/platform_gateway | Platform Owner |
| `gateway_activation_status` | inactive/pending_review/active/suspended | Platform Owner |
| `is_online_payment_enabled` | computed on save | System |

---

### Technician Wage Configuration (موجود)

| Level | Model | Fields |
|---|---|---|
| Percentage-based | `Technician` | service_wage_percent, goods_wage_percent, travel_wage_percent |
| Fixed per item | `TechnicianServiceRate` | fixed_wage_rial per item_definition |

**Note (ADR-005):** Phase 1 فقط fixed. Phase 2 target: percentage/formula pricing types.

---

## Discount Policies

### Four Allocation Strategies

```python
class DiscountPolicy(TextChoices):
    COMPANY = "company"            # شرکت کل تخفیف را جذب
    TECHNICIAN = "technician"      # تکنسین کل تخفیف را جذب
    HALF_HALF = "half_half"        # نصف-نصف
    PROPORTIONAL_SHARE = "proportional_share"  # نسبت به سهم ناخالص
```

### جداسازی per Discount Type

| Discount Type | Policy Field |
|---|---|
| Extra/Manual discount | `extra_discount_policy` |
| Campaign/Code discount | `campaign_discount_policy` |

---

## Policy Snapshot at Decision Time (P08)

سیاست‌ها هرگز retroactively اعمال نمی‌شوند:

| When | What is Snapshotted | Where Stored |
|---|---|---|
| Invoice ISSUED | Wage percentages | `Invoice.technician_*_wage_percent_snapshot` |
| Invoice PAID | Discount policies + all calculated values | `Invoice.settled_*` fields |
| Payment verified | Platform fee percent + payout strategy | `PaymentSplitSnapshot.*_snapshot` |
| Order completed | Rate at completion time | `TechnicianLedgerEntry.metadata` |

---

## Organization-Specific Configuration (R07, R08)

هر شرکت می‌تواند policy مالی مستقل داشته باشد:

```python
# Company A: 5% commission, company absorbs all discounts
CompanyFinancialPolicy(company=A, platform_fee_percent=5, campaign_discount_policy=COMPANY)

# Company B: 3% commission, proportional discount sharing
CompanyFinancialPolicy(company=B, platform_fee_percent=3, campaign_discount_policy=PROPORTIONAL_SHARE)
```

---

## Policy Change Audit (R50)

**Current:** هیچ audit log مستقلی وجود ندارد.

**Target:** django-auditlog یا custom:
```python
# Track changes to:
# - CompanyFinancialPolicy (all fields)
# - CompanyPaymentSettings (payment_mode, activation_status)
# Fields: who, when, old_value, new_value
```

[OPEN-ISSUE: OI-08]
**Current Status:** تغییر policy فوری و بدون approval workflow.
**Question for Product Owner:** آیا تغییر سیاست‌های مالی نیاز به two-step approval دارد؟
