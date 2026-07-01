# ۰۳ — حسابرسی قوانین تجاری

**تاریخ:** ۳۰ ژوئن ۲۰۲۶  
**روش:** بررسی مستقیم کد منبع و مقایسه با مستندات تجاری

---

## الف — چرخه عمر سفارش

### ۱. وضعیت‌های سفارش (Order.Status)

کد واقعی (`apps/orders/models.py:25-32`):

| کد DB | برچسب انگلیسی (Model) | معادل فارسی رایج |
|---|---|---|
| `pending_review` | Pending Review | در انتظار بررسی اپراتور |
| `new` | New | جدید |
| `waiting` | Waiting | در انتظار |
| `in_progress` | In Progress | در حال انجام |
| `done` | Done | انجام شده |
| `cancel_requested` | Cancel Requested | درخواست لغو |
| `cancelled` | Cancelled | لغو شده |

**⚠️ تضاد با مستند:** `docs/03_Business/ORDER_RULES.md` از "در انتظار انجام خدمت" برای WAITING استفاده می‌کند. کد فعلی از "در انتظار" استفاده می‌کند.

---

### ۲. مسیرهای ایجاد سفارش

#### مسیر ۱: فرم عمومی مشتری (`/ُ<company_code>/request/`)
- **سرویس:** `tenants/services.py:ServiceRequestCreateService.create()`
- **وضعیت اولیه:** `PENDING_REVIEW` (`services.py:177`)
- **دسته‌بندی:** اجباری — `raise ValueError("دسته‌بندی خدمات الزامی است.")` (`services.py:164-165`)
- **اطلاع‌رسانی تکنسین:** ❌ ارسال نمی‌شود (تا زمان تأیید اپراتور)
- **✅ قانون کسب‌وکار ۲ رعایت شده**

#### مسیر ۲: پنل ادمین/اپراتور
- **سرویس:** `orders/services.py:OrderCreateByAdminService.create()`
- **وضعیت اولیه بدون تکنسین:** `NEW` (`services.py:751,778`)
- **وضعیت اولیه با تکنسین:** `WAITING` (`services.py:777-780`)
- **دسته‌بندی:** اجباری — `raise ValueError("دسته‌بندی خدمات الزامی است.")` (`services.py:718-719`)
- **✅ قوانین کسب‌وکار ۳ و ۴ رعایت شده**

#### مسیر ۳: Legacy (منسوخ)
- **سرویس:** `orders/services.py:OrderCreateService.create()`
- **وضعیت:** همیشه `NEW`
- **⚠️ نقص:** دسته‌بندی را اجباری نمی‌داند

---

### ۳. انتقال‌های وضعیت

#### PENDING_REVIEW → NEW (تأیید اپراتور)
- **سرویس:** `orders/services.py:OrderUpdateService.update()` خطوط ۴۸۴-۴۸۶
- **محرک:** وقتی ادمین از طریق edit form وضعیت را تغییر می‌دهد
- **پس از تأیید:** `dispatch_order_available_events()` فراخوانی می‌شود
- **⚠️ نقص:** `set_missing_priority_visibility_times()` در این مسیر فراخوانی نمی‌شود. سفارش‌های عمومی که از PENDING_REVIEW → NEW می‌روند ممکن است `priority2_visible_at` و `priority3_visible_at` تنظیم نشده داشته باشند.

#### NEW → WAITING (قبول تکنسین)
- **قبول توسط ادمین:** `orders/services.py:OrderAssignService.assign()` خطوط ۵۰۳-۵۶۸
- **قبول توسط تکنسین:** `orders/services.py:TechnicianAcceptService.accept()` خطوط ۸۲۹-۹۵۸
- **بررسی ظرفیت:** حداکثر تعداد سفارش فعال از `CompanySettings.max_active_orders_per_technician` (`services.py:897-905`)
- **بررسی اولویت زمانی:** priority1 فوری، priority2 پس از delay، priority3 پس از delay طولانی‌تر
- **✅ قانون کسب‌وکار ۵ (تخصیص = قبولی) رعایت شده**

