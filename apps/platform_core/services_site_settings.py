"""
Platform Site Settings Service.

Provides access to the singleton PlatformSiteSettings row.
Never crashes if the DB row does not exist — creates defaults on first access.
"""
from __future__ import annotations


class PlatformSiteSettingsService:
    """Access the platform site identity settings (singleton)."""

    @staticmethod
    def get():
        """
        Return the PlatformSiteSettings singleton.
        Creates a default row if none exists. Never raises.
        """
        from apps.platform_core.models import PlatformSiteSettings

        obj = PlatformSiteSettings.objects.order_by("id").first()
        if obj is None:
            obj = PlatformSiteSettings.objects.create()
        return obj

    @staticmethod
    def get_context() -> dict:
        """
        Return a context dict suitable for SMS/notification template rendering.

        Keys provided:
            site_name, site_url, login_url, support_phone
        """
        try:
            obj = PlatformSiteSettingsService.get()
            return {
                "site_name": obj.site_name or "",
                "site_url": obj.site_url or "",
                "login_url": obj.login_url or "",
                "support_phone": obj.support_phone or "",
            }
        except Exception:
            # If DB is unavailable during startup/migration, return safe defaults
            return {
                "site_name": "خدمت یار",
                "site_url": "",
                "login_url": "",
                "support_phone": "",
            }
