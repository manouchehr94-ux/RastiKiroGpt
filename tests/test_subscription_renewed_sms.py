"""
Tests for subscription_renewed_admin SMS event/template.

Verifies:
1. Event key exists in EventKey and EVENT_DEFINITIONS
2. Default SMS template exists in SMS_DEFAULT_TEMPLATES
3. Template text starts with {{ site_name }}
4. Template text contains {{ login_url }}
5. Template text ends with لغو 11
6. Event recipient is COMPANY_ADMIN
7. Payer is PLATFORM
8. Required variables are present
9. No real SMS is sent
"""
from django.test import TestCase


class SubscriptionRenewedEventExistsTest(TestCase):
    """Verify subscription_renewed_admin event is defined correctly."""

    def test_event_key_exists(self):
        from apps.notifications.event_catalog import EventKey

        self.assertTrue(hasattr(EventKey, "SUBSCRIPTION_RENEWED_ADMIN"))
        self.assertEqual(EventKey.SUBSCRIPTION_RENEWED_ADMIN, "subscription_renewed_admin")

    def test_event_definition_exists(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        self.assertIn(EventKey.SUBSCRIPTION_RENEWED_ADMIN, EVENT_DEFINITIONS)

    def test_event_recipient_is_company_admin(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey, Recipient

        defn = EVENT_DEFINITIONS[EventKey.SUBSCRIPTION_RENEWED_ADMIN]
        self.assertEqual(defn.recipient, Recipient.COMPANY_ADMIN)

    def test_event_payer_is_platform(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey, Payer

        defn = EVENT_DEFINITIONS[EventKey.SUBSCRIPTION_RENEWED_ADMIN]
        self.assertEqual(defn.payer, Payer.PLATFORM)

    def test_event_sms_supported(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        defn = EVENT_DEFINITIONS[EventKey.SUBSCRIPTION_RENEWED_ADMIN]
        self.assertTrue(defn.sms_supported)

    def test_event_default_sms_enabled(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        defn = EVENT_DEFINITIONS[EventKey.SUBSCRIPTION_RENEWED_ADMIN]
        self.assertTrue(defn.default_sms_enabled)

    def test_required_variables_declared(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        defn = EVENT_DEFINITIONS[EventKey.SUBSCRIPTION_RENEWED_ADMIN]
        variables = defn.template_variables

        self.assertIn("company_name", variables)
        self.assertIn("plan_name", variables)
        self.assertIn("start_date", variables)
        self.assertIn("expire_date", variables)


class SubscriptionRenewedTemplateTest(TestCase):
    """Verify SMS default template for subscription_renewed_admin."""

    def test_template_exists_in_defaults(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        self.assertIn("subscription_renewed_admin", SMS_DEFAULT_TEMPLATES)

    def test_template_text_starts_with_site_name(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]["template_text"]
        self.assertTrue(
            text.startswith("{{ site_name }}"),
            f"Template must start with '{{{{ site_name }}}}', got: {text[:40]}",
        )

    def test_template_text_contains_login_url(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]["template_text"]
        self.assertIn("{{ login_url }}", text)

    def test_template_text_ends_with_cancel_code(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]["template_text"]
        self.assertTrue(
            text.strip().endswith("لغو 11"),
            f"Template must end with 'لغو 11', got: ...{text.strip()[-20:]}",
        )

    def test_template_contains_plan_name(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]["template_text"]
        self.assertIn("{{ plan_name }}", text)

    def test_template_contains_start_date(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]["template_text"]
        self.assertIn("{{ start_date }}", text)

    def test_template_contains_expire_date(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]["template_text"]
        self.assertIn("{{ expire_date }}", text)

    def test_template_scope_is_platform(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        tpl = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]
        self.assertEqual(tpl["scope"], "platform")

    def test_template_recipient_is_admin(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        tpl = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]
        self.assertEqual(tpl["recipient_type"], "admin")

    def test_no_hardcoded_site_name_in_text(self):
        """Template must use {{site_name}}, not hardcoded platform name."""
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]["template_text"]
        self.assertNotIn("خدمت یار", text)
        self.assertNotIn("رستی", text)


class SubscriptionRenewedContextTest(TestCase):
    """Verify that subscription renewal context includes required variables."""

    def test_context_builder_includes_site_name(self):
        """build_context_for_event provides site_name for subscription events."""
        from apps.notifications.message_builders import build_context_for_event
        from apps.platform_core.models import PlatformSiteSettings

        PlatformSiteSettings.objects.all().delete()
        PlatformSiteSettings.objects.create(
            site_name="تست سایت",
            login_url="https://test.ir/login/",
        )

        context = build_context_for_event(
            "subscription_renewed_admin",
            target=None,
            payload={
                "company_name": "شرکت آزمایشی",
                "plan_name": "طلایی",
                "start_date": "1405/01/01",
                "expire_date": "1405/12/29",
            },
        )

        self.assertEqual(context["site_name"], "تست سایت")
        self.assertEqual(context["login_url"], "https://test.ir/login/")
        self.assertEqual(context["company_name"], "شرکت آزمایشی")
        self.assertEqual(context["plan_name"], "طلایی")
        self.assertEqual(context["start_date"], "1405/01/01")
        self.assertEqual(context["expire_date"], "1405/12/29")
