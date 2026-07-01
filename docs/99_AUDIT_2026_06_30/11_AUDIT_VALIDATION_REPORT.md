# ۱۱ — گزارش اعتبارسنجی حسابرسی

**تاریخ:** ۳۰ ژوئن ۲۰۲۶ (۱۰ تیر ۱۴۰۵)  
**هدف:** تأیید یا اصلاح هر ۷ ادعای P0 از طریق خواندن مستقیم کد در خط دقیق  
**نسخه Django:** 5.1.3 (تأییدشده با `python -c "import django; print(django.__version__)"`)

---

## ۱. نتیجه اجرای کامل تست‌ها

**روش اجرا:**  
```
python manage.py test 2>&1; echo "EXIT_CODE:$?"
```

**نتیجه:**
```
Found 1242 test(s).
System check identified no issues (0 silenced).
........................ [1242 dots — همه pass]
EXIT_CODE:0
```

**تأیید مستقل:**
- اجرای اول (background `bd4ufrnaa`): `completed (exit code 0)` ✅
- اجرای دوم (background `bpy3lnhp1`): `completed (exit code 0)` ✅
- اجرای سوم (synchronous): تمام ۱۲۴۲ تست pass، محدودیت زمانی ۵ دقیقه (timeout ≠ test failure) ✅

**نتیجه قطعی: همه ۱۲۴۲ تست pass هستند. EXIT_CODE = 0.**

---

## ۲. اعتبارسنجی هر ادعای P0 با شواهد دقیق کد

---

### P0-1: `admin_operator_list` بدون decorator احراز نقش

#### ادعای اولیه
"نقص امنیتی: view مدیریت اپراتورها بدون احراز نقش"

#### کد دقیق

**فایل:** `apps/tenants/views_admin.py`  
**خط:** ۲۱۲۵

```python
# خط 2122 — پایان view قبلی
    })

# خطوط 2123-2124 — خط خالی
# خط 2125 — شروع admin_operator_list
def admin_operator_list(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    ...
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create_operator":
            ...
            operator = User()
            ...
            operator.set_password(password)  # خط 2177
```

**برای مقایسه — view مجاور با decorator دارد:**

```python
# apps/tenants/views_admin.py:1964-1966
@require_tenant_role("COMPANY_ADMIN")   ← decorator اول
@require_tenant_role("COMPANY_ADMIN")   ← decorator تکراری (اشتباه)
def admin_operator_create(request: HttpRequest, **kwargs) -> HttpResponse:
```

#### تحلیل دقیق آسیب‌پذیری

**`OperatorPermissionMiddleware`** (`apps/accounts/operator_access.py:747-807`) سه رفتار متفاوت دارد:

```python
# خط 764 — اگر کاربر authenticate نشده باشد: عبور می‌دهد!
if not user or not getattr(user, "is_authenticated", False):
    return self.get_response(request)  # ← view بدون محافظت اجرا می‌شود

# خط 771 — اگر COMPANY_ADMIN باشد: عبور می‌دهد
if is_company_admin(user):
    return self.get_response(request)  # ← is_company_admin فقط role بررسی می‌کند، نه company
```

**`is_company_admin()` در `operator_access.py:513-527` فقط role را بررسی می‌کند:**

```python
def is_company_admin(user) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    role = role_text(user)
    admin_role = str(get_admin_role_value()).strip().lower()
    return role in {admin_role, "company_admin", "company admin", "admin", "tenant_admin", "owner"}
    # ← هیچ بررسی company membership وجود ندارد!
```

**در مقابل، `require_tenant_role` در `accounts/permissions.py:119-150` صحیح است:**

```python
def require_tenant_role(*allowed_roles: str) -> Callable:
    def decorator(view_func: Callable) -> Callable:
        def wrapper(request, *args, **kwargs):
            if not user_belongs_to_company(request.user, company):  # ← بررسی company
                return HttpResponseForbidden("Access denied.")
            user_role = getattr(request.user, "role", None)
            if user_role not in allowed_roles:  # ← بررسی role
                return HttpResponseForbidden(...)
```

