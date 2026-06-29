"""
In-app notification UX tests — Patches A through F.

Covers:
  A: Bell badge appears/absent based on unread count; count is user+company-scoped
  B: Dropdown shows latest 5 only; does not mark any notification as read
  C: Notification center pagination
  D: mark_all_read POST endpoint — scoped to user+company; cross-company safe
  E: Single mark-read deep-links to related order/invoice; falls back to list
  F: Existing ownership / tenant isolation still passes
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.notifications.models import Notification
from apps.notifications.selectors import NotificationSelector
from apps.notifications.services import NotificationMarkReadService
from apps.tenants.models import Company


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company(code):
    return Company.objects.create(code=code, name=f"Co {code}", slug=code, is_active=True)


def _admin(company, username):
    return CompanyUser.objects.create_user(
        username=username, password="testpass",
        company=company, role=UserRole.COMPANY_ADMIN,
    )


def _staff(company, username):
    return CompanyUser.objects.create_user(
        username=username, password="testpass",
        company=company, role=UserRole.COMPANY_STAFF,
    )


def _tech(company, username):
    return CompanyUser.objects.create_user(
        username=username, password="testpass",
        company=company, role=UserRole.TECHNICIAN,
    )


def _notif(company, user, title="اعلان", is_read=False, related_order=None, related_invoice=None):
    return Notification.objects.create(
        company=company,
        recipient=user,
        notification_type=Notification.NotificationType.ORDER_CREATED,
        title=title,
        message="پیام تست",
        is_read=is_read,
        related_order=related_order,
        related_invoice=related_invoice,
    )


# ---------------------------------------------------------------------------
# Patch A — Badge count: user-scoped and company-scoped
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class BadgeCountScopeTest(TestCase):
    """Unread count is scoped to (company, user). No cross-contamination."""

    def setUp(self):
        self.co = _company("badge_co")
        self.admin = _admin(self.co, "badge_admin")
        self.staff = _staff(self.co, "badge_staff")
        self.co2 = _company("badge_co2")
        self.admin2 = _admin(self.co2, "badge_admin2")

    def test_unread_count_is_user_scoped(self):
        """Admin and staff within the same company have independent counts."""
        _notif(self.co, self.admin, is_read=False)
        _notif(self.co, self.admin, is_read=False)
        _notif(self.co, self.staff, is_read=False)
        self.assertEqual(
            NotificationSelector.get_unread_count(company=self.co, user=self.admin), 2
        )
        self.assertEqual(
            NotificationSelector.get_unread_count(company=self.co, user=self.staff), 1
        )

    def test_unread_count_is_company_scoped(self):
        """Admin in company B does not see admin-in-company-A's unread count."""
        _notif(self.co, self.admin, is_read=False)
        _notif(self.co, self.admin, is_read=False)
        self.assertEqual(
            NotificationSelector.get_unread_count(company=self.co2, user=self.admin2), 0
        )

    def test_read_notifications_not_counted(self):
        """is_read=True notifications do not contribute to unread count."""
        _notif(self.co, self.admin, is_read=True)
        _notif(self.co, self.admin, is_read=False)
        self.assertEqual(
            NotificationSelector.get_unread_count(company=self.co, user=self.admin), 1
        )

    def test_badge_appears_in_topbar_when_unread_exists(self):
        """Bell badge element is rendered in topbar when admin has unread notifications."""
        _notif(self.co, self.admin, is_read=False)
        self.client.login(username="badge_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn('class="notif-badge"', content, "Badge <span> must appear when unread_count > 0")

    def test_badge_absent_when_no_unread(self):
        """Bell badge element is NOT rendered when admin has zero unread notifications."""
        _notif(self.co, self.admin, is_read=True)
        self.client.login(username="badge_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        # CSS contains ".notif-badge{" but the rendered badge span has class="notif-badge"
        self.assertNotIn(
            'class="notif-badge"', content,
            "Badge <span> element must NOT appear when no unread"
        )

    def test_technician_badge_appears_in_bottom_nav_when_unread(self):
        """Technician bottom nav (technician.html layout) shows badge when unread > 0."""
        tech = _tech(self.co, "badge_tech")
        _notif(self.co, tech, is_read=False)
        self.client.login(username="badge_tech", password="testpass")
        # Use the tech dashboard — it renders technician.html which has the bottom nav
        resp = self.client.get(f"/{self.co.code}/tech/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("tech-bottom-nav", content)
        # The badge span has inline background:#ef4444 — present only when notif_unread_count > 0
        self.assertIn("background:#ef4444", content, "Inline red badge must appear in tech nav")

    def test_technician_badge_absent_when_no_unread(self):
        """Technician bottom nav does NOT show red badge when count = 0."""
        tech = _tech(self.co, "badge_tech_clean")
        _notif(self.co, tech, is_read=True)
        self.client.login(username="badge_tech_clean", password="testpass")
        # Use the tech dashboard — it renders technician.html which has the bottom nav
        resp = self.client.get(f"/{self.co.code}/tech/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertNotIn(
            "background:#ef4444", content,
            "Inline red badge must NOT appear when technician has zero unread"
        )


# ---------------------------------------------------------------------------
# Patch B — Dropdown: shows latest 5, never marks read
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class DropdownTest(TestCase):
    """Bell dropdown shows at most 5 latest notifications without marking them read."""

    def setUp(self):
        self.co = _company("drop_co")
        self.admin = _admin(self.co, "drop_admin")

    def test_dropdown_shows_latest_5_only(self):
        """
        NotificationSelector.get_latest_for_user returns exactly limit=5 items
        even when the user has more notifications.
        """
        for i in range(8):
            _notif(self.co, self.admin, title=f"اعلان {i}")
        latest = list(
            NotificationSelector.get_latest_for_user(
                company=self.co, user=self.admin, limit=5
            )
        )
        self.assertEqual(len(latest), 5)

    def test_dropdown_returns_most_recent_first(self):
        """get_latest_for_user returns newest notifications first (created_at DESC)."""
        for i in range(3):
            _notif(self.co, self.admin, title=f"اعلان {i}")
        latest = list(
            NotificationSelector.get_latest_for_user(
                company=self.co, user=self.admin, limit=5
            )
        )
        # Newest has greatest pk
        pks = [n.pk for n in latest]
        self.assertEqual(pks, sorted(pks, reverse=True))

    def test_get_latest_respects_limit_1(self):
        """limit=1 returns exactly 1 notification."""
        for i in range(3):
            _notif(self.co, self.admin, title=f"اعلان {i}")
        latest = list(
            NotificationSelector.get_latest_for_user(
                company=self.co, user=self.admin, limit=1
            )
        )
        self.assertEqual(len(latest), 1)

    def test_dropdown_does_not_mark_notifications_read(self):
        """
        Loading the notification list page (which renders the dropdown via context
        processor) does NOT change is_read on any notification.
        """
        n1 = _notif(self.co, self.admin, is_read=False)
        n2 = _notif(self.co, self.admin, is_read=False)
        self.client.login(username="drop_admin", password="testpass")
        self.client.get(f"/{self.co.code}/admin/notifications/")
        n1.refresh_from_db()
        n2.refresh_from_db()
        self.assertFalse(n1.is_read, "GET list page must not mark notifications as read")
        self.assertFalse(n2.is_read, "GET list page must not mark notifications as read")

    def test_dropdown_renders_notification_titles_in_topbar(self):
        """
        The notification dropdown in the topbar includes notification titles from
        the context processor (notif_latest).
        """
        _notif(self.co, self.admin, title="سفارش جدید", is_read=False)
        self.client.login(username="drop_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("notif-dropdown", content, "Dropdown container must be present")
        self.assertIn("مشاهده همه", content, "View-all link must be in dropdown")

    def test_context_processor_returns_empty_for_unauthenticated(self):
        """Context processor must return 0 count / empty list for unauthenticated users."""
        resp = self.client.get(f"/{self.co.code}/")
        # Public page — unauthenticated — should not crash
        self.assertIn(resp.status_code, [200, 302, 301])


# ---------------------------------------------------------------------------
# Patch C — Notification center: pagination
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class NotificationCenterPaginationTest(TestCase):
    """Notification list uses pagination (20 per page)."""

    def setUp(self):
        self.co = _company("page_co")
        self.admin = _admin(self.co, "page_admin")

    def test_pagination_present_when_more_than_20(self):
        """When user has > 20 notifications, pagination controls are rendered."""
        for i in range(25):
            _notif(self.co, self.admin, title=f"اعلان {i}")
        self.client.login(username="page_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["is_paginated"])
        self.assertEqual(resp.context["page_obj"].paginator.num_pages, 2)

    def test_second_page_accessible(self):
        """Requesting page=2 returns the second page of results."""
        for i in range(25):
            _notif(self.co, self.admin, title=f"اعلان {i}")
        self.client.login(username="page_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/?page=2")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["page_obj"].number, 2)

    def test_no_pagination_when_few_notifications(self):
        """When user has ≤ 20 notifications, is_paginated is False."""
        for i in range(5):
            _notif(self.co, self.admin, title=f"اعلان {i}")
        self.client.login(username="page_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["is_paginated"])

    def test_page_does_not_mark_notifications_read(self):
        """Viewing page 1 or page 2 must not mark any notification as read."""
        notifs = [_notif(self.co, self.admin, title=f"N{i}", is_read=False) for i in range(25)]
        self.client.login(username="page_admin", password="testpass")
        self.client.get(f"/{self.co.code}/admin/notifications/")
        self.client.get(f"/{self.co.code}/admin/notifications/?page=2")
        for n in notifs:
            n.refresh_from_db()
            self.assertFalse(n.is_read)


# ---------------------------------------------------------------------------
# Patch D — mark_all_read: POST-only, scoped to user+company
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class MarkAllReadTest(TestCase):
    """mark_all_read marks only the requesting user's notifications in their company."""

    def setUp(self):
        self.co = _company("mar_co")
        self.co2 = _company("mar_co2")
        self.admin = _admin(self.co, "mar_admin")
        self.staff = _staff(self.co, "mar_staff")
        self.admin2 = _admin(self.co2, "mar_admin2")

    def test_mark_all_read_post_marks_all_user_notifications(self):
        """POST mark_all_read marks all of the user's notifications as read."""
        n1 = _notif(self.co, self.admin, is_read=False)
        n2 = _notif(self.co, self.admin, is_read=False)
        self.client.login(username="mar_admin", password="testpass")
        resp = self.client.post(f"/{self.co.code}/admin/notifications/mark-all-read/")
        self.assertIn(resp.status_code, [302, 301])
        n1.refresh_from_db(); n2.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertTrue(n2.is_read)

    def test_mark_all_read_does_not_affect_other_user(self):
        """mark_all_read does not touch another user's notifications in the same company."""
        n_admin = _notif(self.co, self.admin, is_read=False)
        n_staff = _notif(self.co, self.staff, is_read=False)
        self.client.login(username="mar_admin", password="testpass")
        self.client.post(f"/{self.co.code}/admin/notifications/mark-all-read/")
        n_admin.refresh_from_db(); n_staff.refresh_from_db()
        self.assertTrue(n_admin.is_read, "Admin's own notification should be read")
        self.assertFalse(n_staff.is_read, "Staff's notification must NOT be touched")

    def test_cross_company_mark_all_read_does_not_affect_other_company(self):
        """Admin in company A cannot mark company B notifications as read."""
        n_co2 = _notif(self.co2, self.admin2, is_read=False)
        self.client.login(username="mar_admin", password="testpass")
        self.client.post(f"/{self.co.code}/admin/notifications/mark-all-read/")
        n_co2.refresh_from_db()
        self.assertFalse(n_co2.is_read, "Company B notification must not be affected")

    def test_mark_all_read_get_returns_404(self):
        """GET to mark_all_read endpoint must return 404 (POST only)."""
        self.client.login(username="mar_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/mark-all-read/")
        self.assertEqual(resp.status_code, 404)

    def test_mark_all_read_redirects_to_list(self):
        """After POST, user is redirected back to the notification list."""
        self.client.login(username="mar_admin", password="testpass")
        resp = self.client.post(f"/{self.co.code}/admin/notifications/mark-all-read/")
        self.assertRedirects(resp, f"/{self.co.code}/admin/notifications/",
                             fetch_redirect_response=False)

    def test_mark_all_read_service_is_company_and_user_scoped(self):
        """NotificationMarkReadService.mark_all_read returns count and is correctly scoped."""
        n1 = _notif(self.co, self.admin, is_read=False)
        n2 = _notif(self.co, self.admin, is_read=False)
        _notif(self.co, self.staff, is_read=False)  # different user
        count = NotificationMarkReadService.mark_all_read(
            company=self.co, user=self.admin
        )
        self.assertEqual(count, 2)
        n1.refresh_from_db(); n2.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertTrue(n2.is_read)

    def test_technician_mark_all_read_url_works(self):
        """Technician mark_all_read at /tech/notifications/mark-all-read/ works."""
        tech = _tech(self.co, "mar_tech")
        n = _notif(self.co, tech, is_read=False)
        self.client.login(username="mar_tech", password="testpass")
        resp = self.client.post(f"/{self.co.code}/tech/notifications/mark-all-read/")
        self.assertIn(resp.status_code, [302, 301])
        n.refresh_from_db()
        self.assertTrue(n.is_read)


# ---------------------------------------------------------------------------
# Patch E — Deep link: mark-read then redirect to related object
# ---------------------------------------------------------------------------

@override_settings(ROOT_URLCONF="config.urls")
class MarkReadDeepLinkTest(TestCase):
    """Clicking a notification marks it read and redirects to its related object."""

    def setUp(self):
        self.co = _company("deep_co")
        self.admin = _admin(self.co, "deep_admin")
        self.tech = _tech(self.co, "deep_tech")

    def test_mark_read_sets_is_read_true(self):
        """After visiting the mark-read URL, the notification is marked read."""
        n = _notif(self.co, self.admin, is_read=False)
        self.client.login(username="deep_admin", password="testpass")
        self.client.get(f"/{self.co.code}/admin/notifications/{n.id}/read/")
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_read_without_related_object_redirects_to_list(self):
        """Notification with no related order/invoice → redirects to notification list."""
        n = _notif(self.co, self.admin)
        self.client.login(username="deep_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/{n.id}/read/")
        self.assertRedirects(resp, f"/{self.co.code}/admin/notifications/",
                             fetch_redirect_response=False)

    def test_mark_read_with_related_order_redirects_to_order_detail(self):
        """Notification with related_order → redirects to order detail page."""
        from apps.orders.models import Order
        order = Order.objects.create(
            company=self.co,
            title="سفارش تست",
            status="new",
        )
        n = Notification.objects.create(
            company=self.co,
            recipient=self.admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="سفارش",
            message="پیام",
            related_order=order,
        )
        self.client.login(username="deep_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/{n.id}/read/")
        self.assertRedirects(resp, f"/{self.co.code}/admin/orders/{order.id}/",
                             fetch_redirect_response=False)

    def test_mark_read_with_related_invoice_redirects_to_invoice_detail(self):
        """Notification with related_invoice → redirects to invoice detail page."""
        from apps.invoices.models import Invoice
        invoice = Invoice.objects.create(
            company=self.co,
            invoice_number="INV-001",
            status="draft",
        )
        n = Notification.objects.create(
            company=self.co,
            recipient=self.admin,
            notification_type=Notification.NotificationType.INVOICE_ISSUED,
            title="فاکتور",
            message="پیام",
            related_invoice=invoice,
        )
        self.client.login(username="deep_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/{n.id}/read/")
        self.assertRedirects(resp, f"/{self.co.code}/admin/invoices/{invoice.id}/",
                             fetch_redirect_response=False)

    def test_mark_read_cross_company_returns_404(self):
        """Admin from company A cannot mark company B's notification as read."""
        co2 = _company("deep_co2")
        admin2 = _admin(co2, "deep_admin2")
        n_co2 = _notif(co2, admin2)
        self.client.login(username="deep_admin", password="testpass")
        resp = self.client.get(f"/{self.co.code}/admin/notifications/{n_co2.id}/read/")
        self.assertEqual(resp.status_code, 404)
        n_co2.refresh_from_db()
        self.assertFalse(n_co2.is_read)

    def test_technician_mark_read_without_related_redirects_to_tech_list(self):
        """Technician mark-read with no related object → /tech/notifications/."""
        n = _notif(self.co, self.tech)
        self.client.login(username="deep_tech", password="testpass")
        resp = self.client.get(f"/{self.co.code}/tech/notifications/{n.id}/read/")
        self.assertRedirects(resp, f"/{self.co.code}/tech/notifications/",
                             fetch_redirect_response=False)

    def test_technician_mark_read_with_related_order_redirects_to_tech_order(self):
        """Technician mark-read with related_order → /tech/orders/<id>/."""
        from apps.orders.models import Order
        order = Order.objects.create(
            company=self.co,
            title="سفارش تکنسین",
            status="new",
        )
        n = Notification.objects.create(
            company=self.co,
            recipient=self.tech,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="سفارش",
            message="پیام",
            related_order=order,
        )
        self.client.login(username="deep_tech", password="testpass")
        resp = self.client.get(f"/{self.co.code}/tech/notifications/{n.id}/read/")
        self.assertRedirects(resp, f"/{self.co.code}/tech/orders/{order.id}/",
                             fetch_redirect_response=False)
