"""
SMS - Inbox Views.

Minimal admin view for viewing received/matched SMS messages.
No reply, no conversation pages.
"""
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.accounts.permissions import require_tenant_role

from .models_inbox import SMSInbox

PAGE_SIZE = 50


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_inbox_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Company inbox list with filtering.

    Filters: match_status, response_type, from_number search, date range.
    Only shows messages matched/ambiguous to this company.
    """
    company = request.company

    match_filter = request.GET.get("match_status", "").strip()
    type_filter = request.GET.get("response_type", "").strip()
    search_q = request.GET.get("q", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    qs = SMSInbox.objects.filter(company=company).select_related(
        "matched_outbox"
    ).order_by("-received_at")

    if match_filter:
        qs = qs.filter(match_status=match_filter)
    if type_filter:
        qs = qs.filter(response_type=type_filter)
    if search_q:
        qs = qs.filter(from_number__icontains=search_q)
    if date_from:
        try:
            from datetime import datetime
            qs = qs.filter(received_at__date__gte=datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import datetime
            qs = qs.filter(received_at__date__lte=datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", "1")
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    from urllib.parse import urlencode
    filter_params = {}
    if match_filter:
        filter_params["match_status"] = match_filter
    if type_filter:
        filter_params["response_type"] = type_filter
    if search_q:
        filter_params["q"] = search_q
    if date_from:
        filter_params["date_from"] = date_from
    if date_to:
        filter_params["date_to"] = date_to
    filter_qs = urlencode(filter_params)

    return render(request, "sms/inbox_list.html", {
        "company": company,
        "page_obj": page_obj,
        "messages": page_obj.object_list,
        "match_filter": match_filter,
        "type_filter": type_filter,
        "search_q": search_q,
        "date_from": date_from,
        "date_to": date_to,
        "filter_qs": filter_qs,
        "match_status_choices": SMSInbox.MatchStatus.choices,
        "response_type_choices": SMSInbox.ResponseType.choices,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_inbox_detail(request: HttpRequest, pk: int, **kwargs) -> HttpResponse:
    """View a single inbox message with match details."""
    company = request.company
    inbox_msg = get_object_or_404(
        SMSInbox.objects.select_related("provider", "matched_outbox"),
        pk=pk,
        company=company,
    )
    return render(request, "sms/inbox_detail.html", {
        "company": company,
        "inbox_msg": inbox_msg,
    })