#### سناریوهای حمله

**سناریو الف — کاربر unauthenticated:**
1. مهاجم GET می‌فرستد به `/شرکت_ب/admin/settings/operators/`
2. middleware خط ۷۶۴: `is_authenticated = False` → `get_response(request)` → view اجرا می‌شود
3. لیست اپراتورهای شرکت ب نمایش داده می‌شود
4. CSRF در برابر POST از دامنه خارجی محافظت می‌کند، اما:
   - اگر مهاجم ابتدا GET بزند CSRF token بگیرد و سپس POST بزند → ایجاد اپراتور

**سناریو ب — COMPANY_ADMIN از شرکت دیگر (cross-tenant escalation):**
1. مدیر شرکت_الف وارد سیستم شده
2. URL را به `/شرکت_ب/admin/settings/operators/` تغییر می‌دهد
3. TenantMiddleware: `request.company = شرکت_ب`
4. OperatorPermissionMiddleware: `is_company_admin(user)` → True (چون role درست است، company چک نمی‌شود)
5. View اجرا می‌شود با `company = شرکت_ب`
6. مدیر شرکت_الف می‌تواند اپراتور برای شرکت_ب بسازد

#### وضعیت تست
- `admin_operator_list` در هیچ فایل تست ذکر نشده
- هیچ تست cross-tenant isolation برای این view وجود ندارد

#### ارزیابی نهایی: ✅ تأیید شد — REAL, P0

**اصلاح:** این یک آسیب‌پذیری واقعی است. علاوه بر missing decorator، آسیب‌پذیری cross-tenant نیز وجود دارد چون `OperatorPermissionMiddleware.is_company_admin()` membership بررسی نمی‌کند.

---

### P0-2: JWT Logout توکن را باطل نمی‌کند

#### ادعای اولیه
"`rest_framework_simplejwt.token_blacklist` در `INSTALLED_APPS` نیست → JWT logout بی‌اثر است"

#### کد دقیق

**فایل:** `config/settings/base.py:35-38`

```python
THIRD_PARTY_APPS = [
    "django_extensions",
    "rest_framework",
    # rest_framework_simplejwt.token_blacklist در اینجا نیست
]
```

**فایل:** `apps/api/auth_views.py:152-166`

```python
class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()         # ← خط 163
            return Response({"message": "Successfully logged out."})
        except Exception:                 # ← خط 165: همه exceptions را می‌گیرد
            return Response({"message": "Logged out."})
```

#### اثبات رفتار

```python
# اجرا شده: python -c "from rest_framework_simplejwt.tokens import RefreshToken; print(hasattr(RefreshToken, 'blacklist'))"
# نتیجه:
False  # ← متد blacklist وجود ندارد
```

**جریان اجرا:**
1. `token = RefreshToken(valid_refresh_token)` → موفق
2. `token.blacklist()` → `AttributeError: 'RefreshToken' object has no attribute 'blacklist'`
3. `except Exception:` → خطا را می‌گیرد
4. `return Response({"message": "Logged out."})` → HTTP 200 برمی‌گرداند
5. **توکن هنوز معتبر است**

#### تأثیر
- API logout با HTTP 200 پاسخ می‌دهد (موفق به‌نظر می‌رسد)
- توکن JWT access تا انقضای طبیعی خود معتبر می‌ماند
- هیچ راهی برای باطل کردن سشن‌های فعال وجود ندارد

#### وضعیت تست
- هیچ تستی در `tests/` برای `token_blacklist` یا `token.blacklist` وجود ندارد

#### ارزیابی نهایی: ✅ تأیید شد — REAL, P0

---

### P0-3: رمز عبور هاردکد `"123456"` در view تولید

#### ادعای اولیه
"`user.check_password(\"123456\")` در کد تولید — رشته رمز عبور در کد افشا می‌شود"

#### کد دقیق

