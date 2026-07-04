"""
EPIC-002 Wave 01 — Manual Test Fix, Problem 3: garbled/mojibake text
rendered near the top-left of /rasti-test/admin/orders/create/ (and, in
fact, every admin page that renders the shared topbar).

Investigation: rendered the real page against the actual "rasti-test"
company/admin account. Found several historical Notification rows (ids 4, 5,
7, 8, 9, 10, 12, 13, 15, 16 in that database) whose `title`/`message` are
genuinely corrupted at the byte level — confirmed via direct codepoint
inspection (characters in the Arabic block mixed with Latin-1 Supplement
characters, e.g. "سفارش" stored as "ط³ظپط§ط±ط´"). This is a *double*
mis-encoding: the original correct UTF-8 bytes were, at some point in the
past, decoded using the Windows-1256 codepage instead of UTF-8, and the
resulting (wrong) string was then re-encoded and saved as UTF-8 — a classic
codepage round-trip corruption. This matches the reported symptom exactly:
one of the corrupted records' message is literally
"...#37: Service Request", matching the "Service Request :" example in the
bug report.

This corrupted text is served to *every* admin page (not just order-create)
via apps.notifications.context_processors.notification_badge, which feeds
the topbar notification-bell dropdown in templates/layouts/dashboard.html —
present in the RTL top bar, hence "top-left" in a right-to-left layout.

Root cause: notification_badge() returned the raw stored title/message with
no sanity check, so any historically-corrupted record was displayed as-is.

Fix: added _repair_legacy_mojibake() (apps/notifications/context_processors.py).
Real notification text (Persian or English) never contains Latin-1
Supplement characters (U+0080-U+00FF); their presence reliably flags this
specific double-encoding corruption. When detected, the text is repaired for
DISPLAY ONLY via the inverse transform (encode as cp1256, decode as utf-8) —
the stored database value is never modified, no migration or delivery-logic
change is involved. This is a template-context/display fix only.
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.notifications.context_processors import _repair_legacy_mojibake
from apps.notifications.models import Notification
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"Notif Co {n}", code=f"nc{n:03d}", slug=f"notif-co-{n}", is_active=True)


def _admin(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"na{n}", password="testpass", company=company, role=UserRole.COMPANY_ADMIN)


# The exact corrupted byte sequence found in production data for a
# "سفارش جدید #37: Service Request" notification, built from raw bytes so
# this test file itself never needs to contain literal mojibake text.
_CORRUPTED_MESSAGE = bytes([
    0xd8, 0xb7, 0xc2, 0xb3, 0xd8, 0xb8, 0xd9, 0xbe, 0xd8, 0xb7, 0xc2, 0xa7,
    0xd8, 0xb7, 0xc2, 0xb1, 0xd8, 0xb7, 0xc2, 0xb4, 0x20, 0xd8, 0xb7, 0xc2,
    0xac, 0xd8, 0xb7, 0xc2, 0xaf, 0xd8, 0xba, 0xc5, 0x92, 0xd8, 0xb7, 0xc2,
    0xaf, 0x20, 0x23, 0x33, 0x37, 0x3a, 0x20, 0x53, 0x65, 0x72, 0x76, 0x69,
    0x63, 0x65, 0x20, 0x52, 0x65, 0x71, 0x75, 0x65, 0x73, 0x74,
]).decode("utf-8")


class RepairLegacyMojibakeUnitTest(TestCase):
    def test_corrupted_text_is_repaired(self):
        fixed = _repair_legacy_mojibake(_CORRUPTED_MESSAGE)
        self.assertNotEqual(fixed, _CORRUPTED_MESSAGE)
        self.assertIn("Service Request", fixed)
        # Repaired text must contain no Latin-1 Supplement characters left over.
        self.assertFalse(any("" <= ch <= "ÿ" for ch in fixed))

    def test_normal_persian_text_untouched(self):
        text = "سفارش جدید ثبت شد"
        self.assertEqual(_repair_legacy_mojibake(text), text)

    def test_normal_english_text_untouched(self):
        text = "New order registered"
        self.assertEqual(_repair_legacy_mojibake(text), text)

    def test_empty_text_untouched(self):
        self.assertEqual(_repair_legacy_mojibake(""), "")
        self.assertEqual(_repair_legacy_mojibake(None), None)


@override_settings(ROOT_URLCONF="config.urls")
class AdminOrderCreatePageNoMojibakeTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        Notification.objects.create(
            company=self.company,
            recipient=self.admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title=_CORRUPTED_MESSAGE,
            message=_CORRUPTED_MESSAGE,
        )

    def test_order_create_page_does_not_contain_mojibake(self):
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/admin/orders/create/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        for suspect_char in ("Ø", "Ù", "Ú", "Û"):
            self.assertNotIn(suspect_char, content)
        # "Service Request" (plain ASCII) is present either way — the real
        # signal is that the Persian portion is now correctly repaired.
        self.assertIn("Service Request", content)
        self.assertIn("سفارش", content)
