"""
SMS Inbox Model.

Lightweight reply-capture system for incoming SMS messages.

Purpose:
- Capture customer replies to outgoing SMS (surveys, complaints, confirmations).
- Match incoming messages to the correct company via recent SMSOutbox records.
- Detect survey ratings (single digit 1-5).

NOT a full messaging/CRM system. No conversations, no reply-from-inbox.
"""
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class SMSInbox(TimeStampedModel):
    """
    Incoming SMS message captured from provider inbox.

    Matching logic:
    - incoming.from_number matched against recent SMSOutbox.phone_number
    - Company assigned from matched outbox record
    - If no match within reply window: unmatched
    - If multiple companies equally valid: ambiguous
    """

    class MatchStatus(models.TextChoices):
        MATCHED = "matched", "تطبیق داده شده"
        UNMATCHED = "unmatched", "بدون تطبیق"
        AMBIGUOUS = "ambiguous", "مبهم (چند شرکت)"

    class ResponseType(models.TextChoices):
        SURVEY_RATING = "survey_rating", "امتیاز نظرسنجی"
        CUSTOMER_MESSAGE = "customer_message", "پیام مشتری"
        UNKNOWN = "unknown", "نامشخص"

    # --- Core message fields ---
    from_number = models.CharField(
        max_length=15,
        db_index=True,
        help_text="شماره فرستنده (مشتری)",
    )
    to_number = models.CharField(
        max_length=20,
        db_index=True,
        help_text="شماره گیرنده (خط ارسال‌کننده/Provider)",
    )
    text = models.TextField(
        help_text="متن پیام دریافت‌شده",
    )
    received_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="زمان دریافت پیام از Provider",
    )

    # --- Company (assigned via matching) ---
    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_inbox_messages",
        db_index=True,
        help_text="شرکتی که این پیام به آن تعلق دارد (از طریق تطبیق با Outbox)",
    )

    # --- Provider info ---
    provider = models.ForeignKey(
        "platform_core.PlatformSMSProviderSetting",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbox_messages",
        help_text="Provider که این پیام از آن دریافت شد",
    )
    provider_message_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="شناسه پیام در سیستم Provider (برای جلوگیری از ثبت تکراری)",
    )

    # --- Matching ---
    matched_outbox = models.ForeignKey(
        "sms.SMSOutbox",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbox_replies",
        help_text="پیام ارسالی اخیر که این پاسخ به آن مرتبط شده",
    )
    match_status = models.CharField(
        max_length=20,
        choices=MatchStatus.choices,
        default=MatchStatus.UNMATCHED,
        db_index=True,
        help_text="وضعیت تطبیق با پیام ارسالی",
    )
    match_reason = models.CharField(
        max_length=300,
        blank=True,
        help_text="توضیح نحوه تطبیق یا دلیل عدم تطبیق",
    )

    # --- Response classification ---
    response_type = models.CharField(
        max_length=20,
        choices=ResponseType.choices,
        default=ResponseType.UNKNOWN,
        db_index=True,
        help_text="نوع پاسخ تشخیص‌داده‌شده",
    )
    rating_value = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="مقدار امتیاز نظرسنجی (1 تا 5)، فقط زمانی پر می‌شود که response_type=survey_rating",
    )

    # --- Raw audit data ---
    raw_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="پیلود خام دریافتی از Provider (برای بررسی و رفع خطا)",
    )

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(
                fields=["from_number", "received_at"],
                name="sms_inbox_from_received_idx",
            ),
            models.Index(
                fields=["company", "received_at"],
                name="sms_inbox_company_received_idx",
            ),
            models.Index(
                fields=["match_status", "received_at"],
                name="sms_inbox_match_status_idx",
            ),
            models.Index(
                fields=["response_type"],
                name="sms_inbox_response_type_idx",
            ),
        ]
        verbose_name = "SMS Inbox"
        verbose_name_plural = "SMS Inbox"

    def __str__(self) -> str:
        company_label = self.company.code if self.company else "no-company"
        return f"SMS from {self.from_number} [{self.match_status}] ({company_label})"

    @property
    def text_preview(self) -> str:
        """Short preview of message text."""
        if len(self.text) <= 80:
            return self.text
        return self.text[:77] + "..."
