# 06 — موتور ردیف فاکتور (Invoice Line Engine)

**Version:** v1.0 — Draft — Pending Clarification
**Rules:** R22–R27

---

## ساختار ردیف فاکتور (R22)

هر `InvoiceItem` دارای فیلدهای ثابت زیر:

| Field | Type | Description |
|---|---|---|
| `row_type` | Choice | نوع ردیف (service/goods/travel/additional_discount/loyalty_discount) |
| `description` | CharField(300) | شرح |
| `quantity` | Decimal(12,2) | تعداد |
| `unit_price` | Decimal(12,0) | قیمت واحد (ریال) |
| `discount_amount` | Decimal(12,0) | تخفیف ردیفی |
| `total_price` | Decimal(12,0) | مبلغ کل = (qty × unit_price) - discount |

---

## انواع ردیف (R23)

| RowType | Label | Wage Applicable? |
|---|---|---|
| `service` | اجرت خدمات | ✅ technician_service_wage_percent |
| `goods` | کالا / قطعه | ✅ technician_goods_wage_percent |
| `travel` | ایاب و ذهاب | ✅ technician_travel_wage_percent |
| `additional_discount` | تخفیف مازاد | ❌ (reduces total, no wage) |
| `loyalty_discount` | تخفیف وفاداری | ❌ (reduces total, no wage) |

**Note:** `additional_discount` و `loyalty_discount` ردیف‌هایی با مبلغ منفی (یا quantity=1, unit_price=negative) نیستند — آن‌ها از طریق فیلدهای `extra_discount_amount` و `campaign_discount_amount` در سطح فاکتور اعمال می‌شوند. RowType choices برای categorization و reporting اضافه می‌شوند.

---

## مثال عددی کامل

### سناریو: نصب پکیج با تعویض قطعه

```
ردیف 1: [service]  نصب پکیج دیواری     × 1    @ 4,000,000    تخفیف: 0      = 4,000,000
ردیف 2: [goods]   لوله مسی ½ اینچ      × 3    @ 500,000      تخفیف: 0      = 1,500,000
ردیف 3: [goods]   شیر گاز ¾            × 1    @ 800,000      تخفیف: 100,000 = 700,000
ردیف 4: [travel]  ایاب و ذهاب           × 1    @ 300,000      تخفیف: 0      = 300,000
```

### محاسبه subtotals (R26)

```
service_total = 4,000,000
goods_total   = 1,500,000 + 700,000 = 2,200,000
travel_total  = 300,000
───────────────────────────────────────
invoice_net_total = 6,500,000
```

### اعمال تخفیفات سطح فاکتور

```
extra_discount_amount    = 200,000  (تخفیف دستی مدیر)
campaign_discount_amount = 300,000  (کد تخفیف مشتری)
total_discount           = 500,000
───────────────────────────────────────
total_amount = 6,500,000 - 500,000 = 6,000,000
```

### محاسبه سهم تکنسین (R27)

فرض: service_wage_percent=40%, goods_wage_percent=20%, travel_wage_percent=30%

```
service_wage = 4,000,000 × 40% = 1,600,000
goods_wage   = 2,200,000 × 20% = 440,000
travel_wage  = 300,000 × 30%   = 90,000
───────────────────────────────────────
technician_gross_share = 2,130,000
company_gross_share    = 6,500,000 - 2,130,000 = 4,370,000
```

### تخصیص تخفیف (R28, R31)

فرض policies:
- extra_discount_policy = TECHNICIAN (تکنسین جذب)
- campaign_discount_policy = COMPANY (شرکت جذب)

```
extra_discount (200,000):
  tech_absorbed = 200,000    comp_absorbed = 0

campaign_discount (300,000):
  tech_absorbed = 0          comp_absorbed = 300,000

total_tech_absorbed = 200,000
total_comp_absorbed = 300,000
```

### نتیجه نهایی

```
final_technician_wage = 2,130,000 - 200,000 = 1,930,000
final_company_share   = 4,370,000 - 300,000 = 4,070,000
───────────────────────────────────────
Check: 1,930,000 + 4,070,000 = 6,000,000 ✅ (= total_amount)
```

---

## پیاده‌سازی موجود

تمام منطق بالا در `apps/invoices/services_wage.py` → `_calculate_policy_aware_wage()` پیاده‌سازی شده:
- `_collect_category_totals()` → R26
- `_get_wage_percentages()` → R27
- `_allocate_discount()` → R28, R31

**وضعیت:** ✅ کاملاً پیاده‌سازی شده — نیاز به extension فقط برای RowType choices جدید.
