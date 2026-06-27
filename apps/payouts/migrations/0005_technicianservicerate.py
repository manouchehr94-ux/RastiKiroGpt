import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("orders", "0001_initial"),
        ("payouts", "0004_financialbackfilltask"),
        ("tenants", "0005_company_payment_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="TechnicianServiceRate",
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
                    "fixed_wage_rial",
                    models.PositiveBigIntegerField(
                        help_text="مبلغ ثابت اجرت تکنسین به ازای هر واحد این آیتم سفارش، به ریال",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)ss",
                        to="tenants.company",
                    ),
                ),
                (
                    "technician",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_rates",
                        to="accounts.technician",
                    ),
                ),
                (
                    "item_definition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="technician_rates",
                        to="orders.orderitemdefinition",
                    ),
                ),
            ],
            options={
                "ordering": ["technician", "item_definition"],
            },
        ),
        migrations.AddConstraint(
            model_name="technicianservicerate",
            constraint=models.UniqueConstraint(
                fields=["company", "technician", "item_definition"],
                name="unique_tech_rate_per_item",
            ),
        ),
        migrations.AddConstraint(
            model_name="technicianservicerate",
            constraint=models.CheckConstraint(
                check=models.Q(fixed_wage_rial__gte=0),
                name="tech_rate_wage_non_negative",
            ),
        ),
    ]
