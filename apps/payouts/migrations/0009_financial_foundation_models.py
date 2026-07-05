import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Sprint 1 — Financial Foundation Models.

    Creates four purely additive tables per the approved target
    architecture (docs/13_Financial_Core/target_architecture/19_DATA_MODEL.md):
      - EscrowRecord
      - SettlementBatch
      - SettlementItem
      - AdjustmentDocument

    Zero downtime: CREATE TABLE only. No existing table, column, or
    constraint is altered, dropped, or renamed. No data backfill is
    required or performed. Existing rows in every other table remain
    valid and untouched.
    """

    dependencies = [
        ("accounts", "0006_technician_rejected_by_technician_verification_note_and_more"),
        ("invoices", "0005_alter_invoicecancellationrequest_company"),
        ("payments", "0003_alter_payment_status"),
        ("payouts", "0008_allow_negative_technician_service_rate"),
        ("tenants", "0005_company_payment_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="SettlementBatch",
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
                    "level",
                    models.CharField(
                        choices=[
                            ("platform_to_org", "پلتفرم به شرکت"),
                            ("org_to_provider", "شرکت به تکنسین"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("calculating", "در حال محاسبه"),
                            ("ready", "آماده اجرا"),
                            ("executing", "در حال اجرا"),
                            ("completed", "تکمیل شده"),
                            ("failed", "ناموفق"),
                        ],
                        db_index=True,
                        default="calculating",
                        max_length=20,
                    ),
                ),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField()),
                (
                    "net_amount_rial",
                    models.BigIntegerField(
                        default=0,
                        help_text=(
                            "Signed: positive = platform owes org, "
                            "negative = org owes platform."
                        ),
                    ),
                ),
                ("total_credits", models.PositiveBigIntegerField(default=0)),
                ("total_debits", models.PositiveBigIntegerField(default=0)),
                ("items_count", models.PositiveIntegerField(default=0)),
                ("executed_at", models.DateTimeField(blank=True, null=True)),
                ("bank_reference", models.CharField(blank=True, max_length=200)),
                ("failure_reason", models.TextField(blank=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)ss",
                        to="tenants.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_settlement_batches",
                        to="accounts.companyuser",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="EscrowRecord",
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
                    "amount_rial",
                    models.PositiveBigIntegerField(
                        help_text="Total customer payment amount held in escrow.",
                    ),
                ),
                ("platform_commission_rial", models.PositiveBigIntegerField(default=0)),
                ("organization_share_rial", models.PositiveBigIntegerField(default=0)),
                ("provider_share_rial", models.PositiveBigIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("held", "نگهداری"),
                            ("reserved", "رزرو شده"),
                            ("distributed", "تخصیص یافته"),
                            ("pending_settlement", "در انتظار تسویه"),
                            ("settled", "تسویه شده"),
                            ("closed", "بسته شده"),
                        ],
                        db_index=True,
                        default="held",
                        max_length=25,
                    ),
                ),
                ("held_at", models.DateTimeField(auto_now_add=True)),
                ("distributed_at", models.DateTimeField(blank=True, null=True)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)ss",
                        to="tenants.company",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="escrow_records",
                        to="invoices.invoice",
                    ),
                ),
                (
                    "payment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="escrow_record",
                        to="payments.payment",
                    ),
                ),
                (
                    "settlement_batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="escrow_records",
                        to="payouts.settlementbatch",
                    ),
                ),
            ],
            options={
                "ordering": ["-held_at"],
            },
        ),
        migrations.AddIndex(
            model_name="settlementbatch",
            index=models.Index(
                fields=["company", "level", "status"],
                name="settlement_batch_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="settlementbatch",
            index=models.Index(
                fields=["company", "period_start", "period_end"],
                name="settlement_period_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="escrowrecord",
            index=models.Index(
                fields=["company", "status"],
                name="escrow_company_status_idx",
            ),
        ),
        migrations.CreateModel(
            name="SettlementItem",
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
                    "amount_rial",
                    models.BigIntegerField(
                        help_text="Signed contribution to the batch net position.",
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="payouts.settlementbatch",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)ss",
                        to="tenants.company",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="settlement_items",
                        to="invoices.invoice",
                    ),
                ),
                (
                    "ledger_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="payouts.technicianledgerentry",
                    ),
                ),
                (
                    "platform_fee_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="payouts.companyplatformfeeentry",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="settlementitem",
            index=models.Index(
                fields=["batch", "invoice"],
                name="settlement_item_batch_inv_idx",
            ),
        ),
        migrations.CreateModel(
            name="AdjustmentDocument",
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
                    "document_type",
                    models.CharField(
                        choices=[
                            ("full_refund", "بازپرداخت کامل"),
                            ("partial_refund", "بازپرداخت جزئی"),
                            ("credit_note", "اعتبارنامه"),
                            ("debit_note", "بدهکاری"),
                            ("manual_adjustment", "اصلاح دستی"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "پیش‌نویس"),
                            ("pending_approval", "در انتظار تأیید"),
                            ("approved", "تأییدشده"),
                            ("applied", "اعمال‌شده"),
                            ("rejected", "رد شده"),
                            ("cancelled", "لغو شده"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("amount_rial", models.PositiveBigIntegerField()),
                (
                    "reason",
                    models.TextField(
                        help_text="Mandatory justification for this correction.",
                    ),
                ),
                (
                    "technician_wage_reversal",
                    models.DecimalField(
                        blank=True, decimal_places=0, max_digits=12, null=True,
                    ),
                ),
                (
                    "platform_fee_reversal",
                    models.DecimalField(
                        blank=True, decimal_places=0, max_digits=12, null=True,
                    ),
                ),
                (
                    "company_share_reversal",
                    models.DecimalField(
                        blank=True, decimal_places=0, max_digits=12, null=True,
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_adjustments",
                        to="accounts.companyuser",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)ss",
                        to="tenants.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_adjustments",
                        to="accounts.companyuser",
                    ),
                ),
                (
                    "original_invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adjustment_documents",
                        to="invoices.invoice",
                    ),
                ),
                (
                    "platform_fee_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="adjustment_documents",
                        to="payouts.companyplatformfeeentry",
                    ),
                ),
                (
                    "technician_ledger_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="adjustment_documents",
                        to="payouts.technicianledgerentry",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="adjustmentdocument",
            index=models.Index(
                fields=["company", "status", "document_type"],
                name="adj_doc_status_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="adjustmentdocument",
            index=models.Index(
                fields=["company", "original_invoice"],
                name="adj_doc_invoice_idx",
            ),
        ),
    ]