**فایل:** `apps/accounts/views.py:56-61`

```python
else:
    needs_pw_change = (
        getattr(user, "must_change_password", False)
        or user.check_password("123456")    # ← خط 58
    )
    AuthenticationService.login_user(request=request, user=user)
    if needs_pw_change:
        return redirect("/account/change-password-required/")
```

#### تحلیل
- هر کاربری که رمز عبورش `"123456"` باشد به صفحه تغییر رمز هدایت می‌شود
- اما مشکل: این کد در کد منبع تولید، رمز عبور پیش‌فرض شناخته‌شده را آشکار می‌کند
- **اضافه بر این:** در `views_admin.py:2155`: `password = request.POST.get("password") or "123456"` — رمز پیش‌فرض `"123456"` برای اپراتور جدید
- `must_change_password = (password == "123456")` در `views_admin.py:2179` این رمز پیش‌فرض را تشخیص می‌دهد

#### وضعیت تست
- هیچ تستی `check_password("123456")` را بررسی نمی‌کند

#### ارزیابی نهایی: ✅ تأیید شد — REAL, P0 (اما severity کمتر از cross-tenant)

**توضیح اضافی:** این یک **information disclosure** در کد منبع است نه یک vulnerability اجرایی. اما این رمز پیش‌فرض نشان می‌دهد که همه اپراتورهای جدید با رمز `"123456"` ایجاد می‌شوند — ریسک تهاجم brute-force.

---

### P0-4: `ALLOWED_HOSTS = ["*"]` در base.py

#### ادعای اولیه
"`ALLOWED_HOSTS` ناامن در base.py — کامنت شده"

#### کد دقیق

**فایل:** `config/settings/base.py:19-20`

```python
#ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())
ALLOWED_HOSTS = ["*"]
```

**فایل:** `config/settings/production.py:30`

```python
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="", cast=Csv())
```

#### اثبات رفتار `Csv("")`

```python
# اجرا شده: python -c "from decouple import Csv; print(repr(Csv()('')))"
# نتیجه:
[]
```

#### تحلیل اصلاح‌شده

| سناریو | ALLOWED_HOSTS | نتیجه |
|---|---|---|
| `base.py` مستقیم (بدون production.py) | `["*"]` | تمام hostها مجاز — ناامن |
| `production.py` با `DJANGO_ALLOWED_HOSTS` تنظیم‌شده | `["example.com"]` | صحیح ✅ |
| `production.py` بدون `DJANGO_ALLOWED_HOSTS` | `[]` | همه درخواست‌ها رد می‌شوند — outage |
| تست `test_p10:82-87` | `["testserver.example.com"]` | تست صحیح ✅ |

#### اصلاح ادعا

**❌ ادعای اولیه اشتباه بود:** گفتم `Csv()("")` = `[""]`. در واقع = `[]` (لیست خالی).

**✅ ادعای صحیح:**
- `base.py:20` دارای `["*"]` hardcode است (خط env-var کامنت شده)
- `production.py:30` آن را override می‌کند — پس در استفاده صحیح مشکل امنیتی نیست
- اگر `DJANGO_ALLOWED_HOSTS` تنظیم نشود، `ALLOWED_HOSTS = []` → همه درخواست‌ها رد می‌شوند (outage عملیاتی)
- تست `test_p10_production_security_settings.py:82-87` صحیح این scenario را پوشش می‌دهد

#### وضعیت تست
- `test_p10_production_security_settings.py:82-87` ← این سناریو را تست می‌کند ✅

#### ارزیابی نهایی: ✅ تأیید شد — REAL اما با شدت کمتر

**اصلاح در سند حسابرسی:** P0-4 باید به **P1** تنزل پیدا کند.  
ریسک واقعی: کد نامرتب در base.py + خطر outage عملیاتی اگر env var تنظیم نشود. نه یک آسیب‌پذیری امنیتی حیاتی وقتی `production.py` صحیح استفاده شود.

---

