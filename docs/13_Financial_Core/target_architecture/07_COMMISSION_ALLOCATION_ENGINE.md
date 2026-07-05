# 07 — موتور تخصیص کمیسیون (Commission Allocation Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R06–R10, R26–R28

---

## فرمول تخصیص کمیسیون

### مرحله 1: محاسبه subtotal هر دسته (R26)

```
service_total = SUM(item.total_price WHERE row_type = 'service')
goods_total   = SUM(item.total_price WHERE row_type = 'goods')
travel_total  = SUM(item.total_price WHERE row_type = 'travel')
```

### مرحله 2: محاسبه سهم ناخالص (R27)

```
service_wage = service_total × technician_service_wage_percent / 100
goods_wage   = goods_total × technician_goods_wage_percent / 100
travel_wage  = travel_total × technician_travel_wage_percent / 100

technician_gross_share = service_wage + goods_wage + travel_wage
company_gross_share    = (service_total + goods_total + travel_total) - technician_gross_share
```

### مرحله 3: تخصیص تخفیفات (R28, R31)

برای هر تخفیف (extra و campaign) بر اساس policy:

| Policy | تکنسین جذب می‌کند | شرکت جذب می‌کند |
|---|---|---|
| COMPANY | 0 | discount |
| TECHNICIAN | discount | 0 |
| HALF_HALF | discount/2 | discount/2 |
| PROPORTIONAL_SHARE | discount × (tech_gross / total_gross) | discount × (comp_gross / total_gross) |

### مرحله 4: سهم خالص نهایی

```
final_technician_wage = technician_gross_share - total_tech_absorbed
final_company_share   = company_gross_share - total_comp_absorbed
```

**Invariant:** `final_technician_wage + final_company_share = invoice_net_total - total_discount`

---

## کارمزد پلتفرم (R09)

```
platform_fee = invoice.total_amount × platform_fee_percent / 100
```

**R09 صریحاً می‌گوید:** کارمزد بر مبنای **کل مبلغ فاکتور** — نه فقط سهم شرکت.

### شرایط اعمال (ADR-003)

کارمزد فقط وقتی ایجاد می‌شود که ALL شرایط زیر true:
1. `CompanyPaymentSettings.payment_mode == "platform_gateway"`
2. `Payment.status == "paid"`
3. `PaymentGateway.owner_type == "platform"`
4. `CompanyFinancialPolicy.platform_fee_percent > 0`

**شرط اضافی (R10, R38):** برای پرداخت نقدی:
5. `CompanyFinancialPolicy.charge_commission_on_cash == True` (target field)

---

## بخش تخفیف

[OPEN-ISSUE: OI-03]

**Current Status:**
- محاسبه revenue sharing بعد از تخفیفات انجام می‌شود (R28 ✅)
- سیاست‌های extra و campaign جداگانه قابل پیکربندی (R31 ✅)
- اما **دقیقاً کدام ذینفع هر نوع تخفیف را جذب می‌کند** هنوز نهایی نشده

**Temporary Assumption:**
- Row discount: قبلاً از unit_price کسر شده → در gross share هر دو طرف تأثیر می‌گذارد (proportional)
- Extra discount: مطابق `extra_discount_policy`
- Campaign discount: مطابق `campaign_discount_policy`
- Rounding discount: TBD (R29 — target implementation)
- Loyalty discount: TBD (mapping to campaign_discount_policy فعلاً)

**Question for Product Owner:**
دقیقاً کدام ذینفع (پلتفرم، شرکت، تکنسین) هزینه هر نوع تخفیف زیر را تحمل می‌کند؟
- تخفیف ردیفی (line discount)
- تخفیف مازاد/دستی (extra discount)
- تخفیف کمپین/کد (campaign discount)
- تخفیف وفاداری (loyalty discount)
- تخفیف رُند (rounding discount)

---

## سند تخصیص (Commission Allocation Document)

در implementation فعلی، «سند تخصیص» معادل فیلدهای `settled_*` روی Invoice است:

| Field | Meaning |
|---|---|
| `settled_service_total` | مجموع خدمات |
| `settled_goods_total` | مجموع کالا |
| `settled_travel_total` | مجموع ایاب‌وذهاب |
| `settled_technician_gross_share` | سهم ناخالص تکنسین |
| `settled_company_gross_share` | سهم ناخالص شرکت |
| `settled_technician_absorbed_discount` | تخفیف جذب‌شده تکنسین |
| `settled_company_absorbed_discount` | تخفیف جذب‌شده شرکت |
| `settled_technician_wage` | سهم خالص نهایی تکنسین |
| `settled_company_share` | سهم خالص نهایی شرکت |
| `settled_campaign_discount_policy` | policy اعمال‌شده |
| `settled_extra_discount_policy` | policy اعمال‌شده |

**این فیلدها پس از settle شدن تغییرناپذیر هستند (P09).**

---

## وضعیت پیاده‌سازی

| Component | Status |
|---|---|
| Category subtotal calculation (R26) | ✅ `_collect_category_totals()` |
| Per-type wage percentages (R27) | ✅ Technician model fields + snapshot |
| Post-discount revenue sharing (R28) | ✅ `_calculate_policy_aware_wage()` |
| 4 discount policies (R31) | ✅ `_allocate_discount()` |
| Platform fee on total (R09) | ✅ `PlatformFeeService.compute_fee_for_invoice()` |
| Cash commission toggle (R10, R38) | 🟡 Target: new field needed |
| Rounding discount (R29) | ❌ Target: new fields + logic |
