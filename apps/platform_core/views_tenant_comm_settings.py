"""
Tenant communication settings.

Company admins can enable/disable company-paid notification/SMS events here.
Phase 19B: Template view, preview, and change request views.
Phase TASK-017: Business Cause Matrix UI replacing flat event list.
"""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template import Context, Template
from django.utils import timezone

from apps.accounts.permissions import require_tenant_role
from apps.notifications.event_catalog import EVENT_DEFINITIONS, Payer
from apps.notifications.models import NotificationSetting
from apps.notifications.services import NotificationSettingService
from apps.sms.models import SMSOutbox, SMSTemplate
from apps.sms.models_master import SMSMasterTemplate
from apps.sms.services import SMSOutboxProcessorService, SMSSendingSafetyService


RECIPIENT_LABELS = {
    "CUSTOMER": "مشتری",
    "TECHNICIAN": "نیروی خدماتی",
    "COMPANY_ADMIN": "مدیر شرکت",
    "AVAILABLE_TECHNICIANS": "نیروهای واجد شرایط",
}

SAMPLE_PREVIEW_CONTEXT = {
    "company_name": "شرکت نمونه",
    "customer_name": "علی رضایی",
    "customer_phone": "09121234567",
    "customer_address": "تهران، خیابان نمونه، پلاک ۱۰",
    "technician_name": "رضا محمدی",
    "technician_phone": "09129876543",
    "order_id": "123",
    "order_title": "سفارش نمونه",
    "service_category": "نظافت منزل",
    "invoice_number": "INV-123",
    "invoice_amount": "۲,۵۰۰,۰۰۰",
    "public_invoice_link": "https://example.com/i/sample",
    "survey_link": "https://example.com/survey/sample",
    "reason": "نمونه علت",
    "admin_name": "مدیر نمونه",
    "admin_phone": "09120000000",
    "support_phone": "02191001234",
    "subscription_plan": "پلن حرفه‌ای",
    "subscription_end_date": "1404/06/31",
    "platform_invoice_number": "PB-001",
    "platform_invoice_amount": "۵۰۰,۰۰۰",
    "payment_link": "https://example.com/pay/sample",
}

# ---------------------------------------------------------------------------
# Business Cause Catalog  (Python-only, no DB model)
# ---------------------------------------------------------------------------
# Maps UI business causes to role-specific event_keys.
# admin/operator/technician/customer values are event_key strings or None.
# None means no notification is defined for that role+cause combination.
# ---------------------------------------------------------------------------

