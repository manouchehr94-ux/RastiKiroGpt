# ۰۶ — مشکلات ناوبری و ریسک‌ها

**مبنا:** بررسی مستقیم URL‌ها، view‌ها، قالب‌های ناوبری، و decorator‌ها  
**تاریخ:** ۱ ژوئیه ۲۰۲۶

---

## ۱. مشکلات امنیتی (Critical)

### مشکل ۱ — `admin_operator_list` بدون decorator امنیتی

**شدت:** 🔴 بحرانی (P0-1)  
**فایل:** `apps/tenants/views_admin.py:2125`  
**URL:** `/<code>/admin/settings/operators/`

```python
# بدون هیچ @require_tenant_role یا @require_tenant_auth
def admin_operator_list(request, **kwargs):
    company = request.company
    ...
```

**ریسک:**
- هر بازدیدکننده احراز هویت‌نشده می‌تواند به صفحه مدیریت اپراتورها دسترسی داشته باشد
- `OperatorPermissionMiddleware` در `operator_access.py:764` کاربران ناشناس را رد می‌کند اما `is_company_admin()` فقط نقش را بررسی می‌کند نه عضویت در شرکت
- **نقص cross-tenant:** مدیر شرکت A می‌تواند اپراتورهای شرکت B را مدیریت کند

**مقایسه با view مشابه:**
```python
# admin_operator_create — درست است (دارای decorator)
@require_tenant_role("COMPANY_ADMIN")
@require_tenant_role("COMPANY_ADMIN")  # ← اما duplicate بیهوده
def admin_operator_create(request, **kwargs):
```

---

### مشکل ۲ — JWT Logout کارنمی‌کند

**شدت:** 🔴 بحرانی (P0-2)  
**فایل:** `apps/api/auth_views.py:152-166`  
**URL:** `/api/auth/logout/`

```python
class LogoutAPI(APIView):
    def post(self, request):
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()  # AttributeError — blacklist app نصب نیست
        except Exception:      # همه خطاها بلعیده می‌شوند
            pass
        return Response({"message": "Logged out."})  # HTTP 200 ولی token هنوز معتبر است
```

**ریسک:** کاربران API که logout می‌کنند token‌شان همچنان معتبر است.

---

## ۲. صفحات بدون لینک در ناوبری (Orphan Pages)

### صفحات ادمین بدون لینک مستقیم در sidebar

موارد زیر در sidebar ادمین وجود ندارند اما URL معتبر دارند:

| URL | مشکل |
|-----|-------|
| `/<code>/admin/financial-reports/summary/` | در sidebar نیست — باید از URL مستقیم برود |
| `/<code>/admin/financial-reports/technicians/` | صرفاً از طریق nav financial reports |
| `/<code>/admin/payments/gateway-reconciliation/` | هیچ لینکی در sidebar وجود ندارد |
| `/<code>/admin/reports/discount-campaigns/new/` | فقط از طریق customer-segments قابل دسترس |
| `/<code>/admin/technicians/<id>/statement/pdf/` | هیچ دکمه PDF در صفحه statement وجود دارد؟ نیازمند بررسی بیشتر |

### صفحات پلتفرم بدون لینک در sidebar

| URL | مشکل |
|-----|-------|
| `/owner-platform/technician-financial-verifications/` | در `nav_platform.html` وجود ندارد |
| `/owner-platform/sms-template-requests/` | در `nav_platform.html` وجود ندارد |
| `/owner-platform/communication-templates/` | کامنت در nav گوید "deprecated" اما URL هنوز وجود دارد |
| `/owner-platform/password-reset-policy/` | در `nav_platform.html` وجود ندارد |

---

## ۳. قالب‌های تکراری و ناهماهنگ

### تکرار قالب component

دو مکان موازی برای همان component وجود دارد:

| قالب در `components/` | قالب در `includes/components/` |
|-----------------------|--------------------------------|
| `components/badge.html` | `includes/components/badge.html` |
| `components/empty_state.html` | `includes/components/empty_state.html` |
| `components/stat_card.html` | `includes/components/stat_card.html` |
| `components/status_badge.html` | `includes/components/status_badge.html` |

