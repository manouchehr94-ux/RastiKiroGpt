# Generated for owner platform SMS template management.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sms", "0003_alter_smsoutbox_template_key_alter_smstemplate_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="smsmastertemplate",
            name="provider_pattern_code",
            field=models.CharField(blank=True, help_text="Optional internal/provider pattern code for matching this template in an SMS provider panel.", max_length=120),
        ),
        migrations.AddField(
            model_name="smsmastertemplate",
            name="melipayamak_body_id",
            field=models.CharField(blank=True, help_text="MeliPayamak BodyId for pattern sending. Not shown to SMS recipients.", max_length=50),
        ),
        migrations.AddField(
            model_name="smsmastertemplate",
            name="melipayamak_variables_order",
            field=models.TextField(blank=True, help_text="Comma-separated variable order for MeliPayamak SendByBaseNumber2, e.g. code,site_name."),
        ),
    ]
