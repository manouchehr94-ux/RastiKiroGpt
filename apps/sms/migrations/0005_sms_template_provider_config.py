from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('sms','0004_smsmastertemplate_provider_pattern')]
    operations=[
        migrations.CreateModel(name='SMSMasterTemplateProviderConfig', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('provider_setting_id', models.PositiveIntegerField(blank=True, db_index=True, null=True)),
            ('provider_type', models.CharField(blank=True, db_index=True, max_length=30)),
            ('provider_name', models.CharField(blank=True, max_length=120)),
            ('send_mode', models.CharField(choices=[('text','ارسال متن ساده'),('pattern','ارسال پترن/خدماتی')], default='text', max_length=20)),
            ('pattern_code', models.CharField(blank=True, max_length=120)),
            ('variables_order', models.TextField(blank=True)),
            ('is_primary', models.BooleanField(default=False)),
            ('is_fallback', models.BooleanField(default=False)),
            ('priority', models.PositiveIntegerField(default=100)),
            ('is_active', models.BooleanField(default=True)),
            ('notes', models.TextField(blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('master_template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='provider_configs', to='sms.smsmastertemplate')),
        ], options={'ordering':['priority','id']}),
        migrations.AddIndex(model_name='smsmastertemplateproviderconfig', index=models.Index(fields=['master_template','is_primary','is_active'], name='sms_tpl_route_primary_idx')),
        migrations.AddIndex(model_name='smsmastertemplateproviderconfig', index=models.Index(fields=['master_template','is_fallback','is_active'], name='sms_tpl_route_fallback_idx')),
    ]
