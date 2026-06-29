"""
Core in-app notification service tests.

Covers:
- NotificationCreateService.create respects the in_app_enabled gate
- Each payment role has an independent event key:
    payment_success_customer  → controls customer notification only
    payment_success_admin     → controls admin (COMPANY_ADMIN) notification only
    payment_success_operator  → controls operator (COMPANY_STAFF) notification only
- Disabling one key must not suppress the others
- Communication matrix exposes admin/operator/customer columns for payment_success
- Tenant isolation: cross-company mark-read is blocked with 404
"""
from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.notifications.models import Notification, NotificationSetting
from apps.notifications.services import (
    NotificationCreateService,
    NotificationEventHooks,
    NotificationMarkReadService,
)
from apps.tenants.models import Company


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_company(code):
    return Company.objects.create(code=code, name=f"Company {code}", slug=code, is_active=True)


def _make_admin(company, username):
    return CompanyUser.objects.create_user(
        username=username, password="testpass123",
        company=company, role=UserRole.COMPANY_ADMIN,
    )


def _make_staff(company, username):
    return CompanyUser.objects.create_user(
        username=username, password="testpass123",
        company=company, role=UserRole.COMPANY_STAFF,
    )


def _make_customer_user(company, username):
    return CompanyUser.objects.create_user(
        username=username, password="testpass123",
        company=company, role=UserRole.CUSTOMER,
    )


def _payment_mock(company, invoice=None, amount=500000):
    """Minimal payment mock. invoice=None skips the customer notification branch."""
    p = MagicMock()
    p.company = company
    p.amount = amount
    p.invoice = invoice
    return p


def _disable_key(company, event_key):
    """Explicitly disable an event key for a company."""
    NotificationSetting.objects.update_or_create(
        company=company,
        event_key=event_key,
        defaults={"in_app_enabled": False, "sms_enabled": False},
    )


def _enable_key(company, event_key):
    """Explicitly enable an event key for a company (or rely on fail-open default)."""
    NotificationSetting.objects.update_or_create(
        company=company,
        event_key=event_key,
        defaults={"in_app_enabled": True, "sms_enabled": True},
    )


# ---------------------------------------------------------------------------
# Section 1: NotificationCreateService gate
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class NotificationCreateServiceGateTest(TestCase):
    """NotificationCreateService.create respects in_app_enabled."""

    def setUp(self):
        self.company = _make_company("gate_co")
        self.admin = _make_admin(self.company, "gate_admin")

    def test_create_makes_notification_row(self):
        """Basic sanity: create() returns a saved Notification."""
        n = NotificationCreateService.create(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="تست",
            message="پیام تست",
        )
        self.assertIsNotNone(n)
        self.assertIsNotNone(n.pk)
        self.assertEqual(n.company, self.company)
        self.assertEqual(n.recipient, self.admin)
        self.assertFalse(n.is_read)

    def test_create_blocked_when_in_app_disabled(self):
        """create() returns None and creates no row when in_app_enabled=False."""
        _disable_key(self.company, NotificationSetting.EventKey.ORDER_CREATED_ADMIN)
        result = NotificationCreateService.create(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="تست",
            message="پیام تست",
            event_key=NotificationSetting.EventKey.ORDER_CREATED_ADMIN,
        )
        self.assertIsNone(result)
        self.assertEqual(Notification.objects.filter(company=self.company).count(), 0)

    def test_create_enabled_when_no_setting_row_exists(self):
        """create() defaults to enabled when NotificationSetting row is absent (fail-open)."""
        n = NotificationCreateService.create(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
            title="تست",
            message="پیام تست",
            event_key=NotificationSetting.EventKey.PAYMENT_SUCCESS_ADMIN,
        )
        self.assertIsNotNone(n)

    def test_no_business_notification_uses_empty_event_key(self):
        """
        Business notifications must not use event_key=''.
        Any caller passing '' bypasses the configuration gate entirely, which
        is forbidden by the product architecture rule.

        This test deliberately creates a notification with event_key='' to prove
        it is 'ungated', then asserts that production paths (on_payment_paid)
        do NOT use this pattern.
        """
        # event_key="" always creates (ungated) — it IS possible but forbidden
        n = NotificationCreateService.create(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="ungated",
            message="this should never happen in production",
            event_key="",
        )
        self.assertIsNotNone(n, "event_key='' bypasses the gate — proves empty key is ungated")
        # Ensure the production on_payment_paid path uses real keys (not "")
        from apps.notifications.services import NotificationEventHooks
        import inspect
        source = inspect.getsource(NotificationEventHooks.on_payment_paid)
        self.assertNotIn('event_key=""', source, "on_payment_paid must not use event_key=''")
        self.assertNotIn("event_key=''", source, "on_payment_paid must not use event_key=''")


