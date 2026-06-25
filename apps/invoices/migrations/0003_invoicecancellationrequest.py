import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0002_initial'),
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceCancellationRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invoices_invoicecancellationrequests',
                    to='tenants.company',
                )),
                ('invoice', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cancellation_requests',
                    to='invoices.invoice',
                )),
                ('requested_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='invoice_cancellation_requests',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('reason', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'در انتظار بررسی'),
                        ('approved', 'تأیید شده'),
                        ('rejected', 'رد شده'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_invoice_cancellation_requests',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_note', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='invoicecancellationrequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(status='pending'),
                fields=['invoice'],
                name='unique_pending_cancel_request_per_invoice',
            ),
        ),
    ]
