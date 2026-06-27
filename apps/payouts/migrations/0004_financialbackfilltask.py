import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0004_invoicecounter_unique_active_invoice_per_order"),
        ("payments", "0001_initial"),
        ("payouts", "0003_company_platform_fee_entry_p6"),
        ("tenants", "0005_company_payment_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="FinancialBackfillTask",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "task_type",
                    models.CharField(
                        choices=[
                            ("technician_ledger", "Technician Ledger"),
                            ("platform_fee", "Platform Fee"),
                            ("payment_split_snapshot", "Payment Split Snapshot"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("resolved", "Resolved"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)ss",
                        to="tenants.company",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="backfill_tasks",
                        to="invoices.invoice",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="backfill_tasks",
                        to="payments.payment",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["company", "status", "task_type"],
                        name="fbk_co_status_type_idx",
                    )
                ],
            },
        ),
    ]