# ---------------------------------------------------------------------------
# Section 2: payment_success_customer controls ONLY the customer notification
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class PaymentSuccessCustomerKeyTest(TestCase):
    """payment_success_customer gates customer notification; does not affect admin or operator."""

    def setUp(self):
        self.company = _make_company("pay_cust_co")
        self.admin = _make_admin(self.company, "pcust_admin")
        self.staff = _make_staff(self.company, "pcust_staff")
        self.customer_user = _make_customer_user(self.company, "pcust_cust")

    def test_customer_notification_gated_by_payment_success_customer(self):
        """Disabling payment_success_customer blocks the customer notification row."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER)
        result = NotificationCreateService.create(
            company=self.company,
            recipient=self.customer_user,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
            title="پرداخت موفق",
            message="پرداخت انجام شد.",
            event_key=NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER,
        )
        self.assertIsNone(result)
        self.assertEqual(
            Notification.objects.filter(company=self.company, recipient=self.customer_user).count(), 0
        )

    def test_customer_notification_created_when_payment_success_customer_enabled(self):
        """Customer notification is created when payment_success_customer is enabled (default)."""
        result = NotificationCreateService.create(
            company=self.company,
            recipient=self.customer_user,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
            title="پرداخت موفق",
            message="پرداخت انجام شد.",
            event_key=NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER,
        )
        self.assertIsNotNone(result)

    def test_disabling_payment_success_customer_does_not_affect_admin(self):
        """Disabling payment_success_customer has no effect on the admin notification."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER)
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        admin_count = Notification.objects.filter(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
        ).count()
        self.assertEqual(admin_count, 1,
            "Admin must receive PAYMENT_PAID when only payment_success_customer is disabled")

    def test_disabling_payment_success_customer_does_not_affect_operator(self):
        """Disabling payment_success_customer has no effect on the operator notification."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER)
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        staff_count = Notification.objects.filter(
            company=self.company,
            recipient=self.staff,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
        ).count()
        self.assertEqual(staff_count, 1,
            "Operator must receive PAYMENT_PAID when only payment_success_customer is disabled")


# ---------------------------------------------------------------------------
# Section 3: payment_success_admin controls ONLY the admin notification
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class PaymentSuccessAdminKeyTest(TestCase):
    """payment_success_admin gates admin (COMPANY_ADMIN) notification only."""

    def setUp(self):
        self.company = _make_company("pay_admin_co")
        self.admin = _make_admin(self.company, "padmin_admin")
        self.staff = _make_staff(self.company, "padmin_staff")
        self.customer_user = _make_customer_user(self.company, "padmin_cust")

    def test_admin_notification_gated_by_payment_success_admin(self):
        """Disabling payment_success_admin blocks the admin notification row."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_ADMIN)
        result = NotificationCreateService.create(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
            title="پرداخت موفق",
            message="پرداخت انجام شد.",
            event_key=NotificationSetting.EventKey.PAYMENT_SUCCESS_ADMIN,
        )
        self.assertIsNone(result)

    def test_admin_receives_notification_when_payment_success_admin_enabled(self):
        """Admin notification is created when payment_success_admin is enabled (default)."""
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)
        count = Notification.objects.filter(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
        ).count()
        self.assertEqual(count, 1)

    def test_disabling_payment_success_admin_blocks_admin_via_hook(self):
        """on_payment_paid does NOT create admin notification when payment_success_admin disabled."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_ADMIN)
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        admin_count = Notification.objects.filter(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
        ).count()
        self.assertEqual(admin_count, 0,
            "Admin must NOT receive notification when payment_success_admin is disabled")

    def test_disabling_payment_success_admin_does_not_affect_operator(self):
        """Disabling payment_success_admin has no effect on the operator notification."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_ADMIN)
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        staff_count = Notification.objects.filter(
            company=self.company,
            recipient=self.staff,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
        ).count()
        self.assertEqual(staff_count, 1,
            "Operator must still receive PAYMENT_PAID when only payment_success_admin is disabled")

    def test_disabling_payment_success_admin_does_not_affect_customer(self):
        """Disabling payment_success_admin has no effect on the customer gate."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_ADMIN)
        # Customer key is enabled — customer should receive notification
        result = NotificationCreateService.create(
            company=self.company,
            recipient=self.customer_user,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
            title="پرداخت موفق",
            message="پرداخت انجام شد.",
            event_key=NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER,
        )
        self.assertIsNotNone(result,
            "Customer notification must not be affected by payment_success_admin being disabled")


# ---------------------------------------------------------------------------
# Section 4: payment_success_operator controls ONLY the operator notification
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class PaymentSuccessOperatorKeyTest(TestCase):
    """payment_success_operator gates operator (COMPANY_STAFF) notification only."""

    def setUp(self):
        self.company = _make_company("pay_op_co")
        self.admin = _make_admin(self.company, "pop_admin")
        self.staff = _make_staff(self.company, "pop_staff")

    def test_operator_notification_gated_by_payment_success_operator(self):
        """Disabling payment_success_operator blocks the operator notification row."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_OPERATOR)
        result = NotificationCreateService.create(
            company=self.company,
            recipient=self.staff,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
            title="پرداخت موفق",
            message="پرداخت انجام شد.",
            event_key=NotificationSetting.EventKey.PAYMENT_SUCCESS_OPERATOR,
        )
        self.assertIsNone(result)

    def test_operator_receives_notification_when_payment_success_operator_enabled(self):
        """Operator notification is created when payment_success_operator is enabled (default)."""
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)
        count = Notification.objects.filter(
            company=self.company,
            recipient=self.staff,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
        ).count()
        self.assertEqual(count, 1)

    def test_disabling_payment_success_operator_blocks_operator_via_hook(self):
        """on_payment_paid does NOT create operator notification when payment_success_operator disabled."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_OPERATOR)
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        staff_count = Notification.objects.filter(
            company=self.company,
            recipient=self.staff,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
        ).count()
        self.assertEqual(staff_count, 0,
            "Operator must NOT receive notification when payment_success_operator is disabled")

    def test_disabling_payment_success_operator_does_not_affect_admin(self):
        """Disabling payment_success_operator has no effect on admin notification."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_OPERATOR)
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        admin_count = Notification.objects.filter(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
        ).count()
        self.assertEqual(admin_count, 1,
            "Admin must still receive PAYMENT_PAID when only payment_success_operator is disabled")


