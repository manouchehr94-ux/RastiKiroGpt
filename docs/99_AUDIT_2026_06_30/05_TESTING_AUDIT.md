# ۰۵ — حسابرسی تست‌ها

**تاریخ:** ۳۰ ژوئن ۲۰۲۶  
**نتیجه اجرا:** `python manage.py test` — خروج با کد ۰ (همه ۱۲۴۲ تست pass)  
**ابزار:** Django test runner با SQLite

---

## نتیجه اجرای تست

```
Found 1242 test(s).
System check identified no issues (0 silenced).
[..........] (exit code 0)
```

✅ تمام ۱۲۴۲ تست با موفقیت اجرا شدند.  
⚠️ تست‌ها روی SQLite اجرا می‌شوند، نه PostgreSQL.

---

## آمار کلی

| شاخص | مقدار |
|---|---|
| فایل‌های تست | ۸۸ |
| تعداد کلاس | ~۲۵۷ |
| تعداد تست | ۱۲۴۲ |
| محل تست‌ها | همه در `tests/` ریشه (هیچ تستی داخل اپ‌ها نیست) |
| سبک نام‌گذاری | `test_p[n]_*` و `test_task[n]_*` — نشان‌دهنده patch-driven |

---

## طبقه‌بندی تست‌ها

### دسته ۱: تست‌های منطق تجاری (کیفیت بالا)

این تست‌ها سرویس‌ها را مستقیماً آزمایش می‌کنند، وضعیت DB را پس از عملیات بررسی می‌کنند و موارد خطا را تست می‌کنند:

| فایل | حوزه | کیفیت |
|---|---|---|
| `test_task010c_direct_settlement.py` | ۲۲ تست برای همه شرایط لجر DEBIT | ⭐⭐⭐ |
| `test_invoice_lifecycle_stabilization.py` | race guard، signal، redirect | ⭐⭐⭐ |
| `test_task007a_financial_integrity.py` | DB constraints، لجر، recalculate blocked | ⭐⭐⭐ |
| `test_notifications_core.py` | ایزولاسیون رویداد، استقلال کلیدها | ⭐⭐⭐ |
| `test_p0_order_protection.py` | محافظت وضعیت terminal در همه ترکیبات | ⭐⭐⭐ |
| `test_invoice_duplicate_guard.py` | guard تکرار فاکتور | ⭐⭐ |
| `test_order_unassign.py` | حذف تکنسین و بازگشت به NEW | ⭐⭐ |
| `test_p0a_technician_accept_waiting.py` | انتقال NEW → WAITING | ⭐⭐ |
| `test_p0b_pending_review_approval.py` | تأیید PENDING_REVIEW | ⭐⭐ |
| `test_invoice_cancellation_request.py` | درخواست لغو فاکتور | ⭐⭐ |

### دسته ۲: تست‌های smoke (فقط بررسی عدم crash)

این تست‌ها فقط `status_code == 200` را بررسی می‌کنند:

| فایل | توضیح |
|---|---|
| `test_dashboard_views_no_crash.py` | "نباید NameError بدهد" — صرفاً smoke |
| `test_p19_ui_core_low_risk_polish.py` تا `test_p35_*.py` | ۱۵ فایل CSS migration — فقط بررسی وجود CSS class در HTML |
| `test_p13_payment_operations_dashboard.py` | navigation check |
| `test_p14_payment_ops_navigation.py` | navigation check |

### دسته ۳: تست‌های با آنتی‌پترن

| فایل | مشکل |
|---|---|
| `test_notifications_core.py:159-162` | `inspect.getsource()` — شکننده در برابر refactor |
| `test_p22_high_risk_template_migration.py:119-123` | بررسی cross-tenant با ۲ شرکت — خوب اما ناکافی |

---

## نقشه پوشش تست (Test Coverage Map)

### ✅ پوشش کافی دارد

| حوزه | فایل‌های تست |
|---|---|
| انتقال وضعیت سفارش | `test_p0_*.py`, `test_done_path_unification.py` |
| چرخه حیات فاکتور | `test_invoice_lifecycle_*.py`, `test_fix1-4_invoice_*.py` |
| پرداخت | `test_p4`, `test_p7`, `test_p8`, `test_p11-16` |
| یکپارچگی مالی | `test_task007a`, `test_task010c-i`, `test_task011a` |
| نرخ و اجرت تکنسین | `test_task010a`, `test_task010b1`, `test_task015` |
| سیستم اطلاع‌رسانی | `test_notifications_core`, `test_task017` |
| SMS | `test_sms_otp_flows`, `test_sms_no_duplicate_order`, `test_sms_footer_enforcement` |
| امنیت KYC | `test_p9_kyc_document_security` |
| تنظیمات امنیتی تولید | `test_p10_production_security_settings` |

