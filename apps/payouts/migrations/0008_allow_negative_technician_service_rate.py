from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payouts", "0007_alter_financialbackfilltask_task_type"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="technicianservicerate",
            name="tech_rate_wage_non_negative",
        ),
        migrations.AlterField(
            model_name="technicianservicerate",
            name="fixed_wage_rial",
            field=models.BigIntegerField(
                help_text="مبلغ ثابت اجرت تکنسین به ازای هر واحد این آیتم سفارش، به ریال",
            ),
        ),
    ]
