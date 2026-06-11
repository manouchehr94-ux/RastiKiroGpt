# Migration for PlatformSiteSettings singleton model.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("platform_core", "0003_platform_sms_multi_provider"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformSiteSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_name", models.CharField(default="خدمت یار", help_text="نام پلتفرم/سایت — در ابتدای پیامک‌های پلتفرم نمایش داده می‌شود.", max_length=100)),
                ("site_url", models.URLField(blank=True, help_text="آدرس اصلی سایت پلتفرم (مثال: https://khedmatyar.ir)")),
                ("login_url", models.URLField(blank=True, help_text="آدرس ورود به پنل (مثال: https://khedmatyar.ir/login/)")),
                ("support_phone", models.CharField(blank=True, help_text="شماره پشتیبانی پلتفرم (اختیاری)", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Platform Site Settings",
                "verbose_name_plural": "Platform Site Settings",
            },
        ),
    ]