# ---------------------------------------------------------------------------
# Section 5: Full independence — all three keys are independent
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class PaymentSuccessThreeWayIndependenceTest(TestCase):
    """
    Confirms the three payment success event keys are fully independent.
    Disabling any one must not affect the other two.
    """

    def setUp(self):
        self.company = _make_company("pay_3way_co")
        self.admin = _make_admin(self.company, "3way_admin")
        self.staff = _make_staff(self.company, "3way_staff")
        self.customer_user = _make_customer_user(self.company, "3way_cust")

    def test_all_three_disabled_means_no_payment_notifications(self):
        """When all three keys are disabled, on_payment_paid creates no notifications."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER)
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_ADMIN)
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_OPERATOR)

        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                notification_type=Notification.NotificationType.PAYMENT_PAID,
            ).count(),
            0,
        )

    def test_only_admin_disabled(self):
        """Only admin is blocked; operator receives notification."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_ADMIN)
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        self.assertEqual(
            Notification.objects.filter(company=self.company, recipient=self.admin).count(), 0,
            "Admin must be blocked"
        )
        self.assertEqual(
            Notification.objects.filter(company=self.company, recipient=self.staff).count(), 1,
            "Operator must be unaffected"
        )

    def test_only_operator_disabled(self):
        """Only operator is blocked; admin receives notification."""
        _disable_key(self.company, NotificationSetting.EventKey.PAYMENT_SUCCESS_OPERATOR)
        payment = _payment_mock(self.company)
        NotificationEventHooks.on_payment_paid(payment=payment)

        self.assertEqual(
            Notification.objects.filter(company=self.company, recipient=self.staff).count(), 0,
            "Operator must be blocked"
        )
        self.assertEqual(
            Notification.objects.filter(company=self.company, recipient=self.admin).count(), 1,
            "Admin must be unaffected"
        )

    def test_event_keys_present_in_model_choices(self):
        """All three payment success event keys exist as valid NotificationSetting.EventKey choices."""
        choice_values = [c[0] for c in NotificationSetting.EventKey.choices]
        self.assertIn("payment_success_customer", choice_values)
        self.assertIn("payment_success_admin", choice_values)
        self.assertIn("payment_success_operator", choice_values)

    def test_event_keys_present_in_event_definitions(self):
        """All three payment success event keys are registered in EVENT_DEFINITIONS."""
        from apps.notifications.event_catalog import EVENT_DEFINITIONS
        self.assertIn("payment_success_customer", EVENT_DEFINITIONS)
        self.assertIn("payment_success_admin", EVENT_DEFINITIONS)
        self.assertIn("payment_success_operator", EVENT_DEFINITIONS)

    def test_new_event_definitions_have_correct_payer(self):
        """payment_success_admin and payment_success_operator are payer=COMPANY (not PLATFORM)."""
        from apps.notifications.event_catalog import EVENT_DEFINITIONS, Payer
        admin_def = EVENT_DEFINITIONS["payment_success_admin"]
        operator_def = EVENT_DEFINITIONS["payment_success_operator"]
        self.assertEqual(admin_def.payer, Payer.COMPANY)
        self.assertEqual(operator_def.payer, Payer.COMPANY)

    def test_new_event_definitions_have_in_app_enabled(self):
        """payment_success_admin and payment_success_operator default to in_app_enabled=True."""
        from apps.notifications.event_catalog import EVENT_DEFINITIONS
        admin_def = EVENT_DEFINITIONS["payment_success_admin"]
        operator_def = EVENT_DEFINITIONS["payment_success_operator"]
        self.assertTrue(admin_def.default_in_app_enabled)
        self.assertTrue(operator_def.default_in_app_enabled)


