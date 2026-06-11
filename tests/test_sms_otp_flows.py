"""
Tests for the two SMS OTP sending flows:

1. Registration OTP (apps/public/services.py → generate_and_send_otp)
2. Password Reset OTP (apps/accounts/views_password_reset.py → _send_reset_sms)

Both MUST use:
    send_user_mobile_verification_sms(mobile=..., otp_code=..., expire_minutes=...)

which routes through the approved MeliPayamak pattern system.

Required verifications:
- OTP code is generated
- Approved SMS function is called (not direct provider API)
- Mobile number is passed correctly
- expire_minutes is passed correctly
- No direct requests.post from the view/service
- Failure is handled gracefully (never crashes the flow)
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone


# =============================================================================
# REGISTRATION OTP TESTS
# =============================================================================


class RegistrationOTPSendTest(TestCase):
    """Test that registration flow uses the approved SMS sending function."""

    def setUp(self):
        from apps.tenants.models import Company
        # Ensure session infrastructure
        pass

    @patch("apps.public.services.send_user_mobile_verification_sms")
    def test_generate_and_send_otp_calls_approved_function(self, mock_send):
        """generate_and_send_otp must call send_user_mobile_verification_sms."""
        from apps.public.services import CompanyRegistrationService

        mock_send.return_value = {"success": True, "message_id": "12345"}

        service = CompanyRegistrationService()

        # We need a session_key for OTP storage
        from django.contrib.sessions.backends.db import SessionStore
        session = SessionStore()
        session.create()

        code = service.generate_and_send_otp("09171234567", session.session_key)

        # Code must be 6 digits
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

        # The approved function must have been called
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        # Check positional/keyword arguments
        if call_kwargs.kwargs:
            self.assertEqual(call_kwargs.kwargs["mobile"], "09171234567")
            self.assertEqual(call_kwargs.kwargs["otp_code"], code)
            self.assertEqual(call_kwargs.kwargs["expire_minutes"], 5)
        else:
            # Called with positional args
            args = call_kwargs.args
            self.assertEqual(args[0], "09171234567")  # mobile
            self.assertEqual(args[1], code)  # otp_code

    @patch("apps.public.services.send_user_mobile_verification_sms")
    def test_otp_stored_in_database(self, mock_send):
        """OTP code must be stored in RegistrationOTP model."""
        from apps.accounts.models import RegistrationOTP
        from apps.public.services import CompanyRegistrationService

        mock_send.return_value = {"success": True}

        service = CompanyRegistrationService()
        from django.contrib.sessions.backends.db import SessionStore
        session = SessionStore()
        session.create()

        code = service.generate_and_send_otp("09179876543", session.session_key)

        # Must exist in database
        otp = RegistrationOTP.objects.get(
            phone="09179876543",
            code=code,
            session_key=session.session_key,
        )
        self.assertIsNotNone(otp)
        self.assertFalse(otp.is_used)

    @patch("apps.public.services.send_user_mobile_verification_sms")
    def test_sms_failure_does_not_crash(self, mock_send):
        """If SMS send fails, the function must not raise."""
        from apps.public.services import CompanyRegistrationService

        mock_send.side_effect = Exception("Provider down")

        service = CompanyRegistrationService()
        from django.contrib.sessions.backends.db import SessionStore
        session = SessionStore()
        session.create()

        # Must not raise
        code = service.generate_and_send_otp("09170000001", session.session_key)

        # Code is still generated and returned (for possible dev display)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    @patch("apps.public.services.send_user_mobile_verification_sms")
    def test_no_direct_requests_post(self, mock_send):
        """Verify no direct requests.post is called (only the approved function)."""
        from apps.public.services import CompanyRegistrationService

        mock_send.return_value = {"success": True}

        service = CompanyRegistrationService()
        from django.contrib.sessions.backends.db import SessionStore
        session = SessionStore()
        session.create()

        with patch("requests.post") as mock_requests_post:
            service.generate_and_send_otp("09171111111", session.session_key)
            mock_requests_post.assert_not_called()


# =============================================================================
# PASSWORD RESET OTP TESTS
# =============================================================================


class PasswordResetOTPSendTest(TestCase):
    """Test that password reset flow uses the approved SMS sending function."""

    @patch("apps.accounts.views_password_reset.send_user_mobile_verification_sms")
    def test_send_reset_sms_calls_approved_function(self, mock_send):
        """_send_reset_sms must call send_user_mobile_verification_sms."""
        from apps.accounts.views_password_reset import _send_reset_sms

        mock_send.return_value = {"success": True, "message_id": "67890"}

        # Call with a phone, otp_code, and empty users list
        _send_reset_sms("09171234567", "654321", [])

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        if call_kwargs.kwargs:
            self.assertEqual(call_kwargs.kwargs["mobile"], "09171234567")
            self.assertEqual(call_kwargs.kwargs["otp_code"], "654321")
            self.assertEqual(call_kwargs.kwargs["expire_minutes"], 2)
        else:
            args = call_kwargs.args
            self.assertEqual(args[0], "09171234567")
            self.assertEqual(args[1], "654321")

    @patch("apps.accounts.views_password_reset.send_user_mobile_verification_sms")
    def test_send_reset_sms_passes_correct_expire(self, mock_send):
        """Password reset OTP must use expire_minutes=2."""
        from apps.accounts.views_password_reset import _send_reset_sms

        mock_send.return_value = {"success": True}

        _send_reset_sms("09179999999", "123456", [])

        call_kwargs = mock_send.call_args
        if call_kwargs.kwargs:
            self.assertEqual(call_kwargs.kwargs["expire_minutes"], 2)
        else:
            self.assertEqual(call_kwargs.args[2], 2)  # 3rd positional arg

    @patch("apps.accounts.views_password_reset.send_user_mobile_verification_sms")
    def test_send_reset_sms_failure_does_not_raise(self, mock_send):
        """_send_reset_sms must never raise, even if SMS provider fails."""
        from apps.accounts.views_password_reset import _send_reset_sms

        mock_send.side_effect = Exception("MeliPayamak timeout")

        # Must not raise
        _send_reset_sms("09170000000", "111111", [])

    @patch("apps.accounts.views_password_reset.send_user_mobile_verification_sms")
    def test_no_direct_outbox_creation(self, mock_send):
        """Password reset must NOT directly create SMSOutbox/PlatformSMSOutbox records.
        The approved function handles logging internally."""
        from apps.accounts.views_password_reset import _send_reset_sms

        mock_send.return_value = {"success": True}

        with patch("apps.sms.models.SMSOutbox.objects") as mock_outbox:
            with patch("apps.platform_core.models.PlatformSMSOutbox.objects") as mock_platform_outbox:
                _send_reset_sms("09171234567", "999999", [])
                mock_outbox.create.assert_not_called()
                mock_platform_outbox.create.assert_not_called()

    @patch("apps.accounts.views_password_reset.send_user_mobile_verification_sms")
    def test_no_direct_requests_post(self, mock_send):
        """No direct HTTP calls from password reset."""
        from apps.accounts.views_password_reset import _send_reset_sms

        mock_send.return_value = {"success": True}

        with patch("requests.post") as mock_requests_post:
            _send_reset_sms("09172222222", "555555", [])
            mock_requests_post.assert_not_called()


# =============================================================================
# INTEGRATION: Both flows use the same underlying route
# =============================================================================


class OTPFlowsUseApprovedRouteTest(TestCase):
    """Verify both flows ultimately call send_template_pattern_by_owner_route."""

    @patch("apps.sms.providers.melipayamak.send_template_pattern_by_owner_route")
    def test_registration_otp_uses_pattern_route(self, mock_route):
        """Registration OTP → send_user_mobile_verification_sms → pattern route."""
        mock_route.return_value = {"success": True, "message_id": "111"}

        from apps.public.services import CompanyRegistrationService
        from django.contrib.sessions.backends.db import SessionStore

        service = CompanyRegistrationService()
        session = SessionStore()
        session.create()

        code = service.generate_and_send_otp("09173333333", session.session_key)

        mock_route.assert_called_once()
        call_kwargs = mock_route.call_args
        self.assertEqual(call_kwargs.kwargs["template_key"], "user_mobile_verification")
        self.assertEqual(call_kwargs.kwargs["to"], "09173333333")
        self.assertIn("otp_code", call_kwargs.kwargs["variables"])
        self.assertEqual(call_kwargs.kwargs["variables"]["otp_code"], code)

    @patch("apps.sms.providers.melipayamak.send_template_pattern_by_owner_route")
    def test_password_reset_uses_pattern_route(self, mock_route):
        """Password reset → send_user_mobile_verification_sms → pattern route."""
        mock_route.return_value = {"success": True, "message_id": "222"}

        from apps.accounts.views_password_reset import _send_reset_sms

        _send_reset_sms("09174444444", "998877", [])

        mock_route.assert_called_once()
        call_kwargs = mock_route.call_args
        self.assertEqual(call_kwargs.kwargs["template_key"], "user_mobile_verification")
        self.assertEqual(call_kwargs.kwargs["to"], "09174444444")
        self.assertEqual(call_kwargs.kwargs["variables"]["otp_code"], "998877")
