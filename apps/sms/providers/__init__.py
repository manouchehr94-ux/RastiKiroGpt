"""
SMS - Provider Abstraction.

SMS gateway provider interface, registry, and implementations.
"""
from .base import BaseSMSProvider, SMSSendRequest, SMSSendResponse
from .fake import FakeSMSProvider
from .registry import get_sms_provider
from .melipayamak import (
    MeliPayamakProvider,
    SMSProviderError,
    build_pattern_text,
    send_melipayamak_pattern,
    send_template_pattern_by_owner_route,
)

__all__ = [
    "BaseSMSProvider",
    "SMSSendRequest",
    "SMSSendResponse",
    "FakeSMSProvider",
    "MeliPayamakProvider",
    "get_sms_provider",
    "SMSProviderError",
    "build_pattern_text",
    "send_melipayamak_pattern",
    "send_template_pattern_by_owner_route",
]