**ریسک:** تغییر در یک فایل اثری روی دیگری ندارد — ناهماهنگی UI.

---

## ۴. صفحات Deprecated که هنوز URL دارند

| URL | مشکل |
|-----|-------|
| `/<code>/customer/` | redirect به صفحه عمومی — پنل مشتری حذف شده (Phase 24) اما URL هنوز وجود دارد و `dashboard/customer_home.html` وجود دارد |
| `/loginlogin/` | legacy redirect — هنوز تعریف شده اما باید deprecated اعلام شود |
| `/loginlogin/<path>` | legacy redirect |
| `/<code>/login/` | به `/login/?company=<code>` redirect می‌کند — باید در docs مشخص شود |
| `/owner-platform/communication-templates/` | nav_platform.html کامنت دارد "deprecated" اما URL فعال است |

---

## ۵. جریان‌های کاربری گیج‌کننده

### مشکل ۵ — redirect پس از login برای مشتری

**مشکل:** پس از login، مشتری به `/<code>/invoices/` ریدایرکت می‌شود. اما اگر مشتری مستقیم به `/<code>/customer/` برود، ریدایرکت می‌شود به صفحه عمومی شرکت — که اصلاً پنل نیست.

```python
# views.py
def redirect_customer_to_public(request, **kwargs):
    # مشتری به صفحه عمومی می‌رود
```

**اثر:** مشتری confused می‌شود — انتظار داشبورد را دارد اما صفحه بازاریابی می‌بیند.

---

### مشکل ۶ — مسیر متفاوت ایجاد فاکتور تکنسین

```
/<code>/tech/orders/<id>/invoice/create/
  → redirect به →
/<code>/tech/invoices/order/<id>/create/
```

دو URL برای همان عملکرد وجود دارد. اول ریدایرکت به دوم می‌کند. این برای توسعه‌دهنده و تست گیج‌کننده است.

---

### مشکل ۷ — صفحه `/<code>/admin/orders/` vs `/<code>/admin/requests/`

دو صفحه جداگانه برای مدیریت کار وجود دارد:
- `admin/orders/` — سفارشات با status کامل
- `admin/requests/` — درخواست‌های `PENDING_REVIEW`

اما این تمایز در ناوبری sidebar مشخص نیست — کاربر ممکن است هر دو را چک کند.

---

## ۶. URL‌هایی که Permission Check ندارند یا ضعیف دارند

| URL | مشکل Permission |
|-----|-----------------|
| `/<code>/admin/settings/operators/` | بدون decorator (P0-1) |
| `/<code>/admin/customers/lookup/` | AJAX endpoint — نیازمند بررسی decorator |
| `/<code>/payments/callback/` | بدون auth — اما مبلغ باید تأیید شود (ریسک PSP spoofing) |
| `/i/<public_code>/` | عمومی است — اما invoice باید ISSUED/PAID باشد (چک می‌شود) |
| `/<code>/invoices/public/<code>/` | عمومی است — اما فقط ISSUED/PAID (چک می‌شود) |

---

## ۷. ناهماهنگی نام‌گذاری URL

| مشکل | نمونه |
|------|-------|
| برخی URL‌ها `/admin/` prefix دارند، برخی ندارند | `/<code>/admin/orders/` vs `/<code>/invoices/` |
| تکنسین از `tech/` استفاده می‌کند اما فاکتورهای عمومی از `invoices/` | `/<code>/tech/invoices/` vs `/<code>/invoices/` |
| app_name ها ناهماهنگ هستند | `dashboard_technician` vs `orders_technician` vs `invoices_technician` |
| namespace پیشوند `api-` دارد | `api-auth:auth-login` — نام مضاعف `auth` |

---

## ۸. مشکلات موبایل و RTL

