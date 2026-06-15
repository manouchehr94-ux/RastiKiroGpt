import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

# ===== 1. اضافه کردن URL =====
urls_file = "apps/tenants/urls.py"
with open(urls_file, 'r', encoding='utf-8') as f:
    urls = f.read()

old = 'path("admin/settings/operators/create/", views_admin.admin_operator_create, name="admin_operator_create"),'
new = ('path("admin/settings/operators/create/", views_admin.admin_operator_create, name="admin_operator_create"),\n'
       '    path("admin/settings/operators/<int:operator_id>/edit/", views_admin.admin_operator_edit, name="admin_operator_edit"),')

if 'admin_operator_edit' not in urls:
    urls = urls.replace(old, new)
    with open(urls_file, 'w', encoding='utf-8') as f:
        f.write(urls)
    print("URL added")
else:
    print("URL already exists")

# ===== 2. اضافه کردن View =====
views_file = "apps/tenants/views_admin.py"
with open(views_file, 'r', encoding='utf-8') as f:
    views = f.read()

new_view = '''
@require_tenant_role("COMPANY_ADMIN")
def admin_operator_edit(request: HttpRequest, operator_id: int, **kwargs) -> HttpResponse:
    company = request.company
    from django.contrib.auth import get_user_model
    from apps.accounts.models import OperatorPermission
    from apps.accounts.operator_access import (
        get_operator_queryset,
        get_user_display,
        get_user_identifier,
        grouped_permission_items,
        list_operator_permission_items,
        model_has_field,
        set_if_field,
        set_user_display_name,
    )
    User = get_user_model()
    operator = get_operator_queryset(company).filter(id=operator_id).first()
    if not operator:
        from django.shortcuts import redirect
        return redirect(f"/{company.code}/admin/settings/operators/")

    items = list_operator_permission_items()
    error = ""
    success = ""

    if request.method == "POST":
        display_name = (request.POST.get("display_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone_raw = (request.POST.get("phone") or "").strip()
        is_active = request.POST.get("is_active") == "on"
        selected = set(request.POST.getlist("permissions"))

        set_user_display_name(operator, display_name)
        set_if_field(operator, "email", email)
        if phone_raw:
            from apps.common.phone_utils import normalize_iran_mobile
            set_if_field(operator, "phone", normalize_iran_mobile(phone_raw) or phone_raw)
        if model_has_field(User, "is_active"):
            operator.is_active = is_active
        operator.save()

        for item in items:
            row, _ = OperatorPermission.objects.get_or_create(
                company=company,
                operator=operator,
                permission_key=item.key,
                defaults={"is_allowed": False},
            )
            row.is_allowed = item.key in selected
            row.save(update_fields=["is_allowed"])

        success = "اطلاعات و دسترسی‌های اپراتور ذخیره شد."

    allowed_keys = set(
        OperatorPermission.objects.filter(
            company=company, operator=operator, is_allowed=True,
        ).values_list("permission_key", flat=True)
    )
    grouped_master = grouped_permission_items()
    grouped = []
    for group, group_items in grouped_master.items():
        grouped.append({
            "group": group,
            "items": [
                {
                    "key": item.key,
                    "title": item.title,
                    "description": item.description,
                    "action_label": item.action_label,
                    "path_template": item.path_template.replace("{company_code}", company.code),
                    "is_allowed": item.key in allowed_keys,
                }
                for item in group_items
            ],
        })

    display = get_user_display(operator)
    identifier = get_user_identifier(operator)

    return render(request, "tenants/admin_operator_edit.html", {
        "company": company,
        "operator": operator,
        "operator_display": display,
        "has_display_name": bool(display and display != identifier),
        "grouped_permissions": grouped,
        "error": error,
        "success": success,
    })

'''

marker = '\ndef admin_operator_list'
if 'admin_operator_edit' not in views:
    views = views.replace(marker, new_view + marker)
    with open(views_file, 'w', encoding='utf-8') as f:
        f.write(views)
    print("View added")
else:
    print("View already exists")

print("Done")
