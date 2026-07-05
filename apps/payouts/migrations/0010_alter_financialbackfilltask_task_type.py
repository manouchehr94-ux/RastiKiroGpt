from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Sprint 3 — Escrow Integration.

    Adds "escrow_record" to FinancialBackfillTask.TaskType.choices, following
    the exact precedent already set by migration 0007 (which added
    "payment_split_snapshot" / "direct_gateway_settlement" the same way).

    Choices-only AlterField: no column type, length, index, or constraint
    change. No data migration. Zero downtime. Existing rows with any other
    task_type value are completely unaffected.
    """

    dependencies = [
        ("payouts", "0009_financial_foundation_models"),
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
                    ("escrow_record", "Escrow Record"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]