### bottom navigation تکنسین
- `base_dashboard.html` یک bottom nav bar موبایل برای TECHNICIAN دارد (5 آیتم)
- اما برای COMPANY_ADMIN روی موبایل فقط hamburger menu دارد — sidebar toggle
- اگر sidebar collapse شود روی موبایل، ممکن است breadcrumb از بین برود

### RTL
- پروژه RTL است (فارسی) اما layout‌های sidebar از `right-0` برای slide استفاده می‌کند:
```html
<!-- base_dashboard.html -->
fixed inset-y-0 right-0 z-40 w-64 ... transform translate-x-full lg:translate-x-0
```
این برای RTL درست است اما باید تأیید شود که روی همه مرورگرها کار می‌کند.

---

## ۹. Breadcrumb

- `components/breadcrumb.html` وجود دارد اما نیازمند بررسی بیشتر است که آیا در همه صفحات include می‌شود
- در `base_dashboard.html` هیچ breadcrumb اتوماتیک وجود ندارد — هر template باید خودش مدیریت کند
- **ریسک:** کاربران در پنل‌های عمیق (مثلاً `/<code>/admin/financial-reports/technicians/`) ممکن است مسیر فعلی را گم کنند

---

## ۱۰. مشکلات احراز هویت و هدایت

### مشکل ۱۰ — Password change required نامرئی است

پس از login، اگر کاربر `must_change_password=True` داشته باشد:
- به `/account/change-password-required/` redirect می‌شود
- اما اگر تغییر رمز را snooze کند (از session) یک banner در `base_dashboard.html` نشان داده می‌شود
- این banner ممکن است در صفحات print نمایش داده شود (نیازمند بررسی بیشتر)

### مشکل ۱۱ — کاربر غیرفعال شده

از `views.py:52-53`:
```python
elif not user.is_active:
    error = "حساب کاربری شما توسط مدیر شرکت غیرفعال شده است."
elif user.company and not user.company.is_active:
    error = "دسترسی پنل شرکت توسط مالک پلتفرم محدود شده است."
```
اما `AUTHENTICATION_BACKENDS = AllowAllUsersModelBackend` است — یعنی Django اجازه login به کاربر غیرفعال را می‌دهد و فقط view این را چک می‌کند. این ممکن است در DRF views چک نشود.

---

## ۱۱. URL‌های مبهم یا خطرناک

| URL | ریسک |
|-----|-------|
| `/<code>/admin/orders/<id>/return-to-cycle/` | نام گویا نیست — "return to cycle" یعنی چه؟ |
| `/owner-platform/sms-billing/invoices/<id>/mark-paid/` | POST بدون تأیید — می‌تواند فاکتور جعلی را paid کند |
| `/<code>/admin/sms/outbox/bulk-retry/` | Bulk action بدون rate limit |
| `/<code>/admin/payments/gateway-reconciliation/` | view ای با این عنوان ولی بدون URL در sidebar — ممکن است orphan باشد |

---

## خلاصه ریسک‌ها

| # | ریسک | شدت | فایل مرتبط |
|---|------|-----|-----------|
| 1 | `admin_operator_list` بدون decorator | 🔴 بحرانی | `views_admin.py:2125` |
| 2 | JWT logout بی‌اثر | 🔴 بحرانی | `auth_views.py:152` |
| 3 | قالب‌های تکراری component | 🟡 متوسط | `templates/includes/components/` |
| 4 | صفحات deprecated هنوز فعال | 🟡 متوسط | `/<code>/customer/` |
| 5 | redirect مشتری گیج‌کننده | 🟡 متوسط | `views.py:redirect_customer` |
| 6 | redirect دوگانه فاکتور تکنسین | 🟢 کم | `orders/views.py:408` |
| 7 | orphan pages بدون لینک sidebar | 🟡 متوسط | چندین URL |
| 8 | breadcrumb ناقص | 🟢 کم | `base_dashboard.html` |
| 9 | bottom nav فقط برای تکنسین | 🟢 کم | `base_dashboard.html` |
| 10 | AllowAllUsersModelBackend | 🟠 مهم | `config/settings/base.py` |