#### WAITING → IN_PROGRESS (شروع کار)
- **سرویس:** `orders/services.py:TechnicianStatusUpdateService.update_status()`
- **انتقال مجاز:** `ALLOWED_TRANSITIONS[WAITING] = [IN_PROGRESS, CANCEL_REQUESTED]` (`services.py:1082-1085`)
- **اطلاع‌رسانی:** `_emit_order_notification_event("order_started", ...)` (`services.py:1175`)
- **✅ قانون کسب‌وکار ۶ رعایت شده**

#### IN_PROGRESS → DONE (تکمیل)
- **سرویس:** `orders/services.py:OrderCompleteService.complete()` خطوط ۱۶۳-۲۳۸
- **اقدامات جانبی:** ارسال اجرت تکنسین، ایجاد پیش‌نویس فاکتور
- **✅ قانون کسب‌وکار ۷ رعایت شده**

#### → CANCEL_REQUESTED (درخواست لغو)
- **از هر وضعیت (NEW/WAITING/IN_PROGRESS):** `orders/services.py:OrderCancelService.request_cancel()` خطوط ۲۶۶-۳۱۲
- **توسط تکنسین هم:** از طریق `TechnicianStatusUpdateService`
- **✅ قانون کسب‌وکار ۸ رعایت شده**

#### CANCEL_REQUESTED → CANCELLED (تأیید لغو)
- **سرویس:** `orders/cancel_review_service.py:OrderCancelReviewService.approve()` خطوط ۲۴-۶۹
- **اجرا توسط:** فقط COMPANY_ADMIN یا COMPANY_STAFF (بررسی view-level)
- **✅ قانون کسب‌وکار ۸ (فقط ادمین/اپراتور با مجوز) رعایت شده**

#### CANCEL_REQUESTED → بازگشت به وضعیت قبل (رد لغو)
- **سرویس:** `orders/cancel_review_service.py:OrderCancelReviewService.reject()` خطوط ۷۱-۱۵۹
- **منطق:** `OrderStatusLog` را می‌خواند تا `old_status` قبل از درخواست لغو را بیابد

#### WAITING → NEW (حذف تکنسین)
- **سرویس:** `orders/services.py:OrderUnassignService.unassign()` خطوط ۵۸۰-۶۰۸
- **محافظت:** اگر فاکتور فعال وجود داشته باشد، مسدود می‌شود
- **پس از حذف:** `dispatch_order_available_events()` فراخوانی می‌شود (تکنسین‌ها مجدد می‌بینند)
- **✅ قانون کسب‌وکار ۱۰ رعایت شده**

---

### ۴. مدیریت دسته‌بندی خدمات

| قانون | وضعیت | شواهد کد |
|---|---|---|
| دسته‌بندی در مسیر ادمین اجباری | ✅ | `orders/services.py:718-719` |
| دسته‌بندی در مسیر عمومی اجباری | ✅ | `tenants/services.py:164-165` |
| دسته‌بندی در سطح مدل اجباری | ❌ | `orders/models.py:112-118` — `null=True,blank=True` |
| دسته‌بندی غیرفعال رد می‌شود | ✅ | `services.py:715-718` — `is_active=True` در filter |
| دسته‌بندی شرکت دیگر رد می‌شود | ✅ | `services.py:715` — `company=company` در filter |
| تکنسین باید مهارت دسته‌بندی داشته باشد | ✅ | `services.py:887-894` (TechnicianCategorySkill check) |

---

## ب — صورتحساب (Invoice)

### چرخه حیات

```
DRAFT → ISSUED → PAID (terminal)
DRAFT → CANCELLED (terminal)
ISSUED → CANCELLED (terminal)
```

### قوانین محافظت

| قانون | وضعیت | شواهد کد |
|---|---|---|
| PAID قابل ویرایش نیست | ✅ | `invoices/services.py:209` |
| PAID قابل recalculate نیست | ✅ | `invoices/models.py:256-259` |
| PAID قابل لغو نیست | ✅ | `invoices/services.py:293` + `services_cancel_request.py:84` |
| settlement_at تغییرناپذیر است | ✅ | `invoices/services.py:321` |
| یک فاکتور فعال در هر سفارش | ✅ | UniqueConstraint در `invoices/models.py:198-203` |
| مبلغ پرداخت باید با فاکتور برابر باشد | ✅ | `invoices/services.py:329` |

