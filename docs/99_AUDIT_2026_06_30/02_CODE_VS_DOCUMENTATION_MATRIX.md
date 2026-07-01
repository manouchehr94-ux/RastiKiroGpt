# ۰۲ — ماتریس مقایسه کد با مستندات

**تاریخ:** ۳۰ ژوئن ۲۰۲۶  
**روش:** بررسی مستقیم کد منبع + خواندن همه فایل‌های مستندات

---

## راهنمای طبقه‌بندی

| کد | معنی |
|---|---|
| ✅ VALID | مستند صحیح و با کد همخوان |
| ⚠️ OUTDATED | قدیمی یا منسوخ |
| ❌ CONFLICT | تضاد مستقیم با کد یا مستند دیگر |
| 📋 DOCUMENTED_NOT_IMPLEMENTED | در مستند هست، در کد نیست |
| 🔍 IMPLEMENTED_NOT_DOCUMENTED | در کد هست، در مستند نیست |
| ❓ UNKNOWN | نیازمند بررسی بیشتر |

---

## بخش الف: قوانین تجاری (docs/03_Business/)

### `ORDER_RULES.md`

| ادعای مستند | وضعیت | شواهد کد |
|---|---|---|
| سفارش عمومی → PENDING_REVIEW | ✅ VALID | `tenants/services.py:177` — `status=Order.Status.PENDING_REVIEW` |
| سفارش اپراتور بدون تکنسین → NEW | ✅ VALID | `orders/services.py:642,778` |
| سفارش اپراتور با تکنسین → WAITING | ✅ VALID | `orders/services.py:777-780` |
| تکنسین قبول کرد → WAITING | ✅ VALID | `orders/services.py:938-944` (TechnicianAcceptService) |
| تکنسین شروع کرد → IN_PROGRESS | ✅ VALID | `orders/services.py:1082-1085` (ALLOWED_TRANSITIONS) |
| تکنسین تکمیل کرد → DONE | ✅ VALID | `orders/services.py:186-238` (OrderCompleteService) |
| لغو → CANCELLED | ✅ VALID | `orders/cancel_review_service.py:52-53` |
| دسته‌بندی اجباری | ❌ CONFLICT | مستند می‌گوید اجباری است؛ `Order.service_category` در model با `null=True,blank=True` تعریف شده (`orders/models.py:112-118`). اجباری فقط در service layer است نه model level |
| برچسب فارسی WAITING: "در انتظار انجام خدمت" | ❌ CONFLICT | `fa_labels.py` و dashboard از "در انتظار" استفاده می‌کنند نه "در انتظار انجام خدمت" |
| مدل CancellationRequest جداگانه | ❌ CONFLICT | چنین مدلی وجود ندارد. وضعیت `CANCEL_REQUESTED` در `Order.status` ذخیره می‌شود |

### `INVOICE_RULES.md`

| ادعای مستند | وضعیت | شواهد کد |
|---|---|---|
| DRAFT → ISSUED → PAID | ✅ VALID | `invoices/models.py:31-35` |
| PAID قابل ویرایش نیست | ✅ VALID | `invoices/services.py:209` |
| settlement_at تغییرناپذیر | ✅ VALID | `invoices/services.py:321` + model save override |
| یک فاکتور فعال در هر سفارش | ✅ VALID | DB UniqueConstraint `invoices/models.py:198-203` |
| تخفیف campaign → شرکت | ✅ VALID | `services_settlement.py:35` (DiscountPolicy.COMPANY default) |

### `PAYMENT_RULES.md`

| ادعای مستند | وضعیت | شواهد کد |
|---|---|---|
| ۴ شرط برای کارمزد پلتفرم | ✅ VALID | `services_platform_fee.py:162-177` — همه ۴ شرط enforce شده |
| NEEDS_RECONCILIATION برای مبهم | ✅ VALID | `payments/services.py:247-295` |
| شرکت نمی‌تواند payment mode را فعال کند | ✅ VALID | `@require_platform_owner` روی view مربوطه |

### `NOTIFICATION_RULES.md`

