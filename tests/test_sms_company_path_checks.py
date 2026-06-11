"""
Tests for company SMS path business rule enforcement.

Verifies that the queue/send pipeline correctly applies:
1. Company SMS enable/disable
2. Platform SMS enable/disable (global toggle)
3. Template active/inactive
4. Allowed sending hours (send_at scheduling)
5. Credit check at send time
6. Refund on provider failure
7. Deduplication of queued messages

These tests do NOT send real SMS. They mock the provider layer.
"""
from datetime import time, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone


class CompanySMSDisabledTest(TestCase):
    """Disabled company SMS does not create SMSOutbox."""

    def setUp(self):
        from apps.tenants.models import Company
        self.company = Company.objects.create(
            name="Switch Test Co", code="swco", slug="swco", is_active=True
        )

    @patch("apps.sms.services.SMSEventSwitchService.is_enabled", return_value=False)
    def test_disabled_event_returns_none(self, mock_switch):
        """When company has disabled SMS for a template_key, queue returns None."""
        from apps.sms.services import SMSQueueFromTemplateService

        result = SMSQueueFromTemplateService.queue_from_template(
            company=self.company,
            template_key="order_created_admin",
            phone_number="09171234567",
            context={"order_id": 1, "company_name": "Test"},
            fallback_message="Test message",
        )

        self.assertIsNone(result)

    @patch("apps.sms.services.SMSEventSwitchService.is_enabled", return_value=False)
    def test_disabled_event_creates_no_outbox(self, mock_switch):
        """When SMS is disabled, no SMSOutbox record is created at all."""
        from apps.sms.models import SMSOutbox
        from apps.sms.services import SMSQueueFromTemplateService

        initial_count = SMSOutbox.objects.filter(company=self.company).count()

        SMSQueueFromTemplateService.queue_from_template(
            company=self.company,
            template_key="order_created_admin",
            phone_number="09171234567",
            context={},
            fallback_message="Test",
        )

        self.assertEqual(SMSOutbox.objects.filter(company=self.company).count(), initial_count)


class TemplateInactiveTest(TestCase):
    """Inactive template does not create SMSOutbox."""

    def setUp(self):
        from apps.tenants.models import Company
        self.company = Company.objects.create(
            name="Template Test Co", code="tmco", slug="tmco", is_active=True
        )

    @patch("apps.sms.services.SMSEventSwitchService.is_enabled", return_value=True)
    @patch("apps.sms.template_resolver.resolve_effective_sms_template")
    def test_inactive_template_returns_none(self, mock_resolve, mock_switch):
        """If resolved template is inactive, queue_from_template returns None."""
        from apps.sms.services import SMSQueueFromTemplateService

        mock_resolve.return_value = {
            "text": "Some text",
            "source": "master",
            "source_label": "platform",
            "template_obj": MagicMock(key="order_created_admin"),
            "allowed_variables": "",
            "is_active": False,  # INACTIVE
            "send_start_time": None,
            "send_end_time": None,
        }

        result = SMSQueueFromTemplateService.queue_from_template(
            company=self.company,
            template_key="order_created_admin",
            phone_number="09171234567",
            context={"order_id": 1},
            fallback_message="Fallback",
        )

        self.assertIsNone(result)


class SendingHoursTest(TestCase):
    """Outside allowed hours, SMS is scheduled (send_at set) not sent immediately."""

    def setUp(self):
        from apps.tenants.models import Company
        self.company = Company.objects.create(
            name="Hours Test Co", code="hrco", slug="hrco", is_active=True
        )

    @patch("apps.sms.services.SMSEventSwitchService.is_enabled", return_value=True)
    @patch("apps.sms.template_resolver.resolve_effective_sms_template")
    @patch("apps.sms.services.SMSTimeWindowService.calculate_send_at")
    def test_outside_hours_sets_send_at(self, mock_calc_send_at, mock_resolve, mock_switch):
        """When outside allowed hours, SMSOutbox is created with send_at in the future."""
        from apps.sms.models import SMSOutbox
        from apps.sms.services import SMSQueueFromTemplateService

        # Simulate: outside hours, scheduled for tomorrow 8:00
        scheduled_time = timezone.now() + timedelta(hours=10)
        mock_calc_send_at.return_value = scheduled_time

        mock_resolve.return_value = {
            "text": "سفارش جدید #1 ثبت شد.",
            "source": "master",
            "source_label": "platform",
            "template_obj": MagicMock(key="order_created_admin"),
            "allowed_variables": "",
            "is_active": True,
            "send_start_time": time(8, 0),
            "send_end_time": time(20, 0),
        }

        result = SMSQueueFromTemplateService.queue_from_template(
            company=self.company,
            template_key="order_created_admin",
            phone_number="09171234567",
            context={"order_id": 1},
            fallback_message="Fallback",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, SMSOutbox.Status.QUEUED)
        self.assertIsNotNone(result.send_at)
        self.assertEqual(result.send_at, scheduled_time)