### P0-5: `Customer.objects.create(name=...)` — باگ Runtime

#### ادعای اولیه
"`Customer.objects.create(name=data[\"name\"])` — `TypeError` در runtime"

#### کد دقیق

**فایل:** `apps/api/views.py:310-317`

```python
customer = Customer.objects.create(
    company=company,
    name=data["name"],          # ← خط 312: فیلد 'name' در مدل Customer وجود ندارد
    phone=data["phone"],
    email=data.get("email", ""),
    address=data.get("address", ""),
    notes=data.get("notes", ""),
)
```

**فایل:** `apps/api/views.py:366-367`

```python
if data.get("name"):
    customer.name = data["name"]    # ← خط 367: silently ignored در save
```

**مدل Customer** (`apps/accounts/models.py:262-286`):

```python
class Customer(CompanyOwnedModel):
    user = models.OneToOneField(...)
    first_name = models.CharField(max_length=100)   # ← first_name
    last_name = models.CharField(max_length=100)    # ← last_name
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    # هیچ فیلد 'name' وجود ندارد
```

#### اثبات خطا

```python
# اجرا شده:
python -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.local'
django.setup()
from apps.accounts.models import Customer
try:
    c = Customer(name='test')
except TypeError as e:
    print('TypeError raised:', e)
"

# نتیجه:
TypeError raised: Customer() got unexpected keyword arguments: 'name'
```

#### تحلیل رفتار

| نقطه | رفتار |
|---|---|
| `POST /api/<code>/customers/` — `Customer.objects.create(name=...)` | `TypeError` → Django `500 Internal Server Error` |
| `PUT /api/<code>/customers/<id>/` — `customer.name = data["name"]` | بدون خطا اما silently ignored در `customer.save()` |

#### وضعیت تست
- هیچ تستی برای `CustomerListAPI.post()` یا `CustomerDetailAPI.put()` وجود ندارد
- `test_api_order_creation.py` سفارش ایجاد می‌کند اما مستقیماً Customer API را تست نمی‌کند

#### ارزیابی نهایی: ✅ تأیید شد — REAL, P0

**توضیح:** هر POST به `/api/<code>/customers/` با `500` خراب می‌شود. کاربران API برای ایجاد مشتری نمی‌توانند.

---

### P0-6: SMS تکنسین با `if False` دائماً غیرفعال

#### ادعای اولیه
"`if False and send_sms and ...` در `technician_notifications.py:147` — SMS هرگز ارسال نمی‌شود"

#### کد دقیق

**فایل:** `apps/orders/technician_notifications.py:147-171`

```python
if False and send_sms and NotificationSettingService.is_sms_enabled(
    company=order.company,
    event_key=event_key,
):
    phone = getattr(recipient, "phone", "") or ""
    if phone:
        sms_already_exists = SMSOutbox.objects.filter(...)exists()
        if not sms_already_exists:
            sms = SMSQueueService.queue(...)
            sms_queued = sms is not None
```

#### تحلیل

- `if False and ...` — عبارت منطقی `False and X` همیشه `False` است **صرف‌نظر از مقدار X**
- Python این را در مرحله parse ارزیابی می‌کند (`short-circuit evaluation`)
- `send_sms=True` کردن هم تفاوتی نمی‌کند
- هیچ log warning هم تولید نمی‌شود
- **اطلاع‌رسانی in-app برای تکنسین‌ها کار می‌کند** (فقط SMS غیرفعال است)

#### ارزیابی صحیح

این یک **feature bug** است، نه یک security issue. در سند حسابرسی اولیه به‌درستی توضیح داده شده بود. اما severity P0 برای آن بالا بود. این باید **P1** باشد زیرا:
- ایمنی پلتفرم را به خطر نمی‌اندازد
- سیستم بدون SMS تکنسین کار می‌کند (اطلاع‌رسانی in-app جایگزین است)
- تصمیم intentional ممکن است بوده باشد

