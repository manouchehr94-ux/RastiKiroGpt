"""
SMS - MeliPayamak Inbox Fetcher.

Fetches received (incoming) SMS messages from MeliPayamak panel.

Endpoint:
    POST https://rest.payamak-panel.com/api/SendSMS/GetMessages

Request body:
{
    "username": "<panel_username>",
    "password": "<api_key>",
    "location": 1,
    "index": 0,
    "count": 100
}

Response (MyBase structure):
{
    "MyBase": {
        "Value": "...",
        "RetStatus": 1,
        "StrRetStatus": "Ok"
    },
    "Data": [
        {
            "MsgID": 123456,
            "Body": "4",
            "SenderNumber": "09171234567",
            "RecipientNumber": "5000xxxx",
            "SendDate": "/Date(1715000000000+0430)/"
        }
    ]
}

Note: Despite the controller name "SendSMS", the GetMessages method with
location=1 returns RECEIVED (incoming) messages. This is MeliPayamak's
API design — all message operations live under the SendSMS controller.
"""
import logging
import re
from datetime import datetime, timezone as dt_timezone
from typing import Optional

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

MELIPAYAMAK_RECEIVE_ENDPOINT = (
    "https://rest.payamak-panel.com/api/SendSMS/GetMessages"
)


class InboxFetchError(Exception):
    """Raised when inbox fetching encounters an error."""
    pass


def _extract_credentials(provider) -> tuple[str, str]:
    """
    Extract username and password from a PlatformSMSProviderSetting.

    MeliPayamak expects the API key as the "password" field in payloads.
    The actual credential is typically stored in provider.api_key, while
    provider.password may be empty. We prioritize api_key over password.
    """
    username = (
        getattr(provider, "username", None)
        or getattr(provider, "sender_number", None)
        or ""
    )
    # api_key is the primary credential for MeliPayamak (sent as "password")
    password = (
        getattr(provider, "api_key", None)
        or getattr(provider, "password", None)
        or getattr(provider, "api_secret", None)
        or ""
    )
    return str(username).strip(), str(password).strip()


def _parse_melipayamak_date(date_str: str) -> Optional[datetime]:
    """
    Parse MeliPayamak date format: /Date(1715000000000+0430)/

    Returns a timezone-aware datetime or None.
    """
    if not date_str:
        return None

    match = re.match(r"/Date\((\d+)([+-]\d{4})?\)/", str(date_str))
    if match:
        timestamp_ms = int(match.group(1))
        return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=dt_timezone.utc)

    # ISO fallback
    try:
        return datetime.fromisoformat(str(date_str))
    except (ValueError, TypeError):
        return None


def _normalize_sender(raw: str) -> str:
    """Normalize sender number to 09xxxxxxxxx format."""
    phone = str(raw or "").strip()
    phone = re.sub(r"[\s\-\(\)]+", "", phone)

    if phone.startswith("+98"):
        phone = "0" + phone[3:]
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]
    elif phone.startswith("9") and len(phone) == 10:
        phone = "0" + phone

    return phone


def fetch_melipayamak_inbox(
    provider,
    *,
    count: int = 100,
    index: int = 0,
) -> list[dict]:
    """
    Fetch received messages from MeliPayamak inbox.

    Args:
        provider: PlatformSMSProviderSetting instance
        count: Number of messages to fetch (max 100)
        index: Start index for pagination

    Returns:
        List of normalized message dicts:
        [
            {
                "provider_message_id": "123456",
                "from_number": "09171234567",
                "to_number": "50001234",
                "text": "4",
                "received_at": datetime,
                "raw": {...}
            }
        ]

    Raises:
        InboxFetchError on API or validation errors.
    """
    username, password = _extract_credentials(provider)

    if not username:
        raise InboxFetchError("نام کاربری ملی پیامک تنظیم نشده است.")
    if not password:
        raise InboxFetchError("APIKey/Password ملی پیامک تنظیم نشده است.")

    payload = {
        "username": username,
        "password": password,
        "location": 1,  # 1 = inbox (received)
        "index": index,
        "count": min(count, 100),
    }

    logger.info("MeliPayamak inbox fetch: index=%d, count=%d", index, count)

    try:
        response = requests.post(
            MELIPAYAMAK_RECEIVE_ENDPOINT,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error("MeliPayamak inbox HTTP error: %s", exc)
        raise InboxFetchError(f"خطای ارتباط با ملی پیامک: {exc}")

    if response.status_code != 200:
        logger.error("MeliPayamak inbox HTTP %s: %s", response.status_code, response.text)
        raise InboxFetchError(f"HTTP {response.status_code}: {response.text}")

    try:
        data = response.json()
    except Exception:
        raise InboxFetchError(f"پاسخ نامعتبر از ملی پیامک: {response.text[:200]}")

    # MeliPayamak GetMessages wraps status in "MyBase" and messages in "Data":
    # {"MyBase": {"RetStatus": 1, "StrRetStatus": "Ok"}, "Data": [...]}
    # Some endpoints return flat: {"RetStatus": 1, "Messages": [...]}
    # Handle both structures.
    my_base = data.get("MyBase") or {}
    ret_status = my_base.get("RetStatus") if my_base else data.get("RetStatus")
    str_ret_status = my_base.get("StrRetStatus") if my_base else data.get("StrRetStatus")

    if ret_status != 1 and str(str_ret_status or "").lower() != "ok":
        raise InboxFetchError(
            f"خطای ملی پیامک: RetStatus={ret_status}, "
            f"StrRetStatus={str_ret_status}"
        )

    # Messages may be in "Data" (MyBase structure) or "Messages" (flat)
    messages_raw = data.get("Data") or data.get("Messages") or []
    if not isinstance(messages_raw, list):
        return []

    results = []
    for msg in messages_raw:
        msg_id = str(msg.get("MsgID") or msg.get("MessageId") or "")
        body = str(msg.get("Body") or msg.get("MessageBody") or "")
        sender = _normalize_sender(
            msg.get("SenderNumber") or msg.get("Sender") or ""
        )
        recipient = str(
            msg.get("RecipientNumber") or msg.get("Recipient") or ""
        ).strip()
        send_date = _parse_melipayamak_date(
            msg.get("SendDate") or msg.get("ReceiveDate") or ""
        )

        results.append({
            "provider_message_id": msg_id,
            "from_number": sender,
            "to_number": recipient,
            "text": body,
            "received_at": send_date or timezone.now(),
            "raw": msg,
        })

    logger.info("MeliPayamak inbox fetched %d messages", len(results))
    return results
