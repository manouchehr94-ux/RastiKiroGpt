"""
Tests for customer address in technician order-related SMS templates.

Verifies:
1. build_order_context includes customer_address
2. If address missing, customer_address fallback is "ثبت نشده"
3. order_available_technician template contains {{ customer_address }}
4. order_assigned_technician template contains {{ customer_address }}
5. order_cancel_approved_technician template contains {{ customer_address }}
6. order_cancel_rejected_technician template contains {{ customer_address }}
7. All modified technician templates end with لغو 11
8. No real SMS is sent
"""
from unittest.mock import MagicMock

from django.test import TestCase


TECHNICIAN_ORDER_KEYS = [
    "order_available_technician",
    "order_assigned_technician",
    "order_cancel_approved_technician",
    "order_cancel_rejected_technician",
]


class BuildOrderContextAddressTest(TestCase):
    """Test build_order_context provides customer_address."""

    def test_context_includes_customer_address_from_order(self):
        """build_order_context extracts address from order.address."""
        from apps.notifications.message_builders import build_order_context

        order = MagicMock()
        order.company = MagicMock()
        order.company.name = "Test Co"
        order.company.code = "tc"
        order.id = 1
        order.customer_name = "Ali"
        order.display_customer_name = "Ali"
        order.customer_phone = "09171234567"
        order.display_customer_phone = "09171234567"
        order.address = "خیابان ولیعصر، پلاک ۱۲"
        order.customer_address = ""
        order.display_address = ""
        order.service_date = None
        order.scheduled_at = None
        order.preferred_time = ""
        order.technician = None

        ctx = build_order_context(order)

        self.assertEqual(ctx["customer_address"], "خیابان ولیعصر، پلاک ۱۲")

    def test_context_fallback_when_address_missing(self):
        """If all address fields are empty, fallback is 'ثبت نشده'."""
        from apps.notifications.message_builders import build_order_context

        order = MagicMock()
        order.company = MagicMock()
        order.company.name = "Test Co"
        order.company.code = "tc"
        order.id = 2
        order.customer_name = "Sara"
        order.display_customer_name = "Sara"
        order.customer_phone = "09179876543"
        order.display_customer_phone = "09179876543"
        order.address = ""
        order.customer_address = ""
        order.display_address = ""
        order.service_date = None
        order.scheduled_at = None
        order.preferred_time = ""
        order.technician = None

        ctx = build_order_context(order)

        self.assertEqual(ctx["customer_address"], "ثبت نشده")

    def test_context_includes_scheduled_at(self):
        """build_order_context includes scheduled_at if available."""
        from apps.notifications.message_builders import build_order_context

        order = MagicMock()
        order.company = MagicMock()
        order.company.name = "Co"
        order.company.code = "co"
        order.id = 3
        order.customer_name = "R"
        order.display_customer_name = "R"
        order.customer_phone = "09170000000"
        order.display_customer_phone = "09170000000"
        order.address = "آدرس"
        order.customer_address = ""
        order.display_address = ""
        order.service_date = "1405/03/15"
        order.scheduled_at = None
        order.preferred_time = ""
        order.technician = None

        ctx = build_order_context(order)

        self.assertIn("scheduled_at", ctx)
        self.assertEqual(ctx["scheduled_at"], "1405/03/15")


class TechnicianTemplateAddressTest(TestCase):
    """Verify technician order templates include customer_address."""

    def test_order_available_technician_has_address(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["order_available_technician"]["template_text"]
        self.assertIn("{{ customer_address }}", text)

    def test_order_assigned_technician_has_address(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["order_assigned_technician"]["template_text"]
        self.assertIn("{{ customer_address }}", text)

    def test_order_cancel_approved_technician_has_address(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["order_cancel_approved_technician"]["template_text"]
        self.assertIn("{{ customer_address }}", text)

    def test_order_cancel_rejected_technician_has_address(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["order_cancel_rejected_technician"]["template_text"]
        self.assertIn("{{ customer_address }}", text)


class TechnicianTemplateEndWithCancelTest(TestCase):
    """All modified technician order templates must end with لغو 11."""

    def test_all_technician_order_templates_end_with_cancel(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        for key in TECHNICIAN_ORDER_KEYS:
            text = SMS_DEFAULT_TEMPLATES[key]["template_text"]
            self.assertTrue(
                text.strip().endswith("لغو 11"),
                f"Template '{key}' must end with 'لغو 11', got: ...{text.strip()[-20:]}",
            )


class TechnicianTemplateVariablesTest(TestCase):
    """Verify customer_address is declared in template_variables."""

    def test_all_technician_order_templates_declare_customer_address(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        for key in TECHNICIAN_ORDER_KEYS:
            variables = SMS_DEFAULT_TEMPLATES[key]["template_variables"]
            self.assertIn(
                "customer_address",
                variables,
                f"Template '{key}' must declare 'customer_address' in template_variables",
            )

    def test_event_definitions_declare_customer_address(self):
        from apps.notifications.event_catalog import EVENT_DEFINITIONS

        for key in TECHNICIAN_ORDER_KEYS:
            defn = EVENT_DEFINITIONS.get(key)
            self.assertIsNotNone(defn, f"Event '{key}' not found in EVENT_DEFINITIONS")
            self.assertIn(
                "customer_address",
                defn.template_variables,
                f"Event '{key}' must declare 'customer_address' in template_variables",
            )
