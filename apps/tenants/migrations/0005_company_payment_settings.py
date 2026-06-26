# Generated for TASK-003 — CompanyPaymentSettings foundational model.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_payment_settings_for_existing_companies(apps, schema_editor):
    """Seed one disabled/inactive row per company that lacks one."""
    Company = apps.get_model("tenants", "Company")
    CompanyPaymentSettings = apps.get_model("tenants", "CompanyPaymentSettings")
    db_alias = schema_editor.connection.alias

    existing_company_ids = set(
        CompanyPaymentSettings.objects.using(db_alias).values_list("company_id", flat=True)
    )

    new_rows = [
        CompanyPaymentSettings(
            company=company,
            payment_mode="disabled",
            is_online_payment_enabled=False,
            gateway_activation_status="inactive",
        )
        for company in Company.objects.using(db_alias).exclude(id__in=existing_company_ids)
    ]
    if new_rows:
        CompanyPaymentSettings.objects.using(db_alias).bulk_create(new_rows)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0004_ordercustomfield_ordercustomfieldvalue"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyPaymentSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "payment_mode",
                    models.CharField(
                        choices=[
                            ("disabled", "Disabled"),
                            ("company_gateway", "Company Gateway"),
                            ("platform_gateway", "Platform Gateway"),
                        ],
                        db_index=True,
                        default="disabled",
                        help_text="Payment mode for this company. Only platform owner may change.",
                        max_length=20,
                    ),
                ),
                (
                    "is_online_payment_enabled",
                    models.BooleanField(
                        default=False,
                        help_text="True only when mode is not disabled and status is active.",
                    ),
                ),
                (
                    "gateway_activation_status",
                    models.CharField(
                        choices=[
                            ("inactive", "Inactive"),
                            ("pending_review", "Pending Review"),
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                        ],
                        db_index=True,
                        default="inactive",
                        help_text="Activation lifecycle. Controlled by platform owner.",
                        max_length=20,
                    ),
                ),
                (
                    "activated_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "deactivated_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "deactivation_reason",
                    models.TextField(blank=True),
                ),
                (
                    "notes",
                    models.TextField(blank=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "activated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activated_payment_settings",
                        help_text="Platform owner who activated this company's payment mode.",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_settings",
                        to="tenants.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Company Payment Settings",
                "verbose_name_plural": "Company Payment Settings",
            },
        ),
        migrations.RunPython(
            create_payment_settings_for_existing_companies,
            reverse_code=noop,
        ),
    ]
