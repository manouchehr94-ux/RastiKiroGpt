"""
SMS Inbox Services.

Lightweight reply-capture system:
- Match incoming SMS to the correct company via recent SMSOutbox records.
- Detect survey ratings (single digit 1-5).
- Deduplicate by provider_message_id.

Matching algorithm:
1. Normalize incoming from_number.
2. Find recent SMSOutbox records where phone_number == from_number
   AND sent_at is within the reply window (default 24 hours).
3. Pick the latest matching outbox record.
4. Assign company from matched_outbox.company.
5. If no match: match_status = "unmatched".
6. If multiple companies equally valid: match_status = "ambiguous".
"""
import logging
import re
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import SMSOutbox
from .models_inbox import SMSInbox

logger = logging.getLogger(__name__)

# Default reply window: incoming SMS must arrive within this time after
# the most recent outgoing SMS to that customer for a match to occur.
DEFAULT_REPLY_WINDOW_HOURS = getattr(settings, "SMS_REPLY_WINDOW_HOURS", 24)

# Phone normalization regex
_IRAN_MOBILE_REGEX = re.compile(r"^09[0-9]{9}$")


# =============================================================================
# PHONE NORMALIZATION
# =============================================================================


def normalize_phone(raw: str) -> str:
    """
    Normalize a phone number to 09xxxxxxxxx format.

    Handles: +989..., 989..., 9..., 09..., numbers with dashes/spaces.
    Returns empty string if input is empty/None.
    """
    if not raw:
        return ""

    phone = str(raw).strip()
    phone = re.sub(r"[\s\-\(\)]+", "", phone)

    # Persian/Arabic digit normalization
    phone = (
        phone
        .replace("\u06f0", "0").replace("\u06f1", "1").replace("\u06f2", "2")
        .replace("\u06f3", "3").replace("\u06f4", "4").replace("\u06f5", "5")
        .replace("\u06f6", "6").replace("\u06f7", "7").replace("\u06f8", "8")
        .replace("\u06f9", "9")
        .replace("\u0660", "0").replace("\u0661", "1").replace("\u0662", "2")
        .replace("\u0663", "3").replace("\u0664", "4").replace("\u0665", "5")
        .replace("\u0666", "6").replace("\u0667", "7").replace("\u0668", "8")
        .replace("\u0669", "9")
    )

    if phone.startswith("+"):
        phone = phone[1:]

    if phone.startswith("0098"):
        phone = "0" + phone[4:]
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]
    elif phone.startswith("9") and len(phone) == 10:
        phone = "0" + phone

    return phone


# =============================================================================
# SURVEY DETECTION
# =============================================================================


def detect_response_type(text: str) -> tuple[str, Optional[int]]:
    """
    Classify incoming SMS text.

    Returns:
        (response_type, rating_value)

    Rules:
    - If text (stripped) is exactly one digit 1-5: survey_rating
    - Otherwise: customer_message
    """
    cleaned = (text or "").strip()

    if cleaned in ("1", "2", "3", "4", "5"):
        return SMSInbox.ResponseType.SURVEY_RATING, int(cleaned)

    # Also accept Persian digits ۱-۵
    persian_map = {"\u06f1": 1, "\u06f2": 2, "\u06f3": 3, "\u06f4": 4, "\u06f5": 5}
    if cleaned in persian_map:
        return SMSInbox.ResponseType.SURVEY_RATING, persian_map[cleaned]

    if cleaned:
        return SMSInbox.ResponseType.CUSTOMER_MESSAGE, None

    return SMSInbox.ResponseType.UNKNOWN, None


# =============================================================================
# MATCHING SERVICE
# =============================================================================


