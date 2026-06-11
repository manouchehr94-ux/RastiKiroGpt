"""Platform owner SMS views."""
from datetime import time

from django.http import HttpRequest, HttpResponse
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_platform_owner

from .models import PlatformSMSMessageTypeSetting, PlatformSMSOutbox, PlatformSMSProviderSetting
from .services_platform_sms import (
    PlatformSMSMessageTypeService,
    PlatformSMSOutboxProcessorService,
    PlatformSMSProviderService,
    PlatformSMSSendService,
)


def _parse_time(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) < 2:
        raise ValueError("ساعت باید با فرمت HH:MM باشد.")
    return time(hour=int(parts[0]), minute=int(parts[1]))


@require_platform_owner
def platform_sms_index(request: HttpRequest) -> HttpResponse:
    PlatformSMSMessageTypeService.ensure_defaults()
    queued = PlatformSMSOutbox.objects.filter(status=PlatformSMSOutbox.Status.QUEUED).count()
    failed = PlatformSMSOutbox.objects.filter(status=PlatformSMSOutbox.Status.FAILED).count()
    sent = PlatformSMSOutbox.objects.filter(status=PlatformSMSOutbox.Status.SENT).count()
    provider = PlatformSMSProviderService.get_or_create_singleton()
    return render(request, "platform_core/platform_sms/index.html", {"queued": queued, "failed": failed, "sent": sent, "provider": provider})


@require_platform_owner
def platform_sms_message_types(request: HttpRequest) -> HttpResponse:
    settings = PlatformSMSMessageTypeService.ensure_defaults()
    success = ""
    error = ""
    if request.method == "POST":
        try:
            if request.POST.get("action") == "apply_company_defaults":
                count = PlatformSMSMessageTypeService.apply_company_sms_defaults()
                success = f"پیش‌فرض پیامک برای {count} تنظیم شرکت اعمال شد."
            else:
                for row in settings:
                    key = row.key
                    row.is_active = bool(request.POST.get(f"is_active_{key}"))
                    row.default_company_sms_enabled = bool(request.POST.get(f"default_sms_{key}"))
                    row.send_start_time = _parse_time(request.POST.get(f"start_{key}", ""))
                    row.send_end_time = _parse_time(request.POST.get(f"end_{key}", ""))
                    row.updated_by = request.user
                    row.save(update_fields=["is_active", "default_company_sms_enabled", "send_start_time", "send_end_time", "updated_by", "updated_at"])
                success = "تنظیمات نوع پیامک ذخیره شد."
        except Exception as exc:
            error = str(exc)
        settings = PlatformSMSMessageTypeService.ensure_defaults()
    return render(request, "platform_core/platform_sms/message_types.html", {"settings": settings, "success": success, "error": error, "payer_company": PlatformSMSMessageTypeSetting.Payer.COMPANY})


@require_platform_owner
def platform_sms_provider_settings(request: HttpRequest) -> HttpResponse:
    provider = PlatformSMSProviderService.get_or_create_singleton()
    success = ""
    error = ""
    if request.method == "POST":
        try:
            provider.name = request.POST.get("name", "").strip() or provider.name
            provider.provider_type = request.POST.get("provider_type", provider.provider_type)
            provider.api_key = request.POST.get("api_key", "").strip()
            provider.sender_number = request.POST.get("sender_number", "").strip()
            provider.is_active = bool(request.POST.get("is_active"))
            provider.updated_by = request.user
            provider.save()
            success = "تنظیمات ارائه‌دهنده پیامک پلتفرم ذخیره شد."
        except Exception as exc:
            error = str(exc)
    return render(request, "platform_core/platform_sms/provider.html", {"provider": provider, "provider_choices": PlatformSMSProviderSetting.ProviderType.choices, "success": success, "error": error})


