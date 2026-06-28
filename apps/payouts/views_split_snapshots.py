"""
Payouts - Split Snapshot Views (Company Admin).

Report pages for PaymentSplitSnapshot rows scoped to the current tenant.
"""
import datetime
import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import render

from apps.accounts.permissions import require_tenant_role
from apps.payouts.models import PaymentSplitSnapshot


def _parse_reconciliation_date(value: str):
    """Parse date string from GET params. Tries Jalali first, then Gregorian."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        from apps.common.jalali import normalize_digits, parse_jalali_date
        parsed = parse_jalali_date(normalize_digits(value))
        if parsed:
            return parsed
    except Exception:
        pass
    try:
        return datetime.datetime.strptime(value.replace("-", "/"), "%Y/%m/%d").date()
    except Exception:
        return None


REASON_LABELS = {
    "split_with_verified_technician": "در این پرداخت، سهم تکنسین برای تسهیم مستقیم آماده شده است.",
    "payout_strategy_is_direct_to_company": "شرکت حالت واریز کامل به حساب شرکت را انتخاب کرده است.",
    "technician_not_verified": "تکنسین از نظر مالی تأیید نشده است.",
    "technician_has_no_sub_merchant_id": "شناسه پذیرنده/زیرپذیرنده تکنسین ثبت نشده است.",
    "technician_wage_is_zero": "سهم تکنسین برای این فاکتور صفر است.",
    "no_technician": "این فاکتور تکنسین ندارد.",
    "fallback_to_company": "دلیل نامشخص/نیازمند بررسی.",
}


def _base_qs(company):
    return (
        PaymentSplitSnapshot.objects
        .filter(company=company)
        .select_related(
            "payment",
            "payment__gateway",
            "invoice",
            "invoice__order",
            "invoice__order__technician",
            "invoice__order__technician__user",
        )
        .order_by("-created_at", "-id")
    )


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def split_snapshot_list(request, company_code=None):
    company = request.company
    qs = _base_qs(company)

    split_filter = request.GET.get("split", "")
    reason_filter = request.GET.get("reason", "")
    technician_filter = request.GET.get("technician", "")
    q = request.GET.get("q", "").strip()

    if split_filter == "yes":
        qs = qs.filter(should_split_with_technician=True)
    elif split_filter == "no":
        qs = qs.filter(should_split_with_technician=False)

    if reason_filter:
        qs = qs.filter(reason=reason_filter)

    if technician_filter:
        qs = qs.filter(invoice__order__technician_id=technician_filter)

    if q:
        qs = qs.filter(invoice__invoice_number__icontains=q) | \
             qs.filter(payment__tracking_code__icontains=q) | \
             qs.filter(payment__reference_id__icontains=q)
        qs = qs.distinct()

    from apps.accounts.models import Technician
    technicians = Technician.objects.filter(company=company).select_related("user").order_by("user__first_name")

    reason_choices = list(REASON_LABELS.items())

    return render(request, "payouts/split_snapshot_list.html", {
        "company": company,
        "snapshots": qs[:200],
        "split_filter": split_filter,
        "reason_filter": reason_filter,
        "technician_filter": technician_filter,
        "q": q,
        "technicians": technicians,
        "reason_choices": reason_choices,
    })


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def split_snapshot_detail(request, snapshot_id: int, company_code=None):
    company = request.company
    try:
        snapshot = _base_qs(company).get(id=snapshot_id)
    except PaymentSplitSnapshot.DoesNotExist:
        raise Http404("اسنپ‌شات یافت نشد.")

    reason_label = REASON_LABELS.get(snapshot.reason, "دلیل نامشخص/نیازمند بررسی.")
    raw_json = json.dumps(snapshot.raw_decision, ensure_ascii=False, indent=2)

    return render(request, "payouts/split_snapshot_detail.html", {
        "company": company,
        "snapshot": snapshot,
        "reason_label": reason_label,
        "raw_json": raw_json,
    })


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def gateway_reconciliation(request, company_code=None):
    """
    Shaparak gateway settlement reconciliation review page.

    Read-only: shows PaymentSplitSnapshot rows for the current company with
    date and split-status filters. No financial writes or corrections here.
    """
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET"])

    company = request.company
    qs = _base_qs(company)

    split_filter = request.GET.get("split", "")
    from_date_raw = (request.GET.get("from_date") or "").strip()
    to_date_raw = (request.GET.get("to_date") or "").strip()
    from_date = _parse_reconciliation_date(from_date_raw)
    to_date = _parse_reconciliation_date(to_date_raw)

    if split_filter == "yes":
        qs = qs.filter(should_split_with_technician=True)
    elif split_filter == "no":
        qs = qs.filter(should_split_with_technician=False)

    if from_date:
        qs = qs.filter(created_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(created_at__date__lte=to_date)

    return render(request, "payouts/gateway_reconciliation.html", {
        "company": company,
        "snapshots": qs[:500],
        "split_filter": split_filter,
        "from_date_raw": from_date_raw,
        "to_date_raw": to_date_raw,
        "from_date": from_date,
        "to_date": to_date,
    })
