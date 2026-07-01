# ۰۶ — برنامه بازسازی مستندات

**تاریخ:** ۳۰ ژوئن ۲۰۲۶  
**روش:** خواندن ۱۲۱ فایل مستند + مقایسه با کد

---

## وضعیت فعلی مستندات

- **تعداد کل فایل:** ۱۲۱ فایل مستند
- **کیفیت محتوا:** ۸/۱۰ — بخش‌های ADR و Business Rules بسیار خوب
- **سازماندهی:** ۶/۱۰ — ساختار RDOS خوب اما با redundancy و تضادهای مسیر
- **به‌روزبودن:** ۵/۱۰ — چندین فایل به مسیرهای قدیمی ارجاع می‌دهند

---

## دسته‌بندی همه فایل‌های مستند

### 🗃️ بایگانی (ARCHIVE) — باید به `docs/archive/` منتقل شوند

| فایل | دلیل |
|---|---|
| `docs/Rasti_Master_Roadmap_FA.md` | نسخه فارسی منسوخ از PROJECT_ROADMAP_2026-2030 |
| `docs/Rasti_Production_Readiness_Audit_Review_FA.md` | تکراری با MASTER_PROJECT_AUDIT (نسخه فارسی)؛ مسیر قدیمی |
| `docs/Rasti_Scalability_Roadmap_FA.md` | تکراری با FUTURE_PLATFORM_RECOMMENDATIONS |
| `docs/DEPLOYMENT_GUIDE_TASK_007A.md` | راهنمای task-specific، نه عمومی |
| `docs/00_Project/PROJECT_STATUS_FA.md` | تضاد مستقیم با واقعیت (ادعای حذف تست‌ها) |
| `docs/00_Project/START_HERE_FA.md` | مسیر قدیمی (`D:\mySaaSsite`)، منسوخ |
| `docs/00_Project/README_FAST_DEV.md` | مسیر قدیمی (`C:\Projects\saaSwebsite`) |
| `docs/00_Project/COPY_INSTRUCTIONS.md` | برای نصخه `5 tir`، منسوخ |
| `docs/06_Phases/PHASE_01_FOUNDATION.md` | وظایف کامل شده |
| `docs/06_Phases/ROADMAP.md` | ۴ خط خلاصه، جایگزین شده با PROJECT_ROADMAP_2026-2030 |

### ✏️ بازنویسی (REWRITE) — اصلاح لازم دارند

| فایل | مشکل | راه‌حل |
|---|---|---|
| `docs/00_Project/SMOKE_CHECKLIST_FA.md` | مسیر قدیمی | update مسیر، update URL‌ها |
| `docs/02_Development_System/CLAUDE_READINESS_PROMPT.md` | مسیر قدیمی (`5 tir`) | update مسیر |
| `docs/06_Phases/PHASE_02_PAYMENT.md` | برخی task‌ها انجام شده | update وضعیت task‌ها |
| `docs/07_ADR/ADR-006-*.md` §۲ | ادعا "service هنوز پیاده‌سازی نشده" اما کد وجود دارد | update این بند |

### ✅ نگه‌دار (KEEP) — معتبر و مفید

**docs/00_Project/ (نگه‌دار):**
- `PROJECT_VISION.md`, `PROJECT_SCOPE.md`, `PROJECT_PRINCIPLES.md`
- `GLOSSARY.md`, `TERMINOLOGY.md`, `SKILL.md`
- `MASTER_PROJECT_AUDIT_2026-06-28.md`
- `FINANCIAL_CORE_FINAL_AUDIT_2026-06-28.md`
- `FUTURE_PLATFORM_RECOMMENDATIONS_2026-06-28.md`
- `PROJECT_BACKLOG_2026-06-28.md`
- `PROJECT_ROADMAP_2026-2030.md`

**docs/01_Architecture/ (همه نگه‌دار)**

**docs/02_Development_System/ (همه نگه‌دار جز CLAUDE_READINESS_PROMPT که باید rewrite شود)**

**docs/03_Business/ (همه نگه‌دار)**

**docs/04_Testing/ (همه نگه‌دار)**

**docs/05_Deployment/ (همه نگه‌دار)**

**docs/07_ADR/ (همه نگه‌دار)**

**docs/AI/ (همه نگه‌دار با تذکر):**
- `AI_Workspace_Framework_v1_Architecture_Report_EN.md` — نگه‌دار با flag "این یک vision است، نه واقعیت فعلی"

**docs/rasti_audit_outputs/ (همه نگه‌دار)**

**docs/archive/ (همه نگه‌دار)**

---

## فایل‌های کاملاً جدید که باید ایجاد شوند

### اولویت بالا (پیش از تولید)

| فایل | محتوا | جایگاه |
|---|---|---|
| `docs/05_Deployment/DEPLOYMENT_RUNBOOK.md` | راهنمای گام‌به‌گام استقرار: migrate، collectstatic، gunicorn، verify | `docs/05_Deployment/` |
| `docs/05_Deployment/OPERATIONAL_RUNBOOKS.md` | runbook‌های عملیاتی: کردیت SMS، backfill مالی، reconciliation | `docs/05_Deployment/` |
| `docs/00_Project/ONBOARDING.md` | onboarding توسعه‌دهنده: setup، دموی داده، اجرای تست | `docs/00_Project/` |

