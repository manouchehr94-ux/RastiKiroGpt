import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0003_invoicecancellationrequest"),
        ("tenants", "0005_company_payment_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvoiceCounter",
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
                ("last_number", models.PositiveIntegerField(default=0)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoice_counter",
                        to="tenants.company",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=["draft", "issued"]),
                fields=["order"],
                name="unique_active_invoice_per_order",
            ),
        ),
    ]
