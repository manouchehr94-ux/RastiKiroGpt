"""
Notifications context processor.

Provides unread count and latest notifications to every template
rendered for authenticated admin/operator/technician users.

Safety invariants:
- Returns zero/empty on unauthenticated requests.
- Returns zero/empty if request.company is absent (public pages).
- Returns zero/empty for CUSTOMER / PLATFORM_OWNER roles.
- Never raises — any DB error silently degrades to zero/empty.
- Issues exactly two DB queries per eligible request (count + latest-10).
"""
from __future__ import annotations

_ELIGIBLE_ROLES = frozenset(("COMPANY_ADMIN", "COMPANY_STAFF", "TECHNICIAN"))


def _empty_context():
    return {"notif_unread_count": 0, "notif_latest": []}


def _repair_legacy_mojibake(text):
    """
    Display-only repair for a legacy encoding bug: some historical
    notifications were stored after their Persian text got round-tripped
    through the Windows-1256 codepage instead of UTF-8, corrupting it into a
    mix of Arabic-block characters and Latin-1 Supplement characters (e.g.
    "سفارش" became "ط³ظپط§ط±ط´"). Real notification text (Persian or
    English) never contains Latin-1 Supplement characters (U+0080-U+00FF),
    so their presence reliably flags this specific corruption. The database
    value itself is left untouched; only the in-memory text used for display
    is corrected.
    """
    if not text or not any(chr(0x80) <= ch <= chr(0xff) for ch in text):
        return text
    try:
        return text.encode("cp1256").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


# One consistent (title, message-template) presentation per notification
# type, used instead of the raw stored title/message for the dropdown
# preview. The message template is filled in purely from structured fields
# (related_order_id / related_invoice.invoice_number) so the preview never
# shows duplicated wording, mixed English/Persian text, or internal
# identifiers/model names — regardless of what free-text was stored at
# creation time (apps/notifications/services.py and apps/orders/*_events.py
# are unchanged; this is a display-only transform).
_TYPE_PRESENTATION = {
    "order_created": ("سفارش جدید", "شماره سفارش {order_id}"),
    "order_available": ("سفارش جدید قابل بررسی", "شماره سفارش {order_id}"),
    "order_assigned": ("سفارش جدید تخصیص یافت", "شماره سفارش {order_id}"),
    "order_accepted": ("سفارش تایید شد", "شماره سفارش {order_id}"),
    "order_completed": ("سفارش تکمیل شد", "شماره سفارش {order_id}"),
    "order_cancel_requested": ("درخواست لغو سفارش", "شماره سفارش {order_id}"),
    "order_cancel_approved": ("درخواست لغو تایید شد", "شماره سفارش {order_id}"),
    "order_cancel_rejected": ("درخواست لغو رد شد", "شماره سفارش {order_id}"),
    "invoice_issued": ("فاکتور صادر شد", "شماره فاکتور {invoice_number}"),
    "payment_paid": ("پرداخت موفق", "شماره فاکتور {invoice_number}"),
    "payment_failed": ("پرداخت ناموفق", "شماره فاکتور {invoice_number}"),
}


def _build_clean_presentation(notification):
    """
    Return (title, message) for the dropdown preview: a single consistent
    presentation derived from notification_type + related_order/
    related_invoice, falling back to the (mojibake-repaired) raw stored
    text when the type is unrecognized or its related object is missing.
    """
    template = _TYPE_PRESENTATION.get(notification.notification_type)
    if template is None:
        return notification.title, notification.message

    title, message_template = template
    if "{order_id}" in message_template:
        order_id = notification.related_order_id
        if not order_id:
            return notification.title, notification.message
        return title, message_template.format(order_id=order_id)
    if "{invoice_number}" in message_template:
        invoice = notification.related_invoice
        if invoice is None:
            return notification.title, notification.message
        return title, message_template.format(invoice_number=invoice.invoice_number)
    return title, message_template


def notification_badge(request):
    try:
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return _empty_context()
        company = getattr(request, "company", None)
        if company is None:
            return _empty_context()
        role = getattr(user, "role", None)
        if role not in _ELIGIBLE_ROLES:
            return _empty_context()
        from .selectors import NotificationSelector
        count = NotificationSelector.get_unread_count(company=company, user=user)
        latest = list(
            NotificationSelector.get_latest_for_user(company=company, user=user, limit=10)
        )
        for notification in latest:
            notification.title = _repair_legacy_mojibake(notification.title)
            notification.message = _repair_legacy_mojibake(notification.message)
            notification.title, notification.message = _build_clean_presentation(notification)
        return {"notif_unread_count": count, "notif_latest": latest}
    except Exception:
        return _empty_context()
