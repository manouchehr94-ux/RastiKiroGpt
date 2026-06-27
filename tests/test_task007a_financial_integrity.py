"""
TASK-007A — Financial Data Integrity Tests.

Covers all hardening changes:
  1. Invoice number uniqueness — InvoiceCounter never produces duplicates.
  2. One active invoice per order — DB constraint blocks a second DRAFT/ISSUED.
  3. Ledger immutability — TechnicianLedgerEntry cannot be deleted or have
     amount_rial / balance_after mutated.
  4. CompanyPlatformFeeEntry — same immutability guarantees.
  5. PlatformFeeRecordingFailed — raised instead of silently returning None.
  6. CompanyPaymentSettings.save() — is_online_payment_enabled stays in sync.
  7. recalculate_totals() blocked on PAID invoices.
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem, InvoiceCounter, generate_invoice_number
from apps.invoices.services import InvoiceCreateService, InvoiceIssueService
from apps.orders.models import Order
from apps.payouts.models import CompanyPlatformFeeEntry, TechnicianLedgerEntry
from apps.payouts.services_platform_fee import PlatformFeeRecordingFailed, PlatformFeeService
from apps.tenants.models import Company, CompanyFinancialPolicy, CompanyPaymentSettings

_counter = itertools.count(1)


def _n():
    return next(_counter)


def _company(suffix=None):
    tag = suffix or _n()
    return Company.objects.create(
        name=f"IntegrityTest Co {tag}",
        code=f"int{tag}",
        slug=f"integrity-test-{tag}",
        is_active=True,
    )


def _order(company, status=Order.Status.IN_PROGRESS):
    return Order.objects.create(company=company, title=f"Order {_n()}", status=status)


def _technician(company):
    user = CompanyUser.objects.create_user(
        username=f"tech{_n()}",
        password="pass",
        company=company,
        role=UserRole.TECHNICIAN,
    )
    return Technician.objects.create(
        company=company,
        user=user,
        service_wage_percent=Decimal("60"),
        goods_wage_percent=Decimal("10"),
        travel_wage_percent=Decimal("100"),
    )


def _draft_invoice(company, order=None):
    inv = InvoiceCreateService.create(company=company, order=order, items=[])
    InvoiceItem.objects.create(
        company=company,
        invoice=inv,
        description="Service",
        row_type=InvoiceItem.RowType.SERVICE,
        quantity=1,
        unit_price=100_000,
        discount_amount=0,
        total_price=100_000,
    )
    inv.recalculate_totals(save=True)
    return inv


# =============================================================================
# 1. Invoice number uniqueness
# =============================================================================

class InvoiceCounterTest(TestCase):
    """InvoiceCounter generates sequential, non-duplicate numbers."""

    def test_first_invoice_gets_sequence_1(self):
        company = _company()
        num = generate_invoice_number(company)
        self.assertEqual(num, f"INV-{company.code.upper()}-00001")

    def test_second_invoice_increments(self):
        company = _company()
        n1 = generate_invoice_number(company)
        n2 = generate_invoice_number(company)
        self.assertNotEqual(n1, n2)
        self.assertEqual(n1, f"INV-{company.code.upper()}-00001")
        self.assertEqual(n2, f"INV-{company.code.upper()}-00002")

    def test_counter_is_per_company(self):
        c1 = _company()
        c2 = _company()
        n1 = generate_invoice_number(c1)
        n2 = generate_invoice_number(c2)
        # Both start at 00001 independently
        self.assertEqual(n1, f"INV-{c1.code.upper()}-00001")
        self.assertEqual(n2, f"INV-{c2.code.upper()}-00001")

    def test_no_duplicate_numbers_from_service(self):
        """Creating multiple invoices via InvoiceCreateService yields unique numbers."""
        company = _company()
        numbers = set()
        for _ in range(5):
            inv = InvoiceCreateService.create(company=company, items=[])
            numbers.add(inv.invoice_number)
        self.assertEqual(len(numbers), 5)

    def test_invoice_counter_row_is_created(self):
        company = _company()
        self.assertFalse(InvoiceCounter.objects.filter(company=company).exists())
        generate_invoice_number(company)
        self.assertTrue(InvoiceCounter.objects.filter(company=company).exists())
        self.assertEqual(InvoiceCounter.objects.get(company=company).last_number, 1)


# =============================================================================
# 2. One active invoice per order (DB constraint)
# =============================================================================

class UniqueActiveInvoicePerOrderTest(TestCase):
    """DB constraint blocks a second DRAFT or ISSUED invoice for the same order."""

    def test_two_draft_invoices_for_same_order_raises(self):
        company = _company()
        order = _order(company)
        InvoiceCreateService.create(company=company, order=order, items=[])
        with self.assertRaises((IntegrityError, Exception)):
            with transaction.atomic():
                Invoice.objects.create(
                    company=company,
                    order=order,
                    invoice_number=f"INV-TEST-{_n():05d}",
                    status=Invoice.Status.DRAFT,
                )

    def test_paid_invoice_does_not_block_new_draft(self):
        """A PAID invoice for an order does not block a new DRAFT."""
        company = _company()
        order = _order(company)
        inv = _draft_invoice(company, order)
        # Force to PAID directly (bypass business logic for test simplicity)
        Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.PAID)

        # A new DRAFT must be allowed now
        try:
            new_inv = Invoice.objects.create(
                company=company,
                order=order,
                invoice_number=f"INV-TEST-{_n():05d}",
                status=Invoice.Status.DRAFT,
            )
            self.assertIsNotNone(new_inv.pk)
        except IntegrityError:
            self.fail("Creating a DRAFT invoice after PAID should succeed")

    def test_cancelled_invoice_does_not_block_new_draft(self):
        """A CANCELLED invoice for an order does not block a new DRAFT."""
        company = _company()
        order = _order(company)
        inv = _draft_invoice(company, order)
        Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.CANCELLED)

        try:
            new_inv = Invoice.objects.create(
                company=company,
                order=order,
                invoice_number=f"INV-TEST-{_n():05d}",
                status=Invoice.Status.DRAFT,
            )
            self.assertIsNotNone(new_inv.pk)
        except IntegrityError:
            self.fail("Creating a DRAFT invoice after CANCELLED should succeed")

    def test_standalone_invoices_are_not_constrained(self):
        """Multiple standalone DRAFT invoices (order=None) are allowed."""
        company = _company()
        for _ in range(3):
            inv = Invoice.objects.create(
                company=company,
                order=None,
                invoice_number=f"INV-TEST-{_n():05d}",
                status=Invoice.Status.DRAFT,
            )
            self.assertIsNotNone(inv.pk)


# =============================================================================
# 3. TechnicianLedgerEntry immutability
# =============================================================================

class TechnicianLedgerImmutabilityTest(TestCase):
    """TechnicianLedgerEntry cannot be deleted or have financial fields mutated."""

    def _make_entry(self, company, technician):
        return TechnicianLedgerEntry.objects.create(
            company=company,
            technician=technician,
            entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
            source=TechnicianLedgerEntry.Source.MANUAL_PAYMENT,
            amount_rial=50_000,
            balance_after=50_000,
            idempotency_key=f"test:ledger:{_n()}",
            description="Test entry",
        )

    def test_delete_raises_permission_error(self):
        company = _company()
        tech = _technician(company)
        entry = self._make_entry(company, tech)
        with self.assertRaises(PermissionError):
            entry.delete()

    def test_entry_still_exists_after_delete_attempt(self):
        company = _company()
        tech = _technician(company)
        entry = self._make_entry(company, tech)
        try:
            entry.delete()
        except PermissionError:
            pass
        self.assertTrue(TechnicianLedgerEntry.objects.filter(pk=entry.pk).exists())

    def test_mutating_amount_rial_raises(self):
        company = _company()
        tech = _technician(company)
        entry = self._make_entry(company, tech)
        entry.amount_rial = 999_999
        with self.assertRaises(PermissionError):
            entry.save()

    def test_mutating_balance_after_raises(self):
        company = _company()
        tech = _technician(company)
        entry = self._make_entry(company, tech)
        entry.balance_after = -1
        with self.assertRaises(PermissionError):
            entry.save()

    def test_updating_description_is_allowed(self):
        """Non-financial fields like description may be updated."""
        company = _company()
        tech = _technician(company)
        entry = self._make_entry(company, tech)
        entry.description = "Updated note"
        entry.save(update_fields=["description"])
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Updated note")


# =============================================================================
# 4. CompanyPlatformFeeEntry immutability
# =============================================================================

class PlatformFeeEntryImmutabilityTest(TestCase):
    """CompanyPlatformFeeEntry cannot be deleted or have financial fields mutated."""

    def _make_entry(self, company):
        return CompanyPlatformFeeEntry.objects.create(
            company=company,
            entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
            source=CompanyPlatformFeeEntry.Source.ONLINE_GATEWAY,
            amount_rial=10_000,
            balance_after=10_000,
            platform_fee_percent_snapshot=Decimal("2.00"),
            idempotency_key=f"test:fee:{_n()}",
            description="Test fee entry",
        )

    def test_delete_raises_permission_error(self):
        company = _company()
        entry = self._make_entry(company)
        with self.assertRaises(PermissionError):
            entry.delete()

    def test_entry_still_exists_after_delete_attempt(self):
        company = _company()
        entry = self._make_entry(company)
        try:
            entry.delete()
        except PermissionError:
            pass
        self.assertTrue(CompanyPlatformFeeEntry.objects.filter(pk=entry.pk).exists())

    def test_mutating_amount_rial_raises(self):
        company = _company()
        entry = self._make_entry(company)
        entry.amount_rial = 1
        with self.assertRaises(PermissionError):
            entry.save()

    def test_mutating_balance_after_raises(self):
        company = _company()
        entry = self._make_entry(company)
        entry.balance_after = 0
        with self.assertRaises(PermissionError):
            entry.save()

    def test_updating_description_is_allowed(self):
        company = _company()
        entry = self._make_entry(company)
        entry.description = "Audit note"
        entry.save(update_fields=["description"])
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Audit note")


# =============================================================================
# 5. PlatformFeeRecordingFailed is raised, not swallowed
# =============================================================================

class PlatformFeeRecordingFailedTest(TestCase):
    """record_invoice_fee() raises PlatformFeeRecordingFailed on write error."""

    def _make_invoice_and_payment(self):
        from apps.payments.models import Payment, PaymentGateway
        company = _company()
        CompanyFinancialPolicy.objects.create(
            company=company,
            platform_fee_percent=Decimal("2.00"),
        )
        gateway = PaymentGateway.objects.create(
            company=company,
            name="Platform GW",
            gateway_type=PaymentGateway.GatewayType.FAKE,
            owner_type=PaymentGateway.OwnerType.PLATFORM,
            is_active=True,
            is_default=True,
        )
        order = _order(company)
        inv = _draft_invoice(company, order)
        Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.ISSUED)
        inv.refresh_from_db()
        payment = Payment.objects.create(
            company=company,
            invoice=inv,
            gateway=gateway,
            amount=inv.total_amount,
            status=Payment.Status.PAID,
        )
        return inv, payment

    def test_raises_on_db_failure(self):
        inv, payment = self._make_invoice_and_payment()
        with patch.object(
            PlatformFeeService,
            "_write_entry",
            side_effect=RuntimeError("DB exploded"),
        ):
            with self.assertRaises(PlatformFeeRecordingFailed):
                PlatformFeeService.record_invoice_fee(inv, payment=payment)

    def test_does_not_return_none_on_failure(self):
        """record_invoice_fee must raise, not silently return None."""
        inv, payment = self._make_invoice_and_payment()
        with patch.object(
            PlatformFeeService,
            "_write_entry",
            side_effect=Exception("unexpected"),
        ):
            result = None
            raised = False
            try:
                result = PlatformFeeService.record_invoice_fee(inv, payment=payment)
            except PlatformFeeRecordingFailed:
                raised = True
            self.assertTrue(raised, "PlatformFeeRecordingFailed was not raised")
            self.assertIsNone(result, "Should not have returned a value before raising")

    def test_returns_none_when_conditions_not_met(self):
        """record_invoice_fee returns None (no raise) when conditions are not satisfied."""
        # payment=None → conditions not met, returns None without raising
        company = _company()
        inv = _draft_invoice(company)
        result = PlatformFeeService.record_invoice_fee(inv, payment=None)
        self.assertIsNone(result)


# =============================================================================
# 6. CompanyPaymentSettings.save() syncs is_online_payment_enabled
# =============================================================================

class CompanyPaymentSettingsSyncTest(TestCase):
    """save() always keeps is_online_payment_enabled consistent."""

    def _ps(self, mode, status):
        company = _company()
        ps = CompanyPaymentSettings(
            company=company,
            payment_mode=mode,
            gateway_activation_status=status,
            is_online_payment_enabled=False,  # deliberately wrong — save() corrects it
        )
        ps.save()
        return ps

    def test_disabled_inactive_is_false(self):
        ps = self._ps(
            CompanyPaymentSettings.PaymentMode.DISABLED,
            CompanyPaymentSettings.ActivationStatus.INACTIVE,
        )
        self.assertFalse(ps.is_online_payment_enabled)

    def test_company_gateway_active_is_true(self):
        ps = self._ps(
            CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            CompanyPaymentSettings.ActivationStatus.ACTIVE,
        )
        self.assertTrue(ps.is_online_payment_enabled)

    def test_platform_gateway_active_is_true(self):
        ps = self._ps(
            CompanyPaymentSettings.PaymentMode.PLATFORM_GATEWAY,
            CompanyPaymentSettings.ActivationStatus.ACTIVE,
        )
        self.assertTrue(ps.is_online_payment_enabled)

    def test_disabled_active_is_false(self):
        """DISABLED mode overrides even an ACTIVE status."""
        ps = self._ps(
            CompanyPaymentSettings.PaymentMode.DISABLED,
            CompanyPaymentSettings.ActivationStatus.ACTIVE,
        )
        self.assertFalse(ps.is_online_payment_enabled)

    def test_company_gateway_suspended_is_false(self):
        ps = self._ps(
            CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            CompanyPaymentSettings.ActivationStatus.SUSPENDED,
        )
        self.assertFalse(ps.is_online_payment_enabled)

    def test_save_with_update_fields_still_syncs(self):
        """save(update_fields=[...]) also persists the recomputed boolean."""
        company = _company()
        ps = CompanyPaymentSettings.objects.create(
            company=company,
            payment_mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            gateway_activation_status=CompanyPaymentSettings.ActivationStatus.ACTIVE,
        )
        # Sanity: should be True after create
        ps.refresh_from_db()
        self.assertTrue(ps.is_online_payment_enabled)

        # Update notes only — sync must still persist is_online_payment_enabled
        ps.notes = "note"
        ps.save(update_fields=["notes"])
        ps.refresh_from_db()
        self.assertTrue(ps.is_online_payment_enabled)

    def test_changing_mode_to_disabled_turns_off_enabled(self):
        company = _company()
        ps = CompanyPaymentSettings.objects.create(
            company=company,
            payment_mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            gateway_activation_status=CompanyPaymentSettings.ActivationStatus.ACTIVE,
        )
        ps.refresh_from_db()
        self.assertTrue(ps.is_online_payment_enabled)

        ps.payment_mode = CompanyPaymentSettings.PaymentMode.DISABLED
        ps.save()
        ps.refresh_from_db()
        self.assertFalse(ps.is_online_payment_enabled)


# =============================================================================
# 7. recalculate_totals() blocked on PAID invoices
# =============================================================================

class RecalculateTotalsGuardTest(TestCase):
    """recalculate_totals() raises ValueError on PAID invoices."""

    def test_raises_on_paid_invoice(self):
        company = _company()
        inv = _draft_invoice(company)
        Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.PAID)
        inv.refresh_from_db()
        with self.assertRaises(ValueError, msg="recalculate_totals must raise on PAID invoice"):
            inv.recalculate_totals(save=False)

    def test_allowed_on_draft(self):
        company = _company()
        inv = _draft_invoice(company)
        try:
            inv.recalculate_totals(save=True)
        except ValueError:
            self.fail("recalculate_totals must NOT raise on DRAFT invoice")

    def test_allowed_on_issued(self):
        company = _company()
        inv = _draft_invoice(company)
        Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.ISSUED)
        inv.refresh_from_db()
        try:
            inv.recalculate_totals(save=True)
        except ValueError:
            self.fail("recalculate_totals must NOT raise on ISSUED invoice")