# ---------------------------------------------------------------------------
# Section 6: Communication Matrix shows all three columns for payment_success
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class PaymentSuccessMatrixCatalogTest(TestCase):
    """
    COMMUNICATION_GROUP_CATALOG payment_success row must wire all three role columns.
    """

    def test_payment_success_row_maps_admin_key(self):
        """payment_success cause must map admin → payment_success_admin."""
        from apps.platform_core.views_tenant_comm_settings import COMMUNICATION_GROUP_CATALOG
        row = self._find_row("payment_success")
        self.assertEqual(row["admin"], "payment_success_admin")

    def test_payment_success_row_maps_operator_key(self):
        """payment_success cause must map operator → payment_success_operator."""
        from apps.platform_core.views_tenant_comm_settings import COMMUNICATION_GROUP_CATALOG
        row = self._find_row("payment_success")
        self.assertEqual(row["operator"], "payment_success_operator")

    def test_payment_success_row_maps_customer_key(self):
        """payment_success cause must map customer → payment_success_customer."""
        from apps.platform_core.views_tenant_comm_settings import COMMUNICATION_GROUP_CATALOG
        row = self._find_row("payment_success")
        self.assertEqual(row["customer"], "payment_success_customer")

    def test_payment_success_row_has_no_technician_key(self):
        """payment_success cause must have technician → None (no technician payment notification)."""
        row = self._find_row("payment_success")
        self.assertIsNone(row["technician"])

    def _find_row(self, cause_key):
        from apps.platform_core.views_tenant_comm_settings import COMMUNICATION_GROUP_CATALOG
        for group in COMMUNICATION_GROUP_CATALOG:
            for row in group["rows"]:
                if row["cause_key"] == cause_key:
                    return row
        self.fail(f"cause_key '{cause_key}' not found in COMMUNICATION_GROUP_CATALOG")

    def test_matrix_page_renders_payment_success_admin_chip(self):
        """
        The full communication settings matrix page renders with payment_success_admin
        chip visible for the admin column of پرداخت موفق row.
        """
        company = _make_company("matrix_pay_co")
        admin = _make_admin(company, "matrix_pay_admin")
        self.client.login(username="matrix_pay_admin", password="testpass123")
        response = self.client.get(f"/{company.code}/admin/communication-settings/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("payment_success_admin", content,
            "Matrix page must expose payment_success_admin event key in rendered HTML")
        self.assertIn("payment_success_operator", content,
            "Matrix page must expose payment_success_operator event key in rendered HTML")
        self.assertIn("payment_success_customer", content,
            "Matrix page must expose payment_success_customer event key in rendered HTML")


