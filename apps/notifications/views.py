"""
Notifications - Views.

Thin views for notification list and mark-as-read.
"""
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import require_tenant_auth

from .models import Notification
from .selectors import NotificationSelector
from .services import NotificationMarkReadService

_PAGE_SIZE = 20


def _notif_list_url(company_code: str, role: str) -> str:
    if role == "TECHNICIAN":
        return f"/{company_code}/tech/notifications/"
    if role in ("COMPANY_ADMIN", "COMPANY_STAFF"):
        return f"/{company_code}/admin/notifications/"
    return f"/{company_code}/notifications/"


def _mark_all_read_url(company_code: str, role: str) -> str:
    if role == "TECHNICIAN":
        return f"/{company_code}/tech/notifications/mark-all-read/"
    if role in ("COMPANY_ADMIN", "COMPANY_STAFF"):
        return f"/{company_code}/admin/notifications/mark-all-read/"
    return ""


def _deep_link_url(*, company_code: str, role: str, notification: Notification) -> str:
    """
    Build the redirect URL after marking a notification as read.

    For admin/staff:
      related_order   → /<code>/admin/orders/<id>/
      related_invoice → /<code>/admin/invoices/<id>/
    For technician:
      related_order   → /<code>/tech/orders/<id>/
      related_invoice → /<code>/tech/invoices/<id>/
    Falls back to notification list if no related object.
    """
    if role in ("COMPANY_ADMIN", "COMPANY_STAFF"):
        if notification.related_order_id:
            return f"/{company_code}/admin/orders/{notification.related_order_id}/"
        if notification.related_invoice_id:
            return f"/{company_code}/admin/invoices/{notification.related_invoice_id}/"
        return f"/{company_code}/admin/notifications/"
    if role == "TECHNICIAN":
        if notification.related_order_id:
            return f"/{company_code}/tech/orders/{notification.related_order_id}/"
        if notification.related_invoice_id:
            return f"/{company_code}/tech/invoices/{notification.related_invoice_id}/"
        return f"/{company_code}/tech/notifications/"
    return f"/{company_code}/notifications/"


@require_tenant_auth
def notification_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List notifications for the current user with pagination."""
    company = request.company
    role = getattr(request.user, "role", None)
    qs = NotificationSelector.get_for_user(company=company, user=request.user)
    paginator = Paginator(qs, _PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    unread_count = NotificationSelector.get_unread_count(company=company, user=request.user)
    mark_all_url = _mark_all_read_url(company.code, role) if unread_count > 0 else ""
    return render(request, "notifications/list.html", {
        "notifications": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "unread_count": unread_count,
        "mark_all_read_url": mark_all_url,
        "company": company,
    })


@require_tenant_auth
def notification_mark_read(request: HttpRequest, notification_id: int, **kwargs) -> HttpResponse:
    """Mark a single notification as read and redirect to related object (deep link)."""
    company = request.company
    notification = Notification.objects.filter(
        id=notification_id, company=company, recipient=request.user
    ).first()

    if notification is None:
        raise Http404("Notification not found.")

    if not notification.is_read:
        NotificationMarkReadService.mark_read(notification=notification)
    role = getattr(request.user, "role", None)
    return redirect(_deep_link_url(
        company_code=company.code,
        role=role,
        notification=notification,
    ))


@require_tenant_auth
def notification_mark_all_read(request: HttpRequest, **kwargs) -> HttpResponse:
    """Mark all notifications as read for the current user. POST only."""
    if request.method != "POST":
        raise Http404
    company = request.company
    NotificationMarkReadService.mark_all_read(company=company, user=request.user)
    role = getattr(request.user, "role", None)
    return redirect(_notif_list_url(company.code, role))
