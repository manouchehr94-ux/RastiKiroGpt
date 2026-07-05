"""
Payouts — Settlement Calculator (Sprint 4 — Settlement Engine, Phase B, Step 1).

Deterministic, read-only calculation layer for the two-layer settlement
model (Layer 1 — Platform <-> Organization, Layer 2 — Organization <->
Provider), per the approved Phase A design:
  docs/13_Financial_Core/target_architecture/13_SETTLEMENT_NETTING_ENGINE.md

SCOPE (Step 1 only — strictly calculation, nothing else):
  - Reads Invoice, EscrowRecord, PaymentSplitSnapshot,
    TechnicianLedgerEntry, CompanyPlatformFeeEntry, AdjustmentDocument.
  - NEVER writes to the database. No .save(), .create(), .update(),
    .delete() call exists anywhere in this module.
  - Does NOT create SettlementBatch or SettlementItem rows.
  - Does NOT execute any settlement, bank transfer, or refund.
  - Does NOT select/exclude invoices for batching (that is the future
    Settlement Planner's job, a separate step per the approved Phase A
    roadmap — this module deliberately does not query SettlementBatch /
    SettlementItem for exclusion purposes, to avoid scope creep into
    Planner responsibilities in this step).

CONCURRENCY:
  No lock (select_for_update, advisory lock, etc.) is acquired anywhere
  in this module, and none is required. Every method here only performs
  read-only SELECT queries and returns a computed, immutable dataclass —
  it never observes or depends on a multi-statement read-then-write
  sequence, so there is no race condition for a lock to protect against.
  (Contrast with Sprint 4's future Batch Builder step, which the Phase A
  Concurrency Strategy ADR requires to hold a `select_for_update()` lock
  on `CompanyFinancialPolicy` — that requirement applies to the future
  write path, not to this calculator.) This is also covered by an
  explicit test (`test_no_database_writes_occur_during_calculation`) in
  tests/test_sprint4_settlement_calculator.py.

WHY ALREADY-FROZEN VALUES ARE READ, NOT RECOMPUTED:
  For Layer 1, once an EscrowRecord has reached DISTRIBUTED (or later),
  its platform_commission_rial / organization_share_rial /
  provider_share_rial fields are the authoritative, already-validated
  split (EscrowRecordService.mark_distributed() enforces
  commission + organization + provider == amount_rial at write time).
  This calculator reads those frozen fields directly rather than
  re-deriving them via PlatformFeeService.compute_fee_for_invoice(), to
  guarantee the calculator can never silently drift from the value that
  was actually validated and persisted. If an EscrowRecord has not yet
  reached DISTRIBUTED, Layer 1 settlement for that invoice is reported
  as BLOCKED rather than independently computed — see
  Layer1SettlementResult.position / blocked_reason below.

KNOWN, DELIBERATELY-DISCLOSED ARCHITECTURAL INCONSISTENCY (not fixed
here — Step 1 is calculation-only and must not modify existing files):
  EscrowRecordService.create_for_payment() sets escrow.amount_rial =
  payment.amount unconditionally, even when a PaymentSplitSnapshot shows
  a direct Shaparak gateway split already occurred for the same payment
  (i.e. some of that money never actually reached the platform's
  account). Similarly, reserve_and_distribute_escrow_for_invoice() sets
  provider_share_rial = invoice.settled_technician_wage unconditionally,
  regardless of whether a direct split has already paid the technician
  directly. This calculator surfaces both figures
  (`provider_share_rial` and `direct_provider_split_rial`) honestly and
  separately, without attempting to reconcile or net one against the
  other — inventing a reconciliation policy here would be exactly the
  kind of undocumented business-logic invention this project's
  governance explicitly forbids. This should be raised with the Product
  Owner as a genuine open question, not silently patched.

WHY ADJUSTMENT/REFUND FIGURES ARE INFORMATIONAL ONLY, NEVER NETTED:
  AdjustmentDocument.status == APPLIED does NOT mean a reversal has
  actually been posted to the ledger or escrow — per
  AdjustmentDocumentService.mark_applied()'s own docstring (Sprint 2),
  that method "only transitions APPROVED -> APPLIED and sets applied_at
  ... It does NOT create any TechnicianLedgerEntry or
  CompanyPlatformFeeEntry reversal ... actual reversal execution is
  explicitly deferred to a future RefundExecutionService (blocked on
  [OPEN-ISSUE: OI-07])". Therefore this calculator reports
  `adjustment_rial` / `refund_rial` purely as forward-looking visibility
  into documents that exist but have NOT yet changed any real balance.
  `net_position_rial` is always computed exclusively from already-posted
  ledger/escrow state (never adjusted by these informational fields), so
  that once Sprint 6 actually executes a reversal as a real ledger/escrow
  entry, this calculator does not double-count it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from django.db.models import Sum


def _sum_field(queryset, field: str = "amount_rial") -> int:
    """Sum a field over a queryset, returning 0 (not None) when empty."""
    return int(queryset.aggregate(total=Sum(field))["total"] or 0)


class SettlementPosition(str, Enum):
    """
    Explicit classification of a computed settlement result.

    PAYABLE   — the paying party (Platform for Layer 1, Organization for
                Layer 2) owes the receiving party a positive amount.
    RECEIVABLE — the direction is reversed: the party that would normally
                receive money instead owes the other side (a negative net
                position, represented honestly rather than clamped to
                zero, per Step 1's explicit rule against silently forcing
                negative amounts to zero).
    ZERO      — net position is exactly 0. Not the same as BLOCKED: this
                means the calculation completed and the true answer is
                "nothing owed either way", not "the answer is unknown".
    BLOCKED   — no meaningful settlement amount can be computed yet
                (e.g. the invoice has no EscrowRecord because it was
                never paid through a platform-owned gateway, or the
                EscrowRecord has not yet reached DISTRIBUTED). See
                `blocked_reason` on the result dataclass for why.
    """

    PAYABLE = "payable"
    RECEIVABLE = "receivable"
    ZERO = "zero"
    BLOCKED = "blocked"


def _classify(net_position_rial: int) -> SettlementPosition:
    if net_position_rial > 0:
        return SettlementPosition.PAYABLE
    if net_position_rial < 0:
        return SettlementPosition.RECEIVABLE
    return SettlementPosition.ZERO


@dataclass(frozen=True)
class Layer1SettlementResult:
    """
    Structured, immutable result of a Layer 1 (Platform <-> Organization)
    settlement calculation for exactly one Invoice.

    All *_rial fields are plain `int`, matching the existing codebase's
    convention for money fields (PositiveBigIntegerField / BigIntegerField
    map to Python int; every existing financial service in this codebase
    — PlatformFeeService, TechnicianLedgerService, EscrowRecordService —
    already uses int rial exclusively, never float).
    """

    invoice_id: int
    company_id: int
    position: SettlementPosition
    blocked_reason: Optional[str]

    gross_invoice_amount_rial: int
    platform_commission_rial: int
    provider_share_rial: int
    direct_provider_split_rial: int
    company_payable_base_rial: int
    prior_company_credit_rial: int
    prior_company_debt_rial: int
    adjustment_rial: int
    refund_rial: int
    net_position_rial: int


@dataclass(frozen=True)
class Layer2SettlementResult:
    """
    Structured, immutable result of a Layer 2 (Organization <-> Provider)
    settlement calculation for exactly one Technician within one Company.
    """

    technician_id: int
    company_id: int
    position: SettlementPosition
    blocked_reason: Optional[str]

    wage_credit_rial: int
    settlement_debit_rial: int
    direct_split_debit_rial: int
    other_debit_rial: int
    adjustment_rial: int
    refund_rial: int
    net_position_rial: int


# Document types that represent a refund vs. a non-refund adjustment.
# Used only to split AdjustmentDocument reversal totals into the two
# informational fields requested by Step 1's scope
# ("adjustment/refund placeholders"). Both sets currently correspond to
# documents that can exist in DRAFT..APPLIED state per Sprint 1/2 schema,
# but — per the module docstring above — none has ever had its reversal
# actually executed, so both totals are informational only today.
_REFUND_DOCUMENT_TYPES = frozenset({"full_refund", "partial_refund"})
_ADJUSTMENT_DOCUMENT_TYPES = frozenset({"credit_note", "debit_note", "manual_adjustment"})


class SettlementCalculator:
    """
    Pure, read-only settlement calculation service.

    Every method is a @staticmethod with no side effects. Calling any
    method any number of times with the same input always produces an
    identical result (verified by
    test_deterministic_repeated_calculation in the test suite) — there is
    no hidden mutable state, no caching, no randomness, no wall-clock
    dependency in any formula below.
    """

    # ------------------------------------------------------------------
    # Layer 1 — Platform <-> Organization
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_layer1_for_invoice(invoice) -> Layer1SettlementResult:
        """
        Compute the Layer 1 settlement position for one Invoice.

        Eligibility (BLOCKED cases):
          - No EscrowRecord exists for this invoice at all: the payment
            was never made through a platform-owned gateway (cash,
            manual, card-to-card, or a company-owned gateway). Per R37,
            R38, and the existing EscrowRecordService.is_eligible_for_
            escrow() gate, the Platform never held this invoice's money,
            so there is nothing for the Platform to settle back to the
            Organization.
          - An EscrowRecord exists but has not yet reached DISTRIBUTED
            (still HELD or RESERVED): the authoritative commission /
            organization-share / provider-share split has not yet been
            computed and validated by EscrowRecordService.mark_distributed(),
            so reporting a number here would mean re-deriving it
            independently and risking drift from whatever value that
            method eventually validates and freezes. This calculator
            never recomputes an already-authoritative figure ahead of
            time — it waits and then reads it.

        All company-scoped queries below explicitly filter by
        `company=invoice.company`, even where the ORM relationship alone
        would already guarantee correct scoping, as an explicit,
        redundant tenant-isolation guarantee (defense in depth).
        """
        from .models import EscrowRecord, PaymentSplitSnapshot

        company = invoice.company

        escrow = (
            EscrowRecord.objects.filter(company=company, invoice=invoice)
            .order_by("-held_at")
            .first()
        )

        gross_invoice_amount_rial = int(invoice.total_amount or 0)

        if escrow is None:
            return Layer1SettlementResult(
                invoice_id=invoice.id,
                company_id=company.id,
                position=SettlementPosition.BLOCKED,
                blocked_reason=(
                    "No EscrowRecord exists for this invoice — the payment "
                    "was not made through a platform-owned gateway (cash, "
                    "manual, card-to-card, or company gateway), so the "
                    "Platform never held this invoice's money."
                ),
                gross_invoice_amount_rial=gross_invoice_amount_rial,
                platform_commission_rial=0,
                provider_share_rial=0,
                direct_provider_split_rial=0,
                company_payable_base_rial=0,
                prior_company_credit_rial=0,
                prior_company_debt_rial=0,
                adjustment_rial=0,
                refund_rial=0,
                net_position_rial=0,
            )

        # Direct-split visibility is independent of escrow distribution
        # status (it reflects a decision made at payment-verification
        # time, not at invoice-settlement time), so it is always looked
        # up regardless of whether the block below fires.
        split_snapshot = (
            PaymentSplitSnapshot.objects.filter(company=company, payment=escrow.payment)
            .first()
        )
        direct_provider_split_rial = 0
        if split_snapshot is not None and split_snapshot.should_split_with_technician:
            direct_provider_split_rial = int(split_snapshot.technician_direct_amount or 0)

        not_yet_distributed = {EscrowRecord.Status.HELD, EscrowRecord.Status.RESERVED}
        if escrow.status in not_yet_distributed:
            return Layer1SettlementResult(
                invoice_id=invoice.id,
                company_id=company.id,
                position=SettlementPosition.BLOCKED,
                blocked_reason=(
                    f"EscrowRecord #{escrow.pk} status is '{escrow.status}' — "
                    "Layer 1 settlement requires DISTRIBUTED status or "
                    "later, because the authoritative commission / "
                    "organization-share / provider-share split has not "
                    "yet been computed and validated."
                ),
                gross_invoice_amount_rial=gross_invoice_amount_rial,
                platform_commission_rial=0,
                provider_share_rial=0,
                direct_provider_split_rial=direct_provider_split_rial,
                company_payable_base_rial=0,
                prior_company_credit_rial=0,
                prior_company_debt_rial=0,
                adjustment_rial=0,
                refund_rial=0,
                net_position_rial=0,
            )

        # DISTRIBUTED, PENDING_SETTLEMENT, SETTLED, or CLOSED: the split
        # is authoritative and frozen. Read it directly — never recompute.
        platform_commission_rial = int(escrow.platform_commission_rial or 0)
        provider_share_rial = int(escrow.provider_share_rial or 0)
        company_payable_base_rial = int(escrow.organization_share_rial or 0)

        prior_company_credit_rial = SettlementCalculator._get_prior_company_credit(company)
        prior_company_debt_rial = SettlementCalculator._get_prior_company_debt(company)

        adjustment_rial, refund_rial = SettlementCalculator._get_invoice_reversal_totals(
            company=company, invoice=invoice,
        )

        net_position_rial = (
            company_payable_base_rial
            + prior_company_credit_rial
            - prior_company_debt_rial
        )

        return Layer1SettlementResult(
            invoice_id=invoice.id,
            company_id=company.id,
            position=_classify(net_position_rial),
            blocked_reason=None,
            gross_invoice_amount_rial=gross_invoice_amount_rial,
            platform_commission_rial=platform_commission_rial,
            provider_share_rial=provider_share_rial,
            direct_provider_split_rial=direct_provider_split_rial,
            company_payable_base_rial=company_payable_base_rial,
            prior_company_credit_rial=prior_company_credit_rial,
            prior_company_debt_rial=prior_company_debt_rial,
            adjustment_rial=adjustment_rial,
            refund_rial=refund_rial,
            net_position_rial=net_position_rial,
        )

    # ------------------------------------------------------------------
    # Layer 2 — Organization <-> Provider (Technician)
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_layer2_for_technician(company, technician) -> Layer2SettlementResult:
        """
        Compute the Layer 2 settlement position for one Technician within
        one Company, using the technician's full ledger history.

        Unlike Layer 1, this is never BLOCKED: TechnicianLedgerService's
        running balance (credits minus debits) is always computable,
        including a negative result (technician owes company) — per
        Step 1's explicit rule against forcing negative amounts to zero.

        Raises ValueError if `technician` does not belong to `company` —
        this is a caller/programming error, not a business state, so it
        is not represented as a BLOCKED result.
        """
        from apps.accounts.models import Technician
        from .models import TechnicianLedgerEntry

        if not isinstance(technician, Technician):
            raise ValueError("technician must be a Technician instance.")
        if technician.company_id != company.id:
            raise ValueError(
                f"Technician #{technician.pk} does not belong to company "
                f"#{company.pk} — refusing to compute a cross-tenant "
                "settlement result."
            )

        entries = TechnicianLedgerEntry.objects.filter(company=company, technician=technician)

        # All CREDIT entries. Labeled "wage credit" because, in the
        # current codebase, TechnicianLedgerService.create_invoice_entries()
        # is the only code path that ever creates a CREDIT entry, and it
        # always represents a technician's earned wage on a paid invoice
        # (regardless of the specific Source value it was tagged with —
        # ONLINE_GATEWAY / CASH_FROM_CUSTOMER / MANUAL_PAYMENT — none of
        # which change the economic meaning of "wage earned").
        wage_credit_rial = _sum_field(
            entries.filter(entry_type=TechnicianLedgerEntry.EntryType.CREDIT)
        )

        debits = entries.filter(entry_type=TechnicianLedgerEntry.EntryType.DEBIT)
        settlement_debit_rial = _sum_field(
            debits.filter(source=TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT)
        )
        direct_split_debit_rial = _sum_field(
            debits.filter(source=TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT)
        )
        # Every other debit source (CASH_FROM_CUSTOMER — technician kept
        # cash and now owes the company; ADJUSTMENT; REFUND) that already
        # has real, posted ledger entries. Summed together rather than
        # forced to a 0 placeholder, per Step 1's instruction to read
        # already-present data rather than assume it doesn't exist.
        other_debit_rial = _sum_field(
            debits.exclude(
                source__in=[
                    TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT,
                    TechnicianLedgerEntry.Source.DIRECT_GATEWAY_SETTLEMENT,
                ]
            )
        )

        # net_position_rial intentionally uses the exact same formula as
        # TechnicianLedgerService.get_balance() (credits minus every
        # debit) so the two are always identical (verified by a
        # dedicated regression test) — this is the ground-truth balance,
        # never adjusted by the informational fields below.
        net_position_rial = (
            wage_credit_rial - settlement_debit_rial - direct_split_debit_rial - other_debit_rial
        )

        adjustment_rial, refund_rial = SettlementCalculator._get_technician_reversal_totals(
            company=company, technician=technician,
        )

        return Layer2SettlementResult(
            technician_id=technician.id,
            company_id=company.id,
            position=_classify(net_position_rial),
            blocked_reason=None,
            wage_credit_rial=wage_credit_rial,
            settlement_debit_rial=settlement_debit_rial,
            direct_split_debit_rial=direct_split_debit_rial,
            other_debit_rial=other_debit_rial,
            adjustment_rial=adjustment_rial,
            refund_rial=refund_rial,
            net_position_rial=net_position_rial,
        )

    # ------------------------------------------------------------------
    # Internal helpers — all read-only, all deterministic
    # ------------------------------------------------------------------

    @staticmethod
    def _get_prior_company_credit(company) -> int:
        """
        [OPEN-ISSUE: OI-05 / OI-06] No model exists today that tracks a
        company's carried-forward credit balance across settlement
        periods. Always 0 until such a model is designed and approved.
        Named and documented explicitly (rather than omitted) so wiring
        in a real value later is a one-line change, not a redesign.
        """
        return 0

    @staticmethod
    def _get_prior_company_debt(company) -> int:
        """
        [OPEN-ISSUE: OI-05 / OI-06] Same rationale as
        _get_prior_company_credit — always 0 until a carried-forward
        debt model is designed and approved.
        """
        return 0

    @staticmethod
    def _get_invoice_reversal_totals(*, company, invoice) -> tuple[int, int]:
        """
        Return (adjustment_rial, refund_rial): the sum of
        AdjustmentDocument.company_share_reversal for APPLIED documents
        against this invoice, split by document type. See the module
        docstring's "WHY ADJUSTMENT/REFUND FIGURES ARE INFORMATIONAL
        ONLY" section — these are visibility-only figures, not netted
        into net_position_rial.
        """
        from .models import AdjustmentDocument

        applied = AdjustmentDocument.objects.filter(
            company=company,
            original_invoice=invoice,
            status=AdjustmentDocument.Status.APPLIED,
        )
        refund_rial = _sum_field(
            applied.filter(document_type__in=_REFUND_DOCUMENT_TYPES),
            field="company_share_reversal",
        )
        adjustment_rial = _sum_field(
            applied.filter(document_type__in=_ADJUSTMENT_DOCUMENT_TYPES),
            field="company_share_reversal",
        )
        return adjustment_rial, refund_rial

    @staticmethod
    def _get_technician_reversal_totals(*, company, technician) -> tuple[int, int]:
        """
        Return (adjustment_rial, refund_rial) for a technician, sourced
        from AdjustmentDocument.technician_wage_reversal for APPLIED
        documents linked via technician_ledger_entry. This FK is
        currently never populated by any code path (see module
        docstring), so both values are always 0 today — visibility-only,
        forward-compatible, never netted into net_position_rial.
        """
        from .models import AdjustmentDocument

        applied = AdjustmentDocument.objects.filter(
            company=company,
            status=AdjustmentDocument.Status.APPLIED,
            technician_ledger_entry__technician=technician,
        )
        refund_rial = _sum_field(
            applied.filter(document_type__in=_REFUND_DOCUMENT_TYPES),
            field="technician_wage_reversal",
        )
        adjustment_rial = _sum_field(
            applied.filter(document_type__in=_ADJUSTMENT_DOCUMENT_TYPES),
            field="technician_wage_reversal",
        )
        return adjustment_rial, refund_rial