class SMSInboxMatchingService:
    """
    Match an incoming SMS to the correct company via recent SMSOutbox records.

    Algorithm:
    1. Find all SMSOutbox records where:
       - phone_number == normalized from_number
       - status in (sent, delivered)
       - sent_at >= (received_at - reply_window)
    2. Group by company.
    3. If exactly one company: matched -> pick latest outbox record.
    4. If multiple companies: ambiguous.
    5. If none: unmatched.
    """

    @staticmethod
    def match(
        *,
        from_number: str,
        received_at=None,
        reply_window_hours: int = None,
    ) -> dict:
        """
        Find the best matching outbox record for an incoming SMS.

        Args:
            from_number: Normalized customer phone number
            received_at: When the incoming SMS was received (default: now)
            reply_window_hours: Hours to look back (default: SMS_REPLY_WINDOW_HOURS)

        Returns:
            {
                "match_status": "matched" | "unmatched" | "ambiguous",
                "matched_outbox": SMSOutbox | None,
                "company": Company | None,
                "match_reason": str,
            }
        """
        if reply_window_hours is None:
            reply_window_hours = DEFAULT_REPLY_WINDOW_HOURS

        now = received_at or timezone.now()
        window_start = now - timedelta(hours=reply_window_hours)

        # Find recent sent messages to this customer
        recent_outbox = SMSOutbox.objects.filter(
            phone_number=from_number,
            status__in=[SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED],
            sent_at__gte=window_start,
            sent_at__lte=now,
        ).select_related("company").order_by("-sent_at")

        if not recent_outbox.exists():
            return {
                "match_status": SMSInbox.MatchStatus.UNMATCHED,
                "matched_outbox": None,
                "company": None,
                "match_reason": (
                    f"هیچ پیام ارسالی به {from_number} "
                    f"در {reply_window_hours} ساعت اخیر یافت نشد."
                ),
            }

        # Group by company
        companies = set()
        for outbox in recent_outbox[:20]:  # Limit scan
            if outbox.company:
                companies.add(outbox.company_id)

        if len(companies) == 0:
            return {
                "match_status": SMSInbox.MatchStatus.UNMATCHED,
                "matched_outbox": None,
                "company": None,
                "match_reason": "پیام‌های ارسالی بدون شرکت یافت شد.",
            }

        if len(companies) > 1:
            # Ambiguous: multiple companies sent to this number recently
            latest = recent_outbox.first()
            return {
                "match_status": SMSInbox.MatchStatus.AMBIGUOUS,
                "matched_outbox": latest,
                "company": latest.company,
                "match_reason": (
                    f"{len(companies)} شرکت مختلف در بازه زمانی "
                    f"به این شماره پیام ارسال کرده‌اند. "
                    f"آخرین ارسال: شرکت {latest.company.code if latest.company else '?'}"
                ),
            }

        # Exactly one company: matched
        latest = recent_outbox.first()
        return {
            "match_status": SMSInbox.MatchStatus.MATCHED,
            "matched_outbox": latest,
            "company": latest.company,
            "match_reason": (
                f"تطبیق با آخرین پیام ارسالی "
                f"(ID={latest.id}, sent_at={latest.sent_at.isoformat() if latest.sent_at else '?'})"
            ),
        }


# =============================================================================
# INGESTION SERVICE
# =============================================================================


class SMSInboxIngestionService:
    """
    Ingest fetched messages: deduplicate, match, classify, store.
    """

    @staticmethod
    def ingest_message(
        *,
        provider,
        provider_message_id: str,
        from_number: str,
        to_number: str,
        text: str,
        received_at=None,
        raw_response: dict = None,
        reply_window_hours: int = None,
    ) -> Optional[SMSInbox]:
        """
        Ingest a single incoming message.

        Steps:
        1. Deduplicate by provider_message_id
        2. Normalize phone number
        3. Match to company via recent outbox
        4. Classify response type
        5. Store in SMSInbox

        Returns SMSInbox if created, None if duplicate.
        """
        # Deduplication
        if provider_message_id:
            if SMSInbox.objects.filter(provider_message_id=provider_message_id).exists():
                logger.debug("Inbox duplicate skipped: msg_id=%s", provider_message_id)
                return None

        # Normalize
        normalized_from = normalize_phone(from_number)
        if not normalized_from:
            logger.warning("Inbox: invalid from_number=%s, skipping", from_number)
            return None

        # Match
        match_result = SMSInboxMatchingService.match(
            from_number=normalized_from,
            received_at=received_at,
            reply_window_hours=reply_window_hours,
        )

        # Classify
        response_type, rating_value = detect_response_type(text)

        # Store
        inbox_msg = SMSInbox.objects.create(
            from_number=normalized_from,
            to_number=to_number or "",
            text=text or "",
            received_at=received_at or timezone.now(),
            company=match_result["company"],
            provider=provider,
            provider_message_id=provider_message_id or "",
            matched_outbox=match_result["matched_outbox"],
            match_status=match_result["match_status"],
            match_reason=match_result["match_reason"],
            response_type=response_type,
            rating_value=rating_value,
            raw_response=raw_response or {},
        )

        logger.info(
            "Inbox ingested: id=%s, from=%s, match=%s, type=%s, company=%s",
            inbox_msg.id,
            normalized_from,
            match_result["match_status"],
            response_type,
            match_result["company"].code if match_result["company"] else "none",
        )
        return inbox_msg

    @staticmethod
    def ingest_batch(
        *,
        provider,
        messages: list[dict],
        reply_window_hours: int = None,
    ) -> dict:
        """
        Ingest a batch of fetched messages.

        Each message dict should have:
            provider_message_id, from_number, to_number, text, received_at, raw

        Returns:
            {"ingested": int, "duplicates": int, "errors": int,
             "matched": int, "unmatched": int, "ambiguous": int}
        """
        stats = {
            "ingested": 0,
            "duplicates": 0,
            "errors": 0,
            "matched": 0,
            "unmatched": 0,
            "ambiguous": 0,
        }

        for msg in messages:
            try:
                result = SMSInboxIngestionService.ingest_message(
                    provider=provider,
                    provider_message_id=msg.get("provider_message_id", ""),
                    from_number=msg.get("from_number", ""),
                    to_number=msg.get("to_number", ""),
                    text=msg.get("text", ""),
                    received_at=msg.get("received_at"),
                    raw_response=msg.get("raw", {}),
                    reply_window_hours=reply_window_hours,
                )
                if result is None:
                    stats["duplicates"] += 1
                else:
                    stats["ingested"] += 1
                    if result.match_status == SMSInbox.MatchStatus.MATCHED:
                        stats["matched"] += 1
                    elif result.match_status == SMSInbox.MatchStatus.AMBIGUOUS:
                        stats["ambiguous"] += 1
                    else:
                        stats["unmatched"] += 1
            except Exception as exc:
                stats["errors"] += 1
                logger.warning(
                    "Inbox ingest error: msg_id=%s, error=%s",
                    msg.get("provider_message_id"), exc,
                )

        return stats


