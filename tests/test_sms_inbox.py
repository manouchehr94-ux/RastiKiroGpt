"""
Unit tests for the SMS Inbox reply-capture system.

Required test cases:
1. Incoming "4" after survey SMS → matched to correct company, survey_rating=4
2. Incoming complaint after technician SMS → matched to correct company
3. Incoming SMS after reply window → unmatched
4. Incoming SMS with no previous outgoing message → unmatched
5. Duplicate provider_message_id → ignored
6. Phone normalization works
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone


class PhoneNormalizationTest(TestCase):
    """Test normalize_phone utility.

    Each input phone number must normalize to the same logical number
    in 09xxxxxxxxx format. The expected values must match the input digits.
    """

    def test_09_format(self):
        from apps.sms.services_inbox import normalize_phone
        self.assertEqual(normalize_phone("09171234567"), "09171234567")

    def test_plus98_format(self):
        from apps.sms.services_inbox import normalize_phone
        # +989171234567 → strip '+' → '989171234567' (12 chars, starts with 98) → '0' + '9171234567'
        self.assertEqual(normalize_phone("+989171234567"), "09171234567")

    def test_98_format(self):
        from apps.sms.services_inbox import normalize_phone
        # 989171234567 → 12 chars, starts with 98 → '0' + '9171234567'
        self.assertEqual(normalize_phone("989171234567"), "09171234567")

    def test_9_format(self):
        from apps.sms.services_inbox import normalize_phone
        # 9171234567 → 10 chars, starts with 9 → '0' + '9171234567'
        self.assertEqual(normalize_phone("9171234567"), "09171234567")

    def test_0098_format(self):
        from apps.sms.services_inbox import normalize_phone
        # 00989171234567 → starts with 0098 → '0' + '9171234567'
        self.assertEqual(normalize_phone("00989171234567"), "09171234567")

    def test_with_dashes_and_spaces(self):
        from apps.sms.services_inbox import normalize_phone
        # Dashes and spaces stripped, then normal 09... format
        self.assertEqual(normalize_phone("0917-123-4567"), "09171234567")
        self.assertEqual(normalize_phone("0917 123 4567"), "09171234567")

    def test_persian_digits(self):
        from apps.sms.services_inbox import normalize_phone
        # ۰۹۱۷۱۲۳۴۵۶۷ → Persian digits converted to ASCII → 09171234567
        self.assertEqual(normalize_phone("\u06f0\u06f9\u06f1\u06f7\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7"), "09171234567")

    def test_empty(self):
        from apps.sms.services_inbox import normalize_phone
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")


class SurveyDetectionTest(TestCase):
    """Test detect_response_type."""

    def test_single_digit_1_to_5(self):
        from apps.sms.services_inbox import detect_response_type
        from apps.sms.models_inbox import SMSInbox

        for digit in range(1, 6):
            rtype, value = detect_response_type(str(digit))
            self.assertEqual(rtype, SMSInbox.ResponseType.SURVEY_RATING)
            self.assertEqual(value, digit)

    def test_persian_digit(self):
        from apps.sms.services_inbox import detect_response_type
        from apps.sms.models_inbox import SMSInbox

        rtype, value = detect_response_type("\u06f4")  # Persian 4
        self.assertEqual(rtype, SMSInbox.ResponseType.SURVEY_RATING)
        self.assertEqual(value, 4)

    def test_digit_with_whitespace(self):
        from apps.sms.services_inbox import detect_response_type
        from apps.sms.models_inbox import SMSInbox

        rtype, value = detect_response_type("  3  ")
        self.assertEqual(rtype, SMSInbox.ResponseType.SURVEY_RATING)
        self.assertEqual(value, 3)

    def test_non_survey_text(self):
        from apps.sms.services_inbox import detect_response_type
        from apps.sms.models_inbox import SMSInbox

        rtype, value = detect_response_type("The technician has not arrived yet.")
        self.assertEqual(rtype, SMSInbox.ResponseType.CUSTOMER_MESSAGE)
        self.assertIsNone(value)

    def test_digit_outside_range(self):
        from apps.sms.services_inbox import detect_response_type
        from apps.sms.models_inbox import SMSInbox

        rtype, value = detect_response_type("7")
        self.assertEqual(rtype, SMSInbox.ResponseType.CUSTOMER_MESSAGE)
        self.assertIsNone(value)

    def test_empty_text(self):
        from apps.sms.services_inbox import detect_response_type
        from apps.sms.models_inbox import SMSInbox

        rtype, value = detect_response_type("")
        self.assertEqual(rtype, SMSInbox.ResponseType.UNKNOWN)
        self.assertIsNone(value)


class SMSInboxMatchingTest(TestCase):
    """Test matching algorithm: incoming SMS matched to company via recent outbox."""

    def setUp(self):
        from apps.tenants.models import Company
        from apps.sms.models import SMSOutbox, SMSProvider

        self.company_a = Company.objects.create(name="Company A", code="compa", slug="compa", is_active=True)
        self.company_b = Company.objects.create(name="Company B", code="compb", slug="compb", is_active=True)

        # Company A's provider
        self.provider_a = SMSProvider.objects.create(
            company=self.company_a, name="ProvA", provider_type="melipayamak",
            api_key="key", is_active=True,
        )

    def _create_sent_outbox(self, company, phone, minutes_ago=10, template_key="survey_request_customer"):
        """Helper: create a sent outbox record."""
        from apps.sms.models import SMSOutbox

        sent_time = timezone.now() - timedelta(minutes=minutes_ago)
        return SMSOutbox.objects.create(
            company=company,
            phone_number=phone,
            message="Please rate our service from 1 to 5.",
            template_key=template_key,
            status=SMSOutbox.Status.SENT,
            sent_at=sent_time,
        )

    def test_survey_reply_matched_to_correct_company(self):
        """Incoming '4' after survey SMS → matched to Company A, survey_rating=4."""
        from apps.sms.services_inbox import SMSInboxIngestionService

        # Company A sent survey to customer 10 minutes ago
        self._create_sent_outbox(self.company_a, "09171234567", minutes_ago=10)

        result = SMSInboxIngestionService.ingest_message(
            provider=None,
            provider_message_id="test_survey_1",
            from_number="09171234567",
            to_number="50001234",
            text="4",
            received_at=timezone.now(),
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "matched")
        self.assertEqual(result.company, self.company_a)
        self.assertEqual(result.response_type, "survey_rating")
        self.assertEqual(result.rating_value, 4)

    def test_complaint_after_technician_sms_matched(self):
        """Incoming complaint after technician dispatch SMS → matched to Company A."""
        from apps.sms.services_inbox import SMSInboxIngestionService

        self._create_sent_outbox(
            self.company_a, "09179876543", minutes_ago=60,
            template_key="order_assigned_technician",
        )

        result = SMSInboxIngestionService.ingest_message(
            provider=None,
            provider_message_id="test_complaint_1",
            from_number="09179876543",
            to_number="50001234",
            text="The technician has not arrived yet.",
            received_at=timezone.now(),
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "matched")
        self.assertEqual(result.company, self.company_a)
        self.assertEqual(result.response_type, "customer_message")
        self.assertIsNone(result.rating_value)

    def test_incoming_after_reply_window_unmatched(self):
        """Incoming SMS after 24-hour reply window → unmatched."""
        from apps.sms.services_inbox import SMSInboxIngestionService

        # Outbox sent 25 hours ago (outside default 24h window)
        self._create_sent_outbox(self.company_a, "09170000001", minutes_ago=25 * 60)

        result = SMSInboxIngestionService.ingest_message(
            provider=None,
            provider_message_id="test_expired_1",
            from_number="09170000001",
            to_number="50001234",
            text="Hello",
            received_at=timezone.now(),
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "unmatched")
        self.assertIsNone(result.company)

    def test_incoming_no_previous_outgoing_unmatched(self):
        """Incoming SMS with no previous outgoing message → unmatched."""
        from apps.sms.services_inbox import SMSInboxIngestionService

        result = SMSInboxIngestionService.ingest_message(
            provider=None,
            provider_message_id="test_no_outbox_1",
            from_number="09160000000",
            to_number="50001234",
            text="Random message",
            received_at=timezone.now(),
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "unmatched")
        self.assertIsNone(result.company)
        self.assertEqual(result.response_type, "customer_message")

    def test_duplicate_provider_message_id_ignored(self):
        """Duplicate provider_message_id is ignored (returns None)."""
        from apps.sms.services_inbox import SMSInboxIngestionService
        from apps.sms.models_inbox import SMSInbox

        self._create_sent_outbox(self.company_a, "09171111111", minutes_ago=5)

        # First ingest
        r1 = SMSInboxIngestionService.ingest_message(
            provider=None,
            provider_message_id="dup_msg_001",
            from_number="09171111111",
            to_number="50001234",
            text="5",
            received_at=timezone.now(),
        )
        self.assertIsNotNone(r1)

        # Second ingest with same provider_message_id
        r2 = SMSInboxIngestionService.ingest_message(
            provider=None,
            provider_message_id="dup_msg_001",
            from_number="09171111111",
            to_number="50001234",
            text="5",
            received_at=timezone.now(),
        )
        self.assertIsNone(r2)

        # Only one record in DB
        count = SMSInbox.objects.filter(provider_message_id="dup_msg_001").count()
        self.assertEqual(count, 1)

    def test_ambiguous_when_multiple_companies(self):
        """If multiple companies sent to the same number, match_status=ambiguous."""
        from apps.sms.services_inbox import SMSInboxIngestionService

        # Both companies sent to same customer
        self._create_sent_outbox(self.company_a, "09172222222", minutes_ago=30)
        self._create_sent_outbox(self.company_b, "09172222222", minutes_ago=15)

        result = SMSInboxIngestionService.ingest_message(
            provider=None,
            provider_message_id="test_ambiguous_1",
            from_number="09172222222",
            to_number="50001234",
            text="2",
            received_at=timezone.now(),
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "ambiguous")
        # Should still assign the most recent company
        self.assertEqual(result.company, self.company_b)

    def test_custom_reply_window(self):
        """Custom reply window: 2 hours. Message sent 3h ago → unmatched."""
        from apps.sms.services_inbox import SMSInboxIngestionService

        self._create_sent_outbox(self.company_a, "09173333333", minutes_ago=180)

        result = SMSInboxIngestionService.ingest_message(
            provider=None,
            provider_message_id="test_short_window_1",
            from_number="09173333333",
            to_number="50001234",
            text="1",
            received_at=timezone.now(),
            reply_window_hours=2,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.match_status, "unmatched")


class MeliPayamakInboxFetcherTest(TestCase):
    """Test MeliPayamak inbox fetcher with mocked HTTP."""

    def test_endpoint_uses_sendsms_controller(self):
        """Verify the endpoint is /api/SendSMS/GetMessages (not ReceiveSMS)."""
        from apps.sms.providers.melipayamak_inbox import MELIPAYAMAK_RECEIVE_ENDPOINT

        self.assertEqual(
            MELIPAYAMAK_RECEIVE_ENDPOINT,
            "https://rest.payamak-panel.com/api/SendSMS/GetMessages",
        )
        self.assertNotIn("ReceiveSMS", MELIPAYAMAK_RECEIVE_ENDPOINT)

    @patch("apps.sms.providers.melipayamak_inbox.requests.post")
    def test_fetch_posts_to_correct_url(self, mock_post):
        """Confirm fetch_melipayamak_inbox POSTs to the correct endpoint."""
        from apps.sms.providers.melipayamak_inbox import fetch_melipayamak_inbox

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MyBase": {"RetStatus": 1, "StrRetStatus": "Ok"},
            "Data": [],
        }
        mock_post.return_value = mock_response

        provider = MagicMock()
        provider.username = "989177305910"
        provider.password = ""
        provider.api_key = "test_key"
        provider.api_secret = ""
        provider.sender_number = ""

        fetch_melipayamak_inbox(provider, count=10)

        mock_post.assert_called_once()
        called_url = mock_post.call_args[0][0]
        self.assertEqual(called_url, "https://rest.payamak-panel.com/api/SendSMS/GetMessages")

    @patch("apps.sms.providers.melipayamak_inbox.requests.post")
    def test_fetch_success(self, mock_post):
        from apps.sms.providers.melipayamak_inbox import fetch_melipayamak_inbox

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MyBase": {"RetStatus": 1, "StrRetStatus": "Ok"},
            "Data": [
                {
                    "MsgID": 99999,
                    "Body": "4",
                    "SenderNumber": "09171234567",
                    "RecipientNumber": "50001234",
                    "SendDate": "/Date(1715000000000+0430)/",
                }
            ],
        }
        mock_post.return_value = mock_response

        provider = MagicMock()
        provider.username = "989177305910"
        provider.api_key = "test_key"
        provider.password = ""
        provider.api_secret = ""
        provider.sender_number = ""

        results = fetch_melipayamak_inbox(provider, count=50)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["provider_message_id"], "99999")
        self.assertEqual(results[0]["from_number"], "09171234567")
        self.assertEqual(results[0]["text"], "4")

    @patch("apps.sms.providers.melipayamak_inbox.requests.post")
    def test_fetch_empty(self, mock_post):
        from apps.sms.providers.melipayamak_inbox import fetch_melipayamak_inbox

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MyBase": {"RetStatus": 1, "StrRetStatus": "Ok"},
            "Data": [],
        }
        mock_post.return_value = mock_response

        provider = MagicMock()
        provider.username = "user"
        provider.api_key = "pass"
        provider.password = ""
        provider.api_secret = ""
        provider.sender_number = ""

        results = fetch_melipayamak_inbox(provider)
        self.assertEqual(len(results), 0)

    def test_fetch_missing_credentials(self):
        from apps.sms.providers.melipayamak_inbox import InboxFetchError, fetch_melipayamak_inbox

        provider = MagicMock()
        provider.username = ""
        provider.password = ""
        provider.sender_number = ""
        provider.api_secret = ""
        provider.api_key = ""

        with self.assertRaises(InboxFetchError):
            fetch_melipayamak_inbox(provider)

    @patch("apps.sms.providers.melipayamak_inbox.requests.post")
    def test_fetch_uses_api_key_when_password_empty(self, mock_post):
        """When provider.password is empty, api_key is used as the credential."""
        from apps.sms.providers.melipayamak_inbox import fetch_melipayamak_inbox

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MyBase": {"RetStatus": 1, "StrRetStatus": "Ok"},
            "Data": [],
        }
        mock_post.return_value = mock_response

        provider = MagicMock()
        provider.username = "989177305910"
        provider.password = ""  # empty
        provider.api_key = "my_real_api_key_here"
        provider.api_secret = ""
        provider.sender_number = ""

        fetch_melipayamak_inbox(provider)

        # Verify the payload sent uses api_key value as "password"
        call_kwargs = mock_post.call_args
        sent_payload = call_kwargs[1]["json"] if "json" in (call_kwargs[1] or {}) else call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("json")
        # The json kwarg
        sent_json = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        self.assertEqual(sent_json["password"], "my_real_api_key_here")
        self.assertEqual(sent_json["username"], "989177305910")

    @patch("apps.sms.providers.melipayamak_inbox.requests.post")
    def test_fetch_parses_mybase_response_structure(self, mock_post):
        """Response status is parsed from MyBase, messages from Data."""
        from apps.sms.providers.melipayamak_inbox import fetch_melipayamak_inbox

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MyBase": {"Value": "123", "RetStatus": 1, "StrRetStatus": "Ok"},
            "Data": [
                {
                    "MsgID": 77777,
                    "Body": "سلام",
                    "SenderNumber": "09171234567",
                    "RecipientNumber": "50001234",
                    "SendDate": "/Date(1715000000000+0430)/",
                }
            ],
        }
        mock_post.return_value = mock_response

        provider = MagicMock()
        provider.username = "989177305910"
        provider.api_key = "test_key"
        provider.password = ""
        provider.api_secret = ""
        provider.sender_number = ""

        results = fetch_melipayamak_inbox(provider)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["provider_message_id"], "77777")
        self.assertEqual(results[0]["from_number"], "09171234567")
        self.assertEqual(results[0]["text"], "سلام")

    @patch("apps.sms.providers.melipayamak_inbox.requests.post")
    def test_fetch_invalid_data_error_from_mybase(self, mock_post):
        """InvalidData (RetStatus=35) from MyBase raises InboxFetchError."""
        from apps.sms.providers.melipayamak_inbox import InboxFetchError, fetch_melipayamak_inbox

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MyBase": {"Value": "", "RetStatus": 35, "StrRetStatus": "InvalidData"},
            "Data": [],
        }
        mock_post.return_value = mock_response

        provider = MagicMock()
        provider.username = "989177305910"
        provider.api_key = "wrong_key"
        provider.password = ""
        provider.api_secret = ""
        provider.sender_number = ""

        with self.assertRaises(InboxFetchError) as ctx:
            fetch_melipayamak_inbox(provider)

        error_msg = str(ctx.exception)
        self.assertIn("35", error_msg)
        self.assertIn("InvalidData", error_msg)


class SMSInboxModelTest(TestCase):
    """Test SMSInbox model."""

    def test_text_preview_short(self):
        from apps.sms.models_inbox import SMSInbox
        msg = SMSInbox(from_number="09171234567", to_number="5000", text="Short")
        self.assertEqual(msg.text_preview, "Short")

    def test_text_preview_long(self):
        from apps.sms.models_inbox import SMSInbox
        msg = SMSInbox(from_number="09171234567", to_number="5000", text="A" * 200)
        self.assertTrue(msg.text_preview.endswith("..."))
        self.assertEqual(len(msg.text_preview), 80)

    def test_str_representation(self):
        from apps.sms.models_inbox import SMSInbox
        msg = SMSInbox(from_number="09171234567", to_number="5000", text="Hi", match_status="unmatched")
        self.assertIn("09171234567", str(msg))
        self.assertIn("unmatched", str(msg))
