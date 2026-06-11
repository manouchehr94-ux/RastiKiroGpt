"""
Tests for convert_template_to_pattern utility.

Verifies:
1. Simple variables converted to {0}, {1}, ...
2. Repeated variables get same number
3. Variables with extra spaces handled
4. variables_order override controls numbering
5. No variables → empty map
6. Persian text and line breaks preserved
7. Unsupported filters do not crash (warning added)
8. format_variable_map_display output
"""
from django.test import TestCase


class ConvertTemplateBasicTest(TestCase):
    """Test basic variable conversion."""

    def test_simple_variables(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "«{{ company_name }}»\nفاکتور {{ invoice_number }}\nمبلغ: {{ invoice_amount }}"
        result = convert_template_to_pattern(text)

        self.assertEqual(result.pattern_text, "«{0}»\nفاکتور {1}\nمبلغ: {2}")
        self.assertEqual(result.variable_map, [
            ("company_name", 0),
            ("invoice_number", 1),
            ("invoice_amount", 2),
        ])

    def test_repeated_variable_same_number(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "{{ company_name }}\nخوش آمدید\n{{ company_name }}"
        result = convert_template_to_pattern(text)

        self.assertEqual(result.pattern_text, "{0}\nخوش آمدید\n{0}")
        self.assertEqual(len(result.variable_map), 1)
        self.assertEqual(result.variable_map[0], ("company_name", 0))

    def test_variables_with_spaces(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "{{company_name}} و {{  invoice_number  }}"
        result = convert_template_to_pattern(text)

        self.assertEqual(result.pattern_text, "{0} و {1}")
        self.assertEqual(result.variable_map[0][0], "company_name")
        self.assertEqual(result.variable_map[1][0], "invoice_number")

    def test_no_variables(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "سلام، پیام ثابت بدون متغیر."
        result = convert_template_to_pattern(text)

        self.assertEqual(result.pattern_text, text)
        self.assertEqual(result.variable_map, [])

    def test_empty_text(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        result = convert_template_to_pattern("")
        self.assertEqual(result.pattern_text, "")
        self.assertEqual(result.variable_map, [])

    def test_persian_text_and_linebreaks_preserved(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "{{ company_name }}\nسفارش جدید ثبت شد.\nمشتری: {{ customer_name }}\nلغو 11"
        result = convert_template_to_pattern(text)

        self.assertIn("سفارش جدید ثبت شد.", result.pattern_text)
        self.assertIn("\n", result.pattern_text)
        self.assertIn("لغو 11", result.pattern_text)
        self.assertEqual(result.pattern_text.count("\n"), 3)


class ConvertTemplateOrderOverrideTest(TestCase):
    """Test variables_order override."""

    def test_order_string_overrides_numbering(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "{{ company_name }}\nمبلغ: {{ amount }}\nشماره: {{ invoice_number }}"
        # Override: amount should be {0}, company_name {1}, invoice_number {2}
        result = convert_template_to_pattern(text, variables_order="amount,company_name,invoice_number")

        self.assertIn("{1}", result.pattern_text)  # company_name → index 1
        self.assertIn("{0}", result.pattern_text)  # amount → index 0
        self.assertIn("{2}", result.pattern_text)  # invoice_number → index 2

    def test_order_list_overrides_numbering(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "{{ a }} {{ b }}"
        result = convert_template_to_pattern(text, variables_order=["b", "a"])

        self.assertEqual(result.pattern_text, "{1} {0}")

    def test_order_with_extra_variables_adds_warning(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "{{ known }} {{ unknown_extra }}"
        result = convert_template_to_pattern(text, variables_order="known")

        self.assertIn("{0}", result.pattern_text)  # known → 0
        self.assertIn("{1}", result.pattern_text)  # unknown_extra → 1
        self.assertTrue(len(result.warnings) > 0)


class ConvertTemplateFilterHandlingTest(TestCase):
    """Test Django filter handling (should not crash)."""

    def test_variable_with_filter(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "مبلغ: {{ amount|intcomma }} ریال"
        result = convert_template_to_pattern(text)

        self.assertEqual(result.pattern_text, "مبلغ: {0} ریال")
        self.assertEqual(result.variable_map[0][0], "amount")
        # Should have a warning about filter
        self.assertTrue(len(result.warnings) > 0)
        self.assertIn("فیلتر", result.warnings[0])

    def test_dotted_variable(self):
        from apps.sms.template_to_provider_pattern import convert_template_to_pattern

        text = "نام: {{ user.name }}"
        result = convert_template_to_pattern(text)

        self.assertEqual(result.pattern_text, "نام: {0}")
        self.assertEqual(result.variable_map[0][0], "user.name")


class FormatVariableMapDisplayTest(TestCase):
    """Test display formatting."""

    def test_format_output(self):
        from apps.sms.template_to_provider_pattern import format_variable_map_display

        variable_map = [("company_name", 0), ("invoice_number", 1), ("amount", 2)]
        display = format_variable_map_display(variable_map)

        self.assertIn("{0} = company_name", display)
        self.assertIn("{1} = invoice_number", display)
        self.assertIn("{2} = amount", display)

    def test_empty_map(self):
        from apps.sms.template_to_provider_pattern import format_variable_map_display

        self.assertEqual(format_variable_map_display([]), "")
