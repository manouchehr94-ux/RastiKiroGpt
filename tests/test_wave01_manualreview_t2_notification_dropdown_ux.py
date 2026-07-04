"""
EPIC-002 Product Polish — Manual Review Fix, Task 2: Notification Dropdown UX.

Manual review: notification rendering is no longer broken (mojibake fixed —
see tests/test_wave01_manualfix_p3_notification_mojibake.py), but the raw
stored text is poor UX, e.g. for an ORDER_CREATED notification:
  title:   "سفارش جدید ثبت شد"
  message: "سفارش جدید #35: Service Request"
This duplicates "سفارش جدید" across title/message, mixes in the English
order title ("Service Request", a demo/seed placeholder), and is
inconsistent from one notification type to the next.

Root cause: apps.notifications.context_processors.notification_badge fed the
topbar dropdown the raw stored title/message verbatim. The underlying
Notification rows are created in several places (apps/notifications/
services.py::NotificationEventHooks, apps/orders/assignment_events.py,
apps/orders/cancel_request_events.py, apps/orders/technician_notifications.py)
with inconsistent, sometimes verbose or English-mixed free text — none of
which this fix touches (per "keep existing notification system, only
presentation" and "no notification delivery changes").

Fix: added _build_clean_presentation() (apps/notifications/context_processors.py),
which derives a single consistent (title, message) pair purely from
notification_type + related_order_id / related_invoice.invoice_number —
never from the stored free-text title/message — for every known
NotificationType. This guarantees no duplicated wording, no English order
titles, no internal identifiers, for every notification shown in the
dropdown, regardless of what was stored at creation time. Falls back to the
(mojibake-repaired) raw text only for unrecognized types or notifications
missing their related object.

apps/notifications/selectors.py::NotificationSelector.get_latest_for_user
now also select_related("related_invoice") so building the invoice-number
message does not add an extra query per notification (no N+1).
"""
import itertools

from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.invoices.models import Invoice
from apps.notifications.context_processors import _build_clean_presentation
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.tenants.models import Company

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company():
    n = _n()
    return Company.objects.create(name=f"NotifUX Co {n}", code=f"nu{n:03d}", slug=f"notifux-co-{n}", is_active=True)


def _admin(company):
    n = _n()
    return CompanyUser.objects.create_user(username=f"nua{n}", password="testpass", company=company, role=UserRole.COMPANY_ADMIN)


def _order(company, n=None):
    n = n if n is not None else _n()
    return Order.objects.create(company=company, title="Service Request", status=Order.Status.NEW)


def _invoice(company):
    n = _n()
    return Invoice.objects.create(company=company, invoice_number=f"INV-{n:05d}", status=Invoice.Status.ISSUED)


class BuildCleanPresentationUnitTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def _notif(self, notification_type, title="raw title", message="raw message", related_order=None, related_invoice=None):
        return Notification.objects.create(
            company=self.company, recipient=self.admin,
            notification_type=notification_type,
            title=title, message=message,
            related_order=related_order, related_invoice=related_invoice,
        )

    def test_order_created_shows_order_number_only_no_english(self):
        order = _order(self.company, n=35)
        n = self._notif(
            Notification.NotificationType.ORDER_CREATED,
            title="سفارش جدید ثبت شد",
            message=f"سفارش جدید #{order.id}: Service Request",
            related_order=order,
        )
        title, message = _build_clean_presentation(n)
        self.assertEqual(title, "سفارش جدید")
        self.assertEqual(message, f"شماره سفارش {order.id}")
        self.assertNotIn("Service Request", message)
        self.assertNotIn("Service Request", title)

    def test_no_duplicated_wording_between_title_and_message(self):
        order = _order(self.company)
        n = self._notif(Notification.NotificationType.ORDER_CREATED, related_order=order)
        title, message = _build_clean_presentation(n)
        self.assertNotIn(title, message)

    def test_order_completed_presentation(self):
        order = _order(self.company)
        n = self._notif(Notification.NotificationType.ORDER_COMPLETED, related_order=order)
        title, message = _build_clean_presentation(n)
        self.assertEqual(title, "سفارش تکمیل شد")
        self.assertEqual(message, f"شماره سفارش {order.id}")

    def test_invoice_issued_presentation_uses_invoice_number_not_order_id(self):
        invoice = _invoice(self.company)
        n = self._notif(Notification.NotificationType.INVOICE_ISSUED, related_invoice=invoice)
        title, message = _build_clean_presentation(n)
        self.assertEqual(title, "فاکتور صادر شد")
        self.assertEqual(message, f"شماره فاکتور {invoice.invoice_number}")

    def test_payment_paid_presentation(self):
        invoice = _invoice(self.company)
        n = self._notif(Notification.NotificationType.PAYMENT_PAID, related_invoice=invoice)
        title, message = _build_clean_presentation(n)
        self.assertEqual(title, "پرداخت موفق")
        self.assertEqual(message, f"شماره فاکتور {invoice.invoice_number}")

    def test_falls_back_to_raw_text_when_related_order_missing(self):
        n = self._notif(Notification.NotificationType.ORDER_CREATED, title="raw title", message="raw message", related_order=None)
        title, message = _build_clean_presentation(n)
        self.assertEqual((title, message), ("raw title", "raw message"))

    def test_falls_back_to_raw_text_when_related_invoice_missing(self):
        n = self._notif(Notification.NotificationType.INVOICE_ISSUED, title="raw title", message="raw message", related_invoice=None)
        title, message = _build_clean_presentation(n)
        self.assertEqual((title, message), ("raw title", "raw message"))

    def test_all_order_and_invoice_notification_types_covered(self):
        """Every NotificationType with a related_order gets a clean, non-empty presentation."""
        order = _order(self.company)
        order_types = [
            Notification.NotificationType.ORDER_CREATED,
            Notification.NotificationType.ORDER_AVAILABLE,
            Notification.NotificationType.ORDER_ASSIGNED,
            Notification.NotificationType.ORDER_ACCEPTED,
            Notification.NotificationType.ORDER_COMPLETED,
            Notification.NotificationType.ORDER_CANCEL_REQUESTED,
            Notification.NotificationType.ORDER_CANCEL_APPROVED,
            Notification.NotificationType.ORDER_CANCEL_REJECTED,
        ]
        for t in order_types:
            n = self._notif(t, related_order=order)
            title, message = _build_clean_presentation(n)
            self.assertTrue(title)
            self.assertIn(str(order.id), message)
            self.assertNotIn("Service Request", message)


@override_settings(ROOT_URLCONF="config.urls")
class NotificationDropdownEndToEndTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def test_dropdown_shows_clean_persian_text_not_raw_stored_text(self):
        order = Order.objects.create(company=self.company, title="Service Request", status=Order.Status.NEW)
        Notification.objects.create(
            company=self.company, recipient=self.admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="سفارش جدید ثبت شد",
            message=f"سفارش جدید #{order.id}: Service Request",
            related_order=order,
        )
        self.client.login(username=self.admin.username, password="testpass")
        resp = self.client.get(f"/{self.company.code}/admin/orders/create/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertNotIn("Service Request", content)
        self.assertIn(f"شماره سفارش {order.id}", content)

    def test_dropdown_query_count_does_not_grow_with_notification_count(self):
        """
        select_related("related_invoice") must prevent N+1: the page's total
        query count with 1 invoice-related notification must equal the count
        with 5 (the dropdown only ever shows the latest 5 anyway).
        """
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        self.client.login(username=self.admin.username, password="testpass")

        # Warm up any one-time lazy state (e.g. auto-created CompanySettings
        # row) so it doesn't skew the query-count comparison below.
        self.client.get(f"/{self.company.code}/admin/orders/create/")

        Notification.objects.create(
            company=self.company, recipient=self.admin,
            notification_type=Notification.NotificationType.INVOICE_ISSUED,
            title="raw", message="raw", related_invoice=_invoice(self.company),
        )
        with CaptureQueriesContext(connection) as captured_one:
            self.client.get(f"/{self.company.code}/admin/orders/create/")

        for _ in range(4):
            Notification.objects.create(
                company=self.company, recipient=self.admin,
                notification_type=Notification.NotificationType.INVOICE_ISSUED,
                title="raw", message="raw", related_invoice=_invoice(self.company),
            )
        with CaptureQueriesContext(connection) as captured_five:
            self.client.get(f"/{self.company.code}/admin/orders/create/")

        self.assertEqual(len(captured_one), len(captured_five))
