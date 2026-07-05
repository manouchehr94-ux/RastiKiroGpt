"""
Payouts - Models.

Financial ledger for technician wages and settlements.
Also contains PaymentSplitSnapshot for split-decision audit trail.

Convention:
  CREDIT  → company owes technician (positive balance contribution)
  DEBIT   → technician owes company, or has been paid out (negative balance contribution)
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class TechnicianLedgerEntry(CompanyOwnedModel):
    """
    One immutable row in the technician's financial ledger.

    balance_after stores the technician's running balance immediately after
    this entry was applied. Positive = company still owes technician.
    Negative = technician still owes company.

    idempotency_key is globally unique. Callers must set a deterministic key
    (e.g. "invoice:42:technician_credit") so that replayed callbacks or
    management commands never create duplicate rows.
    """

    class EntryType(models.TextChoices):
        CREDIT = "credit", "بستانکار"
        DEBIT = "debit", "بدهکار"

    class Source(models.TextChoices):
        ONLINE_GATEWAY = "online_gateway", "پرداخت آنلاین"
        CASH_FROM_CUSTOMER = "cash_from_customer", "نقدی از مشتری (تکنسین)"
        MANUAL_PAYMENT = "manual_payment", "پرداخت دستی"
        MANUAL_SETTLEMENT = "manual_settlement", "تسویه دستی"
        DIRECT_GATEWAY_SETTLEMENT = "direct_gateway_settlement", "تسویه مستقیم درگاه"
        ADJUSTMENT = "adjustment", "تعدیل"
        REFUND = "refund", "بازگشت وجه"
        TECHNICIAN_SERVICE_WAGE = "technician_service_wage", "اجرت خدمت تکنسین"

    technician = models.ForeignKey(
        "accounts.Technician",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        db_index=True,
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    entry_type = models.CharField(max_length=10, choices=EntryType.choices, db_index=True)
    source = models.CharField(max_length=40, choices=Source.choices, db_index=True)

    amount_rial = models.PositiveBigIntegerField()
    balance_after = models.BigIntegerField(
        help_text="Running balance after this entry. Positive = company owes tech."
    )

    description = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True, db_index=True)

    created_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ledger_entries",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["company", "technician", "created_at"],
                name="ledger_company_tech_date_idx",
            ),
            models.Index(
                fields=["company", "technician", "entry_type"],
                name="ledger_company_tech_type_idx",
            ),
        ]

    def __str__(self) -> str:
        sign = "+" if self.entry_type == self.EntryType.CREDIT else "-"
        return f"{sign}{self.amount_rial:,} [{self.source}] key={self.idempotency_key}"

    def delete(self, *args, **kwargs):
        raise PermissionError(
            f"TechnicianLedgerEntry #{self.pk} is immutable and cannot be deleted. "
            "Reverse with an offsetting entry."
        )

    def save(self, *args, **kwargs):
        if self.pk is not None:
            update_fields = kwargs.get("update_fields")
            immutable = {"amount_rial", "balance_after"}
            if update_fields is None or immutable & set(update_fields):
                original = (
                    TechnicianLedgerEntry.objects
                    .filter(pk=self.pk)
                    .values("amount_rial", "balance_after")
                    .first()
                )
                if original is not None:
                    if original["amount_rial"] != self.amount_rial:
                        raise PermissionError(
                            f"TechnicianLedgerEntry #{self.pk}: amount_rial is immutable."
                        )
                    if original["balance_after"] != self.balance_after:
                        raise PermissionError(
                            f"TechnicianLedgerEntry #{self.pk}: balance_after is immutable."
                        )
        super().save(*args, **kwargs)


class PaymentSplitSnapshot(CompanyOwnedModel):
    """
    Immutable audit record of the split decision made at payment initiation/verification.

    Written once per payment. Answers:
    - What was the payout strategy at the time of this payment?
    - Was the technician verified?
    - How much goes directly to the technician vs. stays in company account?

    This snapshot is NOT the ledger (TechnicianLedgerEntry handles balances).
    It is the audit trail for the split routing decision.
    """

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="split_snapshot",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="split_snapshots",
    )

    # --- Amounts at decision time ---
    total_amount = models.PositiveBigIntegerField(default=0)
    platform_fee_amount = models.PositiveBigIntegerField(default=0)
    company_deposit_amount = models.PositiveBigIntegerField(default=0)
    technician_direct_amount = models.PositiveBigIntegerField(default=0)
    technician_ledger_amount = models.PositiveBigIntegerField(default=0)

    # --- Snapshot of settings at decision time ---
    payout_strategy_snapshot = models.CharField(max_length=30, blank=True)
    technician_verified_snapshot = models.BooleanField(default=False)
    technician_sub_merchant_id_snapshot = models.CharField(max_length=100, blank=True)
    platform_fee_percent_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )

    should_split_with_technician = models.BooleanField(default=False)
    reason = models.CharField(max_length=300, blank=True)
    raw_decision = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SplitSnapshot payment={self.payment_id} split={self.should_split_with_technician}"


class CompanyPlatformFeeEntry(CompanyOwnedModel):
    """
    One immutable row in the company's platform-fee ledger.

    Convention (from platform's perspective):
      DEBIT  → company owes platform more (fee accrued on a cash/manual payment).
      CREDIT → company paid / platform fee was settled.

    balance_after is the running total of what the company owes the platform
    at the moment this entry was written. Positive = company still owes.

    idempotency_key is globally unique.  Callers must supply a deterministic key
    (e.g. "platform_fee:invoice:42") so that retries never double-create.
    """

    class EntryType(models.TextChoices):
        DEBIT = "debit", "بدهکار (شرکت به پلتفرم)"
        CREDIT = "credit", "بستانکار (تسویه)"

    class Source(models.TextChoices):
        CASH_INVOICE = "cash_invoice", "فاکتور نقدی"
        ONLINE_GATEWAY = "online_gateway", "درگاه آنلاین"
        MANUAL_ADJUSTMENT = "manual_adjustment", "تعدیل دستی"
        PLATFORM_FEE_SETTLEMENT = "platform_fee_settlement", "تسویه کارمزد"
        REFUND = "refund", "برگشت"

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_fee_entries",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_fee_entries",
    )

    entry_type = models.CharField(max_length=10, choices=EntryType.choices, db_index=True)
    source = models.CharField(max_length=40, choices=Source.choices, db_index=True)

    amount_rial = models.PositiveBigIntegerField()
    balance_after = models.BigIntegerField(
        help_text="Running balance after this entry. Positive = company still owes platform."
    )
    platform_fee_percent_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Platform fee percent at time of recording.",
    )

    description = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True, db_index=True)

    created_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_platform_fee_entries",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["company", "created_at"],
                name="platform_fee_company_date_idx",
            ),
        ]

    def __str__(self) -> str:
        sign = "+" if self.entry_type == self.EntryType.DEBIT else "-"
        return f"{sign}{self.amount_rial:,} [{self.source}] key={self.idempotency_key}"

    def delete(self, *args, **kwargs):
        raise PermissionError(
            f"CompanyPlatformFeeEntry #{self.pk} is immutable and cannot be deleted. "
            "Reverse with an offsetting credit entry."
        )

    def save(self, *args, **kwargs):
        if self.pk is not None:
            update_fields = kwargs.get("update_fields")
            immutable = {"amount_rial", "balance_after"}
            if update_fields is None or immutable & set(update_fields):
                original = (
                    CompanyPlatformFeeEntry.objects
                    .filter(pk=self.pk)
                    .values("amount_rial", "balance_after")
                    .first()
                )
                if original is not None:
                    if original["amount_rial"] != self.amount_rial:
                        raise PermissionError(
                            f"CompanyPlatformFeeEntry #{self.pk}: amount_rial is immutable."
                        )
                    if original["balance_after"] != self.balance_after:
                        raise PermissionError(
                            f"CompanyPlatformFeeEntry #{self.pk}: balance_after is immutable."
                        )
        super().save(*args, **kwargs)


class FinancialBackfillTask(CompanyOwnedModel):
    """
    Tracks a failed financial write (ledger or platform fee) that must be retried.

    Created by InvoiceMarkPaidService when TechnicianLedgerService or
    PlatformFeeService fails to write. FinancialBackfillService.process_pending()
    retries each task and marks it RESOLVED on success.

    Idempotency: at most one PENDING or PROCESSING task may exist per
    (company, task_type, invoice) combination. Enforced by create_task().
    """

    class TaskType(models.TextChoices):
        TECHNICIAN_LEDGER = "technician_ledger", "Technician Ledger"
        PLATFORM_FEE = "platform_fee", "Platform Fee"
        PAYMENT_SPLIT_SNAPSHOT = "payment_split_snapshot", "Payment Split Snapshot"
        DIRECT_GATEWAY_SETTLEMENT = "direct_gateway_settlement", "Direct Gateway Settlement"
        ESCROW_RECORD = "escrow_record", "Escrow Record"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        RESOLVED = "resolved", "Resolved"
        FAILED = "failed", "Failed"

    task_type = models.CharField(
        max_length=30,
        choices=TaskType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backfill_tasks",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backfill_tasks",
    )
    error_message = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "status", "task_type"],
                name="fbk_co_status_type_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"BackfillTask #{self.pk} [{self.task_type}] "
            f"status={self.status} invoice={self.invoice_id}"
        )


class TechnicianServiceRate(CompanyOwnedModel):
    """
    Fixed rial wage per countable order item for a specific technician.

    Rates are read at order completion time and frozen in the ledger entry.
    Changing a rate after an order is completed never affects past ledger rows.

    Only OrderItemDefinition with kind=NUMBER may have a rate — non-countable
    item types (MONEY, TEXT, BOOL) do not represent billable service units.
    """

    technician = models.ForeignKey(
        "accounts.Technician",
        on_delete=models.CASCADE,
        related_name="service_rates",
    )
    item_definition = models.ForeignKey(
        "orders.OrderItemDefinition",
        on_delete=models.CASCADE,
        related_name="technician_rates",
    )
    fixed_wage_rial = models.BigIntegerField(
        help_text="مبلغ ثابت اجرت تکنسین به ازای هر واحد این آیتم سفارش، به ریال",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["technician", "item_definition"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "technician", "item_definition"],
                name="unique_tech_rate_per_item",
            ),
        ]

    def __str__(self) -> str:
        tech_name = getattr(getattr(self, "technician", None), "user", None)
        tech_label = tech_name.get_full_name() if tech_name else f"Tech#{self.technician_id}"
        item_label = getattr(getattr(self, "item_definition", None), "title", f"Item#{self.item_definition_id}")
        return f"{tech_label} / {item_label} = {self.fixed_wage_rial:,} ریال"

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        errors = {}

        if self.technician_id and self.company_id:
            tech = self.technician
            if tech.company_id != self.company_id:
                errors["technician"] = "تکنسین باید به همین شرکت تعلق داشته باشد."

        if self.item_definition_id and self.company_id:
            defn = self.item_definition
            if defn.company_id != self.company_id:
                errors["item_definition"] = "آیتم سفارش باید به همین شرکت تعلق داشته باشد."

        if self.item_definition_id:
            defn = self.item_definition
            if defn.kind != "number":
                errors["item_definition"] = (
                    "تنها آیتم‌های از نوع عدد (NUMBER) می‌توانند نرخ اجرت داشته باشند."
                )
            elif self.is_active and not defn.is_active:
                errors["item_definition"] = (
                    "نمی‌توان برای آیتم غیرفعال، نرخ اجرت فعال ثبت کرد."
                )

        if errors:
            raise ValidationError(errors)


# ---------------------------------------------------------------------------
# Financial Foundation Models (Sprint 1)
#
# These four models are purely additive scaffolding for the Financial Engine
# target architecture documented in:
#   docs/13_Financial_Core/target_architecture/04_DOMAIN_MODEL.md
#   docs/13_Financial_Core/target_architecture/19_DATA_MODEL.md
#
# They introduce NO new behavior. No existing service reads or writes to
# these models yet. No signal, no view, no API references them. They exist
# so that Sprint 2+ services (EscrowService, SettlementService,
# RefundService) have a stable schema to build on, without any change to
# the current payment, invoice, or payout flows.
# ---------------------------------------------------------------------------


class EscrowRecord(CompanyOwnedModel):
    """
    Explicit ownership tracking of customer funds held by the Platform.

    Materializes the Money Ownership Lifecycle described in
    target_architecture/05_MONEY_OWNERSHIP_LIFECYCLE.md. Not yet populated
    by any service — this model is schema-only in Sprint 1.

    Invariant (enforced by future EscrowService, not by this model):
        platform_commission_rial + organization_share_rial
        + provider_share_rial == amount_rial
    """

    class Status(models.TextChoices):
        HELD = "held", "نگهداری"
        RESERVED = "reserved", "رزرو شده"
        DISTRIBUTED = "distributed", "تخصیص یافته"
        PENDING_SETTLEMENT = "pending_settlement", "در انتظار تسویه"
        SETTLED = "settled", "تسویه شده"
        CLOSED = "closed", "بسته شده"

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="escrow_record",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escrow_records",
    )

    amount_rial = models.PositiveBigIntegerField(
        help_text="Total customer payment amount held in escrow.",
    )
    platform_commission_rial = models.PositiveBigIntegerField(default=0)
    organization_share_rial = models.PositiveBigIntegerField(default=0)
    provider_share_rial = models.PositiveBigIntegerField(default=0)

    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.HELD,
        db_index=True,
    )

    held_at = models.DateTimeField(auto_now_add=True)
    distributed_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    settlement_batch = models.ForeignKey(
        "payouts.SettlementBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escrow_records",
    )

    class Meta:
        ordering = ["-held_at"]
        indexes = [
            models.Index(
                fields=["company", "status"],
                name="escrow_company_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"EscrowRecord #{self.pk} [{self.status}] payment={self.payment_id}"


class SettlementBatch(CompanyOwnedModel):
    """
    A batch of invoices (or ledger entries) settled together in one
    net-position transfer.

    Materializes the Net Position Settlement design described in
    target_architecture/13_SETTLEMENT_NETTING_ENGINE.md. Not yet populated
    or executed by any service — this model is schema-only in Sprint 1.
    No `process_settlements` command exists yet; that is deferred to a
    later sprint.
    """

    class Level(models.TextChoices):
        PLATFORM_TO_ORG = "platform_to_org", "پلتفرم به شرکت"
        ORG_TO_PROVIDER = "org_to_provider", "شرکت به تکنسین"

    class Status(models.TextChoices):
        CALCULATING = "calculating", "در حال محاسبه"
        READY = "ready", "آماده اجرا"
        EXECUTING = "executing", "در حال اجرا"
        COMPLETED = "completed", "تکمیل شده"
        FAILED = "failed", "ناموفق"

    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CALCULATING,
        db_index=True,
    )

    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    net_amount_rial = models.BigIntegerField(
        default=0,
        help_text="Signed: positive = platform owes org, negative = org owes platform.",
    )
    total_credits = models.PositiveBigIntegerField(default=0)
    total_debits = models.PositiveBigIntegerField(default=0)
    items_count = models.PositiveIntegerField(default=0)

    executed_at = models.DateTimeField(null=True, blank=True)
    bank_reference = models.CharField(max_length=200, blank=True)
    failure_reason = models.TextField(blank=True)

    created_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_settlement_batches",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "level", "status"],
                name="settlement_batch_idx",
            ),
            models.Index(
                fields=["company", "period_start", "period_end"],
                name="settlement_period_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"SettlementBatch #{self.pk} [{self.level}/{self.status}]"


class SettlementItem(CompanyOwnedModel):
    """
    One invoice (or ledger entry) included in a SettlementBatch's net
    position calculation.

    Schema-only in Sprint 1 — no service creates these rows yet.
    """

    batch = models.ForeignKey(
        SettlementBatch,
        on_delete=models.CASCADE,
        related_name="items",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settlement_items",
    )
    ledger_entry = models.ForeignKey(
        "payouts.TechnicianLedgerEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    platform_fee_entry = models.ForeignKey(
        "payouts.CompanyPlatformFeeEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    amount_rial = models.BigIntegerField(
        help_text="Signed contribution to the batch net position.",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["batch", "invoice"],
                name="settlement_item_batch_inv_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"SettlementItem #{self.pk} batch={self.batch_id} amount={self.amount_rial:,}"


class AdjustmentDocument(CompanyOwnedModel):
    """
    Formal correction document for a PAID invoice (Credit Note, Debit Note,
    Full/Partial Refund, Manual Adjustment).

    Satisfies R52 (corrections must happen via a separate document, never
    by editing a PAID invoice or an existing ledger entry).

    Schema-only in Sprint 1. No RefundExecutionService exists yet — no
    code path creates, approves, or applies these documents. The
    `technician_ledger_entry` and `platform_fee_entry` FKs remain unused
    until that service is built, per
    target_architecture/26_REFUND_REVERSAL_ENGINE_SPECIFICATION.md.

    [OPEN-ISSUE: OI-07] — Full/Partial Refund definitions and reversal
    proportionality formulas are not yet finalized by the Product Owner.
    This model only reserves the schema; it does not implement any
    reversal logic.
    """

    class DocumentType(models.TextChoices):
        FULL_REFUND = "full_refund", "بازپرداخت کامل"
        PARTIAL_REFUND = "partial_refund", "بازپرداخت جزئی"
        CREDIT_NOTE = "credit_note", "اعتبارنامه"
        DEBIT_NOTE = "debit_note", "بدهکاری"
        MANUAL_ADJUSTMENT = "manual_adjustment", "اصلاح دستی"

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PENDING_APPROVAL = "pending_approval", "در انتظار تأیید"
        APPROVED = "approved", "تأییدشده"
        APPLIED = "applied", "اعمال‌شده"
        REJECTED = "rejected", "رد شده"
        CANCELLED = "cancelled", "لغو شده"

    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    original_invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.CASCADE,
        related_name="adjustment_documents",
    )

    amount_rial = models.PositiveBigIntegerField()
    reason = models.TextField(
        help_text="Mandatory justification for this correction.",
    )

    # Financial reversal tracking (populated by a future service when APPLIED).
    technician_wage_reversal = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
    )
    platform_fee_reversal = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
    )
    company_share_reversal = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_adjustments",
    )
    approved_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_adjustments",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    technician_ledger_entry = models.ForeignKey(
        "payouts.TechnicianLedgerEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustment_documents",
    )
    platform_fee_entry = models.ForeignKey(
        "payouts.CompanyPlatformFeeEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustment_documents",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "status", "document_type"],
                name="adj_doc_status_type_idx",
            ),
            models.Index(
                fields=["company", "original_invoice"],
                name="adj_doc_invoice_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"AdjustmentDocument #{self.pk} [{self.document_type}/{self.status}] "
            f"invoice={self.original_invoice_id}"
        )
