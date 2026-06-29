"""
Notifications context processor.

Provides unread count and latest notifications to every template
rendered for authenticated admin/operator/technician users.

Safety invariants:
- Returns zero/empty on unauthenticated requests.
- Returns zero/empty if request.company is absent (public pages).
- Returns zero/empty for CUSTOMER / PLATFORM_OWNER roles.
- Never raises — any DB error silently degrades to zero/empty.
- Issues exactly two DB queries per eligible request (count + latest-5).
"""
from __future__ import annotations

_ELIGIBLE_ROLES = frozenset(("COMPANY_ADMIN", "COMPANY_STAFF", "TECHNICIAN"))


def _empty_context():
    return {"notif_unread_count": 0, "notif_latest": []}


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
            NotificationSelector.get_latest_for_user(company=company, user=user, limit=5)
        )
        return {"notif_unread_count": count, "notif_latest": latest}
    except Exception:
        return _empty_context()
