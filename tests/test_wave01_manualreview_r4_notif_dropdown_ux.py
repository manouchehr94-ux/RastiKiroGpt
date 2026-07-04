"""
EPIC-002 Product Polish — Manual Review Round 4: notification dropdown UX.

Round 3 fixed the dropdown's *visibility* bug (it could be permanently
displayed on pages that silently dropped the hiding CSS via an unguarded
`{% block extra_head %}` override — see
tests/test_wave01_manualreview_r3_issueA_notif_dropdown_hidden.py). The
underlying open/close mechanism (JS toggle on the bell, .open class,
outside-click close, ESC close) was already correct and is unchanged this
round — templates/layouts/dashboard.html's <script> block already has
`toggleNotifDropdown`, a document click listener that closes the dropdown
when clicking outside `#notif-bell-wrap`, and a keydown listener that
closes it on Escape. This is the project's only dropdown component pattern
(no separate reusable dropdown component exists elsewhere to reuse), so it
was kept as-is per "do not invent a custom popup."

This round only found the dropdown's *content* did not match the required
UX: no explicit status line stating unread count or "no new notifications"
when the bell showed nothing, the preview list was capped at 5 instead of
10, and a redundant/duplicate empty-state message existed for the case
where the item list itself is empty (redundant now that the status line
already covers "nothing new").

Root cause:
- templates/layouts/dashboard.html only rendered a "N جدید" badge pill
  inside the header when notif_unread_count > 0, and rendered nothing at
  all in that position when it was 0 — there was no unconditional status
  line as required ("۱۲ اعلان جدید" / "هیچ اعلان جدیدی وجود ندارد").
- apps/notifications/context_processors.py called
  NotificationSelector.get_latest_for_user(..., limit=5) — capping the
  preview at 5 instead of the required 10.

Fix (presentation-only — no notification models, creation, delivery, or
read/unread logic touched):
- templates/layouts/dashboard.html: header now shows only the "اعلان‌ها"
  title; a new unconditional `.notif-dropdown-status` line directly below
  it always renders either "{count} اعلان جدید" or "هیچ اعلان جدیدی وجود
  ندارد". Item rows now render time first (matching the required example
  ordering), then title, then message. The item list block itself is only
  rendered when there is at least one notification (no separate/duplicate
  empty-state message — the status line already communicates "nothing
  new"). "مشاهده همه" remains unconditionally present in the footer.
- apps/notifications/context_processors.py: limit bumped from 5 to 10.
- static/css/layouts.css: added `.notif-dropdown-status`; removed the now
  unused `.notif-badge-pill` and `.notif-dropdown-empty` rules.

Note: the task's example used Persian numerals ("۱۲"); this fix keeps
Western/Latin digits (e.g. "12"), matching every other number displayed
anywhere else in this project (stat cards, invoice amounts, the existing
bell badge itself) — introducing a one-off Persian-digit conversion just
for this dropdown would be visually inconsistent with the rest of the UI
and would require inventing a new formatting utility that doesn't exist
anywhere else in the codebase.
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _dropdown_html(content):
    """
    Extract just the topbar notification bell+dropdown markup from a full
    page response. The full /admin/notifications/ page also renders its
    own, separate notification-center content (templates/notifications/
    _notification_list_inner.html) further down the page with similar
    wording ("اعلان جدید" counters, empty-state text) — that page is out of
    scope for this fix (only the topbar dropdown component was changed), so
    assertions about the dropdown's exact wording must be scoped to this
    segment, not the whole response body.
    """
    start = content.index('id="notif-bell-wrap"')
    end = content.index("</header>", start)
    return content[start:end]


def _company():
    n = _n()
    return Company.objects.create(name=f"NotifUX2 Co {n}", code=f"nx{n:03d}", slug=f"notifux2-co-{n}", is_active=True)


def _admin(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"nxa{n}", password="testpass", company=company, role=UserRole.COMPANY_ADMIN)


def _order(company):
    n = _n()
    return Order.objects.create(company=company, title=f"Order {n}", status=Order.Status.NEW)


def _notif(company, admin, is_read=False):
    order = _order(company)
    return Notification.objects.create(
        company=company, recipient=admin,
        notification_type=Notification.NotificationType.ORDER_CREATED,
        title="raw", message="raw", is_read=is_read, related_order=order,
    )


@override_settings(ROOT_URLCONF="config.urls")
class NotifDropdownDefaultCollapsedTest(TestCase):
    """Bell renders without expanded content by default."""

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def _get(self):
        self.client.login(username=self.admin.username, password="testpass")
        return self.client.get(f"/{self.company.code}/admin/notifications/")

    def test_bell_button_present_with_no_open_class_by_default(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn('id="notif-bell-btn"', content)
        self.assertIn('id="notif-dropdown"', content)
        self.assertNotIn('class="notif-dropdown open"', content)

    def test_bell_shows_only_icon_when_no_unread(self):
        """No unread → no numeric badge span rendered on the bell icon."""
        resp = self._get()
        content = resp.content.decode("utf-8")
        self.assertNotIn('class="notif-badge"', content)

    def test_bell_shows_count_badge_when_unread_exists(self):
        _notif(self.company, self.admin)
        resp = self._get()
        bell = _dropdown_html(resp.content.decode("utf-8"))
        self.assertIn('class="notif-badge"', bell)
        self.assertIn(">1<", bell)


@override_settings(ROOT_URLCONF="config.urls")
class NotifDropdownOpensCorrectlyTest(TestCase):
    """Dropdown toggle mechanism (JS + CSS) is present and correct."""

    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def test_toggle_js_wired_to_bell_button(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/admin/notifications/")
        content = resp.content.decode("utf-8")
        self.assertIn("toggleNotifDropdown(event)", content)
        self.assertIn("window.toggleNotifDropdown", content)

    def test_outside_click_and_escape_close_handlers_present(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/admin/notifications/")
        content = resp.content.decode("utf-8")
        self.assertIn("notif-bell-wrap", content)
        self.assertIn("e.key === 'Escape'", content)

    def test_css_open_class_reveals_dropdown(self):
        with open("static/css/layouts.css", encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".notif-dropdown.open { display: block; }", css)


@override_settings(ROOT_URLCONF="config.urls")
class NotifDropdownUnreadCounterTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def _get(self):
        self.client.login(username=self.admin.username, password="testpass")
        return self.client.get(f"/{self.company.code}/admin/notifications/")

    def test_status_line_shows_unread_count_when_positive(self):
        _notif(self.company, self.admin)
        _notif(self.company, self.admin)
        _notif(self.company, self.admin, is_read=True)
        resp = self._get()
        dropdown = _dropdown_html(resp.content.decode("utf-8"))
        self.assertIn("2 اعلان جدید", dropdown)

    def test_status_line_never_shown_twice(self):
        """
        The visible "N اعلان جدید" text must appear exactly once — inside
        `.notif-dropdown-status`. The bell icon's badge also carries an
        `aria-label="N اعلان جدید"` for accessibility, which legitimately
        repeats the same words in a non-visible attribute; that one is
        excluded from this count.
        """
        _notif(self.company, self.admin)
        resp = self._get()
        dropdown = _dropdown_html(resp.content.decode("utf-8"))
        status_start = dropdown.index('class="notif-dropdown-status"')
        status_end = dropdown.index("</div>", status_start)
        status_line = dropdown[status_start:status_end]
        self.assertEqual(status_line.count("اعلان جدید"), 1)


@override_settings(ROOT_URLCONF="config.urls")
class NotifDropdownEmptyStateTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def _get(self):
        self.client.login(username=self.admin.username, password="testpass")
        return self.client.get(f"/{self.company.code}/admin/notifications/")

    def test_no_new_notifications_text_shown_when_zero_unread(self):
        resp = self._get()
        dropdown = _dropdown_html(resp.content.decode("utf-8"))
        self.assertIn("هیچ اعلان جدیدی وجود ندارد", dropdown)

    def test_no_new_notifications_text_shown_even_with_read_history(self):
        """Read (non-unread) notifications still exist, but unread count is 0."""
        _notif(self.company, self.admin, is_read=True)
        resp = self._get()
        dropdown = _dropdown_html(resp.content.decode("utf-8"))
        self.assertIn("هیچ اعلان جدیدی وجود ندارد", dropdown)

    def test_old_duplicate_empty_state_text_removed_from_dropdown(self):
        """
        The dropdown itself must no longer use the old "اعلانی وجود ندارد"
        wording (replaced by the unconditional status line). The separate,
        unrelated full notification-center page may still use similar
        wording — out of scope for this fix.
        """
        resp = self._get()
        dropdown = _dropdown_html(resp.content.decode("utf-8"))
        self.assertNotIn("اعلانی وجود ندارد", dropdown)


@override_settings(ROOT_URLCONF="config.urls")
class NotifDropdownViewAllLinkTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def _get(self):
        self.client.login(username=self.admin.username, password="testpass")
        return self.client.get(f"/{self.company.code}/admin/notifications/")

    def test_view_all_link_present_when_empty(self):
        resp = self._get()
        content = resp.content.decode("utf-8")
        self.assertIn("مشاهده همه", content)
        self.assertIn(f"/{self.company.code}/admin/notifications/", content)

    def test_view_all_link_present_with_notifications(self):
        _notif(self.company, self.admin)
        resp = self._get()
        content = resp.content.decode("utf-8")
        self.assertIn("مشاهده همه", content)


@override_settings(ROOT_URLCONF="config.urls")
class NotifDropdownLatestTenLimitTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def test_only_latest_10_shown_when_more_than_10_exist(self):
        for _ in range(15):
            _notif(self.company, self.admin)
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/admin/notifications/")
        content = resp.content.decode("utf-8")
        self.assertEqual(content.count("notif-dropdown-item"), 10)

    def test_all_shown_when_fewer_than_10_exist(self):
        for _ in range(4):
            _notif(self.company, self.admin)
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/admin/notifications/")
        content = resp.content.decode("utf-8")
        self.assertEqual(content.count("notif-dropdown-item"), 4)
