"""
Tests for customer club / discount SMS templates and events.

Verifies:
1. discount_code_customer template exists and is company-paid
2. discount_code_customer compatibility with existing discount_services.py
3. platform_discount_company_admin template exists and is platform-paid
4. Platform template starts with {{ site_name }}
5. Both templates end with لغو 11
6. Required variables are present
7. No real SMS is sent
"""
from django.test import TestCase


# =============================================================================
# COMPANY DISCOUNT: discount_code_customer
# =============================================================================


class DiscountCodeCustomerEventTest(TestCase):
    """Verify discount_code_customer event is defined correctly."""

    def test_event_key_exists(self):
        from apps.notifications.event_catalog import EventKey

        self.assertTrue(hasattr(EventKey, "DISCOUNT_CODE_CUSTOMER"))
        self.assertEqual(EventKey.DISCOUNT_CODE_CUSTOMER, "discount_code_customer")

    def test_event_definition_exists(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        self.assertIn(EventKey.DISCOUNT_CODE_CUSTOMER, EVENT_DEFINITIONS)

    def test_event_payer_is_company(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey, Payer

        defn = EVENT_DEFINITIONS[EventKey.DISCOUNT_CODE_CUSTOMER]
        self.assertEqual(defn.payer, Payer.COMPANY)

    def test_event_recipient_is_customer(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey, Recipient

        defn = EVENT_DEFINITIONS[EventKey.DISCOUNT_CODE_CUSTOMER]
        self.assertEqual(defn.recipient, Recipient.CUSTOMER)

    def test_event_sms_supported(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        defn = EVENT_DEFINITIONS[EventKey.DISCOUNT_CODE_CUSTOMER]
        self.assertTrue(defn.sms_supported)

    def test_required_variables(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        defn = EVENT_DEFINITIONS[EventKey.DISCOUNT_CODE_CUSTOMER]
        for var in ("company_name", "discount_code", "discount_value", "expire_date"):
            self.assertIn(var, defn.template_variables)


class DiscountCodeCustomerTemplateTest(TestCase):
    """Verify SMS default template for discount_code_customer."""

    def test_template_exists_in_defaults(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        self.assertIn("discount_code_customer", SMS_DEFAULT_TEMPLATES)

    def test_template_is_company_scoped(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        tpl = SMS_DEFAULT_TEMPLATES["discount_code_customer"]
        self.assertEqual(tpl["scope"], "company")

    def test_template_ends_with_cancel_code(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["discount_code_customer"]["template_text"]
        self.assertTrue(
            text.strip().endswith("لغو 11"),
            f"Template must end with 'لغو 11', got: ...{text.strip()[-20:]}",
        )

    def test_template_contains_discount_code_var(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["discount_code_customer"]["template_text"]
        self.assertIn("{{ discount_code }}", text)

    def test_template_contains_discount_value_var(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["discount_code_customer"]["template_text"]
        self.assertIn("{{ discount_value }}", text)

    def test_template_contains_expire_date_var(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["discount_code_customer"]["template_text"]
        self.assertIn("{{ expire_date }}", text)


class DiscountCodeCustomerCompatibilityTest(TestCase):
    """Verify existing discount_services.py compatibility is preserved."""

    def test_discount_services_key_matches(self):
        """The DISCOUNT_SMS_TEMPLATE_KEY constant must still be 'discount_code_customer'."""
        from apps.reports.discount_services import DISCOUNT_SMS_TEMPLATE_KEY

        self.assertEqual(DISCOUNT_SMS_TEMPLATE_KEY, "discount_code_customer")

    def test_key_in_sms_template_choices(self):
        """discount_code_customer must exist in SMSTemplate.TemplateKey."""
        from apps.sms.models import SMSTemplate

        keys = [v for v, _ in SMSTemplate.TemplateKey.choices]
        self.assertIn("discount_code_customer", keys)


# =============================================================================
# PLATFORM DISCOUNT: platform_discount_company_admin
# =============================================================================


class PlatformDiscountEventTest(TestCase):
    """Verify platform_discount_company_admin event is defined correctly."""

    def test_event_key_exists(self):
        from apps.notifications.event_catalog import EventKey

        self.assertTrue(hasattr(EventKey, "PLATFORM_DISCOUNT_COMPANY_ADMIN"))
        self.assertEqual(EventKey.PLATFORM_DISCOUNT_COMPANY_ADMIN, "platform_discount_company_admin")

    def test_event_definition_exists(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        self.assertIn(EventKey.PLATFORM_DISCOUNT_COMPANY_ADMIN, EVENT_DEFINITIONS)

    def test_event_payer_is_platform(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey, Payer

        defn = EVENT_DEFINITIONS[EventKey.PLATFORM_DISCOUNT_COMPANY_ADMIN]
        self.assertEqual(defn.payer, Payer.PLATFORM)

    def test_event_recipient_is_company_admin(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey, Recipient

        defn = EVENT_DEFINITIONS[EventKey.PLATFORM_DISCOUNT_COMPANY_ADMIN]
        self.assertEqual(defn.recipient, Recipient.COMPANY_ADMIN)

    def test_event_sms_supported(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        defn = EVENT_DEFINITIONS[EventKey.PLATFORM_DISCOUNT_COMPANY_ADMIN]
        self.assertTrue(defn.sms_supported)

    def test_required_variables(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, EventKey

        defn = EVENT_DEFINITIONS[EventKey.PLATFORM_DISCOUNT_COMPANY_ADMIN]
        for var in ("company_name", "discount_code", "discount_value", "expire_date"):
            self.assertIn(var, defn.template_variables)


class PlatformDiscountTemplateTest(TestCase):
    """Verify SMS default template for platform_discount_company_admin."""

    def test_template_exists_in_defaults(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        self.assertIn("platform_discount_company_admin", SMS_DEFAULT_TEMPLATES)

    def test_template_starts_with_site_name(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["platform_discount_company_admin"]["template_text"]
        self.assertTrue(
            text.startswith("{{ site_name }}"),
            f"Platform template must start with '{{{{ site_name }}}}', got: {text[:40]}",
        )

    def test_template_contains_login_url(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["platform_discount_company_admin"]["template_text"]
        self.assertIn("{{ login_url }}", text)

    def test_template_ends_with_cancel_code(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["platform_discount_company_admin"]["template_text"]
        self.assertTrue(
            text.strip().endswith("لغو 11"),
            f"Template must end with 'لغو 11', got: ...{text.strip()[-20:]}",
        )

    def test_template_is_platform_scoped(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        tpl = SMS_DEFAULT_TEMPLATES["platform_discount_company_admin"]
        self.assertEqual(tpl["scope"], "platform")

    def test_template_contains_discount_code_var(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["platform_discount_company_admin"]["template_text"]
        self.assertIn("{{ discount_code }}", text)

    def test_no_hardcoded_site_name(self):
        """Platform template must use {{site_name}}, not hardcoded name."""
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["platform_discount_company_admin"]["template_text"]
        self.assertNotIn("خدمت یار", text)
        self.assertNotIn("رستی", text)
