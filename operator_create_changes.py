import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

# ===== 1. اضافه کردن URL =====
urls_file = "apps/tenants/urls.py"
with open(urls_file, 'r', encoding='utf-8') as f:
    urls = f.read()

old = 'path("admin/settings/operators/", views_admin.admin_operator_list, name="admin_operator_list"),'
new = ('path("admin/settings/operators/", views_admin.admin_operator_list, name="admin_operator_list"),\n'
       '    path("admin/settings/operators/create/", views_admin.admin_operator_create, name="admin_operator_create"),')

if 'admin_operator_create' not in urls:
    urls = urls.replace(old, new)
    with open(urls_file, 'w', encoding='utf-8') as f:
        f.write(urls)
    print("URLs updated")
else:
    print("URL already exists")

# ===== 2. اضافه کردن View =====
views_file = "apps/tenants/views_admin.py"
with open(views_file, 'r', encoding='utf-8') as f:
    views = f.read()

new_view = '''
@require_tenant_role("COMPANY_ADMIN")
def admin_operator_create(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    from django.contrib.auth import get_user_model
    from apps.accounts.operator_access import (
        get_operator_queryset,
        get_staff_role_value,
        model_has_field,
        set_user_display_name,
    )
    from apps.common.phone_utils import normalize_iran_mobile
    User = get_user_model()
    error = ""

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip().lower()
        phone_raw = (request.POST.get("phone") or "").strip()
        display_name = (request.POST.get("display_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = "123456"
        is_active = request.POST.get("is_active") == "on"

        if not username:
            error = "نام کاربری اپراتور الزامی است."
        elif User.objects.filter(username=username).exists():
            error = "این نام کاربری قبلاً استفاده شده است. لطفاً نام کاربری دیگری انتخاب کنید."
        else:
            normalized_phone = normalize_iran_mobile(phone_raw) or phone_raw
            operator = User()
            operator.username = username
            operator.phone = normalized_phone
            operator.email = email
            set_user_display_name(operator, display_name)
            if model_has_field(User, "company"):
                operator.company = company
            if model_has_field(User, "role"):
                operator.role = get_staff_role_value()
            if model_has_field(User, "is_active"):
                operator.is_active = is_active
            operator.set_password(password)
            if hasattr(operator, "must_change_password"):
                operator.must_change_password = True
            operator.save()
            from django.shortcuts import redirect
            return redirect(f"/{company.code}/admin/settings/operators/")

    return render(request, "tenants/admin_operator_create.html", {
        "company": company,
        "error": error,
    })

'''

# اضافه کردن view قبل از admin_operator_list
marker = '\ndef admin_operator_list'
if 'admin_operator_create' not in views:
    views = views.replace(marker, new_view + marker)
    with open(views_file, 'w', encoding='utf-8') as f:
        f.write(views)
    print("View added")
else:
    print("View already exists")

print("Done")