COMMUNICATION_GROUP_CATALOG = [
    {
        "group_key": "orders",
        "group_label": "سفارش",
        "rows": [
            {
                "cause_key": "order_created",
                "cause_label": "سفارش جدید",
                "admin": "order_created_admin",
                "operator": None,
                "technician": "order_available_technician",
                "customer": "order_created_customer",
            },
            {
                "cause_key": "order_assignment",
                "cause_label": "تخصیص تکنسین",
                "admin": None,
                "operator": None,
                "technician": "order_assigned_technician",
                "customer": "order_accepted_customer",
            },
            {
                "cause_key": "order_rejected",
                "cause_label": "رد توسط تکنسین",
                "admin": "order_rejected_technician",
                "operator": None,
                "technician": None,
                "customer": None,
            },
            {
                "cause_key": "order_started",
                "cause_label": "شروع خدمت",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "order_started",
            },
            {
                "cause_key": "order_completed",
                "cause_label": "پایان خدمت",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "order_completed_customer",
            },
            {
                "cause_key": "order_rescheduled",
                "cause_label": "تغییر زمان",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "order_rescheduled",
            },
        ],
    },
    {
        "group_key": "cancellation",
        "group_label": "لغو سفارش",
        "rows": [
            {
                "cause_key": "cancel_by_customer",
                "cause_label": "درخواست لغو توسط مشتری",
                "admin": "order_cancel_requested_customer",
                "operator": None,
                "technician": None,
                "customer": None,
            },
            {
                "cause_key": "cancel_by_admin",
                "cause_label": "درخواست لغو توسط مدیر",
                "admin": "order_cancel_requested_admin",
                "operator": None,
                "technician": None,
                "customer": None,
            },
            {
                "cause_key": "cancel_approved",
                "cause_label": "تأیید لغو",
                "admin": None,
                "operator": None,
                "technician": "order_cancel_approved_technician",
                "customer": None,
            },
            {
                "cause_key": "cancel_rejected",
                "cause_label": "رد لغو",
                "admin": None,
                "operator": None,
                "technician": "order_cancel_rejected_technician",
                "customer": None,
            },
            {
                "cause_key": "order_cancelled_final",
                "cause_label": "لغو نهایی",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "order_cancelled",
            },
        ],
    },
    {
        "group_key": "invoice",
        "group_label": "فاکتور",
        "rows": [
            {
                "cause_key": "invoice_created",
                "cause_label": "ایجاد فاکتور",
                "admin": "invoice_created",
                "operator": None,
                "technician": None,
                "customer": None,
            },
            {
                "cause_key": "invoice_issued",
                "cause_label": "صدور فاکتور",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "invoice_issued_customer",
            },
            {
                "cause_key": "invoice_sent",
                "cause_label": "ارسال فاکتور",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "invoice_sent_customer",
            },
            {
                "cause_key": "invoice_paid",
                "cause_label": "پرداخت فاکتور",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "invoice_paid_customer",
            },
            {
                "cause_key": "invoice_cancelled",
                "cause_label": "لغو فاکتور",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "invoice_cancelled",
            },
        ],
    },
    {
        "group_key": "payment",
        "group_label": "پرداخت",
        "rows": [
            {
                "cause_key": "payment_started",
                "cause_label": "شروع پرداخت",
                "admin": "payment_started",
                "operator": None,
                "technician": None,
                "customer": None,
            },
            {
                "cause_key": "payment_success",
                "cause_label": "پرداخت موفق",
                "admin": "payment_success_admin",
                "operator": "payment_success_operator",
                "technician": None,
                "customer": "payment_success_customer",
            },
            {
                "cause_key": "payment_failed",
                "cause_label": "پرداخت ناموفق",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "payment_failed_customer",
            },
        ],
    },
    {
        "group_key": "team",
        "group_label": "مدیریت تیم",
        "rows": [
            {
                "cause_key": "admin_login",
                "cause_label": "ورود مدیر",
                "admin": "company_admin_login",
                "operator": None,
                "technician": None,
                "customer": None,
            },
            {
                "cause_key": "operator_created",
                "cause_label": "ایجاد اپراتور",
                "admin": None,
                "operator": "operator_created",
                "technician": None,
                "customer": None,
            },
            {
                "cause_key": "technician_created",
                "cause_label": "ایجاد تکنسین",
                "admin": None,
                "operator": None,
                "technician": "technician_created",
                "customer": None,
            },
            {
                "cause_key": "technician_login",
                "cause_label": "ورود تکنسین",
                "admin": None,
                "operator": None,
                "technician": "technician_login",
                "customer": None,
            },
            {
                "cause_key": "technician_status",
                "cause_label": "تغییر وضعیت تکنسین",
                "admin": None,
                "operator": None,
                "technician": "technician_status_changed",
                "customer": None,
            },
            {
                "cause_key": "technician_wage",
                "cause_label": "تغییر درصد اجرت",
                "admin": None,
                "operator": None,
                "technician": "technician_wage_percent_changed",
                "customer": None,
            },
        ],
    },
    {
        "group_key": "service_setup",
        "group_label": "تنظیم خدمات",
        "rows": [
            {
                "cause_key": "category_created",
                "cause_label": "ایجاد رسته خدمات",
                "admin": "service_category_created",
                "operator": None,
                "technician": None,
                "customer": None,
            },
            {
                "cause_key": "item_created",
                "cause_label": "ایجاد آیتم خدمات",
                "admin": "service_item_created",
                "operator": None,
                "technician": None,
                "customer": None,
            },
        ],
    },
    {
        "group_key": "marketing",
        "group_label": "بازاریابی",
        "rows": [
            {
                "cause_key": "survey",
                "cause_label": "نظرسنجی",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "survey_request_customer",
            },
            {
                "cause_key": "discount",
                "cause_label": "کد تخفیف",
                "admin": None,
                "operator": None,
                "technician": None,
                "customer": "discount_code_customer",
            },
        ],
    },
    {
        "group_key": "wallet",
        "group_label": "کیف پول",
        "rows": [
            {
                "cause_key": "wallet_charged",
                "cause_label": "شارژ اعتبار پیامک",
                "admin": "wallet_charged",
                "operator": None,
                "technician": None,
                "customer": None,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_notification_setting(company, event_key, definition):
    setting, _ = NotificationSetting.objects.get_or_create(
        company=company,
        event_key=event_key,
        defaults={
            "sms_enabled": bool(definition.default_sms_enabled),
            "in_app_enabled": bool(definition.default_in_app_enabled),
        },
    )
    return setting


def _get_effective_template(company, event_key):
    """Use centralized resolver for consistency between display and sending."""
    from apps.sms.template_resolver import resolve_effective_sms_template
    return resolve_effective_sms_template(company=company, event_key=event_key)


def _render_preview(template_text):
    """Render template text with sample Persian context for preview."""
    if not template_text:
        return ""
    try:
        tpl = Template(template_text)
        ctx = Context(SAMPLE_PREVIEW_CONTEXT)
        return tpl.render(ctx)
    except Exception:
        return "(خطا در رندر پیش‌نمایش)"


def _build_sms_status(company) -> dict:
    """Return operational SMS statistics scoped strictly to company."""
    today = timezone.now().date()

    queued_count = SMSOutbox.objects.filter(company=company, status=SMSOutbox.Status.QUEUED).count()
    failed_count = SMSOutbox.objects.filter(company=company, status=SMSOutbox.Status.FAILED).count()
    sent_today_count = SMSOutbox.objects.filter(
        company=company,
        status__in=[SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED],
        sent_at__date=today,
    ).count()

    last_sent_row = (
        SMSOutbox.objects.filter(company=company, status__in=[SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED])
        .order_by("-sent_at").values("sent_at").first()
    )
    last_failed_row = (
        SMSOutbox.objects.filter(company=company, status=SMSOutbox.Status.FAILED)
        .order_by("-failed_at").values("failed_at").first()
    )

    provider_info = SMSSendingSafetyService.get_status(company=company)
    provider_obj = provider_info.get("provider")

    sms_balance_rial = None
    try:
        from apps.platform_core.models import CompanySMSWallet
        wallet = CompanySMSWallet.objects.filter(company=company).first()
        if wallet is not None:
            sms_balance_rial = wallet.balance_rial
    except Exception:
        pass

    return {
        "queued_count": queued_count,
        "failed_count": failed_count,
        "sent_today_count": sent_today_count,
        "last_sent_at": last_sent_row["sent_at"] if last_sent_row else None,
        "last_failed_at": last_failed_row["failed_at"] if last_failed_row else None,
        "provider_configured": provider_info["enabled"],
        "provider_name": getattr(provider_obj, "name", "") if provider_obj else "",
        "provider_reason": provider_info.get("reason", ""),
        "sms_balance_rial": sms_balance_rial,
    }


def _chip_for(event_key, channel, settings_map):
    """
    Return chip state dict for one event_key + channel combination.

    state values:
      "on"   — event exists, channel supported, currently enabled
      "off"  — event exists, channel supported, currently disabled
      "lock" — event exists but channel is structurally not supported
      "na"   — no event_key defined for this role+cause
    """
    if event_key is None:
        return {"event_key": None, "supported": False, "enabled": False, "state": "na"}

    definition = EVENT_DEFINITIONS.get(event_key)
    if definition is None:
        return {"event_key": None, "supported": False, "enabled": False, "state": "na"}

    if channel == "sms":
        supported = bool(definition.sms_supported)
    else:
        supported = bool(definition.default_in_app_enabled)

    setting = settings_map.get(event_key)
    if channel == "sms":
        enabled = bool(getattr(setting, "sms_enabled", False)) if setting else False
    else:
        enabled = bool(getattr(setting, "in_app_enabled", False)) if setting else False

    if not supported:
        state = "lock"
    elif enabled:
        state = "on"
    else:
        state = "off"

    return {
        "event_key": event_key,
        "supported": supported,
        "enabled": enabled,
        "state": state,
    }


def _build_event_matrix(company):
    """
    Build the Business Cause Matrix context for the main communication settings page.
    Returns a list of group dicts, each containing rows, each row containing
    sms/in_app chip dicts for 4 roles.
    """
    NotificationSettingService.ensure_defaults(company=company)

    settings_map = {
        item.event_key: item
        for item in NotificationSetting.objects.filter(company=company)
    }

    result_groups = []
    for group in COMMUNICATION_GROUP_CATALOG:
        result_rows = []
        for row_idx, row in enumerate(group["rows"]):
            admin_key = row.get("admin")
            operator_key = row.get("operator")
            tech_key = row.get("technician")
            customer_key = row.get("customer")

            result_rows.append({
                "cause_key": row["cause_key"],
                "cause_label": row["cause_label"],
                "is_first_row": (row_idx == 0),
                "detail_url": f"/{company.code}/admin/communication-settings/cause/{row['cause_key']}/",
                "sms": {
                    "admin":      _chip_for(admin_key,    "sms", settings_map),
                    "operator":   _chip_for(operator_key, "sms", settings_map),
                    "technician": _chip_for(tech_key,     "sms", settings_map),
                    "customer":   _chip_for(customer_key, "sms", settings_map),
                },
                "in_app": {
                    "admin":      _chip_for(admin_key,    "in_app", settings_map),
                    "operator":   _chip_for(operator_key, "in_app", settings_map),
                    "technician": _chip_for(tech_key,     "in_app", settings_map),
                    "customer":   _chip_for(customer_key, "in_app", settings_map),
                },
            })

        result_groups.append({
            "group_key": group["group_key"],
            "group_label": group["group_label"],
            "row_count": len(result_rows),
            "rows": result_rows,
        })

    return result_groups


def _find_cause_in_catalog(cause_key):
    """Return (group_dict, row_dict) for the given cause_key, or (None, None)."""
    for group in COMMUNICATION_GROUP_CATALOG:
        for row in group["rows"]:
            if row["cause_key"] == cause_key:
                return group, row
    return None, None


_ROLE_LABELS = {
    "admin":      "مدیر شرکت",
    "operator":   "اپراتور",
    "technician": "نیروی خدماتی",
    "customer":   "مشتری",
}


def _build_cause_detail(company, cause_key):
    """
    Build detail context for one business cause.
    Returns a dict with group info + list of message cards (one per existing role).
    Returns None if cause_key is not found in catalog.
    """
    found_group, found_row = _find_cause_in_catalog(cause_key)
    if found_row is None:
        return None

    NotificationSettingService.ensure_defaults(company=company)

    settings_map = {
        item.event_key: item
        for item in NotificationSetting.objects.filter(company=company)
    }

    # Pre-fetch all active master templates for quick lookup
    master_by_key = {
        m.key: m
        for m in SMSMasterTemplate.objects.filter(is_active=True)
    }

    messages = []
    for role in ("admin", "operator", "technician", "customer"):
        event_key = found_row.get(role)
        if not event_key:
            continue

        definition = EVENT_DEFINITIONS.get(event_key)
        if definition is None:
            continue

        setting = settings_map.get(event_key)
        sms_enabled = bool(getattr(setting, "sms_enabled", definition.default_sms_enabled)) if setting else bool(definition.default_sms_enabled)
        in_app_enabled = bool(getattr(setting, "in_app_enabled", definition.default_in_app_enabled)) if setting else bool(definition.default_in_app_enabled)

        effective = _get_effective_template(company, event_key)
        template_text = effective["text"] if effective else None
        template_source = effective["source"] if effective else None
        template_source_label = effective["source_label"] if effective else ""
        allowed_variables = effective["allowed_variables"] if effective else ""

        master = master_by_key.get(event_key)
        provider_pattern_code = getattr(master, "provider_pattern_code", "") if master else ""
        melipayamak_body_id = getattr(master, "melipayamak_body_id", "") if master else ""

        sms_supported = bool(definition.sms_supported)
        in_app_supported = bool(definition.default_in_app_enabled)

        messages.append({
            "role": role,
            "role_label": _ROLE_LABELS[role],
            "event_key": event_key,
            "sms_supported": sms_supported,
            "sms_enabled": sms_enabled and sms_supported,
            "in_app_supported": in_app_supported,
            "in_app_enabled": in_app_enabled and in_app_supported,
            "template_text": template_text,
            "template_source": template_source,
            "template_source_label": template_source_label,
            "allowed_variables": allowed_variables,
            "provider_pattern_code": provider_pattern_code,
            "melipayamak_body_id": melipayamak_body_id,
            "has_template": bool(effective),
        })

    return {
        "group_key": found_group["group_key"],
        "group_label": found_group["group_label"],
        "cause_key": cause_key,
        "cause_label": found_row["cause_label"],
        "cards": messages,
    }


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_comm_settings(request: HttpRequest, **kwargs) -> HttpResponse:
    """GET: show company communication settings matrix. POST: toggle event settings or process SMS queue."""
    company = request.company
    success = ""
    error = ""
    process_result = None

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        if action == "process_queue":
            results = SMSOutboxProcessorService.process(company=company, limit=20)
            process_result = results
            scanned = results.get("scanned", 0)
            sent = results.get("sent", 0)
            failed = results.get("failed", 0)
            if scanned == 0:
                success = "هیچ پیامکی در صف ارسال وجود نداشت."
            else:
                success = f"پردازش انجام شد: {sent} ارسال شد، {failed} ناموفق، {scanned} بررسی شد."
        else:
            event_key = request.POST.get("event_key", "").strip()
            field = request.POST.get("field", "").strip()
            value = request.POST.get("value", "").strip() == "1"

            definition = EVENT_DEFINITIONS.get(event_key)
            if not definition or definition.payer != Payer.COMPANY:
                error = "این رویداد برای تنظیمات شرکت معتبر نیست."
                if is_ajax:
                    return JsonResponse({"ok": False, "message": error}, status=400)
            elif field not in ("sms_enabled", "in_app_enabled"):
                error = "نوع تنظیم معتبر نیست."
                if is_ajax:
                    return JsonResponse({"ok": False, "message": error}, status=400)
            else:
                setting = _get_or_create_notification_setting(company, event_key, definition)
                setattr(setting, field, value)
                setting.save(update_fields=[field, "updated_at"])
                success = "تنظیمات پیام ذخیره شد."
                if is_ajax:
                    return JsonResponse({
                        "ok": True,
                        "message": success,
                        "event_key": event_key,
                        "field": field,
                        "new_value": value,
                    })

    groups = _build_event_matrix(company)
    sms_status = _build_sms_status(company)

    return render(request, "tenants/admin_comm_settings.html", {
        "company": company,
        "company_code": company.code,
        "current_path": request.path,
        "success": success,
        "error": error,
        "groups": groups,
        "sms_status": sms_status,
        "process_result": process_result,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_comm_cause_detail(request: HttpRequest, cause_key: str, **kwargs) -> HttpResponse:
    """
    Detail page for one business cause.
    Shows all role-specific message cards (read-only text).
    Allows toggling SMS/In-app enabled state per role message.
    No request-change links are shown.
    """
    company = request.company
    success = ""
    error = ""
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        event_key = request.POST.get("event_key", "").strip()
        field = request.POST.get("field", "").strip()
        value = request.POST.get("value", "").strip() == "1"

        definition = EVENT_DEFINITIONS.get(event_key)
        if not definition or definition.payer != Payer.COMPANY:
            error = "این رویداد معتبر نیست."
            if is_ajax:
                return JsonResponse({"ok": False, "message": error}, status=400)
        elif field not in ("sms_enabled", "in_app_enabled"):
            error = "نوع تنظیم معتبر نیست."
            if is_ajax:
                return JsonResponse({"ok": False, "message": error}, status=400)
        else:
            setting = _get_or_create_notification_setting(company, event_key, definition)
            setattr(setting, field, value)
            setting.save(update_fields=[field, "updated_at"])
            success = "تنظیمات پیام ذخیره شد."
            if is_ajax:
                return JsonResponse({
                    "ok": True,
                    "message": success,
                    "event_key": event_key,
                    "field": field,
                    "new_value": value,
                })

    context_data = _build_cause_detail(company, cause_key)
    if context_data is None:
        return HttpResponse("علت ایجاد یافت نشد.", status=404, content_type="text/plain; charset=utf-8")

    return render(request, "tenants/admin_comm_cause_detail.html", {
        "company": company,
        "company_code": company.code,
        "current_path": request.path,
        "success": success,
        "error": error,
        "back_url": f"/{company.code}/admin/communication-settings/",
        **context_data,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_sms_template_view(request: HttpRequest, event_key: str, **kwargs) -> HttpResponse:
    """
    View the effective SMS template for a given event key (readonly).
    Shows template text, source, allowed variables, and a rendered preview.
    """
    company = request.company

    # Validate event_key
    definition = EVENT_DEFINITIONS.get(event_key)
    if not definition or definition.payer != Payer.COMPANY:
        return render(request, "tenants/admin_sms_template_view.html", {
            "company": company,
            "company_code": company.code,
            "error": "رویداد معتبر نیست.",
            "event_key": event_key,
            "event_title": "",
            "template_text": None,
            "template_source": None,
            "allowed_variables": "",
            "preview": "",
        })

    effective = _get_effective_template(company, event_key)
    template_text = effective["text"] if effective else None
    source = effective["source"] if effective else None
    source_label = effective["source_label"] if effective else ""
    allowed_variables = effective["allowed_variables"] if effective else ""
    preview = _render_preview(template_text) if template_text else ""

    return render(request, "tenants/admin_sms_template_view.html", {
        "company": company,
        "company_code": company.code,
        "event_key": event_key,
        "event_title": definition.title,
        "template_text": template_text,
        "template_source": source,
        "template_source_label": source_label,
        "allowed_variables": allowed_variables,
        "preview": preview,
        "error": "",
    })


# tenant_sms_template_change_request intentionally removed.
# The company-side template change request feature is disabled per product decision.
# Platform owner template management remains available at /owner-platform/sms-template-requests/.