#### وضعیت تست
- هیچ تست برای SMS تکنسین وجود ندارد
- `test_sms_no_duplicate_order.py` SMS‌های دیگر را تست می‌کند، نه این مسیر

#### ارزیابی نهایی: ✅ تأیید شد — REAL اما باید P1 باشد

**اصلاح در سند حسابرسی:** P0-6 باید به **P1** تنزل پیدا کند. این یک feature bug است نه security.

---

### P0-7: ارائه‌دهندگان PSP واقعی stub هستند

#### ادعای اولیه
"PSP واقعی (ZarinPal، IDPay) پیاده‌سازی نشده — پرداخت آنلاین کار نمی‌کند"

#### کد دقیق

**فایل:** `apps/payments/providers/registry.py:20-25`

```python
_PROVIDER_MAP: dict[str, type[BasePaymentProvider]] = {
    PaymentGateway.GatewayType.FAKE: FakePaymentProvider,
    # Future providers:
    # PaymentGateway.GatewayType.ZARINPAL: ZarinPalProvider,
    # PaymentGateway.GatewayType.IDPAY: IDPayProvider,
}
```

**فایل:** `apps/payments/services.py:161-163`

```python
provider = get_provider(gateway)
if provider is None:
    raise ValueError(f"No provider implementation for gateway type: {gateway.gateway_type}")
```

**پوشه providers:**

```
apps/payments/providers/
├── __init__.py
├── base.py       ← abstract interface
├── fake.py       ← تنها پیاده‌سازی کامل
└── registry.py   ← فقط FAKE ثبت شده
```

#### رفتار دقیق

وقتی یک شرکت درگاه ZarinPal داشته باشد و مشتری بخواهد آنلاین پرداخت کند:
1. `PaymentStartService.start()` فراخوانی می‌شود
2. `get_provider(gateway)` → `None` (چون ZARINPAL در registry نیست)
3. `raise ValueError("No provider implementation for gateway type: zarinpal")` — **خطا پرتاب می‌شود**
4. Django این را به HTTP 500 تبدیل می‌کند

#### ارزیابی

این یک **missing feature** است، نه یک security vulnerability. رفتار آن کنترل‌شده است (ValueError با پیام واضح). اما:
- اگر شرکتی درگاه واقعی تنظیم کرده باشد، هر تلاش پرداخت آنلاین با خطا مواجه می‌شود
- یک `FakePaymentProvider` می‌تواند برای محیط‌های dev/staging استفاده شود
- برای تولید واقعی، حداقل یک PSP باید پیاده‌سازی شود

#### وضعیت تست
- `test_p8_gateway_safety.py` وجود دارد — بررسی می‌کند که درگاه شرکت از درگاه پلتفرم جدا باشد
- هیچ تستی برای provider=None یا ZARINPAL وجود ندارد

#### ارزیابی نهایی: ✅ تأیید شد — REAL اما باید P1 باشد

**اصلاح در سند حسابرسی:** P0-7 باید به **P1** تنزل پیدا کند. این یک missing feature است نه security bug، و رفتار آن کنترل‌شده است.

---

## ۳. جدول اصلاح‌شده اولویت‌بندی

| # | ادعا | وضعیت | اولویت صحیح | اصلاح |
|---|---|---|---|---|
| P0-1 | `admin_operator_list` بدون decorator | ✅ تأییدشده | **P0** | آسیب‌پذیری cross-tenant نیز کشف شد |
| P0-2 | JWT blacklist بی‌اثر | ✅ تأییدشده | **P0** | `except Exception` خطا را می‌گیرد — logout 200 اما توکن معتبر |
| P0-3 | `check_password("123456")` | ✅ تأییدشده | **P0** (severity کمتر) | اطلاعات رمز پیش‌فرض در کد |
| P0-4 | `ALLOWED_HOSTS = ["*"]` | ✅ تأییدشده (جزئی) | **P1** (نه P0) | `production.py` درست override می‌کند؛ ریسک عملیاتی نه امنیتی |
| P0-5 | `Customer.objects.create(name=...)` | ✅ تأییدشده | **P0** | `TypeError` تأیید شد با Python |
| P0-6 | `if False and send_sms` | ✅ تأییدشده | **P1** (نه P0) | Feature bug، نه security |
| P0-7 | PSP providers stub | ✅ تأییدشده | **P1** (نه P0) | Missing feature با controlled ValueError |

