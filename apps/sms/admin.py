from django.contrib import admin

from .models import SMSOutbox, SMSProvider, SMSTemplate
from .models_inbox import SMSInbox
from .models_master import SMSMasterTemplate, SMSMasterTemplateProviderConfig, SMSTemplateChangeRequest


@admin.register(SMSProvider)
class SMSProviderAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "provider_type", "is_active"]
    list_filter = ["provider_type", "is_active", "company"]
    search_fields = ["name", "company__name", "company__code"]


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "key", "is_active"]
    list_filter = ["key", "is_active", "company"]
    search_fields = ["title", "template_text", "company__name", "company__code"]


@admin.register(SMSOutbox)
class SMSOutboxAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "phone_number", "status", "template_key", "attempt_count", "sent_at", "delivered_at", "created_at"]
    list_filter = ["status", "template_key", "company"]
    search_fields = ["phone_number", "message", "provider_message_id", "company__name", "company__code"]
    readonly_fields = ["created_at", "updated_at", "queued_at", "sending_at", "sent_at", "delivered_at", "failed_at", "last_attempt_at"]


@admin.register(SMSMasterTemplate)
class SMSMasterTemplateAdmin(admin.ModelAdmin):
    list_display = ["key", "title", "scope", "recipient_type", "melipayamak_body_id", "is_active"]
    list_filter = ["scope", "recipient_type", "is_active"]
    search_fields = ["key", "title", "template_text"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SMSMasterTemplateProviderConfig)
class SMSMasterTemplateProviderConfigAdmin(admin.ModelAdmin):
    list_display = ["master_template", "provider_name", "provider_type", "send_mode", "pattern_code", "is_primary", "is_fallback", "priority", "is_active"]
    list_filter = ["provider_type", "send_mode", "is_primary", "is_fallback", "is_active"]
    search_fields = ["provider_name", "pattern_code", "master_template__key"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SMSTemplateChangeRequest)
class SMSTemplateChangeRequestAdmin(admin.ModelAdmin):
    list_display = ["company", "event_key", "status", "requested_tone", "created_at"]
    list_filter = ["status", "requested_tone"]
    search_fields = ["event_key", "company__name", "company__code"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SMSInbox)
class SMSInboxAdmin(admin.ModelAdmin):
    list_display = [
        "id", "from_number", "company", "match_status",
        "response_type", "rating_value", "text_preview_admin", "received_at",
    ]
    list_filter = ["match_status", "response_type", "company"]
    search_fields = ["from_number", "to_number", "text", "provider_message_id"]
    readonly_fields = ["created_at", "updated_at", "received_at", "raw_response"]
    list_select_related = ["company", "matched_outbox"]
    date_hierarchy = "received_at"

    @admin.display(description="پیش‌نمایش متن")
    def text_preview_admin(self, obj):
        if len(obj.text) <= 50:
            return obj.text
        return obj.text[:47] + "..."
