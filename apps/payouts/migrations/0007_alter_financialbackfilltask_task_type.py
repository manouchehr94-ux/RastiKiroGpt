from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payouts", "0006_alter_technicianledgerentry_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="financialbackfilltask",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("technician_ledger", "Technician Ledger"),
                    ("platform_fee", "Platform Fee"),
                    ("payment_split_snapshot", "Payment Split Snapshot"),
                    ("direct_gateway_settlement", "Direct Gateway Settlement"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]
