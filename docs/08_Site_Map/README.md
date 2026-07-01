---
Title: Site Map — README
Layer: Site Map
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code (config/urls.py, apps/*/urls.py)
---

# 08_Site_Map — نقشه سایت و ناوبری سیستم Rasti

**تاریخ:** ۱ ژوئیه ۲۰۲۶ (۱۰ تیر ۱۴۰۵)  
**مبنا:** کد واقعی در `config/urls.py`، تمام `apps/*/urls*.py`، فایل‌های view و قالب‌های HTML  
**پروژه:** Rasti SaaS Service Platform — Django 5.1.3

---

## محتوای این پوشه

| فایل | توضیح |
|------|-------|
| [README.md](README.md) | همین فایل — راهنمای خواندن مجموعه |
| [01_URL_INVENTORY.md](01_URL_INVENTORY.md) | فهرست کامل تمام URL‌های پروژه با نقش، view، و قالب |
| [02_ROLE_BASED_SITE_MAP.md](02_ROLE_BASED_SITE_MAP.md) | نقشه سایت جداگانه برای هر نقش کاربری |
| [03_NAVIGATION_GRAPH.md](03_NAVIGATION_GRAPH.md) | گراف ناوبری با Mermaid — ورودی‌ها، جریان‌ها، داشبوردها |
| [04_BUSINESS_FLOW_MAP.md](04_BUSINESS_FLOW_MAP.md) | نقشه گردش‌کارهای کسب‌وکار به صورت دیاگرام |
| [05_TEMPLATE_MAP.md](05_TEMPLATE_MAP.md) | نگاشت قالب‌های HTML به صفحات و view‌ها |
| [06_NAVIGATION_GAPS_AND_RISKS.md](06_NAVIGATION_GAPS_AND_RISKS.md) | مشکلات ساختار ناوبری — صفحات고립، خلأهای امنیتی |
| [07_RECOMMENDED_NAVIGATION_REDESIGN.md](07_RECOMMENDED_NAVIGATION_REDESIGN.md) | پیشنهاد طراحی مجدد ناوبری (بدون تغییر کد) |
| [08_GRAPHIFY_STYLE_EXPORT.md](08_GRAPHIFY_STYLE_EXPORT.md) | خروجی گراف‌مانند با جداول Node و Edge |
| [09_FINAL_SITE_MAP_REPORT.md](09_FINAL_SITE_MAP_REPORT.md) | گزارش نهایی فارسی — ساختار فعلی، ریسک‌ها، گام بعدی |

---

## ساختار کلی URL پروژه

پروژه Rasti از **multi-tenancy مبتنی بر URL** استفاده می‌کند. اولین بخش مسیر URL کد شرکت است:

```
/                        ← صفحات عمومی (بازاریابی، ثبت‌نام)
/login/                  ← ورود یکپارچه برای همه نقش‌ها
/owner-platform/         ← پنل مالک پلتفرم (PLATFORM_OWNER)
/admin/                  ← Django Admin (superuser)
/i/<public_code>/        ← لینک کوتاه فاکتور عمومی (بدون auth)
/api/auth/               ← REST API احراز هویت
/api/platform/           ← REST API پلتفرم
/api/<company_code>/     ← REST API tenant
/<company_code>/         ← پنل‌های شرکت (tenant-scoped)
  /<company_code>/admin/ ← پنل مدیر/اپراتور
  /<company_code>/tech/  ← پنل تکنسین
  /<company_code>/invoices/ ← فاکتور عمومی/مشتری
  /<company_code>/payments/ ← پرداخت
```

---

## نقش‌های کاربری

| نقش | نام Django | پنل اصلی |
|-----|-----------|----------|
| مالک پلتفرم | `PLATFORM_OWNER` | `/owner-platform/` |
| مدیر شرکت | `COMPANY_ADMIN` | `/<code>/admin/` |
| اپراتور/کارمند | `COMPANY_STAFF` | `/<code>/admin/` |
| تکنسین | `TECHNICIAN` | `/<code>/tech/` |
| مشتری | `CUSTOMER` | `/<code>/invoices/` + `/<code>/payments/` |
| بازدیدکننده | — (بدون auth) | `/` و `/<code>/` و `/<code>/request/` |

---

## نحوه خواندن این مجموعه

1. برای یافتن یک URL خاص → `01_URL_INVENTORY.md`
2. برای درک جریان دسترسی یک نقش → `02_ROLE_BASED_SITE_MAP.md`
3. برای دیدن نمودار بصری جریان‌ها → `03_NAVIGATION_GRAPH.md` (Mermaid)
4. برای درک فرآیندهای کسب‌وکار → `04_BUSINESS_FLOW_MAP.md`
5. برای یافتن قالب HTML یک صفحه → `05_TEMPLATE_MAP.md`
6. برای یافتن مشکلات ناوبری → `06_NAVIGATION_GAPS_AND_RISKS.md`
7. برای بهبود آینده ناوبری → `07_RECOMMENDED_NAVIGATION_REDESIGN.md`
8. برای تبدیل به ابزار بصری → `08_GRAPHIFY_STYLE_EXPORT.md`
9. گزارش جامع فارسی → `09_FINAL_SITE_MAP_REPORT.md`

---

## آمار کلی

| آیتم | تعداد |
|------|-------|
| URL pattern کل | ≈ 226 |
| URL عمومی (بدون auth) | 18 |
| URL پنل مدیر/اپراتور | 83 |
| URL پنل تکنسین | 17 |
| URL پلتفرم‌ (مالک) | 70 |
| URL REST API | 17 |
| URL لگسی/ریدایرکت | 10 |
| قالب HTML شناسایی‌شده | 199+ |
| نقش کاربری | 5 (+ بازدیدکننده) |