@require_platform_owner
def platform_sms_outbox(request: HttpRequest) -> HttpResponse:
    import re as _re
    status = (request.GET.get("status") or "").strip()
    messages = list(PlatformSMSOutbox.objects.select_related("recipient_company", "provider").order_by("-created_at")[:200])
    if status:
        messages = [m for m in messages if m.status == status]
    for m in messages:
        if "password_reset" in (m.template_key or ""):
            m.display_message = _re.sub(r"\b\d{6}\b", "******", m.message or "")
        else:
            m.display_message = (m.message or "")
    return render(request, "platform_core/platform_sms/outbox.html", {"messages": messages, "status": status, "status_choices": PlatformSMSOutbox.Status.choices})




@require_platform_owner
def platform_sms_outbox_detail(request: HttpRequest, sms_id: int) -> HttpResponse:
    sms = get_object_or_404(PlatformSMSOutbox.objects.select_related('recipient_company', 'provider'), id=sms_id)
    return render(request, 'platform_core/platform_sms/detail.html', {'sms': sms})
@require_platform_owner
def platform_sms_outbox_send_now(request: HttpRequest, sms_id: int) -> HttpResponse:
    sms = get_object_or_404(PlatformSMSOutbox, id=sms_id)
    if request.method == "POST":
        PlatformSMSSendService.send(sms=sms)
    return redirect("/owner-platform/platform-sms/outbox/")


