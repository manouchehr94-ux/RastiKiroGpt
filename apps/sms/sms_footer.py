"""
SMS Footer Helper.

Ensures all outgoing SMS texts end with the standard unsubscribe footer.

Usage:
    from apps.sms.sms_footer import ensure_sms_footer
    text = ensure_sms_footer(some_text)

Rules:
- Trims trailing whitespace
- Appends "\nلغو 11" only if not already present
- Preserves existing line breaks
- Never duplicates the footer

Exclusions:
- OTP pattern sends (MeliPayamak BaseServiceNumber) are excluded because
  the provider expects ONLY the code digits as the text payload.
  The footer is for human-readable queued SMS, not pattern payloads.
"""

SMS_UNSUBSCRIBE_FOOTER = "لغو 11"

# Template keys that must NOT have the footer appended.
# These are sent via MeliPayamak pattern where text = code only.
FOOTER_EXCLUDED_KEYS = frozenset({
    "user_mobile_verification",
})


def ensure_sms_footer(text: str) -> str:
    """
    Ensure SMS text ends with the standard unsubscribe footer.

    Args:
        text: The SMS message text

    Returns:
        text with footer appended if missing, unchanged if already present.
    """
    if not text:
        return SMS_UNSUBSCRIBE_FOOTER

    stripped = text.rstrip()
    if stripped.endswith(SMS_UNSUBSCRIBE_FOOTER):
        return stripped

    return stripped + "\n" + SMS_UNSUBSCRIBE_FOOTER


def should_have_footer(template_key: str) -> bool:
    """Check if a template key should have the unsubscribe footer."""
    return template_key not in FOOTER_EXCLUDED_KEYS