### ❌ پوشش ندارد یا ناکافی است

| حوزه | خطر | توضیح |
|---|---|---|
| **ایزولاسیون چند‌مستأجری order/invoice** | 🔴 بالا | آیا شرکت الف می‌تواند سفارشات شرکت ب را ببیند؟ هیچ تستی وجود ندارد |
| **جریان کامل end-to-end** | 🔴 بالا | Order→Invoice→Payment→Ledger در یک تست یکپارچه |
| **race conditions واقعی** | 🔴 بالا | `select_for_update()` روی SQLite تست نمی‌شود |
| **ثبت‌نام شرکت و onboarding مشتری** | 🟠 متوسط | هیچ تست برای `/request/` و OTP مشتری وجود ندارد |
| **subscription و billing** | 🟠 متوسط | `apps/billing/` کاملاً untested |
| **PSP providers واقعی** | 🟠 متوسط | فقط `fake.py` تست می‌شود |
| **`admin_operator_list` (نقص امنیتی)** | 🔴 بالا | نقص permissions در این view هیچ تستی ندارد |
| **communication settings matrix** | 🟡 کم | فقط render tests |
| **صورت‌حساب تکنسین (statement PDF)** | 🟡 کم | UI test فقط |

---

## ۵ منطقه بحرانی بدون تست

### ۱. ایزولاسیون چند‌مستأجری برای سفارش و صورتحساب (خطر بالا)
هیچ تستی وجود ندارد که:
- بررسی کند کاربر شرکت A نمی‌تواند سفارشات شرکت B را با تغییر URL ببیند
- بررسی کند `request.company` در همه view‌های اصلی enforce می‌شود

**پیامد احتمالی:** نشت داده بین مستأجران

### ۲. جریان Order → Invoice → Payment → Ledger (یکپارچه)
هر لایه به‌تنهایی تست می‌شود اما هیچ تست end-to-end وجود ندارد.

### ۳. مجوزها روی view‌هایی که نقص دارند
`admin_operator_list` (`tenants/views_admin.py:2125`) هیچ decorator ندارد اما تست نیز ندارد.

### ۴. ثبت‌نام شرکت و onboarding مشتری
مسیر `/register/` و `/request/` هیچ integration test ندارد.

### ۵. اشتراک و billing
`apps/billing/` و `Subscription` model کاملاً بدون تست هستند.

---

## ارزیابی کیفیت تست

| جنبه | امتیاز | توضیح |
|---|---|---|
| پوشش منطق تجاری | ۷/۱۰ | سفارش، فاکتور، پرداخت خوب test شده |
| پوشش امنیت | ۳/۱۰ | KYC خوب، ایزولاسیون چند‌مستأجری کم |
| پوشش integration | ۵/۱۰ | ماژول‌ها به‌تنهایی خوب، end-to-end کم |
| کیفیت تست‌ها | ۶/۱۰ | ۱۵ فایل CSS-smoke تست ارزش کمی دارند |
| DB backend | ۳/۱۰ | SQLite ≠ PostgreSQL در concurrency |

---

## توصیه‌های اولویت‌بندی شده

### اولویت ۱ (قبل از تولید)
```python
# نوشتن تست cross-tenant isolation:
def test_company_a_cannot_see_company_b_orders():
    response = client.get(f"/{company_a.code}/admin/orders/{order_b.id}/")
    assert response.status_code in [403, 404]
```

### اولویت ۲ (قبل از تولید)
```python
# تست end-to-end مالی
def test_full_order_to_payment_flow():
    order = create_order()
    invoice = complete_order_and_get_invoice(order)
    payment = pay_invoice(invoice)
    assert TechnicianLedgerEntry.objects.filter(order=order).exists()
```

### اولویت ۳ (ماه اول)
- تست‌های integration برای ثبت‌نام شرکت و مشتری
- تست‌های PostgreSQL (staging environment)
- تست race condition برای `select_for_update()`
