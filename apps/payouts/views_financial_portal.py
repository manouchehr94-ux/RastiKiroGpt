"""
Payouts — Financial Portal Views (Phase 1, read-only).

Browser-accessible financial management pages for company admins/operators.
All views are read-only GET pages that consume existing Sprint 1-8 services.

No mutations, no execute buttons, no approve actions in Phase 1.
Every query is company-scoped via request.company (tenant isolation).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.accounts.permissions import require_tenant_role


def _parse_period(request: HttpRequest):
    """
    Parse period_start/period_end from GET params.
    Defaults to last 30 days if not provided.
    Returns (period_start, period_end) as datetime objects.
    """
    from apps.common.jalali import normalize_digits, parse_jalali_date
    import datetime as dt

    now = timezone.now()
    default_start = now - timedelta(days=30)
    default_end = now

    raw_start = normalize_digits((request.GET.get("from_date") or "").strip())
    raw_end = normalize_digits((request.GET.get("to_date") or "").strip())

    period_start = default_start
    period_end = default_end

    if raw_start:
        parsed = parse_jalali_date(raw_start)
        if parsed:
            period_start = timezone.make_aware(
                dt.datetime.combine(parsed, dt.time.min)
            ) if timezone.is_naive(
                dt.datetime.combine(parsed, dt.time.min)
            ) else dt.datetime.combine(parsed, dt.time.min)
        else:
            try:
                d = dt.datetime.strptime(raw_start.replace("-", "/"), "%Y/%m/%d")
                period_start = timezone.make_aware(d)
            except (ValueError, TypeError):
                pass

    if raw_end:
        parsed = parse_jalali_date(raw_end)
        if parsed:
            period_end = timezone.make_aware(
                dt.datetime.combine(parsed, dt.time.max)
            ) if timezone.is_naive(
                dt.datetime.combine(parsed, dt.time.max)
            ) else dt.datetime.combine(parsed, dt.time.max)
        else:
            try:
                d = dt.datetime.strptime(raw_end.replace("-", "/"), "%Y/%m/%d")
                period_end = timezone.make_aware(
                    dt.datetime.combine(d.date(), dt.time.max)
                )
            except (ValueError, TypeError):
                pass

    return period_start, period_end



# =============================================================================
# 1. Financial Dashboard
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_dashboard(request: HttpRequest, **kwargs) -> HttpResponse:
    """Financial portal dashboard with overview cards."""
    company = request.company
    period_start, period_end = _parse_period(request)

    from apps.payouts.services_financial_reporting import FinancialReportingService

    report = FinancialReportingService.generate_period_report(
        company=company,
        period_start=period_start,
        period_end=period_end,
    )

    return render(request, "payouts/financial_portal/dashboard.html", {
        "company": company,
        "report": report,
        "period_start": period_start,
        "period_end": period_end,
        "filters": {
            "from_date": request.GET.get("from_date", ""),
            "to_date": request.GET.get("to_date", ""),
        },
    })


# =============================================================================
# 2. Technician Settlement Statements (list)
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_technician_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List technicians with financial summary."""
    company = request.company
    period_start, period_end = _parse_period(request)

    from django.db.models import Sum
    from apps.accounts.models import Technician
    from apps.payouts.models import TechnicianLedgerEntry
    from apps.payouts.services import TechnicianLedgerService

    technicians = Technician.objects.filter(
        company=company,
    ).select_related("user").order_by("user__first_name", "user__last_name")

    rows = []
    for tech in technicians:
        entries_qs = TechnicianLedgerEntry.objects.filter(
            company=company,
            technician=tech,
            created_at__gte=period_start,
            created_at__lte=period_end,
        )
        credits = entries_qs.filter(
            entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
        ).aggregate(t=Sum("amount_rial"))["t"] or 0
        debits = entries_qs.filter(
            entry_type=TechnicianLedgerEntry.EntryType.DEBIT,
        ).aggregate(t=Sum("amount_rial"))["t"] or 0

        balance = TechnicianLedgerService.get_balance(company, tech)

        rows.append({
            "technician": tech,
            "total_earned": int(credits),
            "total_debited": int(debits),
            "period_net": int(credits) - int(debits),
            "current_balance": balance,
        })

    return render(request, "payouts/financial_portal/technician_list.html", {
        "company": company,
        "rows": rows,
        "period_start": period_start,
        "period_end": period_end,
        "filters": {
            "from_date": request.GET.get("from_date", ""),
            "to_date": request.GET.get("to_date", ""),
        },
    })


# =============================================================================
# 3. Technician Statement Detail
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_technician_detail(request: HttpRequest, technician_id: int, **kwargs) -> HttpResponse:
    """Detailed financial statement for one technician."""
    company = request.company
    period_start, period_end = _parse_period(request)

    from apps.accounts.models import Technician
    from apps.payouts.models import TechnicianLedgerEntry
    from apps.payouts.services import TechnicianLedgerService

    technician = get_object_or_404(Technician, id=technician_id, company=company)
    balance = TechnicianLedgerService.get_balance(company, technician)

    entries = TechnicianLedgerEntry.objects.filter(
        company=company,
        technician=technician,
        created_at__gte=period_start,
        created_at__lte=period_end,
    ).select_related("invoice", "order", "payment").order_by("-created_at", "-id")

    return render(request, "payouts/financial_portal/technician_detail.html", {
        "company": company,
        "technician": technician,
        "balance": balance,
        "entries": entries,
        "period_start": period_start,
        "period_end": period_end,
        "filters": {
            "from_date": request.GET.get("from_date", ""),
            "to_date": request.GET.get("to_date", ""),
        },
    })