| ادعای مستند | وضعیت | شواهد کد |
|---|---|---|
| اطلاع‌رسانی پس از تأیید پرداخت | ✅ VALID | `notifications/signals.py` از `Invoice.post_save` trigger می‌شود |
| ایزولاسیون بین مستأجران | ✅ VALID | `Notification.company` FK در همه queriesها |

### `SMS_RULES.md`

| ادعای مستند | وضعیت | شواهد کد |
|---|---|---|
| Footer "لغو ۱۱" | ❌ CONFLICT | `sms_footer.py` تعریف شده اما هرگز در pipeline فراخوانی نمی‌شود (`services.py:421-489` مشخصاً `ensure_sms_footer` را نمی‌فراخواند) |
| جلوگیری از تکرار SMS | ✅ VALID | `services.py:469-478` — dedup check روی status=QUEUED |

---

## بخش ب: معماری (docs/01_Architecture/)

### `MULTI_TENANT.md`

| ادعای مستند | وضعیت | شواهد کد |
|---|---|---|
| هرگز بدون company filter query نزنید | ✅ VALID (اکثر موارد) | `orders/selectors.py` — همه queriesها company-scoped |
| 🔍 استثنا: `platform_core/views_merchant_profile.py:134` | ❌ CONFLICT | `CompanyMerchantProfile.objects.get(id=profile_id)` بدون company scope (اما تحت `@require_platform_owner`) |
| `request.company` از middleware | ✅ VALID | `tenants/middleware.py:73` |

### `PERMISSIONS.md`

| ادعای مستند | وضعیت | شواهد کد |
|---|---|---|
| COMPANY_ADMIN نمی‌تواند payment mode فعال کند | ✅ VALID | `@require_platform_owner` روی views مربوطه |
| COMPANY_STAFF نقش اپراتور دارد | ✅ VALID | `UserRole.COMPANY_STAFF` در `accounts/models.py:32` |

### `SERVICE_LAYER.md`

| ادعای مستند | وضعیت | شواهد کد |
|---|---|---|
| منطق تجاری فقط در services | ✅ VALID (اکثر موارد) | همه سرویس‌ها از `@transaction.atomic` استفاده می‌کنند |
| 🔍 استثنا: `orders/views.py:339` | ❌ CONFLICT | `Order.objects.filter(...)` مستقیماً در view (نه selector) |

---

## بخش ج: ADRها (docs/07_ADR/)

| ADR | وضعیت پیاده‌سازی | شواهد |
|---|---|---|
| ADR-001: Rasti یک SaaS provider است | ✅ IMPLEMENTED | همه مدل‌ها، URLs، و billing architecture |
| ADR-002: CompanyPaymentSettings مالک activation | ✅ IMPLEMENTED | `payments/services.py:115-131` |
| ADR-003: معماری PaymentGateway | ✅ IMPLEMENTED | `PaymentGateway.owner_type` + `PlatformFeeService` |
| ADR-004: نظم دفتر‌کل | ✅ IMPLEMENTED | `TechnicianLedgerEntry.delete()` + `save()` overrides |
| ADR-005: قیمت‌گذاری خدمت تکنسین | ✅ IMPLEMENTED | `TechnicianServiceRate` + `TechnicianWagePostingService` |
| ADR-006: معماری دفتر‌کل و صورت‌حساب | ✅ IMPLEMENTED (جزئی) | `services_statement.py` کامل است؛ `metadata_version` در invoice entries گم است |
| ADR-007: خط زمانی رویدادهای مالی | ✅ IMPLEMENTED | همه ۱۰ رویداد قابل ردیابی در کد |
| ADR-008: سیاست بازیابی مالی | ✅ IMPLEMENTED | `FinancialBackfillTask` + `FinancialBackfillService` |

---

## بخش د: تضادهای مستندات با یکدیگر

