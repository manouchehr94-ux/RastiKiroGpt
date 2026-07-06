"""
Sprint 6 — Financial Reconciliation Engine Tests.

Exercises FinancialReconciliationService (apps/payouts/services_reconciliation.py)
against real, already-persisted financial records produced by the existing
Sprint 1-5 payment/invoice/escrow/settlement/refund flows — mirroring the
exact fixture conventions already used in test_sprint4_settlement_execution.py
and test_sprint5_refund_execution.py.

Scope: read-only detection only. No test in this file asserts that the
service mutates anything — several tests explicitly assert the opposite
(no database writes occur as a result of calling reconcile_company()).
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.services import PaymentCallbackService
from apps.payouts.models import (
    AdjustmentDocument,
    CompanyPlatformFeeEntry,
    EscrowRecord,
    FinancialBackfillTask,
    PaymentSplitSnapshot,
    SettlementItem,
    TechnicianLedgerEntry,
)
from apps.payouts.services_adjustment import AdjustmentDocumentService
from apps.payouts.services_escrow import EscrowRecordService
from apps.payouts.services_reconciliation import (
    FinancialReconciliationService,
    IssueCode,
    ReconciliationReport,
    ReconciliationSeverity,
)
from apps.payouts.services_settlement_batch import SettlementBatchService
from apps.tenants.models import Company, CompanyFinancialPolicy

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _company(**overrides) -> Company:
    tag = _n()
    defaults = {
        "name": f"Reconciliation Test Co {tag}",
        "code": f"recon{tag}",
        "slug": f"recon-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _technician(company, service_pct=60, goods_pct=10, travel_pct=100) -> Technician:
    user = CompanyUser.objects.create_user(
        username=f"recontech{_n()}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=Decimal(str(service_pct)),
        goods_wage_percent=Decimal(str(goods_pct)),
        travel_wage_percent=Decimal(str(travel_pct)),
    )


def _order(company, technician=None) -> Order:
    return Order.objects.create(
        company=company,
        title=f"Reconciliation Test Order {_n()}",
        status=Order.Status.DONE,
        technician=technician,
    )


def _financial_policy(company, fee_percent=1) -> CompanyFinancialPolicy:
    policy, _ = CompanyFinancialPolicy.objects.get_or_create(
        company=company,
        defaults={
            "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
            "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
            "platform_fee_percent": Decimal(str(fee_percent)),
        },
    )
    policy.platform_fee_percent = Decimal(str(fee_percent))
    policy.save(update_fields=["platform_fee_percent"])
    return policy


def _issued_invoice(company, technician=None, total=10_000_000) -> Invoice:
    order = _order(company, technician=technician)
    invoice = Invoice.objects.create(
        company=company,
        order=order,
        invoice_number=f"INV-{company.code.upper()}-{Invoice.objects.count() + 1:05d}",
        status=Invoice.Status.ISSUED,
        issued_at=timezone.now(),
        subtotal=total,
        total_amount=total,
        net_amount_before_invoice_discounts=total,
        gross_amount=total,
        technician_service_wage_percent_snapshot=(
            Decimal(str(technician.service_wage_percent)) if technician else Decimal("0")
        ),
        technician_goods_wage_percent_snapshot=(
            Decimal(str(technician.goods_wage_percent)) if technician else Decimal("0")
        ),
        technician_travel_wage_percent_snapshot=(
            Decimal(str(technician.travel_wage_percent)) if technician else Decimal("0")
        ),
    )
    InvoiceItem.objects.create(
        company=company,
        invoice=invoice,
        description="خدمات تست",
        row_type=InvoiceItem.RowType.SERVICE,
        quantity=1,
        unit_price=total,
        total_price=total,
    )
    return invoice


def _platform_gateway(company) -> PaymentGateway:
    gateway, _created = PaymentGateway.objects.get_or_create(
        company=company,
        gateway_type=PaymentGateway.GatewayType.FAKE,
        defaults={
            "name": "Platform Test Gateway",
            "owner_type": PaymentGateway.OwnerType.PLATFORM,
            "is_active": True,
            "is_default": True,
        },
    )
    return gateway


def _pending_payment(company, invoice, gateway, reference_id) -> Payment:
    return Payment.objects.create(
        company=company,
        invoice=invoice,
        gateway=gateway,
        amount=invoice.total_amount,
        status=Payment.Status.PENDING,
        reference_id=reference_id,
    )


def _distributed_invoice(company, technician, *, total=10_000_000, fee_percent=1):
    """
    Build a fully real, DISTRIBUTED-escrow, PAID invoice by driving it
    through the actual production callback flow (PaymentCallbackService),
    never by hand-crafting an EscrowRecord row directly.
    """
    _financial_policy(company, fee_percent=fee_percent)
    gateway = _platform_gateway(company)
    invoice = _issued_invoice(company, technician=technician, total=total)
    payment = _pending_payment(company, invoice, gateway, f"SUCCESS-recon-{_n()}")
    success, _, _ = PaymentCallbackService.handle_callback(
        company=company, reference_id=payment.reference_id,
    )
    assert success, "setup failed: payment callback did not succeed"
    invoice.refresh_from_db()
    return invoice, payment


def _approved_full_refund(company, invoice, amount_rial=None):
    document = AdjustmentDocumentService.create_draft(
        company=company,
        original_invoice=invoice,
        document_type=AdjustmentDocument.DocumentType.FULL_REFUND,
        amount_rial=amount_rial or int(invoice.total_amount),
        reason="Customer requested full refund (test)",
    )
    document = AdjustmentDocumentService.submit_for_approval(document)
    document = AdjustmentDocumentService.approve(document, approved_by=None)
    return document


# =============================================================================
# 1. Payment <-> Invoice
# =============================================================================

class PaymentInvoiceConsistencyTest(TestCase):

    def test_paid_invoice_without_paid_payment_is_detected(self):
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech)
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at"])

        issues = FinancialReconciliationService.check_payment_invoice_consistency(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.INVOICE_PAID_WITHOUT_PAYMENT.value, codes)
        matching = [
            i for i in issues if i.code == IssueCode.INVOICE_PAID_WITHOUT_PAYMENT.value
        ]
        self.assertEqual(matching[0].object_id, invoice.id)
        self.assertEqual(matching[0].severity, ReconciliationSeverity.ERROR)
        self.assertEqual(matching[0].code_name, "INVOICE_PAID_WITHOUT_PAYMENT")
        # Stable code contract: must always be the literal "FIN-0001", never
        # a language-dependent string, and never renumbered.
        self.assertEqual(matching[0].code, "FIN-0001")

    def test_clean_paid_invoice_produces_no_issue(self):
        company = _company()
        tech = _technician(company)
        invoice, _payment = _distributed_invoice(company, tech)

        issues = FinancialReconciliationService.check_payment_invoice_consistency(company)

        self.assertEqual(issues, [])

    def test_duplicate_paid_payment_is_detected(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        gateway = _platform_gateway(company)

        # Hand-construct a second PAID payment for the same invoice — a
        # broken state that cannot occur via the real callback flow, so it
        # must be created directly to exercise this detection path.
        Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=gateway,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
            reference_id=f"SUCCESS-recon-dup-{_n()}",
            paid_at=timezone.now(),
        )

        issues = FinancialReconciliationService.check_payment_invoice_consistency(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.DUPLICATE_PAID_PAYMENT.value, codes)
        self.assertIn("FIN-0002", codes)

    def test_payment_amount_mismatch_is_detected(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech, total=10_000_000)

        # Corrupt the payment amount directly (bypassing any service) to
        # simulate a data inconsistency.
        Payment.objects.filter(pk=payment.pk).update(amount=9_000_000)

        issues = FinancialReconciliationService.check_payment_invoice_consistency(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.PAYMENT_INVOICE_AMOUNT_MISMATCH.value, codes)
        matching = [
            i for i in issues if i.code == IssueCode.PAYMENT_INVOICE_AMOUNT_MISMATCH.value
        ]
        self.assertEqual(matching[0].object_id, payment.id)


# =============================================================================
# 2. Invoice <-> EscrowRecord
# =============================================================================

class InvoiceEscrowConsistencyTest(TestCase):

    def test_clean_distributed_invoice_produces_no_issue(self):
        company = _company()
        tech = _technician(company)
        invoice, _payment = _distributed_invoice(company, tech)

        issues = FinancialReconciliationService.check_invoice_escrow_consistency(company)

        self.assertEqual(issues, [])

    def test_paid_invoice_without_escrow_is_detected(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)

        # Remove the escrow record to simulate a missing-escrow inconsistency
        # (e.g. a write that failed silently in some hypothetical past bug).
        EscrowRecord.objects.filter(payment=payment).delete()

        issues = FinancialReconciliationService.check_invoice_escrow_consistency(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.INVOICE_PAID_WITHOUT_ESCROW.value, codes)
        matching = [
            i for i in issues if i.code == IssueCode.INVOICE_PAID_WITHOUT_ESCROW.value
        ]
        self.assertEqual(matching[0].object_id, invoice.id)
        self.assertEqual(matching[0].severity, ReconciliationSeverity.ERROR)

    def test_cash_paid_invoice_with_no_escrow_is_not_flagged(self):
        """Cash/company-gateway invoices never get escrow — must not be a false positive."""
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech)
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        invoice.settled_payment_method = "cash"
        invoice.save(update_fields=["status", "paid_at", "settled_payment_method"])
        # No Payment row at all for this invoice (pure cash/manual close).

        issues = FinancialReconciliationService.check_invoice_escrow_consistency(company)

        self.assertEqual(issues, [])


# =============================================================================
# 3. EscrowRecord <-> SettlementBatch / SettlementItem
# =============================================================================

class EscrowSettlementConsistencyTest(TestCase):

    def test_distributed_escrow_without_settlement_item_is_detected(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)

        issues = FinancialReconciliationService.check_escrow_settlement_consistency(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.ESCROW_DISTRIBUTED_WITHOUT_SETTLEMENT_ITEM.value, codes)
        matching = [
            i for i in issues
            if i.code == IssueCode.ESCROW_DISTRIBUTED_WITHOUT_SETTLEMENT_ITEM.value
        ]
        self.assertEqual(matching[0].severity, ReconciliationSeverity.WARNING)

    def test_pending_settlement_without_batch_link_is_error(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        escrow = EscrowRecord.objects.get(payment=payment)

        # Force PENDING_SETTLEMENT status without a real batch link, bypassing
        # the service (which would normally require mark_pending_settlement()).
        EscrowRecord.objects.filter(pk=escrow.pk).update(
            status=EscrowRecord.Status.PENDING_SETTLEMENT,
        )

        issues = FinancialReconciliationService.check_escrow_settlement_consistency(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.ESCROW_SETTLEMENT_LINK_MISSING.value, codes)
        matching = [
            i for i in issues if i.code == IssueCode.ESCROW_SETTLEMENT_LINK_MISSING.value
        ]
        self.assertEqual(matching[0].severity, ReconciliationSeverity.ERROR)

    def test_settled_with_batch_but_no_item_is_error(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        escrow = EscrowRecord.objects.get(payment=payment)

        batch = SettlementBatchService.create_batch(
            company=company,
            level="platform_to_org",
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        batch = SettlementBatchService.mark_ready(batch)
        escrow = EscrowRecordService.mark_pending_settlement(escrow, batch)
        EscrowRecordService.mark_settled(escrow)
        # Deliberately never create a SettlementItem for this invoice.

        issues = FinancialReconciliationService.check_escrow_settlement_consistency(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.ESCROW_SETTLEMENT_ITEM_MISSING.value, codes)

    def test_settled_with_batch_and_item_produces_no_issue(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        escrow = EscrowRecord.objects.get(payment=payment)

        batch = SettlementBatchService.create_batch(
            company=company,
            level="platform_to_org",
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        batch = SettlementBatchService.mark_ready(batch)
        escrow = EscrowRecordService.mark_pending_settlement(escrow, batch)
        EscrowRecordService.mark_settled(escrow)
        SettlementItem.objects.create(
            company=company,
            batch=batch,
            invoice=invoice,
            amount_rial=int(invoice.total_amount),
        )

        issues = FinancialReconciliationService.check_escrow_settlement_consistency(company)

        self.assertEqual(issues, [])


# =============================================================================
# 4. SettlementItem source integrity
# =============================================================================

class SettlementItemIntegrityTest(TestCase):

    def test_settlement_item_without_valid_invoice_is_detected(self):
        company = _company()
        batch = SettlementBatchService.create_batch(
            company=company,
            level="platform_to_org",
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        # All three source FKs left NULL — the only structurally detectable
        # "orphan" state given on_delete=SET_NULL on every one of them.
        item = SettlementItem.objects.create(
            company=company,
            batch=batch,
            amount_rial=1_000_000,
        )

        issues = FinancialReconciliationService.check_settlement_item_integrity(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.SETTLEMENT_ITEM_ORPHAN_SOURCE.value, codes)
        matching = [
            i for i in issues if i.code == IssueCode.SETTLEMENT_ITEM_ORPHAN_SOURCE.value
        ]
        self.assertEqual(matching[0].object_id, item.id)

    def test_settlement_item_with_invoice_produces_no_issue(self):
        company = _company()
        tech = _technician(company)
        invoice, _payment = _distributed_invoice(company, tech)
        batch = SettlementBatchService.create_batch(
            company=company,
            level="platform_to_org",
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        SettlementItem.objects.create(
            company=company, batch=batch, invoice=invoice, amount_rial=1_000_000,
        )

        issues = FinancialReconciliationService.check_settlement_item_integrity(company)

        self.assertEqual(issues, [])


# =============================================================================
# 5. TechnicianLedgerEntry balance integrity
# =============================================================================

class TechnicianLedgerBalanceTest(TestCase):

    def test_correct_balances_produce_no_issue(self):
        company = _company()
        tech = _technician(company)
        _distributed_invoice(company, tech)

        issues = FinancialReconciliationService.check_technician_ledger_balances(company)

        self.assertEqual(issues, [])

    def test_technician_ledger_balance_mismatch_is_detected(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)

        # TechnicianLedgerEntry.save() blocks amount_rial/balance_after
        # changes post-creation via its own PermissionError guard — the
        # mismatch must therefore be introduced via a bulk .update(), which
        # bypasses save() entirely, exactly like a hypothetical historical
        # data-migration bug would.
        entry = TechnicianLedgerEntry.objects.filter(
            company=company, technician=tech,
        ).order_by("id").first()
        TechnicianLedgerEntry.objects.filter(pk=entry.pk).update(balance_after=999_999)

        issues = FinancialReconciliationService.check_technician_ledger_balances(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.TECHNICIAN_LEDGER_BALANCE_MISMATCH.value, codes)
        matching = [
            i for i in issues
            if i.code == IssueCode.TECHNICIAN_LEDGER_BALANCE_MISMATCH.value
        ]
        self.assertEqual(matching[0].object_id, entry.id)
        self.assertEqual(matching[0].severity, ReconciliationSeverity.ERROR)


# =============================================================================
# 6. CompanyPlatformFeeEntry balance integrity
# =============================================================================

class PlatformFeeBalanceTest(TestCase):

    def test_correct_balances_produce_no_issue(self):
        company = _company()
        tech = _technician(company)
        _distributed_invoice(company, tech, fee_percent=1)

        issues = FinancialReconciliationService.check_platform_fee_balances(company)

        self.assertEqual(issues, [])

    def test_platform_fee_balance_mismatch_is_detected(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech, fee_percent=1)

        entry = CompanyPlatformFeeEntry.objects.filter(company=company).order_by("id").first()
        self.assertIsNotNone(entry, "setup failed: no platform fee entry was recorded")
        CompanyPlatformFeeEntry.objects.filter(pk=entry.pk).update(balance_after=1)

        issues = FinancialReconciliationService.check_platform_fee_balances(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.PLATFORM_FEE_BALANCE_MISMATCH.value, codes)
        matching = [
            i for i in issues if i.code == IssueCode.PLATFORM_FEE_BALANCE_MISMATCH.value
        ]
        self.assertEqual(matching[0].object_id, entry.id)


# =============================================================================
# 7. Orphan FinancialBackfillTask
# =============================================================================

class OrphanBackfillTaskTest(TestCase):

    def test_orphan_backfill_task_is_detected(self):
        company = _company()
        task = FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
            # invoice and payment left NULL deliberately.
        )

        issues = FinancialReconciliationService.check_orphan_backfill_tasks(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.ORPHAN_BACKFILL_TASK.value, codes)
        matching = [
            i for i in issues if i.code == IssueCode.ORPHAN_BACKFILL_TASK.value
        ]
        self.assertEqual(matching[0].object_id, task.id)
        self.assertEqual(matching[0].severity, ReconciliationSeverity.WARNING)

    def test_backfill_task_with_invoice_is_not_flagged(self):
        company = _company()
        tech = _technician(company)
        invoice, _payment = _distributed_invoice(company, tech)
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
            invoice=invoice,
        )

        issues = FinancialReconciliationService.check_orphan_backfill_tasks(company)

        self.assertEqual(issues, [])

    def test_resolved_orphan_task_is_not_flagged(self):
        """RESOLVED/FAILED tasks are no longer actionable — must not be flagged."""
        company = _company()
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE,
            status=FinancialBackfillTask.Status.RESOLVED,
        )

        issues = FinancialReconciliationService.check_orphan_backfill_tasks(company)

        self.assertEqual(issues, [])


# =============================================================================
# 8. Blocked AdjustmentDocument detection
# =============================================================================

class BlockedAdjustmentDocumentTest(TestCase):

    def test_partial_refund_type_is_flagged_blocked(self):
        company = _company()
        tech = _technician(company)
        invoice, _payment = _distributed_invoice(company, tech)
        document = AdjustmentDocumentService.create_draft(
            company=company,
            original_invoice=invoice,
            document_type=AdjustmentDocument.DocumentType.PARTIAL_REFUND,
            amount_rial=1_000_000,
            reason="test partial",
        )
        document = AdjustmentDocumentService.submit_for_approval(document)
        document = AdjustmentDocumentService.approve(document, approved_by=None)

        issues = FinancialReconciliationService.check_blocked_adjustment_documents(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.ADJUSTMENT_BLOCKED_UNSUPPORTED_TYPE.value, codes)
        matching = [
            i for i in issues
            if i.code == IssueCode.ADJUSTMENT_BLOCKED_UNSUPPORTED_TYPE.value
        ]
        self.assertEqual(matching[0].severity, ReconciliationSeverity.BLOCKED)
        self.assertEqual(matching[0].object_id, document.id)

    def test_after_settlement_full_refund_is_flagged_blocked(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        document = _approved_full_refund(company, invoice)

        escrow = EscrowRecord.objects.get(payment=payment)
        batch = SettlementBatchService.create_batch(
            company=company,
            level="platform_to_org",
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now(),
        )
        batch = SettlementBatchService.mark_ready(batch)
        escrow = EscrowRecordService.mark_pending_settlement(escrow, batch)
        EscrowRecordService.mark_settled(escrow)

        issues = FinancialReconciliationService.check_blocked_adjustment_documents(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.ADJUSTMENT_BLOCKED_AFTER_SETTLEMENT.value, codes)

    def test_direct_split_full_refund_is_flagged_blocked(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        document = _approved_full_refund(company, invoice)

        snapshot = PaymentSplitSnapshot.objects.get(payment=payment)
        snapshot.should_split_with_technician = True
        snapshot.save(update_fields=["should_split_with_technician"])

        issues = FinancialReconciliationService.check_blocked_adjustment_documents(company)

        codes = [i.code for i in issues]
        self.assertIn(IssueCode.ADJUSTMENT_BLOCKED_DIRECT_SPLIT.value, codes)

    def test_clean_approved_full_refund_is_not_flagged(self):
        company = _company()
        tech = _technician(company)
        invoice, _payment = _distributed_invoice(company, tech)
        _approved_full_refund(company, invoice)

        issues = FinancialReconciliationService.check_blocked_adjustment_documents(company)

        self.assertEqual(issues, [])


# =============================================================================
# Tenant isolation
# =============================================================================

class TenantIsolationTest(TestCase):

    def test_tenant_isolation(self):
        company_a = _company()
        company_b = _company()
        tech_a = _technician(company_a)
        tech_b = _technician(company_b)
        invoice_a = _issued_invoice(company_a, technician=tech_a)
        invoice_a.status = Invoice.Status.PAID
        invoice_a.paid_at = timezone.now()
        invoice_a.save(update_fields=["status", "paid_at"])
        # company_b invoice is clean (distributed, no issues).
        _distributed_invoice(company_b, tech_b)

        report_a = FinancialReconciliationService.reconcile_company(company_a)
        report_b = FinancialReconciliationService.reconcile_company(company_b)

        self.assertTrue(any(
            i.code == IssueCode.INVOICE_PAID_WITHOUT_PAYMENT.value
            and i.company_id == company_a.id
            for i in report_a.issues
        ))
        # company_b's report must never contain an issue whose company_id
        # belongs to company_a, and must not surface company_a's own
        # missing-payment problem.
        for issue in report_b.issues:
            self.assertEqual(issue.company_id, company_b.id)
        self.assertFalse(any(
            i.code == IssueCode.INVOICE_PAID_WITHOUT_PAYMENT.value
            for i in report_b.issues
        ))


# =============================================================================
# Determinism
# =============================================================================

class DeterminismTest(TestCase):

    def test_deterministic_repeated_reconciliation(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)

        # Introduce several simultaneous issues so ordering is meaningfully
        # exercised, not just a trivially-empty list.
        EscrowRecord.objects.filter(payment=payment).delete()
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE,
            status=FinancialBackfillTask.Status.PENDING,
        )

        report1 = FinancialReconciliationService.reconcile_company(company)
        report2 = FinancialReconciliationService.reconcile_company(company)

        self.assertEqual(len(report1.issues), len(report2.issues))
        self.assertEqual(
            [(i.code, i.model, i.object_id) for i in report1.issues],
            [(i.code, i.model, i.object_id) for i in report2.issues],
        )

    def test_reconcile_company_returns_report_type(self):
        company = _company()
        tech = _technician(company)
        _distributed_invoice(company, tech)

        report = FinancialReconciliationService.reconcile_company(company)

        self.assertIsInstance(report, ReconciliationReport)
        self.assertEqual(report.company_id, company.id)


# =============================================================================
# No database writes
# =============================================================================

class NoDatabaseWriteTest(TestCase):

    def test_no_database_writes_during_reconciliation(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        _approved_full_refund(
            company,
            Invoice.objects.create(
                company=company,
                invoice_number=f"INV-{company.code.upper()}-99999",
                status=Invoice.Status.PAID,
                total_amount=1_000_000,
                subtotal=1_000_000,
                paid_at=timezone.now(),
            ),
        )
        EscrowRecord.objects.filter(payment=payment).delete()
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.TECHNICIAN_LEDGER,
            status=FinancialBackfillTask.Status.PENDING,
        )

        counts_before = {
            "invoice": Invoice.objects.count(),
            "payment": Payment.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "settlement_item": SettlementItem.objects.count(),
            "ledger_entry": TechnicianLedgerEntry.objects.count(),
            "platform_fee_entry": CompanyPlatformFeeEntry.objects.count(),
            "backfill_task": FinancialBackfillTask.objects.count(),
            "adjustment_document": AdjustmentDocument.objects.count(),
        }

        FinancialReconciliationService.reconcile_company(company)

        counts_after = {
            "invoice": Invoice.objects.count(),
            "payment": Payment.objects.count(),
            "escrow": EscrowRecord.objects.count(),
            "settlement_item": SettlementItem.objects.count(),
            "ledger_entry": TechnicianLedgerEntry.objects.count(),
            "platform_fee_entry": CompanyPlatformFeeEntry.objects.count(),
            "backfill_task": FinancialBackfillTask.objects.count(),
            "adjustment_document": AdjustmentDocument.objects.count(),
        }

        self.assertEqual(counts_before, counts_after)

    def test_no_writes_even_when_issues_found(self):
        """Running reconciliation twice back-to-back must not itself create duplicates."""
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).delete()

        FinancialReconciliationService.reconcile_company(company)
        report2 = FinancialReconciliationService.reconcile_company(company)

        # Same single issue reported both times — nothing accumulated.
        matching = [
            i for i in report2.issues
            if i.code == IssueCode.INVOICE_PAID_WITHOUT_ESCROW.value
        ]
        self.assertEqual(len(matching), 1)


# =============================================================================
# Stable, machine-readable, language-independent issue codes (FIN-XXXX)
# =============================================================================

class IssueCodeContractTest(TestCase):
    """
    Every reconciliation issue must carry a stable, language-independent
    machine-readable code (FIN-XXXX). These tests pin down the contract
    itself, independent of any single check's business logic.
    """

    def test_every_issue_has_a_fin_prefixed_code(self):
        company = _company()
        tech = _technician(company)
        invoice, payment = _distributed_invoice(company, tech)
        EscrowRecord.objects.filter(payment=payment).delete()
        FinancialBackfillTask.objects.create(
            company=company,
            task_type=FinancialBackfillTask.TaskType.PLATFORM_FEE,
            status=FinancialBackfillTask.Status.PENDING,
        )

        report = FinancialReconciliationService.reconcile_company(company)

        self.assertTrue(len(report.issues) > 0, "setup failed: expected at least one issue")
        for issue in report.issues:
            self.assertRegex(issue.code, r"^FIN-\d{4}$")
            self.assertTrue(issue.code_name)
            self.assertIsInstance(issue.code_name, str)

    def test_all_issue_codes_are_unique(self):
        """No two distinct issue types may ever share the same FIN-XXXX code."""
        values = [member.value for member in IssueCode]
        self.assertEqual(len(values), len(set(values)))

    def test_specific_codes_are_pinned_forever(self):
        """
        Regression guard: once assigned, a code's value must never change.
        If this test ever needs editing to make it pass again, that itself
        is a violation of the stability contract and must be rejected.
        """
        self.assertEqual(IssueCode.INVOICE_PAID_WITHOUT_PAYMENT.value, "FIN-0001")
        self.assertEqual(IssueCode.DUPLICATE_PAID_PAYMENT.value, "FIN-0002")
        self.assertEqual(IssueCode.PAYMENT_INVOICE_AMOUNT_MISMATCH.value, "FIN-0003")
        self.assertEqual(IssueCode.INVOICE_PAID_WITHOUT_ESCROW.value, "FIN-0004")
        self.assertEqual(
            IssueCode.ESCROW_DISTRIBUTED_WITHOUT_SETTLEMENT_ITEM.value, "FIN-0005",
        )
        self.assertEqual(IssueCode.ESCROW_SETTLEMENT_LINK_MISSING.value, "FIN-0006")
        self.assertEqual(IssueCode.ESCROW_SETTLEMENT_ITEM_MISSING.value, "FIN-0007")
        self.assertEqual(IssueCode.SETTLEMENT_ITEM_ORPHAN_SOURCE.value, "FIN-0008")
        self.assertEqual(
            IssueCode.TECHNICIAN_LEDGER_BALANCE_MISMATCH.value, "FIN-0009",
        )
        self.assertEqual(IssueCode.PLATFORM_FEE_BALANCE_MISMATCH.value, "FIN-0010")
        self.assertEqual(IssueCode.ORPHAN_BACKFILL_TASK.value, "FIN-0011")
        self.assertEqual(
            IssueCode.ADJUSTMENT_BLOCKED_UNSUPPORTED_TYPE.value, "FIN-0012",
        )
        self.assertEqual(
            IssueCode.ADJUSTMENT_BLOCKED_AFTER_SETTLEMENT.value, "FIN-0013",
        )
        self.assertEqual(IssueCode.ADJUSTMENT_BLOCKED_DIRECT_SPLIT.value, "FIN-0014")

    def test_code_is_independent_of_message_language(self):
        """
        The code must remain identical even though `message` is currently
        English free text that may be translated (e.g. to Persian) later
        without any change to `code`.
        """
        company = _company()
        tech = _technician(company)
        invoice = _issued_invoice(company, technician=tech)
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at"])

        issues = FinancialReconciliationService.check_payment_invoice_consistency(company)
        matching = [
            i for i in issues if i.code == IssueCode.INVOICE_PAID_WITHOUT_PAYMENT.value
        ]
        self.assertEqual(len(matching), 1)
        # The code is a plain str value (not a translatable object) — this
        # is what makes it safe to serialize, log, and match on forever.
        self.assertIsInstance(matching[0].code, str)
        self.assertEqual(matching[0].code, "FIN-0001")
