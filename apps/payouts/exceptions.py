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

    FinancialError (ValueError)
        EscrowError
            EscrowTransitionError
        SettlementError
            SettlementBatchTransitionError
            SettlementItemNotAllowedError
        AdjustmentError
            AdjustmentTransitionError

This module introduces no new behavior: it only organizes existing
exception classes into a shared base so callers may catch broadly
(`except FinancialError`) or narrowly
(`except EscrowTransitionError`) as needed by future Sprint 3+ services.
"""
from __future__ import annotations


class FinancialError(ValueError):
    """
    Base class for every exception raised by a Sprint 2 (or later)
    financial foundation service.

    Subclasses ValueError so existing `except ValueError` handling
    anywhere in the codebase continues to work unchanged.
    """


class EscrowError(FinancialError):
    """Base class for EscrowRecordService-related errors."""


class EscrowTransitionError(EscrowError):
    """Raised when an EscrowRecord state transition is not allowed."""


class SettlementError(FinancialError):
    """Base class for SettlementBatchService / SettlementItemService errors."""


class SettlementBatchTransitionError(SettlementError):
    """Raised when a SettlementBatch state transition is not allowed."""


class SettlementItemNotAllowedError(SettlementError):
    """Raised when adding a SettlementItem to a non-CALCULATING batch."""


class AdjustmentError(FinancialError):
    """Base class for AdjustmentDocumentService-related errors."""


class AdjustmentTransitionError(AdjustmentError):
    """Raised when an AdjustmentDocument state transition is not allowed."""
