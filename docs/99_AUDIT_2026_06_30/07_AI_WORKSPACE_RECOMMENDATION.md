# ۰۷ — توصیه برای AI Workspace

**تاریخ:** ۳۰ ژوئن ۲۰۲۶

---

## ارزیابی کلی AI Workspace

فضای کاری AI پروژه راستی یک سیستم پیشرفته و چند‌لایه است که از Claude، Kiro، و ChatGPT به‌طور همزمان استفاده می‌کند. کیفیت کلی **بالا** است اما با مشکلات سازماندهی و تکرار.

**امتیاز:** ۷/۱۰

---

## ساختار فعلی docs/AI

```
docs/AI/
├── README.md                    ← ورودی AI workspace
├── AI_DEVELOPMENT_PROTOCOL.md   ← workflow و نقش‌ها
├── AI_RULES.md                  ← قوانین و محدودیت‌ها
├── CURRENT_MISSION.md           ← mission فعلی
├── PROJECT_KNOWLEDGE.md         ← دانش تجاری برای AI
├── PROJECT_RULES.md             ← قوانین Rasti برای AI
├── AI_Workspace_Framework_v1_Architecture_Report_EN.md ← vision آینده
├── KNOWLEDGE/                   ← ۵ فایل دانش تجاری
├── POLICIES/                    ← ۶ فایل سیاست
├── PROMPTS/                     ← ۷ template prompt
├── REPORTS/                     ← قالب‌ها (هیچ گزارش واقعی ندارد)
├── REQUESTS/                    ← ۵ درخواست (برخی پاسخ گرفته)
├── STANDARDS/                   ← ۵ استاندارد
├── WORKFLOWS/                   ← ۵ workflow
└── ARCHIVE/README.md
```

---

## طبقه‌بندی مستندات AI

### دسته ۱: مستندات workflow هوش مصنوعی (AI Operating Instructions)
این فایل‌ها درباره چگونگی کار Claude/Kiro هستند، نه درباره راستی:

- `AI/README.md`
- `AI/AI_DEVELOPMENT_PROTOCOL.md`
- `AI/AI_RULES.md`
- `AI/POLICIES/` — همه ۶ فایل
- `AI/PROMPTS/` — همه ۷ فایل
- `AI/REPORTS/` — قالب‌ها
- `AI/WORKFLOWS/` — همه ۵ فایل
- `AI/ARCHIVE/README.md`

### دسته ۲: دانش تجاری راستی (Rasti Business Knowledge)
این فایل‌ها اطلاعات راستی را برای AI agent خلاصه می‌کنند:

- `AI/PROJECT_KNOWLEDGE.md`
- `AI/PROJECT_RULES.md`
- `AI/CURRENT_MISSION.md` (ترکیبی)
- `AI/KNOWLEDGE/` — همه ۵ فایل
- `AI/STANDARDS/DATABASE_STANDARDS.md`, `DJANGO_STANDARDS.md`, `SECURITY_STANDARDS.md`

### دسته ۳: درخواست‌های اجرا (Active Requests)
- `AI/REQUESTS/001_REBUILD_DOCUMENTATION.md` — این حسابرسی پاسخ آن است
- `AI/REQUESTS/002_PRODUCT_BACKLOG.md` — برخی موارد پیاده‌سازی شده
- `AI/REQUESTS/003_FINANCIAL_CORE_AUDIT.md` — پاسخ داده شده (FINANCIAL_CORE_FINAL_AUDIT)
- `AI/REQUESTS/004_PRODUCTION_READINESS.md` — پاسخ داده شده
- `AI/REQUESTS/005_UI_POLISH.md` — پاسخ جزئی داده شده

### دسته ۴: Vision آینده (Framework Document)
- `AI/AI_Workspace_Framework_v1_Architecture_Report_EN.md` — یک سند vision درباره بازسازی ساختار AI workspace در آینده

---

## مشکلات اصلی AI Workspace

### مشکل ۱: هیچ گزارش تکمیل‌شده‌ای در `AI/REPORTS/` وجود ندارد
`AI/REPORTS/README.md` می‌گوید: "هر درخواست تکمیل‌شده باید یک گزارش اینجا داشته باشد." درخواست‌های ۰۰۳ و ۰۰۴ پاسخ گرفته‌اند اما هیچ گزارشی ثبت نشده است.

### مشکل ۲: تکرار دانش تجاری در ۳ مکان
همان قوانین تجاری (multi-tenant، financial، order) در ۳ مکان تکرار می‌شوند:
- `docs/03_Business/*.md`
- `docs/AI/KNOWLEDGE/*.md`
- `docs/AI/PROJECT_RULES.md`

