"""
SMS - MeliPayamak Pattern-Based Provider.

Handles pattern (BaseServiceNumber) sending for MeliPayamak.
Endpoint: https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber

POST body:
{
    "username": "<panel_username>",
    "password": "<api_key>",
    "text": "<semicolon-joined variables in order>",
    "to": "<recipient_mobile>",
    "bodyId": <pattern_body_id>
}

Successful response:
{
    "Value": "...",
    "RetStatus": 1,
    "StrRetStatus": "Ok"
}
"""
import logging

import requests
from django.utils import timezone

from .base import BaseSMSProvider, SMSSendRequest, SMSSendResponse

logger = logging.getLogger(__name__)

MELIPAYAMAK_PATTERN_ENDPOINT = (
    "https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber"
)


class SMSProviderError(Exception):
    """Raised when an SMS provider encounters an error."""
    pass


# ---------------------------------------------------------------------------
# MeliPayamak error code mapping (Farsi)
# ---------------------------------------------------------------------------
MELIPAYAMAK_ERROR_MAP = {
    "-110": "الزام استفاده از APIKey به جای رمز عبور",
    "-109": "الزام تنظیم IP مجاز برای استفاده از API",
    "-108": "مسدود شدن IP به دلیل تلاش ناموفق استفاده از API",
    "-10": "ممنوعیت ارسال لینک در متغیرها",
    "-6": "خطای داخلی ملی پیامک",
    "-5": "متن ارسالی با متغیرهای پترن همخوانی ندارد",
    "-4": "کد متن/BodyId صحیح نیست یا هنوز تأیید نشده",
    "-3": "خط ارسالی در سیستم تعریف نشده است",
    "-2": "محدودیت تعداد شماره؛ هر بار فقط یک شماره",
    "-1": "دسترسی وب‌سرویس غیرفعال است",
    "0": "نام کاربری یا رمز عبور/APIKey صحیح نیست",
    "2": "اعتبار کافی نیست",
    "6": "سامانه در حال بروزرسانی است",
    "7": "متن حاوی کلمه فیلتر شده است",
    "10": "کاربر فعال نیست",
    "11": "ارسال نشده",
    "12": "مدارک کاربر کامل نیست",
    "18": "شماره موبایل معتبر نیست",
    "19": "سقف محدودیت روزانه ارسال از وب‌سرویس",
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _split_variables_order(raw):
    """Parse a comma/semicolon-separated variables_order string into a list."""
    if not raw:
        return []
    return [x.strip() for x in str(raw).replace(";", ",").split(",") if x.strip()]


def build_pattern_text(variables: dict, variables_order: str) -> str:
    """
    Build the 'text' field for MeliPayamak pattern sending.

    For pattern SMS, text = semicolon-joined values in the exact order
    defined by variables_order.

    Example:
        variables = {"otp_code": "53233", "expire_minutes": "2"}
        variables_order = "otp_code;expire_minutes"
        result = "53233;2"

    If variables_order has only one item (e.g. just otp_code):
        result = "53233"
    """
    order = _split_variables_order(variables_order)

    if not order:
        # Fallback: if no order specified, try common OTP variable names
        if isinstance(variables, dict):
            if "otp_code" in variables:
                return str(variables["otp_code"])
            if "code" in variables:
                return str(variables["code"])
            if len(variables) == 1:
                return str(next(iter(variables.values())))
        return str(variables or "")

    return ";".join(str(variables.get(k, "")) for k in order)


# ---------------------------------------------------------------------------
# Core send function
# ---------------------------------------------------------------------------

def send_melipayamak_pattern(provider, to: str, body_id, variables: dict, variables_order: str = "") -> dict:
    """
    Send a pattern-based SMS via MeliPayamak BaseServiceNumber endpoint.

    Args:
        provider: PlatformSMSProviderSetting instance with credentials
        to: recipient mobile number (e.g. "09170432500")
        body_id: MeliPayamak BodyId for the pattern
        variables: dict of template variables (e.g. {"otp_code": "53233"})
        variables_order: comma/semicolon-separated order of variables

    Returns:
        dict with success=True/False, response data, message_id, etc.

    Raises:
        SMSProviderError on validation or API errors
    """
    # --- Credential extraction ---
    username = (
        getattr(provider, "username", None)
        or getattr(provider, "api_username", None)
        or getattr(provider, "sender_number", None)
        or ""
    )
    password = (
        getattr(provider, "password", None)
        or getattr(provider, "api_secret", None)
        or getattr(provider, "api_key", None)
        or ""
    )

    # --- Validation ---
    if not username:
        raise SMSProviderError("نام کاربری ملی پیامک تنظیم نشده است.")
    if not password:
        raise SMSProviderError("APIKey/Password ملی پیامک تنظیم نشده است.")
    if not body_id:
        raise SMSProviderError("BodyId پترن ملی پیامک تنظیم نشده است.")
    if not to:
        raise SMSProviderError("شماره گیرنده خالی است.")

    # --- Build text from variables in order ---
    text = build_pattern_text(variables, variables_order)

    # --- Prepare payload ---
    payload = {
        "username": str(username),
        "password": str(password),
        "text": str(text),
        "to": str(to),
        "bodyId": int(str(body_id).strip()),
    }

    logger.info(
        "MeliPayamak pattern send: to=%s, bodyId=%s, text=%s",
        to, body_id, text,
    )

    # --- Make HTTP request ---
    try:
        response = requests.post(
            MELIPAYAMAK_PATTERN_ENDPOINT,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error("MeliPayamak HTTP error: %s", exc)
        raise SMSProviderError(f"خطای ارتباط با ملی پیامک: {exc}")

    # --- Parse response ---
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}

    if response.status_code != 200:
        logger.error(
            "MeliPayamak HTTP %s: %s", response.status_code, response.text
        )
        raise SMSProviderError(f"HTTP {response.status_code}: {response.text}")

    ret_status = data.get("RetStatus")
    value = str(data.get("Value", ""))
    str_ret = str(data.get("StrRetStatus", "")).lower()

    if ret_status == 1 or str_ret == "ok":
        logger.info(
            "MeliPayamak success: to=%s, message_id=%s", to, value
        )
        return {
            "success": True,
            "provider": "melipayamak",
            "endpoint": MELIPAYAMAK_PATTERN_ENDPOINT,
            "request_text": text,
            "response": data,
            "message_id": value,
            "sent_at": timezone.now().isoformat(),
        }

    # --- Error handling ---
    msg = MELIPAYAMAK_ERROR_MAP.get(value, data.get("StrRetStatus") or response.text)
    logger.warning(
        "MeliPayamak error: to=%s, value=%s, msg=%s", to, value, msg
    )
    raise SMSProviderError(f"خطای ملی پیامک: {value} - {msg}")


# ---------------------------------------------------------------------------
# High-level routing function
# ---------------------------------------------------------------------------

def send_template_pattern_by_owner_route(template_key: str, to: str, variables: dict) -> dict:
    """
    Send a pattern SMS using the platform owner's configured provider routing.

    Resolution order:
    1. SMSMasterTemplateProviderConfig routes (primary first, then fallbacks, by priority)
    2. Default PlatformSMSProviderSetting if no routes exist

    Args:
        template_key: e.g. "user_mobile_verification"
        to: recipient mobile number
        variables: dict of template variables

    Returns:
        dict with success info from the provider

    Raises:
        SMSProviderError if all providers fail
    """
    from apps.sms.models_master import SMSMasterTemplate, SMSMasterTemplateProviderConfig
    from apps.platform_core.models import PlatformSMSProviderSetting

    # --- Load master template ---
    try:
        template = SMSMasterTemplate.objects.get(key=template_key, is_active=True)
    except SMSMasterTemplate.DoesNotExist:
        raise SMSProviderError(
            f"قالب SMS با کلید '{template_key}' پیدا نشد یا غیرفعال است."
        )

    # --- Load provider routes ---
    routes = list(
        SMSMasterTemplateProviderConfig.objects.filter(
            master_template=template, is_active=True
        ).order_by("-is_primary", "priority", "id")
    )

    # --- No routes: use default provider with template-level config ---
    if not routes:
        body_id = (
            getattr(template, "melipayamak_body_id", "")
            or getattr(template, "provider_pattern_code", "")
        )
        variables_order = (
            getattr(template, "melipayamak_variables_order", "")
            or getattr(template, "allowed_variables", "")
        )
        provider = (
            PlatformSMSProviderSetting.objects.filter(
                provider_type="melipayamak", is_active=True
            )
            .order_by("priority", "id")
            .first()
        )
        if not provider:
            raise SMSProviderError("هیچ Provider فعال ملی پیامک پیدا نشد.")

        result = send_melipayamak_pattern(
            provider, to, body_id, variables, variables_order
        )
        _log_platform_outbox(
            provider=provider,
            template_key=template_key,
            to=to,
            text=result.get("request_text", ""),
            result=result,
        )
        return result

    # --- Order routes: primary first, then fallback, then others ---
    ordered_routes = (
        [r for r in routes if r.is_primary]
        + [r for r in routes if r.is_fallback and not r.is_primary]
        + [r for r in routes if not r.is_primary and not r.is_fallback]
    )
    # Deduplicate
    seen = set()
    final_routes = []
    for r in ordered_routes:
        if r.id not in seen:
            seen.add(r.id)
            final_routes.append(r)

    errors = []
    for route in final_routes:
        provider = PlatformSMSProviderSetting.objects.filter(
            id=route.provider_setting_id, is_active=True
        ).first()
        if not provider:
            continue

        try:
            if provider.provider_type == "melipayamak":
                result = send_melipayamak_pattern(
                    provider, to, route.pattern_code, variables, route.variables_order
                )
                _log_platform_outbox(
                    provider=provider,
                    template_key=template_key,
                    to=to,
                    text=result.get("request_text", ""),
                    result=result,
                )
                return result
            else:
                errors.append(
                    f"{provider.name}: provider_type '{provider.provider_type}' "
                    f"هنوز پیاده‌سازی نشده است."
                )
        except SMSProviderError as exc:
            errors.append(f"{getattr(provider, 'name', route.provider_name)}: {exc}")
            _log_platform_outbox(
                provider=provider,
                template_key=template_key,
                to=to,
                text="",
                result=None,
                error=str(exc),
            )

    raise SMSProviderError(
        "ارسال پیامک با همه Providerها ناموفق بود: " + " | ".join(errors)
    )


# ---------------------------------------------------------------------------
# Platform outbox logging
# ---------------------------------------------------------------------------

def _log_platform_outbox(
    *,
    provider,
    template_key: str,
    to: str,
    text: str,
    result: dict = None,
    error: str = "",
):
    """
    Log the send attempt to PlatformSMSOutbox for audit trail.
    """
    try:
        from apps.platform_core.models import PlatformSMSOutbox

        if result and result.get("success"):
            PlatformSMSOutbox.objects.create(
                provider=provider,
                template_key=template_key,
                phone_number=to,
                message=text,
                status=PlatformSMSOutbox.Status.SENT,
                provider_message_id=result.get("message_id", ""),
                sent_at=timezone.now(),
            )
        else:
            PlatformSMSOutbox.objects.create(
                provider=provider,
                template_key=template_key,
                phone_number=to,
                message=text or "(pattern send failed)",
                status=PlatformSMSOutbox.Status.FAILED,
                error_message=error or "Unknown error",
                failed_at=timezone.now(),
            )
    except Exception as log_exc:
        logger.warning("Failed to log PlatformSMSOutbox: %s", log_exc)


# ---------------------------------------------------------------------------
# Class-based provider (for compatibility with providers/ package interface)
# ---------------------------------------------------------------------------

class MeliPayamakProvider(BaseSMSProvider):
    """
    MeliPayamak SMS provider implementing the BaseSMSProvider interface.

    Used for simple text sends via the tenant-scoped provider registry.
    For pattern-based sends, use send_melipayamak_pattern() directly.
    """

    def __init__(self, *, api_key: str = "", sender_number: str = "", **kwargs):
        super().__init__(api_key=api_key, sender_number=sender_number, **kwargs)

    def send(self, request: SMSSendRequest) -> SMSSendResponse:
        """Send a simple text SMS (not pattern-based)."""
        # For simple text SMS via MeliPayamak, we'd use a different endpoint.
        # This is a placeholder; pattern sends should use send_melipayamak_pattern().
        logger.warning(
            "MeliPayamakProvider.send() called for simple text. "
            "Use send_melipayamak_pattern() for pattern-based OTP sends."
        )
        return SMSSendResponse(
            success=False,
            error_message="MeliPayamak simple text send not implemented. Use pattern send.",
        )
