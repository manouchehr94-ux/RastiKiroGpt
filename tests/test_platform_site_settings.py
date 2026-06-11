"""
Tests for PlatformSiteSettings model and service.

Verifies:
1. Default PlatformSiteSettings is created/returned when none exists
2. Platform SMS context contains site_name
3. Platform SMS context contains login_url
4. No hardcoded "خدمت یار" is inserted directly into template text by builders
5. Existing message builders still work with new context injection
6. build_context_for_event always includes site variables
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase


class PlatformSiteSettingsServiceTest(TestCase):
    """Test PlatformSiteSettingsService.get() and get_context()."""

    def test_get_creates_default_when_none_exists(self):
        """get() creates a default row if none exists in DB."""
        from apps.platform_core.models import PlatformSiteSettings
        from apps.platform_core.services_site_settings import PlatformSiteSettingsService

        # Ensure no rows exist
        PlatformSiteSettings.objects.all().delete()

        obj = PlatformSiteSettingsService.get()

        self.assertIsNotNone(obj)
        self.assertIsInstance(obj, PlatformSiteSettings)
        self.assertEqual(obj.site_name, "خدمت یار")
        # Row now exists in DB
        self.assertEqual(PlatformSiteSettings.objects.count(), 1)

    def test_get_returns_existing_row(self):
        """get() returns the existing row without creating duplicates."""
        from apps.platform_core.models import PlatformSiteSettings
        from apps.platform_core.services_site_settings import PlatformSiteSettingsService

        PlatformSiteSettings.objects.all().delete()
        PlatformSiteSettings.objects.create(
            site_name="تست پلتفرم",
            site_url="https://test.ir",
            login_url="https://test.ir/login/",
            support_phone="02112345678",
        )

        obj = PlatformSiteSettingsService.get()

        self.assertEqual(obj.site_name, "تست پلتفرم")
        self.assertEqual(obj.site_url, "https://test.ir")
        self.assertEqual(obj.login_url, "https://test.ir/login/")
        self.assertEqual(obj.support_phone, "02112345678")
        self.assertEqual(PlatformSiteSettings.objects.count(), 1)

    def test_get_context_contains_site_name(self):
        """get_context() dict must contain 'site_name' key."""
        from apps.platform_core.models import PlatformSiteSettings
        from apps.platform_core.services_site_settings import PlatformSiteSettingsService

        PlatformSiteSettings.objects.all().delete()
        PlatformSiteSettings.objects.create(site_name="خدمت یار تست")

        ctx = PlatformSiteSettingsService.get_context()

        self.assertIn("site_name", ctx)
        self.assertEqual(ctx["site_name"], "خدمت یار تست")

    def test_get_context_contains_login_url(self):
        """get_context() dict must contain 'login_url' key."""
        from apps.platform_core.models import PlatformSiteSettings
        from apps.platform_core.services_site_settings import PlatformSiteSettingsService

        PlatformSiteSettings.objects.all().delete()
        PlatformSiteSettings.objects.create(login_url="https://app.ir/login/")

        ctx = PlatformSiteSettingsService.get_context()

        self.assertIn("login_url", ctx)
        self.assertEqual(ctx["login_url"], "https://app.ir/login/")

    def test_get_context_contains_all_keys(self):
        """get_context() must return site_name, site_url, login_url, support_phone."""
        from apps.platform_core.services_site_settings import PlatformSiteSettingsService

        ctx = PlatformSiteSettingsService.get_context()

        self.assertIn("site_name", ctx)
        self.assertIn("site_url", ctx)
        self.assertIn("login_url", ctx)
        self.assertIn("support_phone", ctx)

    def test_get_context_never_crashes(self):
        """get_context() must never raise even if DB is problematic."""
        from apps.platform_core.services_site_settings import PlatformSiteSettingsService

        # Even with no rows, it should return safe defaults
        from apps.platform_core.models import PlatformSiteSettings
        PlatformSiteSettings.objects.all().delete()

        ctx = PlatformSiteSettingsService.get_context()

        self.assertIsInstance(ctx, dict)
        self.assertIn("site_name", ctx)


class BuildContextForEventSiteVarsTest(TestCase):
    """Test that build_context_for_event injects platform site variables."""

    def test_context_includes_site_name_for_any_event(self):
        """Every event context must include site_name."""
        from apps.notifications.message_builders import build_context_for_event
        from apps.platform_core.models import PlatformSiteSettings

        PlatformSiteSettings.objects.all().delete()
        PlatformSiteSettings.objects.create(site_name="سایت تست")

        context = build_context_for_event("order_created_admin", target=None)

        self.assertIn("site_name", context)
        self.assertEqual(context["site_name"], "سایت تست")

    def test_context_includes_login_url(self):
        """Every event context must include login_url."""
        from apps.notifications.message_builders import build_context_for_event
        from apps.platform_core.models import PlatformSiteSettings

        PlatformSiteSettings.objects.all().delete()
        PlatformSiteSettings.objects.create(login_url="https://panel.ir/login/")

        context = build_context_for_event("sms_credit_low_admin", target=None)

        self.assertIn("login_url", context)
        self.assertEqual(context["login_url"], "https://panel.ir/login/")

    def test_payload_can_override_site_vars(self):
        """Explicit payload values should take priority over site settings."""
        from apps.notifications.message_builders import build_context_for_event
        from apps.platform_core.models import PlatformSiteSettings

        PlatformSiteSettings.objects.all().delete()
        PlatformSiteSettings.objects.create(site_name="پلتفرم اصلی")

        context = build_context_for_event(
            "order_created_admin",
            target=None,
            payload={"site_name": "override_name"},
        )

        # Payload wins over site settings
        self.assertEqual(context["site_name"], "override_name")

    def test_existing_order_context_still_works(self):
        """Existing context builders (order, invoice, etc.) still produce correct vars."""
        from apps.notifications.message_builders import build_context_for_event
        from apps.platform_core.models import PlatformSiteSettings

        PlatformSiteSettings.objects.all().delete()
        PlatformSiteSettings.objects.create(site_name="خدمت یار")

        # Mock an order-like object
        order = MagicMock()
        order.__class__.__name__ = "Order"
        order._meta = MagicMock()
        order._meta.app_label = "orders"
        order._meta.object_name = "Order"
        order.id = 42
        order.company = MagicMock()
        order.company.name = "شرکت تست"
        order.company.code = "test_co"
        order.customer_name = "Ali"
        order.display_customer_name = "Ali"
        order.customer_phone = "09171234567"
        order.display_customer_phone = "09171234567"
        order.technician = None
        order.service_category = None

        context = build_context_for_event("order_created_admin", target=order)

        # Original order vars still present
        self.assertEqual(context["company_name"], "شرکت تست")
        self.assertEqual(context["order_id"], 42)
        self.assertEqual(context["customer_name"], "Ali")

        # Site vars also present
        self.assertIn("site_name", context)
        self.assertEqual(context["site_name"], "خدمت یار")

    def test_no_hardcoded_site_name_in_template_default_texts(self):
        """
        SMS default template texts must not contain hardcoded 'خدمت یار'.
        They should use {{site_name}} for platform identity.

        NOTE: This is an aspirational test — current templates use {{company_name}}
        which is correct for company-sent SMS. Only platform-scope templates
        should use {{site_name}}. This test verifies no one accidentally
        hardcoded the platform name in template_text.
        """
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        for key, tpl in SMS_DEFAULT_TEMPLATES.items():
            text = tpl.get("template_text", "")
            self.assertNotIn(
                "خدمت یار",
                text,
                f"Template '{key}' contains hardcoded 'خدمت یار'. "
                f"Use {{{{site_name}}}} instead.",
            )