# =============================================================================
# 4. Settlement Batch List
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_settlement_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List settlement batches for the company."""
    company = request.company
    period_start, period_end = _parse_period(request)

    from apps.payouts.models import SettlementBatch

    batches = SettlementBatch.objects.filter(
        company=company,
        period_start__lte=period_end,
        period_end__gte=period_start,
    ).order_by("-created_at")

    return render(request, "payouts/financial_portal/settlement_list.html", {
        "company": company,
        "batches": batches,
        "period_start": period_start,
        "period_end": period_end,
        "filters": {
            "from_date": request.GET.get("from_date", ""),
            "to_date": request.GET.get("to_date", ""),
        },
    })


# =============================================================================
# 5. Settlement Batch Detail
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_settlement_detail(request: HttpRequest, batch_id: int, **kwargs) -> HttpResponse:
    """Settlement batch detail with items."""
    company = request.company

    from apps.payouts.models import SettlementBatch, SettlementItem

    batch = get_object_or_404(SettlementBatch, id=batch_id, company=company)
    items = SettlementItem.objects.filter(
        company=company,
        batch=batch,
    ).select_related("invoice", "ledger_entry", "platform_fee_entry").order_by("id")

    return render(request, "payouts/financial_portal/settlement_detail.html", {
        "company": company,
        "batch": batch,
        "items": items,
    })


# =============================================================================
# 6. Escrow List
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_escrow_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List escrow records for the company."""
    company = request.company
    period_start, period_end = _parse_period(request)

    from apps.payouts.models import EscrowRecord

    escrows = EscrowRecord.objects.filter(
        company=company,
        held_at__gte=period_start,
        held_at__lte=period_end,
    ).select_related("invoice", "payment", "settlement_batch").order_by("-held_at")

    return render(request, "payouts/financial_portal/escrow_list.html", {
        "company": company,
        "escrows": escrows,
        "period_start": period_start,
        "period_end": period_end,
        "filters": {
            "from_date": request.GET.get("from_date", ""),
            "to_date": request.GET.get("to_date", ""),
        },
    })


# =============================================================================
# 7. Adjustment List
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_adjustment_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List adjustment/refund documents for the company."""
    company = request.company
    period_start, period_end = _parse_period(request)

    from apps.payouts.models import AdjustmentDocument

    documents = AdjustmentDocument.objects.filter(
        company=company,
        created_at__gte=period_start,
        created_at__lte=period_end,
    ).select_related("original_invoice", "created_by").order_by("-created_at")

    return render(request, "payouts/financial_portal/adjustment_list.html", {
        "company": company,
        "documents": documents,
        "period_start": period_start,
        "period_end": period_end,
        "filters": {
            "from_date": request.GET.get("from_date", ""),
            "to_date": request.GET.get("to_date", ""),
        },
    })


# =============================================================================
# 8. Reconciliation Page
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_reconciliation(request: HttpRequest, **kwargs) -> HttpResponse:
    """Reconciliation status page using Sprint 6 service."""
    company = request.company

    from apps.payouts.services_reconciliation import (
        FinancialReconciliationService,
        ReconciliationSeverity,
    )

    report = FinancialReconciliationService.reconcile_company(company)

    errors = report.by_severity(ReconciliationSeverity.ERROR)
    warnings = report.by_severity(ReconciliationSeverity.WARNING)
    blocked = report.by_severity(ReconciliationSeverity.BLOCKED)

    return render(request, "payouts/financial_portal/reconciliation.html", {
        "company": company,
        "report": report,
        "errors": errors,
        "warnings": warnings,
        "blocked": blocked,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "blocked_count": len(blocked),
        "is_clean": report.is_clean,
    })


# =============================================================================
# 9. Closing Readiness Page
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_closing(request: HttpRequest, **kwargs) -> HttpResponse:
    """Period closing readiness page using Sprint 7 engine."""
    company = request.company
    period_start, period_end = _parse_period(request)

    from apps.payouts.services_financial_closing import (
        ClosingStatus,
        FinancialClosingEngine,
    )

    result = FinancialClosingEngine.evaluate(
        company=company,
        period_start=period_start,
        period_end=period_end,
    )

    return render(request, "payouts/financial_portal/closing.html", {
        "company": company,
        "result": result,
        "period_start": period_start,
        "period_end": period_end,
        "filters": {
            "from_date": request.GET.get("from_date", ""),
            "to_date": request.GET.get("to_date", ""),
        },
        "ClosingStatus": ClosingStatus,
    })


# =============================================================================
# 10. Financial Reports Page
# =============================================================================

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_portal_reports(request: HttpRequest, **kwargs) -> HttpResponse:
    """Full structured period report using Sprint 8 service."""
    company = request.company
    period_start, period_end = _parse_period(request)

    from apps.payouts.services_financial_reporting import FinancialReportingService

    report = FinancialReportingService.generate_period_report(
        company=company,
        period_start=period_start,
        period_end=period_end,
    )

    return render(request, "payouts/financial_portal/reports.html", {
        "company": company,
        "report": report,
        "period_start": period_start,
        "period_end": period_end,
        "filters": {
            "from_date": request.GET.get("from_date", ""),
            "to_date": request.GET.get("to_date", ""),
        },
    })
