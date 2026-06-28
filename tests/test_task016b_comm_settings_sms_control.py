"""
TASK-016B — Communication Settings: SMS Runner Visibility and Manual Processing.

Tests:
 1. Communication settings page shows SMS status section.
 2. Queued SMS count is displayed.
 3. Failed SMS count is displayed.
 4. Sent-today count is displayed.
 5. Provider configured status is displayed.
 6. Manual process POST calls SMSOutboxProcessorService.process with limit=20 for current company.
 7. Manual process action affects only current company SMS rows.
 8. Unauthorized user (TECHNICIAN) cannot access the page.
 9. Cross-company isolation: company B's SMS not processed when company A admin clicks process.
10. Existing notification toggle still works (no regression).
"""
import itertools
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CompanyUser, UserRole
from apps.sms.models import SMSOutbox, SMSProvider
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company(name=None):
    tag = _n()
    return Company.objects.create(
        name=name or f"CommCo {tag}",
        code=f"commco{tag}",
        slug=f"commco-{tag}",
        is_active=True,
    )


def _admin(company):
    return CompanyUser.objects.create_user(
        username=f"adm{_n()}",
        password="testpass123",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _tech_user(company):
    return CompanyUser.objects.create_user(
        username=f"tech{_n()}",
        password="techpass123",
        company=company,
        role=UserRole.TECHNICIAN,
        phone=f"091{_n():08d}",
    )


def _provider(company):
    return SMSProvider.objects.create(
        company=company,
        name="Test Provider",
        provider_type=SMSProvider.ProviderType.FAKE,
        api_key="fake-key",
        sender_number="3000",
        is_active=True,
    )


def _sms(company, status=SMSOutbox.Status.QUEUED, sent_at=None, failed_at=None):
    kwargs = dict(
        company=company,
        phone_number="09123456789",
        message="Test message",
        template_key="order_assigned_technician",
        status=status,
        queued_at=timezone.now(),
    )
    if sent_at is not None:
        kwargs["sent_at"] = sent_at
    if failed_at is not None:
        kwargs["failed_at"] = failed_at
    return SMSOutbox.objects.create(**kwargs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class CommSettingsSMSStatusTest(TestCase):
    """Tests for the SMS status section on the communication settings page."""

    def setUp(self):
        self.company = _company("Status Co")
        self.admin = _admin(self.company)
        self.client.login(username=self.admin.username, password="testpass123")
        self.url = f"/{self.company.code}/admin/communication-settings/"

    def test_1_sms_status_section_present(self):
        """Test 1: Communication settings page includes the SMS status section."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("sms-status-section", content)
        self.assertIn("وضعیت ارسال پیامک", content)

    def test_2_queued_count_displayed(self):
        """Test 2: Queued SMS count is rendered in the status card."""
        _sms(self.company, status=SMSOutbox.Status.QUEUED)
        _sms(self.company, status=SMSOutbox.Status.QUEUED)
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("sms-queued-stat", content)
        # queued_count = 2; must appear somewhere in the stats grid
        self.assertIn("در صف ارسال", content)
        # Verify the count comes through the context
        self.assertEqual(response.context["sms_status"]["queued_count"], 2)

    def test_3_failed_count_displayed(self):
        """Test 3: Failed SMS count is rendered in the status card."""
        _sms(self.company, status=SMSOutbox.Status.FAILED, failed_at=timezone.now())
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("sms-failed-stat", content)
        self.assertEqual(response.context["sms_status"]["failed_count"], 1)

    def test_4_sent_today_count_displayed(self):
        """Test 4: Sent-today count is rendered in the status card."""
        _sms(self.company, status=SMSOutbox.Status.SENT, sent_at=timezone.now())
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("sms-sent-today-stat", content)
        self.assertEqual(response.context["sms_status"]["sent_today_count"], 1)

    def test_4b_yesterday_sent_not_counted_today(self):
        """Test 4b: SMS sent yesterday is NOT counted in sent_today."""
        yesterday = timezone.now() - timedelta(days=1)
        _sms(self.company, status=SMSOutbox.Status.SENT, sent_at=yesterday)
        response = self.client.get(self.url)
        self.assertEqual(response.context["sms_status"]["sent_today_count"], 0)

    def test_5_provider_configured_status_absent(self):
        """Test 5a: No provider → page shows provider not configured."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("sms-provider-stat", content)
        self.assertFalse(response.context["sms_status"]["provider_configured"])
        self.assertIn("ارائه‌دهنده تنظیم نشده", content)

    def test_5b_provider_configured_status_present(self):
        """Test 5b: With active provider → page shows provider active."""
        _provider(self.company)
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertTrue(response.context["sms_status"]["provider_configured"])
        self.assertIn("فعال", content)

    def test_queue_warning_shown_when_queued(self):
        """Queue warning banner appears when there are queued SMS."""
        _sms(self.company, status=SMSOutbox.Status.QUEUED)
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("sms-queue-warning", content)
        self.assertIn("پیامک‌های در صف وجود دارد", content)

    def test_failed_warning_shown_when_failed(self):
        """Failed warning banner appears when there are failed SMS."""
        _sms(self.company, status=SMSOutbox.Status.FAILED, failed_at=timezone.now())
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("sms-failed-warning", content)
        self.assertIn("ناموفق بوده‌اند", content)

    def test_process_button_shown_when_queued(self):
        """Process button appears when there are queued SMS."""
        _sms(self.company, status=SMSOutbox.Status.QUEUED)
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("sms-process-btn", content)
        self.assertIn("ارسال پیامک‌های در صف", content)

    def test_runner_documentation_present(self):
        """Runner documentation block is present on the page."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("process_sms_outbox", content)


@override_settings(ROOT_URLCONF="config.urls")
class CommSettingsManualProcessTest(TestCase):
    """Tests for the manual SMS process action."""

    def setUp(self):
        self.company = _company("Process Co")
        self.admin = _admin(self.company)
        self.client.login(username=self.admin.username, password="testpass123")
        self.url = f"/{self.company.code}/admin/communication-settings/"

    def test_6_process_post_calls_service_with_company_and_limit_20(self):
        """Test 6: POST action=process_queue calls SMSOutboxProcessorService.process(company=…, limit=20)."""
        _sms(self.company, status=SMSOutbox.Status.QUEUED)
        with patch(
            "apps.platform_core.views_tenant_comm_settings.SMSOutboxProcessorService.process",
            return_value={"scanned": 1, "sent": 1, "failed": 0, "skipped": 0, "dry_run": False},
        ) as mock_process:
            response = self.client.post(self.url, {"action": "process_queue"})
            mock_process.assert_called_once_with(company=self.company, limit=20)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("sms-process-result", content)

    def test_7_process_shows_result_summary(self):
        """Test 7: After processing, result summary is rendered on the page."""
        _provider(self.company)
        _sms(self.company, status=SMSOutbox.Status.QUEUED)
        with patch(
            "apps.platform_core.views_tenant_comm_settings.SMSOutboxProcessorService.process",
            return_value={"scanned": 1, "sent": 1, "failed": 0, "skipped": 0, "dry_run": False},
        ):
            response = self.client.post(self.url, {"action": "process_queue"})

        content = response.content.decode()
        self.assertIn("نتیجه پردازش", content)
        self.assertIn("پردازش انجام شد", content)

    def test_7b_process_affects_only_current_company_sms(self):
        """Test 7b: The process call receives the current company, not None (cross-co isolation)."""
        other_co = _company("Other Process Co")
        _sms(self.company, status=SMSOutbox.Status.QUEUED)
        _sms(other_co, status=SMSOutbox.Status.QUEUED)

        with patch(
            "apps.platform_core.views_tenant_comm_settings.SMSOutboxProcessorService.process",
            return_value={"scanned": 0, "sent": 0, "failed": 0, "skipped": 0, "dry_run": False},
        ) as mock_process:
            self.client.post(self.url, {"action": "process_queue"})
            # Must be called with THIS company, not None or other_co
            args, kwargs = mock_process.call_args
            self.assertEqual(kwargs["company"], self.company)
            self.assertNotEqual(kwargs["company"], other_co)

    def test_8_unauthorized_technician_cannot_access(self):
        """Test 8: A TECHNICIAN role user is blocked from the communication settings page."""
        tech = _tech_user(self.company)
        self.client.logout()
        self.client.login(username=tech.username, password="techpass123")
        response = self.client.get(self.url)
        self.assertIn(response.status_code, [302, 403])

    def test_8b_unauthorized_technician_cannot_process(self):
        """Test 8b: A TECHNICIAN role user cannot trigger the process action."""
        tech = _tech_user(self.company)
        self.client.logout()
        self.client.login(username=tech.username, password="techpass123")
        response = self.client.post(self.url, {"action": "process_queue"})
        self.assertIn(response.status_code, [302, 403])

    def test_9_cross_company_process_isolation(self):
        """Test 9: Company A's admin cannot process company B's SMS via the action."""
        company_b = _company("Company B")
        sms_b = _sms(company_b, status=SMSOutbox.Status.QUEUED)

        # Admin of company_a triggers process → company_a's company is used
        # company_b's SMS must remain untouched
        with patch(
            "apps.platform_core.views_tenant_comm_settings.SMSOutboxProcessorService.process",
            return_value={"scanned": 0, "sent": 0, "failed": 0, "skipped": 0, "dry_run": False},
        ) as mock_process:
            self.client.post(self.url, {"action": "process_queue"})
            kwargs = mock_process.call_args[1]
            self.assertNotEqual(kwargs["company"], company_b)

        # company_b's SMS should still be QUEUED (not processed)
        sms_b.refresh_from_db()
        self.assertEqual(sms_b.status, SMSOutbox.Status.QUEUED)

    def test_10_existing_toggle_still_works(self):
        """Test 10: Existing event toggle POST still works after view changes (no regression)."""
        response = self.client.post(
            self.url,
            {
                "event_key": "order_assigned_technician",
                "field": "sms_enabled",
                "value": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["event_key"], "order_assigned_technician")
        self.assertEqual(data["field"], "sms_enabled")
        self.assertFalse(data["new_value"])

    def test_no_queued_message_shows_empty_state(self):
        """With no queued SMS, the process button is hidden and no warning shown."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertNotIn("sms-queue-warning", content)
        self.assertEqual(response.context["sms_status"]["queued_count"], 0)