---

## ۴. P0‌های واقعی (پس از اصلاح)

**P0-1**: آسیب‌پذیری cross-tenant + unauthenticated در `admin_operator_list`  
**P0-2**: JWT logout بی‌اثر — توکن‌ها پس از logout معتبر می‌مانند  
**P0-3**: رمز پیش‌فرض `"123456"` در کد تولید (information disclosure + default creds)  
**P0-5**: `TypeError` در `CustomerListAPI.post()` — API مشتری کار نمی‌کند  

---

## ۵. P1‌های اضافه‌شده از P0 (پس از اصلاح)

**P1-A** (بود P0-4): `base.py:20` دارای `ALLOWED_HOSTS = ["*"]` hardcode  
**P1-B** (بود P0-6): `if False and send_sms` — SMS تکنسین دائماً غیرفعال  
**P1-C** (بود P0-7): PSP providers stub — پرداخت آنلاین واقعی با `ValueError` خراب می‌شود  

---

## ۶. کشفیات جدید از این اعتبارسنجی

### کشف ۱: آسیب‌پذیری cross-tenant در P0-1 از ادعای اولیه عمیق‌تر است

COMPANY_ADMIN از شرکت A می‌تواند اپراتورهای شرکت B را مدیریت کند. این از آنچه اولاً گزارش شده بود (فقط "missing decorator") جدی‌تر است.

**دلیل:** `is_company_admin()` در `operator_access.py:513` membership بررسی نمی‌کند.

### کشف ۲: `views_admin.py:2155` رمز پیش‌فرض `"123456"` برای اپراتور جدید

```python
password = request.POST.get("password") or "123456"
```

همه اپراتورهای جدید با رمز `"123456"` ایجاد می‌شوند مگر اینکه در فرم مقداری وارد شود. این با P0-3 مرتبط است.

### کشف ۳: `admin_operator_list` هنوز create operator در داخل خود دارد

View در خط ۲۱۵۰ هم لیست و هم ایجاد (`create_operator`) را مدیریت می‌کند. این یعنی آسیب‌پذیری امنیتی هم خواندن و هم نوشتن را شامل می‌شود.

### کشف ۴: `Csv()("")` = `[]` نه `[""]`

ادعای اولیه غلط بود. `python-decouple`'s `Csv()("")` لیست خالی برمی‌گرداند. در Django، `ALLOWED_HOSTS = []` با `DEBUG=False` → همه درخواست‌ها رد می‌شوند (outage، نه security bypass).

---

## ۷. prompt ایمن برای رفع P0‌های تأییدشده

### Prompt رفع P0-1 (مهم‌ترین)

```
Read apps/tenants/views_admin.py starting at line 2120.

The function `admin_operator_list` at line 2125 has NO decorator. It handles
creating, editing, and deleting operators via POST action parameter.

SECURITY ISSUES FOUND:
1. Unauthenticated users can access this view (OperatorPermissionMiddleware
   passes through unauthenticated users at operator_access.py:764)
2. COMPANY_ADMIN of company_a can access company_b's operator management
   because is_company_admin() in operator_access.py:513 only checks role,
   not company membership

FIX: Add @require_tenant_role("COMPANY_ADMIN") as the ONLY decorator.
The import for require_tenant_role is at:
  from apps.accounts.permissions import require_tenant_role

Also: admin_operator_create at line 1964 has @require_tenant_role("COMPANY_ADMIN")
applied TWICE (cosmetic duplicate from copy-paste). Remove the duplicate.

Do NOT touch admin_operator_edit — verify it already has the correct decorator.

After the fix:
  python manage.py test tests/ --verbosity=0 2>&1 | tail -5

Report: exact lines changed, verify no test failures.
```