---

## ج — پرداخت

### قوانین پلتفرم

**شرایط کارمزد پلتفرم** — همه ۴ شرط باید برقرار باشند (`services_platform_fee.py:162-177`):
1. پرداخت موفق و تأییدشده (status=PAID)
2. از طریق درگاه پلتفرم (gateway.owner_type=PLATFORM)
3. درصد کارمزد > 0 (CompanyFinancialPolicy.platform_fee_percent)
4. تکنسین تأییدشده مالی (financial_verification_status=verified)

**✅ تمام ۴ شرط در کد enforce شده‌اند.**

---

## د — نقش‌ها و مجوزها

### ماتریس دسترسی (از کد)

| عملیات | PLATFORM_OWNER | COMPANY_ADMIN | COMPANY_STAFF | TECHNICIAN | CUSTOMER |
|---|---|---|---|---|---|
| مشاهده سفارشات | — | ✅ همه | ✅ همه | ✅ فقط خودی | ✅ فقط خودی |
| ایجاد سفارش | — | ✅ | ✅ | ❌ | ❌ |
| تخصیص تکنسین | — | ✅ | ✅ | ❌ | ❌ |
| شروع کار | — | ✅ | ✅ | ✅ (سفارش خودش) | ❌ |
| تکمیل | — | ✅ | ✅ | ✅ (سفارش خودش) | ❌ |
| تأیید لغو | — | ✅ | ✅ | ❌ (فقط درخواست) | ❌ (فقط درخواست) |
| مشاهده فاکتور | — | ✅ | ✅ | ✅ فقط خودی | ✅ فقط خودی |
| ایجاد فاکتور | — | ✅ | ✅ | ✅ از سفارش خودش | ❌ |

---

## ه — نواقص قوانین تجاری

### نقص ۱: `priority_visibility_times` تنظیم نمی‌شود پس از PENDING_REVIEW → NEW
**شواهد:** `eligibility.py:set_missing_priority_visibility_times()` زمانی که `order.status != NEW` است فوراً `return` می‌کند. اما `OrderUpdateService.update()` (`services.py:484-486`) پس از انتقال PENDING_REVIEW → NEW این تابع را فراخوانی نمی‌کند.  
**تأثیر:** سفارش‌های عمومی که از PENDING_REVIEW به NEW می‌روند ممکن است `priority2_visible_at=NULL` داشته باشند و رفتار visibility نامعلوم باشد.

### نقص ۲: سفارش PENDING_REVIEW می‌تواند مستقیماً تخصیص دریافت کند
**شواهد:** `OrderAssignService.assign()` (`services.py:532`) وضعیت‌های `[NEW, PENDING_REVIEW]` را قبول می‌کند.  
**تأثیر:** ادمین می‌تواند تکنسین را به سفارشی که هنوز تأیید نشده تخصیص دهد — رفتاری که ممکن است ناخواسته باشد.

### نقص ۳: اطلاع‌رسانی `ORDER_CANCEL_REQUESTED_CUSTOMER` هیچ‌گاه ارسال نمی‌شود
**شواهد:** رویداد در `event_catalog.py` تعریف شده اما هیچ `NotificationEventService.emit(ORDER_CANCEL_REQUESTED_CUSTOMER, ...)` در `orders/services.py` یافت نشد.

### نقص ۴: `ORDER_CANCELLED` پیام نهایی ارسال نمی‌شود
**شواهد:** در `orders/services.py:357` به‌عنوان رشته در لیست ذکر شده اما هیچ emit فعالی در `force_cancel()` یا `cancel_review_service.py` وجود ندارد که این رویداد را به سیستم اطلاع‌رسانی ارسال کند.

### نقص ۵: ارائه‌دهندگان واقعی PSP پیاده‌سازی نشده‌اند
**شواهد:** `payments/providers/` فقط `base.py`, `fake.py`, `registry.py` دارد. انواع درگاه ZARINPAL، IDPAY، NEXTPAY در مدل تعریف شده‌اند اما هیچ کلاس provider واقعی وجود ندارد.  
**تأثیر:** پرداخت آنلاین واقعی کار نمی‌کند.