تغییر در یکی باید در دو جای دیگر هم اعمال شود — خطر inconsistency.

### مشکل ۳: تکرار template‌ها در 02_Development_System و AI/PROMPTS
- `TASK_TEMPLATE.md` ≈ `IMPLEMENT_TEMPLATE.md`
- `REVIEW_TEMPLATE.md` ≈ `AI/PROMPTS/REVIEW_TEMPLATE.md`

### مشکل ۴: CURRENT_MISSION.md نیاز به update دارد
اگر مأموریت تغییر کند، این فایل باید فوری به‌روز شود. بدون مکانیزم، ممکن است قدیمی بماند.

### مشکل ۵: `AI_Workspace_Framework_v1` با واقعیت تطابق ندارد
این سند ساختاری را توصیف می‌کند که وجود ندارد (`AI/core/`, `AI/governance/`, `AI/projects/rasti/`). Agent‌های جدیدی که این سند را می‌خوانند ممکن است گیج شوند.

---

## توصیه‌های مشخص

### ۱. گزارش‌های تکمیل‌شده را بنویسید (اولویت فوری)

برای درخواست‌های ۰۰۳ و ۰۰۴ که پاسخ گرفته‌اند:
```
AI/REPORTS/2026-06-28_003_FINANCIAL_CORE_AUDIT.md
AI/REPORTS/2026-06-28_004_PRODUCTION_READINESS.md
AI/REPORTS/2026-07-01_001_DOCUMENTATION_REBUILD.md  ← این حسابرسی
```

### ۲. درخواست ۰۰۱ را به‌عنوان تکمیل‌شده علامت بزنید

این حسابرسی (`99_AUDIT_2026_06_30/`) پاسخ `AI/REQUESTS/001_REBUILD_DOCUMENTATION.md` است. وضعیت آن باید به "DONE" تغییر کند.

### ۳. `CURRENT_MISSION.md` را update کنید

پس از این حسابرسی، mission جدید باید منعکس شود:
- **انجام شده:** audit کامل مستندات
- **بعدی:** رفع ۷ مشکل حیاتی، نوشتن تست‌های isolation، deployment runbook

### ۴. `AI_Workspace_Framework_v1` را با کاوشن علامت بزنید

یک تذکر در ابتدای سند اضافه کنید:
```
> **توجه:** این سند یک vision آینده است و ساختار فعلی را توصیف نمی‌کند.
> ساختار فعلی docs/AI/ با ساختار پیشنهادی این سند متفاوت است.
```

### ۵. یک "single source of truth" برای قوانین تجاری تعیین کنید

**پیشنهاد:** `docs/03_Business/` منبع اصلی است. `AI/KNOWLEDGE/` نسخه خلاصه‌شده است.  
هر تغییر در `03_Business/` باید یک تغییر متناظر در `AI/KNOWLEDGE/` داشته باشد.

### ۶. درخواست ۰۰۲ را بازبینی کنید

`AI/REQUESTS/002_PRODUCT_BACKLOG.md` ۱۶ مشکل UI/UX فهرست کرده. برخی احتمالاً حل شده‌اند (Communication Matrix). یک session برای بررسی وضعیت هر مورد لازم است.

---

## مستنداتی که باید در AI Workspace بمانند

| فایل | دلیل نگه‌داری |
|---|---|
| `AI/README.md` | ورودی — ضروری |
| `AI/SKILL.md` (در 00_Project) | قرارداد اصلی AI |
| `AI/PROJECT_KNOWLEDGE.md` | خلاصه تجاری برای AI |
| `AI/POLICIES/` | سیاست‌های کاری |
| `AI/PROMPTS/` | template‌های prompt |
| `AI/KNOWLEDGE/` | دانش تجاری خلاصه‌شده |
| `AI/STANDARDS/` | استانداردهای فنی |
| `AI/WORKFLOWS/` | workflow عملیاتی |

---

## نتیجه‌گیری

AI Workspace راستی از لحاظ نهادینه‌سازی دانش پروژه در فایل‌های مستند بسیار پیشرفته است. تنها مشکل اصلی **نبود گزارش‌های تکمیل‌شده** و **عدم به‌روزرسانی CURRENT_MISSION** پس از تغییر اولویت‌هاست. با رفع این نواقص، workspace به سطح آماده‌به‌کار خوبی می‌رسد.