### ADR‌های جدید (اولویت بالا)

| ADR | موضوع | چرا لازم است |
|---|---|---|
| `ADR-009-Refund-Policy.md` | سیاست استرداد و برگشت فاکتور | قبل از هر کار روی refund ضروری است |
| `ADR-010-Subscription-Lifecycle.md` | چرخه حیات اشتراک مستأجر | قبل از توسعه billing |
| `ADR-011-Platform-Fee-All-Methods.md` | کارمزد پلتفرم برای نقد/آفلاین | سیاست فعلی فقط برای online مستند شده |
| `ADR-ORDER-STATE-MACHINE.md` | machine state سفارش رسمی | تمام انتقال‌ها را مستند کند |

---

## مشکلات تکرار (Redundancy) که باید حل شوند

### خوشه ۱: رودمپ‌های متعدد
- **نگه‌دار:** `00_Project/PROJECT_ROADMAP_2026-2030.md`
- **بایگانی:** `Rasti_Master_Roadmap_FA.md`, `06_Phases/ROADMAP.md`
- **بررسی:** `Rasti_Scalability_Roadmap_FA.md` (محتوای unique دارد؟)

### خوشه ۲: راهنماهای توسعه محلی
- **نگه‌دار و update:** `00_Project/SMOKE_CHECKLIST_FA.md`
- **بایگانی:** `00_Project/START_HERE_FA.md`, `00_Project/README_FAST_DEV.md`

### خوشه ۳: مستندات AI/KNOWLEDGE در مقابل docs/03_Business
- **تصمیم:** هر دو نگه‌دار — دو مخاطب متفاوت (AI agent vs انسان)
- **قانون:** هر تغییر در `03_Business` باید در `AI/KNOWLEDGE` هم اعمال شود

### خوشه ۴: template‌های تکراری بین 02_Development_System و AI/PROMPTS
- TASK_TEMPLATE.md ≈ IMPLEMENT_TEMPLATE.md
- REVIEW_TEMPLATE.md ≈ AI/PROMPTS/REVIEW_TEMPLATE.md
- BUG_REPORT_TEMPLATE.md ≈ AI/PROMPTS/BUG_FIX_TEMPLATE.md
- **توصیه:** اول بررسی کنید آیا یکی به دیگری ارجاع می‌دهد؛ در صورت تکرار کامل، یکی را به‌عنوان primary تعیین کنید

---

## اصلاح تضادهای docstring در کد

| فایل | خط | مشکل | راه‌حل |
|---|---|---|---|
| `apps/tenants/models.py` | ۲۸۴-۲۹۰ | "Order با status NEW ایجاد می‌شود" | تغییر به "Order با status PENDING_REVIEW ایجاد می‌شود" |
| `docs/07_ADR/ADR-006-*.md` | §۲ | "service هنوز پیاده‌سازی نشده" | update به "service در services_statement.py پیاده‌سازی شده" |
| `docs/03_Business/ORDER_RULES.md` | برچسب WAITING | "در انتظار انجام خدمت" | تبدیل به "در انتظار" یا اصلاح کد |

---

## برنامه زمانی پیشنهادی

### هفته ۱
- [ ] بایگانی ۱۰ فایل مشخص‌شده در جدول بالا
- [ ] اصلاح docstring در `apps/tenants/models.py:284`
- [ ] اصلاح `docs/07_ADR/ADR-006-*.md` §۲
- [ ] اصلاح `docs/02_Development_System/CLAUDE_READINESS_PROMPT.md` (مسیر)
- [ ] اصلاح `docs/00_Project/SMOKE_CHECKLIST_FA.md` (مسیر)

### هفته ۲-۳
- [ ] نوشتن `DEPLOYMENT_RUNBOOK.md`
- [ ] نوشتن `OPERATIONAL_RUNBOOKS.md`
- [ ] نوشتن `ONBOARDING.md`

### ماه ۲
- [ ] نوشتن ADR-009 (Refund)
- [ ] نوشتن ADR-010 (Subscription)
- [ ] نوشتن ADR-011 (Platform Fee All Methods)
- [ ] نوشتن ADR-ORDER-STATE-MACHINE

---

## مستنداتی که باید ایجاد شوند در AI/REPORTS

طبق `AI/REPORTS/README.md`، هر request تکمیل‌شده باید یک گزارش در `AI/REPORTS/` داشته باشد. در حال حاضر هیچ گزارش تکمیل‌شده‌ای وجود ندارد. درخواست‌های ۰۰۳ و ۰۰۴ پاسخ گرفته‌اند اما گزارشی ثبت نشده است.

**اقدام:** پس از تکمیل هر درخواست در `AI/REQUESTS/`، یک گزارش با قالب `AI/REPORTS/REPORT_TEMPLATE.md` ایجاد شود.
