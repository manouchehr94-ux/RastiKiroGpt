# Migration for SMS Inbox (reply-capture model).

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_core", "0003_platform_sms_multi_provider"),
        ("sms", "0006_alter_smsmastertemplateproviderconfig_pattern_code_and_more"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SMSInbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("from_number", models.CharField(db_index=True, help_text="شماره فرستنده (مشتری)", max_length=15)),
                ("to_number", models.CharField(db_index=True, help_text="شماره گیرنده (خط ارسال‌کننده/Provider)", max_length=20)),
                ("text", models.TextField(help_text="متن پیام دریافت‌شده")),
                ("received_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, help_text="زمان دریافت پیام از Provider")),
                ("provider_message_id", models.CharField(blank=True, db_index=True, help_text="شناسه پیام در سیستم Provider", max_length=100)),
                ("match_status", models.CharField(choices=[("matched", "تطبیق داده شده"), ("unmatched", "بدون تطبیق"), ("ambiguous", "مبهم (چند شرکت)")], db_index=True, default="unmatched", max_length=20)),
                ("match_reason", models.CharField(blank=True, help_text="توضیح نحوه تطبیق یا دلیل عدم تطبیق", max_length=300)),
                ("response_type", models.CharField(choices=[("survey_rating", "امتیاز نظرسنجی"), ("customer_message", "پیام مشتری"), ("unknown", "نامشخص")], db_index=True, default="unknown", max_length=20)),
                ("rating_value", models.PositiveSmallIntegerField(blank=True, help_text="مقدار امتیاز نظرسنجی (1 تا 5)", null=True)),
                ("raw_response", models.JSONField(blank=True, default=dict, help_text="پیلود خام دریافتی از Provider")),
                ("company", models.ForeignKey(blank=True, db_index=True, help_text="شرکتی که این پیام به آن تعلق دارد", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sms_inbox_messages", to="tenants.company")),
                ("provider", models.ForeignKey(blank=True, help_text="Provider که این پیام از آن دریافت شد", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inbox_messages", to="platform_core.platformsmsprovidersetting")),
                ("matched_outbox", models.ForeignKey(blank=True, help_text="پیام ارسالی اخیر که این پاسخ به آن مرتبط شده", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inbox_replies", to="sms.smsoutbox")),
            ],
            options={
                "verbose_name": "SMS Inbox",
                "verbose_name_plural": "SMS Inbox",
                "ordering": ["-received_at"],
            },
        ),
        migrations.AddIndex(
            model_name="smsinbox",
            index=models.Index(fields=["from_number", "received_at"], name="sms_inbox_from_received_idx"),
        ),
        migrations.AddIndex(
            model_name="smsinbox",
            index=models.Index(fields=["company", "received_at"], name="sms_inbox_company_received_idx"),
        ),
        migrations.AddIndex(
            model_name="smsinbox",
            index=models.Index(fields=["match_status", "received_at"], name="sms_inbox_match_status_idx"),
        ),
        migrations.AddIndex(
            model_name="smsinbox",
            index=models.Index(fields=["response_type"], name="sms_inbox_response_type_idx"),
        ),
    ]
