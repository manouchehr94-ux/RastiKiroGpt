"""
Payouts — Financial Service Exception Hierarchy (Sprint 2 — Financial
Foundation Services).

Defines the exception hierarchy used by the Sprint 2 lifecycle services
(EscrowRecordService, SettlementBatchService, SettlementItemService,
AdjustmentDocumentService). All exceptions remain subclasses of
ValueError, preserving the exact runtime behavior already shipped in the
first Sprint 2 commit — no `except ValueError` call site anywhere in the
codebase changes behavior as a result of this hierarchy.

Hierarchy:

    FinancialServiceError (ValueError)
        EscrowServiceError
            EscrowTransitionError
        SettlementServiceError
            SettlementBatchTransitionError
            SettlementItemNotAllowedError
        AdjustmentServiceError
            AdjustmentTransitionError

This module introduces no new behavior: it only organizes existing
exception classes into a shared base so callers may catch broadly
(`except FinancialServiceError`) or narrowly
(`except EscrowTransitionError`) as needed by future Sprint 3+ services.
"""
from __future__ import annotations


class FinancialServiceError(ValueError):
    """
    Base class for every exception raised by a Sprint 2 (or later)
    financial foundation service.

    Subclasses ValueError so existing `except ValueError` handling
    anywhere in the codebase continues to work unchanged.
    """


class EscrowServiceError(FinancialServiceError):
    """Base class for EscrowRecordService-related errors."""


class EscrowTransitionError(EscrowServiceError):
    """Raised when an EscrowRecord state transition is not allowed."""


class SettlementServiceError(FinancialServiceError):
    """Base class for SettlementBatchService / SettlementItemService errors."""


class SettlementBatchTransitionError(SettlementServiceError):
    """Raised when a SettlementBatch state transition is not allowed."""


class SettlementItemNotAllowedError(SettlementServiceError):
    """Raised when adding a SettlementItem to a non-CALCULATING batch."""


class AdjustmentServiceError(FinancialServiceError):
    """Base class for AdjustmentDocumentService-related errors."""


class AdjustmentTransitionError(AdjustmentServiceError):
    """Raised when an AdjustmentDocument state transition is not allowed."""
