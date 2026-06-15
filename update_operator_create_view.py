import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

views_file = "apps/tenants/views_admin.py"
with open(views_file, 'r', encoding='utf-8') as f:
    views = f.read()

# پیدا کردن view admin_operator_create و آپدیت return render
old = '''    return render(request, "tenants/admin_operator_create.html", {
        "company": company,
        "error": error,
    })'''

new = '''    from apps.accounts.operator_access import grouped_permission_items
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
                    "is_allowed": False,
                }
                for item in group_items
            ],
        })
    return render(request, "tenants/admin_operator_create.html", {
        "company": company,
        "error": error,
        "grouped_permissions": grouped,
    })'''

if old in views:
    views = views.replace(old, new)
    with open(views_file, 'w', encoding='utf-8') as f:
        f.write(views)
    print("View updated OK")
else:
    print("Pattern not found - checking...")
    # نمایش چند خط اطراف admin_operator_create
    idx = views.find('def admin_operator_create')
    print(views[idx:idx+500])