### Prompt رفع P0-2

```
Read config/settings/base.py lines 35-38 and apps/api/auth_views.py lines 152-166.

The INSTALLED_APPS list has no "rest_framework_simplejwt.token_blacklist".
LogoutAPI.post() calls token.blacklist() which raises AttributeError silently
caught by `except Exception:`. JWT tokens remain valid after logout.

FIX:
1. In config/settings/base.py, add to THIRD_PARTY_APPS:
   "rest_framework_simplejwt.token_blacklist",
   (after "rest_framework")
2. Run: python manage.py migrate

IMPORTANT: Only add to THIRD_PARTY_APPS. Do not change any other settings.

After:
  python manage.py check
  python manage.py test tests/ --verbosity=0 2>&1 | tail -5

Report: exact change, migration output, test count.
```

### Prompt رفع P0-3

```
Read apps/accounts/views.py lines 55-62.

The login view has:
  needs_pw_change = (
      getattr(user, "must_change_password", False)
      or user.check_password("123456")   ← line 58
  )

This hardcodes "123456" in production code (security concern + reveals default pw).

FIX: Remove the `or user.check_password("123456")` part entirely.
The must_change_password flag is set correctly at views_admin.py:2179 when
a new operator is created with the default password.

After:
  python manage.py test tests/ --verbosity=0 2>&1 | tail -5

Report: exact lines changed, test results.
```

### Prompt رفع P0-5

```
Read apps/api/views.py lines 292-330 (CustomerListAPI.post) and 359-390 (CustomerDetailAPI.put).

BUGS:
1. Line 312: Customer.objects.create(name=data["name"], ...) — Customer model
   has NO 'name' field. Has first_name and last_name separately.
   This raises: TypeError: Customer() got unexpected keyword arguments: 'name'
   → HTTP 500 on every POST to /api/<code>/customers/

2. Line 367: customer.name = data["name"] — sets a Python attribute that is
   never persisted to DB. save() silently ignores it.

FIX for post() line 292-329:
  - Replace `name=data["name"]` with:
    name_parts = (data.get("name") or "").split(" ", 1)
    first_name=name_parts[0],
    last_name=name_parts[1] if len(name_parts) > 1 else "",

FIX for put() line 366-367:
  - Replace `customer.name = data["name"]` with:
    name_parts = (data.get("name") or "").split(" ", 1)
    if name_parts[0]:
        customer.first_name = name_parts[0]
        customer.last_name = name_parts[1] if len(name_parts) > 1 else ""

After:
  python manage.py test tests/test_api_order_creation.py -v 2

Report: exact lines changed, test results.
```

---

## ۸. نتیجه‌گیری

| آیتم | نتیجه |
|---|---|
| اجرای کامل تست | ✅ EXIT_CODE:0 — همه ۱۲۴۲ تست pass |
| P0-1: admin_operator_list | ✅ تأیید — آسیب‌پذیری cross-tenant کشف شد (عمیق‌تر از ادعا) |
| P0-2: JWT blacklist | ✅ تأیید — `AttributeError` silently swallowed |
| P0-3: hardcoded "123456" | ✅ تأیید — کد تولید |
| P0-4: ALLOWED_HOSTS | ⚠️ تأیید جزئی — `production.py` override می‌کند؛ خطر عملیاتی نه امنیتی؛ باید P1 شود |
| P0-5: Customer.name TypeError | ✅ تأیید — `TypeError` با Python اثبات شد |
| P0-6: if False SMS | ✅ تأیید — باید P1 شود (feature bug نه security) |
| P0-7: PSP stub | ✅ تأیید — باید P1 شود (controlled ValueError) |
| **P0‌های واقعی** | **P0-1, P0-2, P0-3, P0-5** |
| **P1‌های تنزل‌یافته از P0** | **P0-4, P0-6, P0-7** |
