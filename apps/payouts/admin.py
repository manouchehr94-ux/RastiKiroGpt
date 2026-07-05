from django.contrib import admin

from .models import (
    AdjustmentDocument,
    EscrowRecord,
    PaymentSplitSnapshot,
    SettlementBatch,
    SettlementItem,
    TechnicianLedgerEntry,
)


@admin.register(TechnicianLedgerEntry)
class TechnicianLedgerEntryAdmin(admin.ModelAdmin):
    list_display = [
        "id", "company", "technician", "entry_type", "source",
        "amount_rial", "balance_after", "idempotency_key", "created_at",
    ]
    list_filter = ["entry_type", "source", "company"]
    search_fields = ["idempotency_key", "description"]
    readonly_fields = [
        "company", "technician", "invoice", "payment", "order",
        "entry_type", "source", "amount_rial", "balance_after",
        "idempotency_key", "created_by", "metadata", "created_at", "updated_at",
    ]


@admin.register(PaymentSplitSnapshot)
class PaymentSplitSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "id", "company", "payment", "should_split_with_technician", "reason",
        "total_amount", "technician_direct_amount", "technician_ledger_amount",
        "payout_strategy_snapshot", "technician_verified_snapshot", "created_at",
    ]
    list_filter = ["should_split_with_technician", "payout_strategy_snapshot", "company"]
    readonly_fields = [f.name for f in PaymentSplitSnapshot._meta.get_fields() if hasattr(f, "name")]


# ---------------------------------------------------------------------------
# Financial Foundation Models (Sprint 1) — Admin registrations.
#
# These four models are schema-only in Sprint 1: no service creates,
# updates, or reads them yet. Admin is registered for inspection and
# manual data entry during Sprint 2+ development only. No business logic
# is added here.
# ---------------------------------------------------------------------------


@admin.register(EscrowRecord)
class EscrowRecordAdmin(admin.ModelAdmin):
    list_display = [
        "id", "company", "payment", "invoice", "status",
        "amount_rial", "platform_commission_rial", "organization_share_rial",
        "provider_share_rial", "held_at",
    ]
    list_filter = ["status", "company"]
    search_fields = ["payment__reference_id", "payment__tracking_code"]
    readonly_fields = ["held_at", "created_at", "updated_at"]


@admin.register(SettlementBatch)
class SettlementBatchAdmin(admin.ModelAdmin):
    list_display = [
        "id", "company", "level", "status", "period_start", "period_end",
        "net_amount_rial", "items_count", "executed_at",
    ]
    list_filter = ["level", "status", "company"]
    search_fields = ["bank_reference"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SettlementItem)
class SettlementItemAdmin(admin.ModelAdmin):
    list_display = [
        "id", "company", "batch", "invoice", "amount_rial",
    ]
    list_filter = ["company"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AdjustmentDocument)
class AdjustmentDocumentAdmin(admin.ModelAdmin):
    list_display = [
        "id", "company", "document_type", "status", "original_invoice",
        "amount_rial", "created_by", "approved_by", "created_at",
    ]
    list_filter = ["document_type", "status", "company"]
    search_fields = ["reason"]
    readonly_fields = [
        "approved_at", "applied_at", "created_at", "updated_at",
    ]
