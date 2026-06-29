"""
TASK-017 — Communication Settings: Business Cause Matrix.

Tests:
 1.  Matrix page loads 200
 2.  Context has `groups`, not `event_rows`
 3.  Context has exactly 8 groups
 4.  SMS runner section with required IDs is unchanged on matrix page
 5.  Order group has 6 rows
 6.  SMS chip for order_created admin exists (event_key set)
 7.  SMS chip for order_created operator is na (no event_key)
 8.  SMS chip for payment_started is lock (sms_supported=False)
 9.  In-app chip for discount cause customer is off/on (no sms, but in_app may differ)
10.  Chips reflect actual NotificationSetting state
11.  Main matrix page contains NO raw message text
12.  Main matrix page has NO comm-toggle-form elements
13.  Detail button link targets the correct cause URL
14.  Cause detail page loads 200 for a valid cause
15.  Cause detail shows only defined role cards (skips None event_keys)
16.  order_assignment cause has exactly 2 message cards
17.  Invalid cause_key returns 404 on detail page
18.  Detail page has NO درخواست تغییر link
19.  Direct access to template change request URL returns 404
20.  AJAX toggle still works on main URL (TASK-016B regression)
21.  AJAX toggle works on detail page URL
22.  Technician role cannot access the matrix page
23.  Technician role cannot access the detail page
24.  Tenant isolation: company B's data not affected by company A's toggle
"""
import itertools

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CompanyUser, UserRole
from apps.notifications.models import NotificationSetting
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
        name=name or f"MatrixCo {tag}",
        code=f"matrixco{tag}",
        slug=f"matrixco-{tag}",
        is_active=True,
    )


def _admin(company):
    return CompanyUser.objects.create_user(
        username=f"madm{_n()}",
        password="testpass123",
        company=company,
        role=UserRole.COMPANY_ADMIN,
    )