| مستند الف | مستند ب | نوع تضاد |
|---|---|---|
| `00_Project/PROJECT_STATUS_FA.md`: "تست‌ها حذف شدند" | `rasti_audit_outputs/PROJECT_METRICS_2026-06-28.md`: ۸۳ فایل تست | ❌ CONFLICT |
| `00_Project/START_HERE_FA.md`: مسیر `D:\mySaaSsite` | مسیر واقعی: `D:\SaaSprojectService\Rasti chekFinal 10 tir` | ❌ CONFLICT |
| `06_Phases/ROADMAP.md`: ۴ فاز | `00_Project/PROJECT_ROADMAP_2026-2030.md`: ۷ فاز | ❌ CONFLICT |
| `Rasti_Master_Roadmap_FA.md`: ساختار docs پیشنهادی | ساختار docs واقعی | ❌ CONFLICT |
| `tenants/models.py:284-290` docstring: "Order با status NEW ایجاد می‌شود" | `tenants/services.py:177`: `status=PENDING_REVIEW` | ❌ CONFLICT |
| ADR-006 §۲: "service هنوز پیاده‌سازی نشده" | `services_statement.py` کامل است | ❌ CONFLICT (ADR قدیمی‌تر از کد) |

---

## بخش ه: پیاده‌سازی‌های فاقد مستند (IMPLEMENTED_NOT_DOCUMENTED)

| ویژگی | محل کد | مستند موجود؟ |
|---|---|---|
| `TechnicianCategorySkill` و priority-based visibility | `accounts/models.py:220-259`, `orders/eligibility.py` | 🔍 در ADR-005 اشاره ندارد |
| `auto_recycle_cancel_request` در CompanySettings | `tenants/models.py:265-268` | 🔍 مستند نشده |
| `OrderCustomField` و `OrderCustomFieldValue` | `tenants/models.py:635-709` | 🔍 فقط در MASTER_PROJECT_AUDIT اشاره کوتاه |
| `PasswordResetSMSBillingPolicy` (چه کسی پول پیامک بازیابی رمز را می‌دهد) | `accounts/models.py:405-461` | 🔍 مستند نشده |
| `OrderNotificationDispatchMiddleware` | `orders/middleware.py` | 🔍 مستند نشده |
| SMS Inbox (پیامک‌های دریافتی) | `sms/models_inbox.py` | 🔍 فقط اشاره کوتاه در SMS_RULES |
| `PlatformSMSMessageTypeSetting` | `platform_core/models.py` | 🔍 مستند نشده |

---

## بخش و: موارد مستندشده اما پیاده‌سازی نشده (DOCUMENTED_NOT_IMPLEMENTED)

| ویژگی | مستند | وضعیت کد |
|---|---|---|
| محدودیت‌های Plan (max_users, max_technicians) | `platform_core/models.py:22-24` | وجود دارند اما enforce نمی‌شوند |
| ارائه‌دهندگان PSP واقعی (ZarinPal، IDPay، NextPay) | `payments/models.py` gateway_type choices | فقط `providers/fake.py` کامل است |
| Footer "لغو ۱۱" در همه پیامک‌ها | `SMS_RULES.md`, `sms_footer.py` | تابع تعریف شده اما فراخوانی نمی‌شود |
| چرخه حیات billing اشتراک | `06_Phases/PHASE_02_PAYMENT.md` | `billing/services.py` stub است |
| ADR-009 تا ADR-012 | ذکر در backlog | هیچ ADR‌ای ننوشته شده |
| گزارش‌های تکمیل‌شده در `AI/REPORTS/` | `AI/REPORTS/README.md` می‌گوید باید باشند | هیچ گزارشی وجود ندارد |
| کامنت‌های تغییر template از شرکت | `platform_core/views_tenant_comm_settings.py:792` | Submit button حذف شده |

---

## خلاصه آماری

| دسته | تعداد |
|---|---|
| ✅ VALID | ۳۲ مورد |
| ❌ CONFLICT | ۱۴ مورد |
| 📋 DOCUMENTED_NOT_IMPLEMENTED | ۷ مورد |
| 🔍 IMPLEMENTED_NOT_DOCUMENTED | ۷ مورد |
| ❓ UNKNOWN | ۲ مورد |
