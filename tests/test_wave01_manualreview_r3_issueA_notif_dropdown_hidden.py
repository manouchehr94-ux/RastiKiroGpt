"""
EPIC-002 Product Polish — Manual Review Round 3, Issue A: notification
dropdown content always visible on /admin/orders/create/.

What was misunderstood in the earlier fix: Problem 3 (Wave 01 manual-test
round) and Task 2 (Round 2) both fixed the *content* of notification text
(mojibake repair, clean presentation), assuming the visibility mechanism
itself (CSS display:none / .open toggle) was already correct. It was — but
only on pages that don't override the layout's extra_head block. This round
found the dropdown was rendered as normal visible page content specifically
on /admin/orders/create/, which is a *visibility* bug, not a text bug.

Root cause: templates/layouts/dashboard.html defined the notification
bell/dropdown CSS (including the load-bearing `.notif-dropdown{display:none}`
/ `.notif-dropdown.open{display:block}` toggle) inside its own
`{% block extra_head %}`. templates/tenants/admin_order_create.html also
defines `{% block extra_head %}` for its own page-specific CSS, but WITHOUT
`{{ block.super }}` — which, per Django template inheritance, completely
replaces the parent block's content rather than extending it. As a result,
on the order-create page, NONE of the notification CSS was ever loaded: the
`.notif-dropdown` <div> had no `display:none` rule at all, so it fell back
to the browser's default `display:block` for a <div> and was rendered as
plain visible content at the top of the page, regardless of its `.open`
class state.

Fix: moved the notification bell/dropdown CSS out of dashboard.html's
overridable extra_head block into static/css/layouts.css (in the existing
.topbar-actions section, right where the topbar's own CSS already lives).
layouts.css is loaded on every page unconditionally via theme.css's
@import chain (templates/base.html always links theme.css), independent of
any page template's extra_head block — so this class of bug can no longer
recur on any current or future page, not just this one. No HTML/markup
changed, no JS changed, no notification content/delivery changed.
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


def _company():
    n = _n()
    return Company.objects.create(name=f"Hide Co {n}", code=f"hd{n:03d}", slug=f"hide-co-{n}", is_active=True)


def _admin(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"hda{n}", password="testpass", company=company, role=UserRole.COMPANY_ADMIN)


class NotifDropdownCssSourceTest(TestCase):
    """Source-level checks: the CSS that hides the dropdown by default must
    live somewhere that is always loaded, not inside an overridable block."""

    def test_layouts_css_defines_dropdown_hidden_by_default(self):
        with open("static/css/layouts.css", encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".notif-dropdown {", css)
        # The base rule (before the .open override) must set display:none.
        base_rule_start = css.index(".notif-dropdown {")
        open_rule_start = css.index(".notif-dropdown.open")
        base_rule = css[base_rule_start:open_rule_start]
        self.assertIn("display: none", base_rule)
        self.assertIn(".notif-dropdown.open", css)

    def test_dashboard_layout_no_longer_inlines_notif_css(self):
        """
        The notification CSS must not remain duplicated inside dashboard.html's
        extra_head block — that's exactly the block that admin_order_create.html
        (and potentially other pages) can silently wipe out.
        """
        with open("templates/layouts/dashboard.html", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn(".notif-dropdown{", content)
        self.assertNotIn(".notif-dropdown {", content)

    def test_theme_css_imports_layouts_css(self):
        """Sanity check the delivery mechanism: layouts.css must be part of
        the always-loaded theme.css @import chain."""
        with open("static/css/theme.css", encoding="utf-8") as f:
            css = f.read()
        self.assertIn("layouts.css", css)


@override_settings(ROOT_URLCONF="config.urls")
class NotifDropdownHiddenOnOrderCreatePageTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def _order_create_url(self):
        return f"/{self.company.code}/admin/orders/create/"

    def test_page_no_longer_inlines_notif_dropdown_css_at_all(self):
        """
        Whether or not this specific page overrides extra_head, it must not
        need to inline the notification CSS itself anymore — proving the
        fix no longer depends on this (or any) page's extra_head block.
        """
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._order_create_url())
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertNotIn(".notif-dropdown{", content)
        self.assertNotIn(".notif-dropdown {", content)

    def test_dropdown_wrapper_has_no_open_class_by_default(self):
        """
        The rendered dropdown container must not carry the `open` class on
        initial page load — it is only added by the client-side toggle JS
        on click.
        """
        order = Order.objects.create(company=self.company, title="Order", status=Order.Status.NEW)
        Notification.objects.create(
            company=self.company, recipient=self.admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="سفارش جدید", message="پیام", related_order=order,
        )
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._order_create_url())
        content = resp.content.decode("utf-8")
        self.assertIn('id="notif-dropdown"', content)
        self.assertNotIn('id="notif-dropdown" class="notif-dropdown open"', content)
        self.assertIn('class="notif-dropdown"', content)

    def test_notification_text_present_but_only_inside_dropdown_container(self):
        """
        Notification item text is expected to be present in the HTML (it's
        a legitimate dropdown item), but it must sit inside the
        `.notif-dropdown` container that layouts.css hides by default — not
        as loose/visible content in the main page body outside that
        container.
        """
        order = Order.objects.create(company=self.company, title="Order", status=Order.Status.NEW)
        Notification.objects.create(
            company=self.company, recipient=self.admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="سفارش جدید", message="پیام", related_order=order,
        )
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._order_create_url())
        content = resp.content.decode("utf-8")

        dropdown_start = content.index('id="notif-dropdown"')
        dropdown_open_tag_end = content.index(">", dropdown_start)
        # Find the matching close of the dropdown div: everything up to the
        # notif-dropdown-footer's closing </div></div> is a reasonable
        # bound for this test; the item text must appear after the dropdown
        # opens and before the <main> content region starts.
        main_content_start = content.index('<main class="dashboard-content">')
        item_position = content.index("شماره سفارش", dropdown_open_tag_end)

        self.assertGreater(item_position, dropdown_open_tag_end)
        self.assertLess(item_position, main_content_start, "Notification text must render before/outside <main>, inside the topbar dropdown — not inside the page's main content area")

    def test_order_create_form_still_renders(self):
        """Regression guard: the fix must not break the order-create form itself."""
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._order_create_url())
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("اضافه کردن سفارش", content)

    def test_notif_bell_button_still_present(self):
        """The bell button/toggle itself must remain (feature is kept, only hidden by default)."""
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(self._order_create_url())
        content = resp.content.decode("utf-8")
        self.assertIn('id="notif-bell-btn"', content)
        self.assertIn("toggleNotifDropdown", content)