@require_platform_owner
def platform_sms_process_outbox(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        PlatformSMSOutboxProcessorService.process(limit=50, dry_run=False)
    return redirect("/owner-platform/platform-sms/outbox/")


def _sms_template_payload_from_post(request: HttpRequest) -> dict:
    return {
        "key": (request.POST.get("key") or "").strip(),
        "title": (request.POST.get("title") or "").strip(),
        "scope": request.POST.get("scope") or "company",
        "recipient_type": request.POST.get("recipient_type") or "customer",
        "template_text": (request.POST.get("template_text") or "").strip(),
        "allowed_variables": (request.POST.get("allowed_variables") or "").strip(),
        "provider_pattern_code": (request.POST.get("provider_pattern_code") or "").strip(),
        "melipayamak_body_id": (request.POST.get("melipayamak_body_id") or "").strip(),
        "melipayamak_variables_order": (request.POST.get("melipayamak_variables_order") or "").strip(),
        "is_active": bool(request.POST.get("is_active")),
    }


def _validate_sms_template_payload(payload: dict) -> str:
    if not payload["key"]:
        return "کد داخلی قالب الزامی است."
    if not payload["title"]:
        return "عنوان قالب الزامی است."
    if not payload["template_text"]:
        return "متن قالب الزامی است."
    return ""


@require_platform_owner
def platform_sms_templates(request: HttpRequest) -> HttpResponse:
    from apps.sms.master_template_defaults import ensure_master_templates
    from apps.sms.models_master import SMSMasterTemplate

    success = ""
    error = ""
    if request.method == "POST" and request.POST.get("action") == "sync_defaults":
        result = ensure_master_templates()
        success = f"قالب‌های پیش‌فرض بررسی شد. ایجاد: {result['created']}، اصلاح: {result['updated']}، کل: {result['total']}"

    q = (request.GET.get("q") or "").strip()
    templates = SMSMasterTemplate.objects.all().order_by("scope", "key")
    if q:
        templates = templates.filter(models.Q(key__icontains=q) | models.Q(title__icontains=q) | models.Q(template_text__icontains=q))
    return render(request, "platform_core/platform_sms/templates.html", {"templates": templates, "q": q, "success": success, "error": error})


@require_platform_owner
def platform_sms_template_create(request: HttpRequest) -> HttpResponse:
    from apps.sms.models_master import SMSMasterTemplate

    error = ""
    template = None
    if request.method == "POST":
        payload = _sms_template_payload_from_post(request)
        error = _validate_sms_template_payload(payload)
        if not error:
            try:
                SMSMasterTemplate.objects.create(**payload)
                return redirect("/owner-platform/platform-sms/templates/")
            except Exception as exc:
                error = str(exc)
        template = type("TemplatePreview", (), payload)()
    return render(request, "platform_core/platform_sms/template_form.html", {"template": template, "error": error, "mode": "create", "scope_choices": SMSMasterTemplate.Scope.choices, "recipient_choices": SMSMasterTemplate.RecipientType.choices})


@require_platform_owner
def platform_sms_template_edit(request: HttpRequest, template_id: int) -> HttpResponse:
    from apps.sms.models_master import SMSMasterTemplate

    template = get_object_or_404(SMSMasterTemplate, id=template_id)
    error = ""
    success = ""
    if request.method == "POST":
        payload = _sms_template_payload_from_post(request)
        error = _validate_sms_template_payload(payload)
        if not error:
            try:
                for field, value in payload.items():
                    setattr(template, field, value)
                template.save()
                success = "قالب پیامکی ذخیره شد."
            except Exception as exc:
                error = str(exc)
    return render(request, "platform_core/platform_sms/template_form.html", {"template": template, "error": error, "success": success, "mode": "edit", "scope_choices": SMSMasterTemplate.Scope.choices, "recipient_choices": SMSMasterTemplate.RecipientType.choices})


@require_platform_owner
def platform_sms_template_delete(request: HttpRequest, template_id: int) -> HttpResponse:
    from apps.sms.models_master import SMSMasterTemplate

    template = get_object_or_404(SMSMasterTemplate, id=template_id)
    if request.method == "POST":
        template.delete()
    return redirect("/owner-platform/platform-sms/templates/")


# --- SMS_MULTI_PROVIDER_ROUTING_PATCH_START ---
def _safe_int(raw, default=0):
    try: return int(str(raw or '').strip() or default)
    except Exception: return default

def _provider_extra_fields_from_post(request):
    return {
        'name': (request.POST.get('name') or '').strip() or 'SMS Provider',
        'provider_type': request.POST.get('provider_type') or PlatformSMSProviderSetting.ProviderType.FAKE,
        'api_key': (request.POST.get('api_key') or '').strip(),
        'sender_number': (request.POST.get('sender_number') or '').strip(),
        'username': (request.POST.get('username') or '').strip(),
        'password': (request.POST.get('password') or '').strip(),
        'api_secret': (request.POST.get('api_secret') or '').strip(),
        'usage_scope': request.POST.get('usage_scope') or 'both',
        'priority': _safe_int(request.POST.get('priority'), 100),
        'is_fallback': bool(request.POST.get('is_fallback')),
        'endpoint_url': (request.POST.get('endpoint_url') or '').strip(),
        'request_method': (request.POST.get('request_method') or 'POST').strip().upper(),
        'headers_template': (request.POST.get('headers_template') or '').strip(),
        'body_template': (request.POST.get('body_template') or '').strip(),
        'success_keywords': (request.POST.get('success_keywords') or '').strip(),
        'is_active': bool(request.POST.get('is_active')),
        'updated_by': request.user,
    }

@require_platform_owner
def platform_sms_provider_settings(request: HttpRequest) -> HttpResponse:
    success = ''; error = ''
    if request.method == 'POST':
        try:
            action = request.POST.get('action') or 'save_provider'
            if action == 'delete_provider':
                PlatformSMSProviderSetting.objects.filter(id=_safe_int(request.POST.get('provider_id'))).delete()
                success = 'ارائه‌دهنده حذف شد.'
            else:
                payload = _provider_extra_fields_from_post(request)
                provider_id = _safe_int(request.POST.get('provider_id'))
                if provider_id:
                    obj = get_object_or_404(PlatformSMSProviderSetting, id=provider_id)
                    for k,v in payload.items():
                        if hasattr(obj,k): setattr(obj,k,v)
                    obj.save(); success = 'ارائه‌دهنده پیامک ذخیره شد.'
                else:
                    PlatformSMSProviderSetting.objects.create(**payload)
                    success = 'ارائه‌دهنده پیامک جدید ساخته شد.'
        except Exception as exc:
            error = str(exc)
    providers = PlatformSMSProviderSetting.objects.all().order_by('priority', 'id')
    editing_provider = PlatformSMSProviderSetting.objects.filter(id=_safe_int(request.GET.get('edit'))).first()
    usage_scope_choices = PlatformSMSProviderSetting.UsageScope.choices if hasattr(PlatformSMSProviderSetting, 'UsageScope') else [('both','پلتفرم و شرکت')]
    return render(request, 'platform_core/platform_sms/provider.html', {'providers': providers, 'editing_provider': editing_provider, 'provider': editing_provider, 'provider_choices': PlatformSMSProviderSetting.ProviderType.choices, 'usage_scope_choices': usage_scope_choices, 'success': success, 'error': error})

def _save_provider_routes_for_template(request, template):
    from apps.sms.models_master import SMSMasterTemplateProviderConfig
    for provider in PlatformSMSProviderSetting.objects.all().order_by('priority','id'):
        pre = f'route_{provider.id}_'
        route = SMSMasterTemplateProviderConfig.objects.filter(master_template=template, provider_setting_id=provider.id).first()
        if not request.POST.get(pre+'enabled'):
            if route:
                route.is_active=False; route.is_primary=False; route.is_fallback=False; route.save(update_fields=['is_active','is_primary','is_fallback','updated_at'])
            continue
        if route is None: route = SMSMasterTemplateProviderConfig(master_template=template, provider_setting_id=provider.id)
        route.provider_type=provider.provider_type; route.provider_name=provider.name
        route.send_mode=request.POST.get(pre+'send_mode') or 'text'
        route.pattern_code=(request.POST.get(pre+'pattern_code') or '').strip()
        route.variables_order=(request.POST.get(pre+'variables_order') or '').strip()
        route.is_primary=bool(request.POST.get(pre+'is_primary'))
        route.is_fallback=bool(request.POST.get(pre+'is_fallback'))
        route.priority=_safe_int(request.POST.get(pre+'priority'), getattr(provider,'priority',100) or 100)
        route.is_active=True; route.save()

def _provider_routes_context(template):
    from apps.sms.models_master import SMSMasterTemplateProviderConfig
    configs = {c.provider_setting_id:c for c in SMSMasterTemplateProviderConfig.objects.filter(master_template=template)}
    return [{'provider':p, 'config':configs.get(p.id)} for p in PlatformSMSProviderSetting.objects.filter(is_active=True).order_by('priority','id')]

@require_platform_owner
def platform_sms_template_edit(request: HttpRequest, template_id: int) -> HttpResponse:
    from apps.sms.models_master import SMSMasterTemplate, SMSMasterTemplateProviderConfig
    template = get_object_or_404(SMSMasterTemplate, id=template_id)
    error=''; success=''
    if request.method == 'POST':
        payload = _sms_template_payload_from_post(request)
        error = _validate_sms_template_payload(payload)
        if not error:
            try:
                for field, value in payload.items():
                    if hasattr(template, field): setattr(template, field, value)
                template.save(); _save_provider_routes_for_template(request, template)
                success = 'قالب پیامکی و مسیرهای ارسال Provider ذخیره شد.'
            except Exception as exc: error = str(exc)
    # Generate provider pattern preview
    from apps.sms.template_to_provider_pattern import convert_template_to_pattern, format_variable_map_display
    pattern_result = convert_template_to_pattern(
        template.template_text or "",
        variables_order=template.melipayamak_variables_order or template.allowed_variables or None,
    )
    return render(request, 'platform_core/platform_sms/template_form.html', {'template': template, 'error': error, 'success': success, 'mode': 'edit', 'scope_choices': SMSMasterTemplate.Scope.choices, 'recipient_choices': SMSMasterTemplate.RecipientType.choices, 'route_rows': _provider_routes_context(template), 'send_mode_choices': SMSMasterTemplateProviderConfig.SendMode.choices, 'provider_pattern_text': pattern_result.pattern_text, 'provider_variable_map': format_variable_map_display(pattern_result.variable_map), 'provider_pattern_warnings': pattern_result.warnings})
# --- SMS_MULTI_PROVIDER_ROUTING_PATCH_END ---

# --- PER_TEMPLATE_PROVIDER_ROUTING_VIEWS_START ---
def _sms_safe_int(raw, default=0):
    try:
        return int(str(raw or "").strip() or default)
    except Exception:
        return default

def platform_sms_provider_settings(request):
    from django.shortcuts import render, get_object_or_404
    from apps.platform_core.models import PlatformSMSProviderSetting
    success = ""
    error = ""
    if request.method == "POST":
        try:
            action = request.POST.get("action") or "save_provider"
            if action == "delete_provider":
                PlatformSMSProviderSetting.objects.filter(id=_sms_safe_int(request.POST.get("provider_id"))).delete()
                success = "Provider حذف شد."
            else:
                provider_id = _sms_safe_int(request.POST.get("provider_id"))
                payload = {
                    "name": (request.POST.get("name") or "").strip() or "SMS Provider",
                    "provider_type": request.POST.get("provider_type") or "fake",
                    "api_key": (request.POST.get("api_key") or "").strip(),
                    "sender_number": (request.POST.get("sender_number") or "").strip(),
                    "is_active": bool(request.POST.get("is_active")),
                }
                optional = {
                    "username": (request.POST.get("username") or "").strip(),
                    "password": (request.POST.get("password") or "").strip(),
                    "api_secret": (request.POST.get("api_secret") or "").strip(),
                    "usage_scope": "both",
                    "priority": _sms_safe_int(request.POST.get("priority"), 100),
                    "is_fallback": bool(request.POST.get("is_fallback")),
                    "endpoint_url": (request.POST.get("endpoint_url") or "").strip(),
                    "request_method": (request.POST.get("request_method") or "POST").strip().upper(),
                    "headers_template": (request.POST.get("headers_template") or "").strip(),
                    "body_template": (request.POST.get("body_template") or "").strip(),
                    "success_keywords": (request.POST.get("success_keywords") or "").strip(),
                }
                payload.update(optional)
                if provider_id:
                    obj = get_object_or_404(PlatformSMSProviderSetting, id=provider_id)
                    for k, v in payload.items():
                        if hasattr(obj, k):
                            setattr(obj, k, v)
                    if hasattr(obj, "updated_by"):
                        obj.updated_by = request.user
                    obj.save()
                    success = "Provider ذخیره شد."
                else:
                    if hasattr(PlatformSMSProviderSetting, "updated_by"):
                        payload["updated_by"] = request.user
                    PlatformSMSProviderSetting.objects.create(**payload)
                    success = "Provider جدید ساخته شد."
        except Exception as exc:
            error = str(exc)
    providers = PlatformSMSProviderSetting.objects.all().order_by("priority", "id")
    editing_provider = PlatformSMSProviderSetting.objects.filter(id=_sms_safe_int(request.GET.get("edit"))).first()
    provider_choices = getattr(PlatformSMSProviderSetting, "ProviderType").choices
    return render(request, "platform_core/platform_sms/provider.html", {
        "providers": providers,
        "editing_provider": editing_provider,
        "provider_choices": provider_choices,
        "success": success,
        "error": error,
    })

try:
    platform_sms_provider_settings = require_platform_owner(platform_sms_provider_settings)
except Exception:
    pass

def _sms_set_if_has(obj, field, value):
    if hasattr(obj, field):
        setattr(obj, field, value)

def _sms_save_routes_for_template(request, template):
    from apps.platform_core.models import PlatformSMSProviderSetting
    from apps.sms.models_master import SMSMasterTemplateProviderConfig
    for provider in PlatformSMSProviderSetting.objects.all().order_by("priority", "id"):
        prefix = f"route_{provider.id}_"
        route = SMSMasterTemplateProviderConfig.objects.filter(master_template=template, provider_setting_id=provider.id).first()
        if not request.POST.get(prefix + "enabled"):
            if route:
                route.is_active = False
                route.is_primary = False
                route.is_fallback = False
                route.save(update_fields=["is_active", "is_primary", "is_fallback", "updated_at"])
            continue
        if route is None:
            route = SMSMasterTemplateProviderConfig(master_template=template, provider_setting_id=provider.id)
        route.provider_type = provider.provider_type
        route.provider_name = provider.name
        route.send_mode = request.POST.get(prefix + "send_mode") or "text"
        route.pattern_code = (request.POST.get(prefix + "pattern_code") or "").strip()
        route.variables_order = (request.POST.get(prefix + "variables_order") or "").strip()
        route.is_primary = bool(request.POST.get(prefix + "is_primary"))
        route.is_fallback = bool(request.POST.get(prefix + "is_fallback"))
        route.priority = _sms_safe_int(request.POST.get(prefix + "priority"), getattr(provider, "priority", 100) or 100)
        route.is_active = True
        route.save()

def _sms_route_rows(template):
    from apps.platform_core.models import PlatformSMSProviderSetting
    from apps.sms.models_master import SMSMasterTemplateProviderConfig
    configs = {c.provider_setting_id: c for c in SMSMasterTemplateProviderConfig.objects.filter(master_template=template)}
    return [{"provider": p, "config": configs.get(p.id)} for p in PlatformSMSProviderSetting.objects.filter(is_active=True).order_by("priority", "id")]

def platform_sms_template_edit(request, template_id):
    from django.shortcuts import render, get_object_or_404
    from apps.sms.models_master import SMSMasterTemplate, SMSMasterTemplateProviderConfig
    template = get_object_or_404(SMSMasterTemplate, id=template_id)
    success = ""
    error = ""
    if request.method == "POST":
        try:
            _sms_set_if_has(template, "title", (request.POST.get("title") or "").strip())
            _sms_set_if_has(template, "scope", request.POST.get("scope") or getattr(template, "scope", "platform"))
            _sms_set_if_has(template, "recipient_type", request.POST.get("recipient_type") or getattr(template, "recipient_type", "customer"))
            _sms_set_if_has(template, "template_text", request.POST.get("template_text") or "")
            _sms_set_if_has(template, "allowed_variables", (request.POST.get("allowed_variables") or "").strip())
            _sms_set_if_has(template, "provider_pattern_code", (request.POST.get("provider_pattern_code") or "").strip())
            _sms_set_if_has(template, "melipayamak_body_id", (request.POST.get("melipayamak_body_id") or "").strip())
            _sms_set_if_has(template, "melipayamak_variables_order", (request.POST.get("melipayamak_variables_order") or "").strip())
            _sms_set_if_has(template, "is_active", bool(request.POST.get("is_active")))
            template.save()
            _sms_save_routes_for_template(request, template)
            success = "قالب و مسیرهای ارسال ذخیره شد."
        except Exception as exc:
            error = str(exc)
    scope_choices = getattr(SMSMasterTemplate, "Scope").choices if hasattr(SMSMasterTemplate, "Scope") else [("platform", "پلتفرم"), ("company", "شرکت")]
    recipient_choices = getattr(SMSMasterTemplate, "RecipientType").choices if hasattr(SMSMasterTemplate, "RecipientType") else [("customer", "مشتری"), ("technician", "تکنسین"), ("admin", "مدیر")]

    # Read-only provider pattern preview for MeliPayamak and other pattern systems.
    # This is computed from the site template and is not stored in DB.
    from apps.sms.template_to_provider_pattern import convert_template_to_pattern, format_variable_map_display
    pattern_result = convert_template_to_pattern(
        template.template_text or "",
        variables_order=(
            getattr(template, "melipayamak_variables_order", None)
            or getattr(template, "allowed_variables", None)
            or None
        ),
    )

    return render(request, "platform_core/platform_sms/template_form.html", {
        "template": template,
        "mode": "edit",
        "scope_choices": scope_choices,
        "recipient_choices": recipient_choices,
        "send_mode_choices": SMSMasterTemplateProviderConfig.SendMode.choices,
        "route_rows": _sms_route_rows(template),
        "provider_pattern_text": pattern_result.pattern_text,
        "provider_variable_map": format_variable_map_display(pattern_result.variable_map),
        "provider_pattern_warnings": pattern_result.warnings,
        "success": success,
        "error": error,
    })

try:
    platform_sms_template_edit = require_platform_owner(platform_sms_template_edit)
except Exception:
    pass
# --- PER_TEMPLATE_PROVIDER_ROUTING_VIEWS_END ---
