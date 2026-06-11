from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('platform_core','0002_alter_platformsmsmessagetypesetting_key_and_more')]
    operations=[
        migrations.AddField(model_name='platformsmsprovidersetting', name='username', field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='password', field=models.CharField(blank=True, max_length=300)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='api_secret', field=models.CharField(blank=True, max_length=300)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='usage_scope', field=models.CharField(choices=[('platform','فقط پیام‌های پلتفرم'),('company','فقط پیام‌های شرکت‌ها'),('both','پلتفرم و شرکت')], default='both', max_length=20)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='priority', field=models.PositiveIntegerField(default=100)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='is_fallback', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='endpoint_url', field=models.URLField(blank=True)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='request_method', field=models.CharField(blank=True, default='POST', max_length=10)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='headers_template', field=models.TextField(blank=True)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='body_template', field=models.TextField(blank=True)),
        migrations.AddField(model_name='platformsmsprovidersetting', name='success_keywords', field=models.CharField(blank=True, max_length=300)),
    ]
