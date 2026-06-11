from django.contrib import admin

from .models import Plan, PlatformSiteSettings, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "price_monthly", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["company", "plan", "status", "expires_at"]
    list_filter = ["status", "plan"]
    search_fields = ["company__name"]


@admin.register(PlatformSiteSettings)
class PlatformSiteSettingsAdmin(admin.ModelAdmin):
    list_display = ["site_name", "site_url", "login_url", "support_phone", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]

    def has_add_permission(self, request):
        # Singleton: only allow adding if none exists
        return not PlatformSiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
