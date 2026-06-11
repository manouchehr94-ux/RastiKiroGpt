"""
Tests for SMS footer (لغو 11) enforcement across all templates.

Verifies:
1. All default SMS templates end with لغو 11, except approved exclusions
2. No duplicate لغو 11
3. OTP pattern route is excluded (user_mobile_verification)
4. ensure_sms_footer helper works correctly
5. Existing PRB/C/D templates still have correct structure
6. No real SMS is sent
"""
from django.test import TestCase


# Approved exclusions: templates that must NOT end with لغو 11
FOOTER_EXCLUSIONS = {"user_mobile_verification"}


class AllTemplatesHaveFooterTest(TestCase):
    """Every default SMS template must end with لغو 11, except exclusions."""

    def test_all_templates_end_with_footer(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        missing = []
        for key, tpl in SMS_DEFAULT_TEMPLATES.items():
            if key in FOOTER_EXCLUSIONS:
                continue
            text = tpl.get("template_text", "")
            if not text.strip().endswith("لغو 11"):
                missing.append(key)

        self.assertEqual(
            missing, [],
            f"Templates missing 'لغو 11' footer: {missing}",
        )

    def test_exclusions_do_not_have_footer(self):
        """user_mobile_verification must NOT end with لغو 11."""
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        for key in FOOTER_EXCLUSIONS:
            text = SMS_DEFAULT_TEMPLATES[key]["template_text"]
            self.assertFalse(
                text.strip().endswith("لغو 11"),
                f"Excluded template '{key}' should NOT have footer.",
            )

    def test_no_duplicate_footer(self):
        """No template should have لغو 11 appearing more than once."""
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        for key, tpl in SMS_DEFAULT_TEMPLATES.items():
            text = tpl.get("template_text", "")
            count = text.count("لغو 11")
            self.assertLessEqual(
                count, 1,
                f"Template '{key}' has duplicate footer (count={count})",
            )


class EnsureSmsFooterHelperTest(TestCase):
    """Test the ensure_sms_footer utility function."""

    def test_adds_footer_when_missing(self):
        from apps.sms.sms_footer import ensure_sms_footer

        result = ensure_sms_footer("سلام، سفارش جدید ثبت شد.")
        self.assertTrue(result.endswith("لغو 11"))

    def test_does_not_duplicate_footer(self):
        from apps.sms.sms_footer import ensure_sms_footer

        text = "سلام\nلغو 11"
        result = ensure_sms_footer(text)
        self.assertEqual(result.count("لغو 11"), 1)

    def test_trims_trailing_whitespace(self):
        from apps.sms.sms_footer import ensure_sms_footer

        result = ensure_sms_footer("سلام   \n\n  ")
        self.assertTrue(result.endswith("لغو 11"))
        self.assertNotIn("   \n", result)

    def test_empty_text_returns_footer(self):
        from apps.sms.sms_footer import ensure_sms_footer

        result = ensure_sms_footer("")
        self.assertEqual(result, "لغو 11")

    def test_preserves_line_breaks(self):
        from apps.sms.sms_footer import ensure_sms_footer

        text = "خط اول\nخط دوم\nخط سوم"
        result = ensure_sms_footer(text)
        self.assertIn("خط اول\nخط دوم\nخط سوم", result)
        self.assertTrue(result.endswith("لغو 11"))

    def test_should_have_footer_returns_true_for_normal_keys(self):
        from apps.sms.sms_footer import should_have_footer

        self.assertTrue(should_have_footer("order_created_admin"))
        self.assertTrue(should_have_footer("invoice_issued_customer"))
        self.assertTrue(should_have_footer("subscription_renewed_admin"))

    def test_should_have_footer_returns_false_for_otp(self):
        from apps.sms.sms_footer import should_have_footer

        self.assertFalse(should_have_footer("user_mobile_verification"))


class OTPPatternExclusionTest(TestCase):
    """OTP pattern route must still send only the code without footer."""

    def test_otp_template_has_no_footer(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["user_mobile_verification"]["template_text"]
        self.assertNotIn("لغو 11", text)
        # Should contain only the OTP code and expiry
        self.assertIn("{{ otp_code }}", text)
        self.assertIn("{{ expire_minutes }}", text)


class ExistingPRTemplatesIntegrityTest(TestCase):
    """Verify PR B/C/D templates maintain their structure with footer."""

    def test_subscription_renewed_starts_with_site_name(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["subscription_renewed_admin"]["template_text"]
        self.assertTrue(text.startswith("{{ site_name }}"))

    def test_platform_discount_starts_with_site_name(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["platform_discount_company_admin"]["template_text"]
        self.assertTrue(text.startswith("{{ site_name }}"))

    def test_technician_order_templates_have_address(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        for key in ["order_available_technician", "order_assigned_technician",
                    "order_cancel_approved_technician", "order_cancel_rejected_technician"]:
            text = SMS_DEFAULT_TEMPLATES[key]["template_text"]
            self.assertIn("{{ customer_address }}", text, f"{key} missing address")

    def test_discount_customer_has_discount_code(self):
        from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES

        text = SMS_DEFAULT_TEMPLATES["discount_code_customer"]["template_text"]
        self.assertIn("{{ discount_code }}", text)
