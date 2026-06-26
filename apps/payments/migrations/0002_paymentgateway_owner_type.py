from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentgateway',
            name='owner_type',
            field=models.CharField(
                choices=[('company', 'Company'), ('platform', 'Platform')],
                default='company',
                db_index=True,
                max_length=10,
            ),
        ),
    ]
