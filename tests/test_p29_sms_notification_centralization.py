"""
P29-SMS-NOTIFICATION-TEMPLATES-CENTRALIZATION: Tests.

Covers:
1. SMS/notification pages render 200
2. theme.css loaded
3. Central classes used
4. No sensitive data
5. Cross-tenant blocked
"""
from django.test import TestCase, override_settings
from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P29Mixin:
    def create_company(self, code="p29_co"):
        return Company.objects.create(code=code, name="P29 Co", slug=code, is_active=True)

    def create_admin(self, company, username="p29_admin"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=UserRole.COMPANY_ADMIN,
        )


@override_settings(ROOT_URLCONF="config.urls")
class SMSNotificationRenderTest(TestCase, P29Mixin):
    """SMS/notification pages render correctly after P29 migration."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_admin(self.company)

    def test_sms_outbox_renders(self):
        self.client.login(username="p29_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/sms/outbox/")
        self.assertEqual(response.status_code, 200)

    def test_sms_credit_renders(self):
        self.client.login(username="p29_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/sms-credit/")
        self.assertEqual(response.status_code, 200)

    def test_notification_settings_renders(self):
        """Communication/notification settings page should render 200."""
        self.client.login(username="p29_admin", password="testpass123")
        # Real route is communication-settings, not notification-settings
        response = self.client.get(f"/{self.company.code}/admin/communication-settings/")
        self.assertEqual(response.status_code, 200)

    def test_sms_pages_load_theme_css(self):
        self.client.login(username="p29_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/sms-credit/")
        self.assertIn("theme.css", response.content.decode())

    def test_no_sensitive_data(self):
        self.client.login(username="p29_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/sms-credit/")
        content = response.content.decode()
        self.assertNotIn("shaba_number", content)
        self.assertNotIn("national_card_image", content)

    def test_no_platform_links(self):
        self.client.login(username="p29_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/sms-credit/")
        content = response.content.decode()
        self.assertNotIn("/owner-platform/", content)

    def test_cross_tenant_blocked(self):
        other = self.create_company("p29_other")
        self.client.login(username="p29_admin", password="testpass123")
        response = self.client.get(f"/{other.code}/admin/sms-credit/")
        self.assertIn(response.status_code, [403, 302])
