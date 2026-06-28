"""
Payouts - Views.

Technician ledger, settlement, and statement pages for company admins.
"""
import datetime
import uuid

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from apps.accounts.models import Technician
from apps.accounts.permissions import require_tenant_role

from .services import TechnicianLedgerService
from .services_statement import TechnicianStatementService


def _parse_statement_date(value: str):
    """Parse a date string from GET params. Supports YYYY/MM/DD, YYYY-MM-DD, and Jalali."""
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

_SETTLEMENT_DIRECTIONS = [
    ("COMPANY_PAID_TECHNICIAN", "شرکت به تکنسین پرداخت کرد"),
    ("TECHNICIAN_PAID_COMPANY", "تکنسین به شرکت پرداخت کرد"),
    ("ADJUSTMENT_CREDIT", "اصلاح بستانکاری"),
    ("ADJUSTMENT_DEBIT", "اصلاح بدهکاری"),
]
_ADJUSTMENT_DIRECTIONS = {"ADJUSTMENT_CREDIT", "ADJUSTMENT_DEBIT"}


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_ledger(request, technician_id: int, company_code=None):
    company = request.company
    technician = get_object_or_404(Technician, id=technician_id, company=company)

    balance = TechnicianLedgerService.get_balance(company, technician)
    entries = TechnicianLedgerService.list_statement(company, technician)

    return render(request, "payouts/technician_ledger.html", {
        "company": company,
        "technician": technician,
        "balance": balance,
        "entries": entries,
    })


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_settlement(request, technician_id: int, company_code=None):
    company = request.company
    technician = get_object_or_404(Technician, id=technician_id, company=company)
    balance = TechnicianLedgerService.get_balance(company, technician)

    if request.method == "POST":
        direction = request.POST.get("direction", "")
        amount_raw = request.POST.get("amount", "").strip()
        reference = request.POST.get("reference", "").strip()
        note = request.POST.get("note", "").strip()
        idempotency_token = request.POST.get("idempotency_token", "").strip()

        errors = []
        valid_directions = {d[0] for d in _SETTLEMENT_DIRECTIONS}
        if direction not in valid_directions:
            errors.append("جهت تسویه نامعتبر است.")

        amount_rial = 0
        try:
            amount_rial = int(amount_raw)
            if amount_rial <= 0:
                errors.append("مبلغ باید بزرگ‌تر از صفر باشد.")
        except (ValueError, TypeError):
            errors.append("مبلغ وارد شده معتبر نیست.")

        if direction in _ADJUSTMENT_DIRECTIONS and not note:
            errors.append("برای تعدیل، توضیحات الزامی است.")

        if not idempotency_token:
            errors.append("توکن یکتا یافت نشد. لطفاً صفحه را رفرش کنید.")

        if errors:
            return render(request, "payouts/technician_settlement.html", {
                "company": company,
                "technician": technician,
                "balance": balance,
                "directions": _SETTLEMENT_DIRECTIONS,
                "errors": errors,
                "form": request.POST,
                "idempotency_token": idempotency_token or str(uuid.uuid4()),
            })

        description = note or ""
        idem_key = f"manual_settlement:{idempotency_token}"

        entry = TechnicianLedgerService.record_manual_settlement(
            company=company,
            technician=technician,
            amount_rial=amount_rial,
            direction=direction,
            reference=reference,
            description=description,
            created_by=request.user,
            idempotency_key=idem_key,
        )
        if entry is None:
            messages.warning(request, "این تسویه قبلاً ثبت شده است (تکراری).")
        messages.success(request, "تسویه با موفقیت ثبت شد.")
        return redirect(f"/{company.code}/admin/technicians/{technician.id}/ledger/")

    # GET: generate fresh idempotency token
    idempotency_token = str(uuid.uuid4())
    return render(request, "payouts/technician_settlement.html", {
        "company": company,
        "technician": technician,
        "balance": balance,
        "directions": _SETTLEMENT_DIRECTIONS,
        "errors": [],
        "form": {},
        "idempotency_token": idempotency_token,
    })


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_statement(request, technician_id: int, company_code=None):
    """
    Read-only technician statement page.

    Delegates entirely to TechnicianStatementService.build(); does not touch
    the ledger directly.
    """
    company = request.company
    technician = get_object_or_404(Technician, id=technician_id, company=company)

    from_date_raw = (request.GET.get("from_date") or "").strip()
    to_date_raw = (request.GET.get("to_date") or "").strip()

    from_date = _parse_statement_date(from_date_raw)
    to_date = _parse_statement_date(to_date_raw)

    statement = TechnicianStatementService.build(
        technician,
        from_date=from_date,
        to_date=to_date,
    )

    return render(request, "payouts/technician_statement.html", {
        "company": company,
        "technician": technician,
        "statement": statement,
        "filters": {
            "from_date": from_date_raw,
            "to_date": to_date_raw,
        },
    })


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_statement_print(request, technician_id: int, company_code=None):
    """Print-optimised HTML statement page. Same filters as main statement view."""
    company = request.company
    technician = get_object_or_404(Technician, id=technician_id, company=company)
    from_date = _parse_statement_date((request.GET.get("from_date") or "").strip())
    to_date = _parse_statement_date((request.GET.get("to_date") or "").strip())
    statement = TechnicianStatementService.build(technician, from_date=from_date, to_date=to_date)
    return render(request, "payouts/technician_statement_print.html", {
        "company": company,
        "technician": technician,
        "statement": statement,
        "from_date": from_date,
        "to_date": to_date,
    })


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_statement_pdf(request, technician_id: int, company_code=None):
    """PDF download of the technician statement via WeasyPrint."""
    company = request.company
    technician = get_object_or_404(Technician, id=technician_id, company=company)
    from_date = _parse_statement_date((request.GET.get("from_date") or "").strip())
    to_date = _parse_statement_date((request.GET.get("to_date") or "").strip())
    statement = TechnicianStatementService.build(technician, from_date=from_date, to_date=to_date)
    html_string = render_to_string("payouts/technician_statement_print.html", {
        "company": company,
        "technician": technician,
        "statement": statement,
        "from_date": from_date,
        "to_date": to_date,
    }, request=request)
    from weasyprint import HTML as WeasyHTML
    pdf_bytes = WeasyHTML(string=html_string).write_pdf()
    tech_name = statement.get("technician_name", f"tech_{technician_id}").replace(" ", "_")
    filename = f"statement_{company.code}_{tech_name}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_statement_export(request, technician_id: int, company_code=None):
    """CSV export of the technician statement. UTF-8 with BOM for Excel compatibility."""
    import csv as _csv
    company = request.company
    technician = get_object_or_404(Technician, id=technician_id, company=company)
    from_date = _parse_statement_date((request.GET.get("from_date") or "").strip())
    to_date = _parse_statement_date((request.GET.get("to_date") or "").strip())
    statement = TechnicianStatementService.build(technician, from_date=from_date, to_date=to_date)
    tech_name = statement.get("technician_name", f"tech_{technician_id}").replace(" ", "_")
    filename = f"statement_{company.code}_{tech_name}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # UTF-8 BOM — Excel requires this for correct Persian rendering
    writer = _csv.writer(response)
    writer.writerow([
        "تاریخ", "شرح", "بستانکار", "بدهکار", "مانده",
        "منبع", "شماره سفارش", "شماره فاکتور", "شناسه پرداخت",
    ])
    for row in statement["rows"]:
        date_str = row["date"].strftime("%Y-%m-%d %H:%M") if row["date"] else ""
        writer.writerow([
            date_str,
            row["description"],
            row["credit"] if row["credit"] else "",
            row["debit"] if row["debit"] else "",
            row["balance_after"],
            row["source"],
            row["order_id"] or "",
            row["invoice_id"] or "",
            row["payment_id"] or "",
        ])
    return response