# =============================================================================
# FETCH ORCHESTRATOR
# =============================================================================


class SMSInboxFetchService:
    """
    Orchestrate fetching inbox messages from all active MeliPayamak providers.

    Called from management command: python manage.py fetch_sms_inbox
    """

    @staticmethod
    def fetch_all(*, count: int = 100, reply_window_hours: int = None) -> dict:
        """
        Fetch incoming messages from all eligible providers and ingest them.

        Returns summary dict.
        """
        from apps.platform_core.models import PlatformSMSProviderSetting
        from apps.sms.providers.melipayamak_inbox import (
            InboxFetchError,
            fetch_melipayamak_inbox,
        )

        providers = PlatformSMSProviderSetting.objects.filter(
            is_active=True,
            provider_type="melipayamak",
        ).order_by("priority", "id")

        results = {
            "providers_checked": 0,
            "total_fetched": 0,
            "total_ingested": 0,
            "total_duplicates": 0,
            "total_errors": 0,
            "total_matched": 0,
            "total_unmatched": 0,
            "total_ambiguous": 0,
            "provider_results": [],
        }

        for provider in providers:
            results["providers_checked"] += 1
            pr = {
                "provider_id": provider.id,
                "provider_name": provider.name,
                "fetched": 0,
                "ingested": 0,
                "error_message": "",
            }

            try:
                messages = fetch_melipayamak_inbox(provider, count=count)
                pr["fetched"] = len(messages)
                results["total_fetched"] += len(messages)
            except InboxFetchError as exc:
                pr["error_message"] = str(exc)
                results["total_errors"] += 1
                logger.error("Inbox fetch failed for %s: %s", provider.name, exc)
                results["provider_results"].append(pr)
                continue

            if not messages:
                results["provider_results"].append(pr)
                continue

            stats = SMSInboxIngestionService.ingest_batch(
                provider=provider,
                messages=messages,
                reply_window_hours=reply_window_hours,
            )

            pr["ingested"] = stats["ingested"]
            results["total_ingested"] += stats["ingested"]
            results["total_duplicates"] += stats["duplicates"]
            results["total_errors"] += stats["errors"]
            results["total_matched"] += stats["matched"]
            results["total_unmatched"] += stats["unmatched"]
            results["total_ambiguous"] += stats["ambiguous"]
            results["provider_results"].append(pr)

        logger.info(
            "Inbox fetch complete: fetched=%d, ingested=%d, matched=%d, unmatched=%d",
            results["total_fetched"],
            results["total_ingested"],
            results["total_matched"],
            results["total_unmatched"],
        )
        return results