class CreditCheckTest(TestCase):
    """Insufficient credit prevents actual send (at send stage)."""

    def setUp(self):
        from apps.tenants.models import Company
        from apps.sms.models import SMSOutbox, SMSProvider

        self.company = Company.objects.create(
            name="Credit Test Co", code="crco", slug="crco", is_active=True
        )
        # Create a provider for the company
        self.provider = SMSProvider.objects.create(
            company=self.company,
            name="Test Provider",
            provider_type="fake",
            api_key="test",
            is_active=True,
        )
        # Create a queued SMS
        self.sms = SMSOutbox.objects.create(
            company=self.company,
            phone_number="09171234567",
            message="Test credit check",
            status=SMSOutbox.Status.QUEUED,
        )

    @patch("apps.platform_core.services_sms_credit.SMSCreditService.try_debit_for_sms")
    def test_insufficient_credit_fails_send(self, mock_debit):
        """When wallet has insufficient credit, send marks SMS as failed."""
        from apps.sms.models import SMSOutbox
        from apps.sms.services import SMSSendService

        # Simulate insufficient credit
        mock_debit.return_value = (False, None, "اعتبار پیامک شرکت کافی نیست.")

        result = SMSSendService.send(sms=self.sms)

        self.assertEqual(result.status, SMSOutbox.Status.FAILED)
        self.assertIn("اعتبار", result.error_message)


class ProviderFailureRefundTest(TestCase):
    """Failed provider send refunds the wallet debit."""

    def setUp(self):
        from apps.tenants.models import Company
        from apps.sms.models import SMSOutbox, SMSProvider

        self.company = Company.objects.create(
            name="Refund Test Co", code="rfco", slug="rfco", is_active=True
        )
        self.provider = SMSProvider.objects.create(
            company=self.company,
            name="Refund Provider",
            provider_type="fake",
            api_key="test",
            is_active=True,
        )
        self.sms = SMSOutbox.objects.create(
            company=self.company,
            phone_number="09001234567",  # Fake provider fails for 0900 numbers
            message="Test refund",
            status=SMSOutbox.Status.QUEUED,
        )

    @patch("apps.platform_core.services_sms_credit.SMSCreditService.refund_sms_debit")
    @patch("apps.platform_core.services_sms_credit.SMSCreditService.try_debit_for_sms")
    def test_provider_failure_triggers_refund(self, mock_debit, mock_refund):
        """When provider returns failure, credit is refunded."""
        from apps.sms.models import SMSOutbox
        from apps.sms.services import SMSSendService

        # Simulate successful debit
        fake_tx = MagicMock()
        mock_debit.return_value = (True, fake_tx, "")

        result = SMSSendService.send(sms=self.sms)

        # FakeSMSProvider fails for 0900* numbers
        self.assertEqual(result.status, SMSOutbox.Status.FAILED)
        # Refund must have been called
        mock_refund.assert_called_once()


class DeduplicationTest(TestCase):
    """Duplicate event does not create duplicate SMSOutbox."""

    def setUp(self):
        from apps.tenants.models import Company
        self.company = Company.objects.create(
            name="Dedup Test Co", code="ddco", slug="ddco", is_active=True
        )

    @patch("apps.sms.services.SMSEventSwitchService.is_enabled", return_value=True)
    @patch("apps.sms.template_resolver.resolve_effective_sms_template")
    @patch("apps.sms.services.SMSTimeWindowService.calculate_send_at", return_value=None)
    def test_duplicate_queued_sms_is_rejected(self, mock_time, mock_resolve, mock_switch):
        """Second queue attempt for same company/template/order returns None."""
        from apps.sms.models import SMSOutbox
        from apps.sms.services import SMSQueueFromTemplateService

        mock_resolve.return_value = {
            "text": "سفارش جدید ثبت شد.",
            "source": "master",
            "source_label": "platform",
            "template_obj": MagicMock(key="order_created_admin"),
            "allowed_variables": "",
            "is_active": True,
            "send_start_time": None,
            "send_end_time": None,
        }

        # First queue — should succeed
        result1 = SMSQueueFromTemplateService.queue_from_template(
            company=self.company,
            template_key="order_created_admin",
            phone_number="09171234567",
            context={"order_id": 99},
            fallback_message="Fallback",
            order_id=99,
        )
        self.assertIsNotNone(result1)
        self.assertEqual(result1.status, SMSOutbox.Status.QUEUED)

        # Second queue for same template/order — should be deduplicated
        result2 = SMSQueueFromTemplateService.queue_from_template(
            company=self.company,
            template_key="order_created_admin",
            phone_number="09171234567",
            context={"order_id": 99},
            fallback_message="Fallback",
            order_id=99,
        )
        self.assertIsNone(result2)

        # Only one outbox record
        count = SMSOutbox.objects.filter(
            company=self.company,
            template_key="order_created_admin",
            order_id=99,
            status=SMSOutbox.Status.QUEUED,
        ).count()
        self.assertEqual(count, 1)
