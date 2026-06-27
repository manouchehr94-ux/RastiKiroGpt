"""
TASK-004 — PaymentStartService Payment Mode Guard Tests.

Verifies that online payment is blocked unless CompanyPaymentSettings explicitly
allows it. All three conditions must be satisfied:
  1. payment_mode != disabled
  2. gateway_activation_status == active
  3. is_online_payment_enabled == True

Missing CompanyPaymentSettings row: fallback creates a row with disabled defaults → blocked.
Cash/manual payment: does NOT go through PaymentStartService → unaffected.

Test matrix:
  Blocking:
    1. payment_mode=disabled → ValueError ("disabled")
    2. gateway_activation_status=inactive → ValueError ("not active")
    3. gateway_activation_status=pending_review → ValueError ("not active")
    4. gateway_activation_status=suspended → ValueError ("not active")
    5. is_online_payment_enabled=False (mode+status OK) → ValueError ("not enabled")
    6. missing CompanyPaymentSettings row → fallback disabled → ValueError

  Allowing:
    7. mode=company_gateway, active, enabled=True → returns (Payment, Attempt, url)
    8. mode=platform_gateway, active, enabled=True → returns (Payment, Attempt, url)
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.tenants.models import Company, CompanyFinancialPolicy, CompanyPaymentSettings


class PaymentModeGuardTestMixin:
    """Shared helpers for payment mode guard tests."""

    def create_company(self, code="pm_co", name="Payment Mode Co"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_technician(self, company):
        user = CompanyUser.objects.create_user(
            username=f"tech_{company.code}",
            password="testpass123",
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

    def create_financial_policy(self, company):
        policy, _ = CompanyFinancialPolicy.objects.get_or_create(
            company=company,
            defaults={
                "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
                "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
                "platform_fee_percent": Decimal("1"),
            },
        )
        return policy

    def create_issued_invoice(self, company, total=1000000):
        order = Order.objects.create(
            company=company,
            title="Mode Guard Test Order",
            status=Order.Status.DONE,
        )
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
            technician_service_wage_percent_snapshot=Decimal("0"),
            technician_goods_wage_percent_snapshot=Decimal("0"),
            technician_travel_wage_percent_snapshot=Decimal("0"),
        )
        InvoiceItem.objects.create(
            company=company,
            invoice=invoice,
            description="تست پرداخت آنلاین",
            row_type=InvoiceItem.RowType.SERVICE,
            quantity=1,
            unit_price=total,
            total_price=total,
        )
        return invoice

    def create_payment_settings(
        self,
        company,
        mode=CompanyPaymentSettings.PaymentMode.DISABLED,
        status=CompanyPaymentSettings.ActivationStatus.INACTIVE,
        enabled=False,
    ):
        ps, _ = CompanyPaymentSettings.objects.get_or_create(company=company)
        ps.payment_mode = mode
        ps.gateway_activation_status = status
        ps.is_online_payment_enabled = enabled
        ps.save(update_fields=["payment_mode", "gateway_activation_status", "is_online_payment_enabled"])
        return ps

    def create_active_settings(
        self,
        company,
        mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
    ):
        """Create fully-enabled CompanyPaymentSettings (all three conditions satisfied)."""
        return self.create_payment_settings(
            company,
            mode=mode,
            status=CompanyPaymentSettings.ActivationStatus.ACTIVE,
            enabled=True,
        )

    def create_fake_gateway(self, company, owner_type=PaymentGateway.OwnerType.COMPANY):
        return PaymentGateway.objects.create(
            company=company,
            name=f"Test Gateway ({owner_type})",
            gateway_type=PaymentGateway.GatewayType.FAKE,
            owner_type=owner_type,
            is_active=True,
            is_default=True,
        )

    def create_approved_kyc(self, company):
        from apps.tenants.models import CompanyMerchantProfile
        return CompanyMerchantProfile.objects.create(
            company=company,
            status=CompanyMerchantProfile.Status.APPROVED,
            legal_company_name="شرکت تست پرداخت",
            owner_national_code="1234567890",
            postal_code="1234567890",
            registered_address="تهران",
            company_phone="02112345678",
            owner_full_name="تست تستی",
            owner_mobile="09121234567",
            bank_name="ملت",
            account_holder_name="تست تستی",
            shaba_number="IR123456789012345678901234",
            national_card_image="test_file.jpg",
        )


# =============================================================================
# BLOCKING TESTS — payment mode guard rejects payment start
# =============================================================================

class PaymentModeDisabledBlockTest(TestCase, PaymentModeGuardTestMixin):
    """payment_mode=disabled must block PaymentStartService regardless of other state."""

    def setUp(self):
        from apps.payments.services import PaymentStartService
        self.PaymentStartService = PaymentStartService

        self.company = self.create_company("blk_dis", "Block Disabled Co")
        self.create_financial_policy(self.company)
        self.invoice = self.create_issued_invoice(self.company)

    def test_disabled_mode_blocks_payment_start(self):
        """payment_mode=disabled raises ValueError before gateway lookup."""
        self.create_payment_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.DISABLED,
            status=CompanyPaymentSettings.ActivationStatus.ACTIVE,
            enabled=True,
        )

        with self.assertRaises(ValueError) as ctx:
            self.PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
            )
        self.assertIn("disabled", str(ctx.exception).lower())

    def test_disabled_mode_no_payment_record_created(self):
        """Blocked payment start must not create any Payment record."""
        self.create_payment_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.DISABLED,
        )
        count_before = Payment.objects.filter(company=self.company).count()

        with self.assertRaises(ValueError):
            self.PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
            )

        self.assertEqual(
            Payment.objects.filter(company=self.company).count(),
            count_before,
            "Blocked start must not create a Payment record.",
        )


class PaymentActivationStatusBlockTest(TestCase, PaymentModeGuardTestMixin):
    """Non-active gateway_activation_status must block payment start."""

    def setUp(self):
        from apps.payments.services import PaymentStartService
        self.PaymentStartService = PaymentStartService

        self.company = self.create_company("blk_st", "Block Status Co")
        self.create_financial_policy(self.company)
        self.invoice = self.create_issued_invoice(self.company)

    def test_inactive_status_blocks_payment_start(self):
        """gateway_activation_status=inactive raises ValueError."""
        self.create_payment_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            status=CompanyPaymentSettings.ActivationStatus.INACTIVE,
        )

        with self.assertRaises(ValueError) as ctx:
            self.PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
            )
        self.assertIn("not active", str(ctx.exception).lower())

    def test_pending_review_status_blocks_payment_start(self):
        """gateway_activation_status=pending_review raises ValueError."""
        self.create_payment_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            status=CompanyPaymentSettings.ActivationStatus.PENDING_REVIEW,
        )

        with self.assertRaises(ValueError) as ctx:
            self.PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
            )
        self.assertIn("not active", str(ctx.exception).lower())

    def test_suspended_status_blocks_payment_start(self):
        """gateway_activation_status=suspended raises ValueError."""
        self.create_payment_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            status=CompanyPaymentSettings.ActivationStatus.SUSPENDED,
        )

        with self.assertRaises(ValueError) as ctx:
            self.PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
            )
        self.assertIn("not active", str(ctx.exception).lower())


class PaymentEnabledFlagBlockTest(TestCase, PaymentModeGuardTestMixin):
    """is_online_payment_enabled=False must block even when mode and status are OK."""

    def setUp(self):
        from apps.payments.services import PaymentStartService
        self.PaymentStartService = PaymentStartService

        self.company = self.create_company("blk_fl", "Block Flag Co")
        self.create_financial_policy(self.company)
        self.invoice = self.create_issued_invoice(self.company)

    def test_is_online_payment_enabled_false_blocks_payment_start(self):
        """Defense-in-depth: inconsistent is_online_payment_enabled=False blocks payment.

        The CompanyPaymentSettings.save() hook keeps is_online_payment_enabled in sync
        with payment_mode + gateway_activation_status, so this inconsistent state cannot
        arise via normal save(). We force it via QuerySet.update() to verify the
        PaymentStartService check acts as a defense-in-depth guard.
        """
        ps = self.create_payment_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            status=CompanyPaymentSettings.ActivationStatus.ACTIVE,
            enabled=False,
        )
        # save() sync sets is_online_payment_enabled=True; bypass it to inject
        # the inconsistent state and verify PaymentStartService catches it.
        CompanyPaymentSettings.objects.filter(pk=ps.pk).update(is_online_payment_enabled=False)

        with self.assertRaises(ValueError) as ctx:
            self.PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
            )
        self.assertIn("not enabled", str(ctx.exception).lower())


class MissingSettingsBlockTest(TestCase, PaymentModeGuardTestMixin):
    """Missing CompanyPaymentSettings row falls back to disabled defaults — payment blocked."""

    def setUp(self):
        from apps.payments.services import PaymentStartService
        self.PaymentStartService = PaymentStartService

        self.company = self.create_company("blk_ms", "Block Missing Settings Co")
        self.create_financial_policy(self.company)
        self.invoice = self.create_issued_invoice(self.company)

    def test_missing_settings_row_is_safely_handled(self):
        """
        Company without CompanyPaymentSettings row: fallback returns disabled defaults.
        PaymentStartService must raise ValueError (disabled) — not an unhandled exception.

        Note: get_company_payment_settings uses get_or_create, but since start() is wrapped
        in @transaction.atomic, the ValueError causes a rollback — the created row does not
        persist. The important guarantee is that no crash occurs and the guard message is correct.
        """
        self.assertFalse(
            CompanyPaymentSettings.objects.filter(company=self.company).exists(),
            "Precondition: no settings row for this company.",
        )

        with self.assertRaises(ValueError) as ctx:
            self.PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
            )

        # Must raise the mode guard error (disabled), not a DoesNotExist or other crash
        self.assertIn("disabled", str(ctx.exception).lower())

        # No Payment record must have been created (transaction rolled back)
        self.assertEqual(
            Payment.objects.filter(company=self.company).count(),
            0,
            "Blocked start must not persist any Payment record.",
        )


# =============================================================================
# ALLOW TESTS — payment mode guard passes, full start flow succeeds
# =============================================================================

class PaymentModeAllowTest(TestCase, PaymentModeGuardTestMixin):
    """
    Companies with fully-enabled CompanyPaymentSettings can start online payment.

    Tests both company_gateway and platform_gateway modes.
    Requires: active settings + valid FAKE gateway + approved KYC.
    """

    def setUp(self):
        from apps.payments.services import PaymentStartService
        self.PaymentStartService = PaymentStartService

        self.company = self.create_company("alw_co", "Allow Payment Co")
        self.create_financial_policy(self.company)
        self.create_approved_kyc(self.company)

    def test_company_gateway_active_allows_payment_start(self):
        """mode=company_gateway + active + enabled=True → Payment, Attempt, redirect_url."""
        self.create_active_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
        )
        gateway = self.create_fake_gateway(
            self.company, owner_type=PaymentGateway.OwnerType.COMPANY
        )
        invoice = self.create_issued_invoice(self.company)

        payment, attempt, redirect_url = self.PaymentStartService.start(
            invoice=invoice,
            callback_url="https://example.com/callback/",
            gateway=gateway,
        )

        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertIsNotNone(attempt)
        self.assertTrue(redirect_url.startswith("https://"))

    def test_platform_gateway_active_allows_payment_start(self):
        """mode=platform_gateway + active + enabled=True → Payment, Attempt, redirect_url."""
        self.create_active_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.PLATFORM_GATEWAY,
        )
        gateway = self.create_fake_gateway(
            self.company, owner_type=PaymentGateway.OwnerType.PLATFORM
        )
        invoice = self.create_issued_invoice(self.company)

        payment, attempt, redirect_url = self.PaymentStartService.start(
            invoice=invoice,
            callback_url="https://example.com/callback/",
            gateway=gateway,
        )

        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertIsNotNone(attempt)
        self.assertTrue(redirect_url.startswith("https://"))

    def test_guard_does_not_block_company_with_all_conditions_met(self):
        """Guard condition check: all three must be True together to allow."""
        self.create_payment_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.COMPANY_GATEWAY,
            status=CompanyPaymentSettings.ActivationStatus.ACTIVE,
            enabled=True,
        )
        gateway = self.create_fake_gateway(self.company)
        invoice = self.create_issued_invoice(self.company)

        # Must not raise a payment mode guard ValueError
        try:
            payment, attempt, redirect_url = self.PaymentStartService.start(
                invoice=invoice,
                callback_url="https://example.com/callback/",
                gateway=gateway,
            )
        except ValueError as exc:
            guard_messages = ("disabled", "not active", "not enabled")
            if any(m in str(exc).lower() for m in guard_messages):
                self.fail(f"Mode guard raised unexpectedly: {exc}")
            raise  # re-raise if it's a different ValueError (e.g. gateway mismatch)


# =============================================================================
# CASH/MANUAL FLOW REGRESSION — guard must not affect cash payments
# =============================================================================

class CashPaymentUnaffectedTest(TestCase, PaymentModeGuardTestMixin):
    """
    Cash and manual payments do NOT use PaymentStartService → guard must not affect them.

    Regression: TASK-004 guard must be constrained to PaymentStartService only.
    """

    def setUp(self):
        self.company = self.create_company("cash_unaf", "Cash Unaffected Co")
        self.create_financial_policy(self.company)

    def test_cash_payment_unaffected_when_online_payment_disabled(self):
        """mark_paid with cash method succeeds even when CompanyPaymentSettings is disabled."""
        from apps.invoices.services import InvoiceMarkPaidService

        # Company has NO payment settings (disabled by fallback)
        self.assertFalse(
            CompanyPaymentSettings.objects.filter(company=self.company).exists()
        )

        invoice = self.create_issued_invoice(self.company)
        InvoiceMarkPaidService.mark_paid(invoice=invoice, payment_method="cash")

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_manual_payment_unaffected_when_online_payment_disabled(self):
        """mark_paid with manual method succeeds even when CompanyPaymentSettings is disabled."""
        from apps.invoices.services import InvoiceMarkPaidService

        self.create_payment_settings(
            self.company,
            mode=CompanyPaymentSettings.PaymentMode.DISABLED,
        )

        invoice = self.create_issued_invoice(self.company)
        InvoiceMarkPaidService.mark_paid(invoice=invoice, payment_method="manual")

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)


# =============================================================================
# MULTI-TENANT ISOLATION — guard is per-company
# =============================================================================

class MultiTenantGuardIsolationTest(TestCase, PaymentModeGuardTestMixin):
    """
    Guard is company-scoped: Company A's settings must not affect Company B.
    """

    def setUp(self):
        from apps.payments.services import PaymentStartService
        self.PaymentStartService = PaymentStartService

        self.company_a = self.create_company("mti_a", "MTI Company A")
        self.company_b = self.create_company("mti_b", "MTI Company B")

        self.create_financial_policy(self.company_a)
        self.create_financial_policy(self.company_b)

    def test_company_b_blocked_when_company_a_is_active(self):
        """Company B's disabled settings block B even if A is fully active."""
        # Company A: fully enabled
        self.create_active_settings(self.company_a)

        # Company B: disabled
        self.create_payment_settings(
            self.company_b,
            mode=CompanyPaymentSettings.PaymentMode.DISABLED,
        )

        invoice_b = self.create_issued_invoice(self.company_b)

        with self.assertRaises(ValueError) as ctx:
            self.PaymentStartService.start(
                invoice=invoice_b,
                callback_url="https://example.com/callback/",
            )
        self.assertIn("disabled", str(ctx.exception).lower())