def _tech(company):
    return CompanyUser.objects.create_user(
        username=f"tech{_n()}",
        password="techpass123",
        company=company,
        role=UserRole.TECHNICIAN,
        phone=f"091{_n():08d}",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class CommMatrixPageTest(TestCase):
    """Tests for the main Business Cause Matrix page."""

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.client.login(username=self.admin.username, password="testpass123")
        self.url = f"/{self.company.code}/admin/communication-settings/"

    def test_1_matrix_page_loads_200(self):
        """Test 1: Matrix page loads with status 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_2_context_has_groups_not_event_rows(self):
        """Test 2: Context has `groups` key and does NOT have `event_rows`."""
        response = self.client.get(self.url)
        self.assertIn("groups", response.context)
        self.assertNotIn("event_rows", response.context)

    def test_3_context_has_eight_groups(self):
        """Test 3: Exactly 8 groups are returned in context."""
        response = self.client.get(self.url)
        groups = response.context["groups"]
        self.assertEqual(len(groups), 8)

    def test_4_sms_runner_section_ids_present(self):
        """Test 4: All required SMS runner section HTML IDs are unchanged."""
        response = self.client.get(self.url)
        content = response.content.decode()
        required_ids = [
            "sms-status-section",
            "sms-queue-warning" if False else "sms-queued-stat",  # queue-warning only appears with queued SMS
            "sms-failed-stat",
            "sms-sent-today-stat",
            "sms-provider-stat",
        ]
        # Always-present IDs
        for id_str in ["sms-status-section", "sms-queued-stat", "sms-failed-stat",
                       "sms-sent-today-stat", "sms-provider-stat"]:
            self.assertIn(id_str, content, f"Missing HTML id: {id_str}")
        self.assertIn("وضعیت ارسال پیامک", content)
        self.assertIn("process_sms_outbox", content)

    def test_5_order_group_has_six_rows(self):
        """Test 5: The `orders` group contains exactly 6 cause rows."""
        response = self.client.get(self.url)
        groups = response.context["groups"]
        order_group = next((g for g in groups if g["group_key"] == "orders"), None)
        self.assertIsNotNone(order_group, "orders group not found")
        self.assertEqual(order_group["row_count"], 6)
        self.assertEqual(len(order_group["rows"]), 6)

    def test_6_sms_chip_for_order_created_admin_has_event_key(self):
        """Test 6: order_created cause admin SMS chip has a non-null event_key."""
        response = self.client.get(self.url)
        groups = response.context["groups"]
        order_group = next(g for g in groups if g["group_key"] == "orders")
        oc_row = next(r for r in order_group["rows"] if r["cause_key"] == "order_created")
        self.assertIsNotNone(oc_row["sms"]["admin"]["event_key"])
        self.assertEqual(oc_row["sms"]["admin"]["event_key"], "order_created_admin")

    def test_7_sms_chip_for_order_created_operator_is_na(self):
        """Test 7: order_created cause operator SMS chip is `na` (no event_key defined)."""
        response = self.client.get(self.url)
        groups = response.context["groups"]
        order_group = next(g for g in groups if g["group_key"] == "orders")
        oc_row = next(r for r in order_group["rows"] if r["cause_key"] == "order_created")
        op_chip = oc_row["sms"]["operator"]
        self.assertIsNone(op_chip["event_key"])
        self.assertEqual(op_chip["state"], "na")

    def test_8_sms_chip_payment_started_admin_is_lock(self):
        """Test 8: payment_started admin SMS chip is `lock` (sms_supported=False)."""
        response = self.client.get(self.url)
        groups = response.context["groups"]
        pay_group = next(g for g in groups if g["group_key"] == "payment")
        ps_row = next(r for r in pay_group["rows"] if r["cause_key"] == "payment_started")
        admin_chip = ps_row["sms"]["admin"]
        self.assertIsNotNone(admin_chip["event_key"])
        self.assertEqual(admin_chip["state"], "lock")
        self.assertFalse(admin_chip["supported"])

    def test_9_chips_reflect_notification_setting_state(self):
        """Test 9: Chip state reflects the current NotificationSetting for the company."""
        # Force order_created_admin to sms_enabled=False
        setting, _ = NotificationSetting.objects.get_or_create(
            company=self.company,
            event_key="order_created_admin",
            defaults={"sms_enabled": True, "in_app_enabled": True},
        )
        setting.sms_enabled = False
        setting.save()

        response = self.client.get(self.url)
        groups = response.context["groups"]
        order_group = next(g for g in groups if g["group_key"] == "orders")
        oc_row = next(r for r in order_group["rows"] if r["cause_key"] == "order_created")
        self.assertEqual(oc_row["sms"]["admin"]["state"], "off")

        # Now enable it
        setting.sms_enabled = True
        setting.save()
        response2 = self.client.get(self.url)
        groups2 = response2.context["groups"]
        order_group2 = next(g for g in groups2 if g["group_key"] == "orders")
        oc_row2 = next(r for r in order_group2["rows"] if r["cause_key"] == "order_created")
        self.assertEqual(oc_row2["sms"]["admin"]["state"], "on")

    def test_10_matrix_has_no_message_text(self):
        """Test 10: Main matrix page does NOT render template body text (cause-tpl-pre element)."""
        response = self.client.get(self.url)
        content = response.content.decode()
        # cause-tpl-pre is the CSS class that displays message template body — must not appear on matrix
        self.assertNotIn("cause-tpl-pre", content)

    def test_11_matrix_has_no_toggle_forms(self):
        """Test 11: Main matrix page has no comm-toggle-form (forms) but does have comm-role-toggle (buttons)."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertNotIn("comm-toggle-form", content)
        # Clickable role toggles are present as buttons, not form elements
        self.assertIn("comm-role-toggle", content)

    def test_12_detail_button_links_to_cause_url(self):
        """Test 12: Detail buttons in the matrix link to the correct cause detail URL."""
        response = self.client.get(self.url)
        content = response.content.decode()
        expected_url = f"/{self.company.code}/admin/communication-settings/cause/order_created/"
        self.assertIn(expected_url, content)

    def test_13_no_request_change_link_on_matrix(self):
        """Test 13: The matrix page has no درخواست تغییر link."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertNotIn("درخواست تغییر", content)
        self.assertNotIn("/request/", content)

    def test_28_supported_chips_render_with_data_event_key(self):
        """Test 28: Supported (on/off) role toggles on the matrix render with data-event-key."""
        response = self.client.get(self.url)
        content = response.content.decode()
        # order_created_admin is a supported SMS event
        self.assertIn('data-event-key="order_created_admin"', content)
        self.assertIn('data-field="sms_enabled"', content)
        self.assertIn('data-field="in_app_enabled"', content)

    def test_29_na_and_lock_items_are_non_interactive(self):
        """Test 29: NA chips use comm-chip-na; locked items use is-disabled (non-interactive span)."""
        response = self.client.get(self.url)
        content = response.content.decode()
        # NA items render with comm-chip-na class (no data-event-key)
        self.assertIn("comm-chip-na", content)
        # Locked items render with is-disabled class (pointer-events:none, not a button)
        self.assertIn("is-disabled", content)
        # At least some clickable buttons with data-event-key must exist
        import re
        data_keys = re.findall(r'data-event-key=', content)
        self.assertGreater(len(data_keys), 0)

    def test_30_ajax_toggle_on_matrix_updates_setting(self):
        """Test 30: AJAX toggle POST to the matrix URL saves the NotificationSetting."""
        event_key = "order_created_admin"
        response = self.client.post(
            self.url,
            {"event_key": event_key, "field": "sms_enabled", "value": "0"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["new_value"])
        setting = NotificationSetting.objects.get(company=self.company, event_key=event_key)
        self.assertFalse(setting.sms_enabled)


@override_settings(ROOT_URLCONF="config.urls")
class CommCauseDetailTest(TestCase):
    """Tests for the business cause detail page."""

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.client.login(username=self.admin.username, password="testpass123")
        self.base_url = f"/{self.company.code}/admin/communication-settings/cause/"

    def test_14_detail_page_loads_200_for_valid_cause(self):
        """Test 14: Detail page returns 200 for a valid cause_key."""
        response = self.client.get(f"{self.base_url}order_created/")
        self.assertEqual(response.status_code, 200)

    def test_15_detail_shows_only_defined_roles(self):
        """Test 15: Detail page shows only roles that have a non-None event_key."""
        response = self.client.get(f"{self.base_url}order_created/")
        self.assertEqual(response.status_code, 200)
        cards = response.context["cards"]
        # order_created: admin=order_created_admin, technician=order_available_technician,
        # customer=order_created_customer — operator=None (skipped)
        roles_present = [c["role"] for c in cards]
        self.assertIn("admin", roles_present)
        self.assertIn("technician", roles_present)
        self.assertIn("customer", roles_present)
        self.assertNotIn("operator", roles_present)

    def test_16_order_assignment_has_two_cards(self):
        """Test 16: order_assignment cause has exactly 2 message cards (technician + customer)."""
        response = self.client.get(f"{self.base_url}order_assignment/")
        self.assertEqual(response.status_code, 200)
        cards = response.context["cards"]
        self.assertEqual(len(cards), 2)
        roles = {c["role"] for c in cards}
        self.assertIn("technician", roles)
        self.assertIn("customer", roles)

    def test_17_invalid_cause_returns_404(self):
        """Test 17: Detail page returns 404 for an unknown cause_key."""
        response = self.client.get(f"{self.base_url}nonexistent_cause_xyz/")
        self.assertEqual(response.status_code, 404)

    def test_18_detail_has_no_request_change_link(self):
        """Test 18: Detail page does NOT contain a درخواست تغییر link."""
        response = self.client.get(f"{self.base_url}order_created/")
        content = response.content.decode()
        self.assertNotIn("درخواست تغییر", content)
        self.assertNotIn("/request/", content)

    def test_19_detail_has_back_link_to_matrix(self):
        """Test 19: Detail page contains a back link to the main matrix page."""
        response = self.client.get(f"{self.base_url}order_created/")
        content = response.content.decode()
        matrix_url = f"/{self.company.code}/admin/communication-settings/"
        self.assertIn(matrix_url, content)

    def test_20_detail_context_has_cause_and_group_info(self):
        """Test 20: Detail context includes cause_key, cause_label, group_label."""
        response = self.client.get(f"{self.base_url}order_created/")
        self.assertIn("cause_key", response.context)
        self.assertIn("cause_label", response.context)
        self.assertIn("group_label", response.context)
        self.assertEqual(response.context["cause_key"], "order_created")

    def test_21_detail_toggle_sms_via_ajax(self):
        """Test 21: AJAX toggle POST to detail URL changes SMS enabled state."""
        detail_url = f"{self.base_url}order_assignment/"
        event_key = "order_assigned_technician"

        response = self.client.post(
            detail_url,
            {"event_key": event_key, "field": "sms_enabled", "value": "0"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["event_key"], event_key)
        self.assertFalse(data["new_value"])

        setting = NotificationSetting.objects.get(company=self.company, event_key=event_key)
        self.assertFalse(setting.sms_enabled)


@override_settings(ROOT_URLCONF="config.urls")
class CommChangeRequestDisabledTest(TestCase):
    """Tests that the company-side request-change URL is disabled."""

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.client.login(username=self.admin.username, password="testpass123")

    def test_22_request_change_url_returns_404(self):
        """Test 22: Direct GET to template change request URL returns 404."""
        url = f"/{self.company.code}/admin/communication-settings/template/order_created_admin/request/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_23_request_change_url_post_also_returns_404(self):
        """Test 23: POST to template change request URL also returns 404."""
        url = f"/{self.company.code}/admin/communication-settings/template/order_created_admin/request/"
        response = self.client.post(url, {"message_text": "new text"})
        self.assertEqual(response.status_code, 404)


@override_settings(ROOT_URLCONF="config.urls")
class CommMatrixAccessControlTest(TestCase):
    """Tests that only COMPANY_ADMIN/COMPANY_STAFF can access matrix and detail pages."""

    def setUp(self):
        self.company = _company()
        self.technician = _tech(self.company)
        self.client.login(username=self.technician.username, password="techpass123")
        self.matrix_url = f"/{self.company.code}/admin/communication-settings/"
        self.detail_url = f"/{self.company.code}/admin/communication-settings/cause/order_created/"

    def test_24_technician_blocked_from_matrix(self):
        """Test 24: TECHNICIAN role is blocked from the matrix page (302 or 403)."""
        response = self.client.get(self.matrix_url)
        self.assertIn(response.status_code, [302, 403])

    def test_25_technician_blocked_from_detail(self):
        """Test 25: TECHNICIAN role is blocked from the cause detail page (302 or 403)."""
        response = self.client.get(self.detail_url)
        self.assertIn(response.status_code, [302, 403])


@override_settings(ROOT_URLCONF="config.urls")
class CommMatrixTenantIsolationTest(TestCase):
    """Tests that company A's toggles cannot affect company B's settings."""

    def setUp(self):
        self.company_a = _company("IsolCo A")
        self.company_b = _company("IsolCo B")
        self.admin_a = _admin(self.company_a)
        self.client.login(username=self.admin_a.username, password="testpass123")
        self.url_a = f"/{self.company_a.code}/admin/communication-settings/"

    def test_26_toggle_only_affects_own_company(self):
        """Test 26: Toggling an event for company A does not affect company B."""
        event_key = "order_assigned_technician"
        # Pre-create setting for company B in enabled state
        setting_b = NotificationSetting.objects.create(
            company=self.company_b,
            event_key=event_key,
            sms_enabled=True,
            in_app_enabled=True,
        )

        # Toggle company A's setting to disabled
        response = self.client.post(
            self.url_a,
            {"event_key": event_key, "field": "sms_enabled", "value": "0"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertTrue(response.json()["ok"])

        # Company B's setting must be unchanged
        setting_b.refresh_from_db()
        self.assertTrue(setting_b.sms_enabled)

    def test_27_ajax_toggle_on_main_url_still_works(self):
        """Test 27: Existing AJAX toggle on the main URL works (TASK-016B regression)."""
        response = self.client.post(
            self.url_a,
            {"event_key": "order_assigned_technician", "field": "sms_enabled", "value": "0"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["new_value"])