# ---------------------------------------------------------------------------
# Section 7: Tenant isolation — mark-read view
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class NotificationMarkReadTenantIsolationTest(TestCase):
    """
    Cross-company access to the mark-read endpoint is blocked by the view's
    three-way filter: (id, company, recipient=request.user).
    """

    def setUp(self):
        self.company_a = _make_company("iso_a")
        self.company_b = _make_company("iso_b")
        self.admin_a = _make_admin(self.company_a, "iso_admin_a")
        self.admin_b = _make_admin(self.company_b, "iso_admin_b")
        self.notif_b = Notification.objects.create(
            company=self.company_b,
            recipient=self.admin_b,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="تست",
            message="پیام تست",
        )

    def test_cross_company_mark_read_returns_404(self):
        """
        admin_a (company A) cannot mark read a notification that belongs to company B.
        The view must return 404 and leave the notification unread.
        """
        self.client.login(username="iso_admin_a", password="testpass123")
        url = f"/{self.company_a.code}/admin/notifications/{self.notif_b.id}/read/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.notif_b.refresh_from_db()
        self.assertFalse(self.notif_b.is_read)

    def test_owner_marks_read_successfully(self):
        """Notification owner in the correct company context can mark it as read."""
        self.client.login(username="iso_admin_b", password="testpass123")
        url = f"/{self.company_b.code}/admin/notifications/{self.notif_b.id}/read/"
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 302])
        self.notif_b.refresh_from_db()
        self.assertTrue(self.notif_b.is_read)

    def test_notification_list_is_company_scoped(self):
        """Notification list returns only notifications for the authenticated user's company."""
        notif_a = Notification.objects.create(
            company=self.company_a,
            recipient=self.admin_a,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="اعلان A",
            message="پیام A",
        )
        self.client.login(username="iso_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company_a.code}/admin/notifications/")
        self.assertEqual(response.status_code, 200)
        ids_in_response = [n.id for n in response.context["notifications"]]
        self.assertIn(notif_a.id, ids_in_response)
        self.assertNotIn(self.notif_b.id, ids_in_response)

    def test_mark_all_read_service_is_company_scoped(self):
        """NotificationMarkReadService.mark_all_read only touches the specified company."""
        notif_a = Notification.objects.create(
            company=self.company_a,
            recipient=self.admin_a,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="اعلان A",
            message="پیام A",
        )
        count = NotificationMarkReadService.mark_all_read(company=self.company_a, user=self.admin_a)
        self.assertEqual(count, 1)
        self.notif_b.refresh_from_db()
        self.assertFalse(self.notif_b.is_read)
        notif_a.refresh_from_db()
        self.assertTrue(notif_a.is_read)
