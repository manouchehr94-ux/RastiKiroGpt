"""
SMS - Registration OTP Hook.

Entry point for sending mobile verification OTP via MeliPayamak pattern.
"""
import logging

logger = logging.getLogger(__name__)


def send_user_mobile_verification_sms(mobile: str, otp_code, expire_minutes: int = 2) -> dict:
    """
    Send OTP code for user mobile verification via MeliPayamak pattern send.

    Args:
        mobile: Recipient mobile number (e.g. "09170432500")
        otp_code: The OTP code to send (e.g. "53233" or 53233)
        expire_minutes: OTP expiration time in minutes (default 2)

    Returns:
        dict with success/failure info from the provider

    Raises:
        SMSProviderError on send failure
    """
    from apps.sms.providers.melipayamak import send_template_pattern_by_owner_route

    logger.info("Sending mobile verification OTP to %s", mobile)

    return send_template_pattern_by_owner_route(
        template_key="user_mobile_verification",
        to=mobile,
        variables={
            "otp_code": str(otp_code),
            "code": str(otp_code),
            "expire_minutes": str(expire_minutes),
        },
    )
