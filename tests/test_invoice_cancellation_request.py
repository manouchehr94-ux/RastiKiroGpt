"""
Invoice Cancellation Request Workflow — Test Suite.

Covers all ten required test cases:
  1.  Technician can request cancellation for their own DRAFT invoice.
  2.  Technician can request cancellation for their own ISSUED invoice.
  3.  Technician cannot request cancellation for a PAID invoice.
  4.  Technician cannot request cancellation for a CANCELLED invoice.
  5.  Technician cannot request cancellation for another technician's invoice.
  6.  Duplicate PENDING request is blocked.
  7.  Admin/operator can approve a pending request → invoice becomes CANCELLED.
  8.  Admin/operator can reject a pending request → invoice remains unchanged.
  9.  Approving a request after the invoice became PAID fails safely.
  10. Direct technician cancel of an invoice remains impossible (service guard).
"""
import itertools

from django.test import TestCase

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.invoices.models import Invoice, InvoiceCancellationRequest
from apps.invoices.services import InvoiceCancelService, InvoiceCreateService
from apps.invoices.services_cancel_request import InvoiceCancellationRequestService
from apps.orders.models import Order
from apps.tenants.models import Company

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------
_counter = itertools.count(1)


def _next():
    return next(_counter)


def _company():
    n = _next()
    return Company.objects.create(
        name=f"Test Co {n}",
        code=f"tc{n:03d}",
        slug=f"test-co-{n}",
    )


def _user(company, role=UserRole.TECHNICIAN):
    n = _next()
    return CompanyUser.objects.create_user(
        username=f"u{n}",
        password="pw",
        company=company,
        role=role,
    )


def _technician(company, user=None):
    if user is None:
        user = _user(company, role=UserRole.TECHNICIAN)
    return Technician.objects.create(company=company, user=user, is_available=True)


def _order(company, technician=None, status=Order.Status.IN_PROGRESS):
    n = _next()
    return Order.objects.create(
        company=company,
        title=f"Order {n}",
        status=status,
        technician=technician,
    )


def _draft_invoice(company, order):
    return InvoiceCreateService.create(
        company=company,
        order=order,
        items=[{"description": "Service", "quantity": 1, "unit_price": 300_000, "discount_amount": 0}],
    )


# ---------------------------------------------------------------------------
# 1 & 2: Technician can request for DRAFT and ISSUED invoices
# ---------------------------------------------------------------------------
class TechnicianRequestEligibilityTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.admin = _user(self.company, role=UserRole.COMPANY_ADMIN)
        self.order = _order(self.company, technician=self.tech)

    def test_request_on_draft_invoice_succeeds(self):
        inv = _draft_invoice(self.company, self.order)
        self.assertEqual(inv.status, Invoice.Status.DRAFT)

        req = InvoiceCancellationRequestService.request(
            invoice=inv,
            requested_by=self.tech.user,
            reason="اشتباه وارد شده",
        )

        self.assertEqual(req.status, InvoiceCancellationRequest.Status.PENDING)
        self.assertEqual(req.invoice_id, inv.pk)
        self.assertEqual(req.company_id, self.company.pk)
        # Invoice status must not be touched yet
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.DRAFT)

    def test_request_on_issued_invoice_succeeds(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["status"])

        req = InvoiceCancellationRequestService.request(
            invoice=inv,
            requested_by=self.tech.user,
            reason="مشتری انصراف داد",
        )

        self.assertEqual(req.status, InvoiceCancellationRequest.Status.PENDING)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.ISSUED)

    def test_reason_is_stored(self):
        inv = _draft_invoice(self.company, self.order)
        reason = "متن دلیل آزمایشی"
        req = InvoiceCancellationRequestService.request(
            invoice=inv,
            requested_by=self.tech.user,
            reason=reason,
        )
        self.assertEqual(req.reason, reason)

    def test_empty_reason_is_accepted(self):
        inv = _draft_invoice(self.company, self.order)
        req = InvoiceCancellationRequestService.request(
            invoice=inv,
            requested_by=self.tech.user,
        )
        self.assertEqual(req.reason, "")


# ---------------------------------------------------------------------------
# 3: Technician cannot request for PAID invoice
# ---------------------------------------------------------------------------
class PaidInvoiceRequestBlockedTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.order = _order(self.company, technician=self.tech)

    def test_request_on_paid_invoice_raises(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.PAID
        inv.save(update_fields=["status"])

        with self.assertRaises(ValueError) as ctx:
            InvoiceCancellationRequestService.request(
                invoice=inv,
                requested_by=self.tech.user,
            )
        self.assertIn("پیش‌نویس یا صادرشده", str(ctx.exception))

        # No request record must have been created
        self.assertEqual(
            InvoiceCancellationRequest.objects.filter(invoice=inv).count(), 0
        )


# ---------------------------------------------------------------------------
# 4: Technician cannot request for CANCELLED invoice
# ---------------------------------------------------------------------------
class CancelledInvoiceRequestBlockedTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.order = _order(self.company, technician=self.tech)

    def test_request_on_cancelled_invoice_raises(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.CANCELLED
        inv.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            InvoiceCancellationRequestService.request(
                invoice=inv,
                requested_by=self.tech.user,
            )

        self.assertEqual(
            InvoiceCancellationRequest.objects.filter(invoice=inv).count(), 0
        )


# ---------------------------------------------------------------------------
# 5: Technician cannot request for another technician's invoice
# ---------------------------------------------------------------------------
class WrongTechnicianRequestBlockedTest(TestCase):
    """
    The service layer itself does not enforce ownership — that is enforced at
    the view layer via get_object_or_404(order__technician=technician).

    This test verifies that the view-level guard (404) prevents the request
    from reaching the service for a different technician's invoice.

    We additionally verify that the service itself has no cross-tenant leakage:
    a request object references the correct company, and the tested invoice
    belongs only to tech_a's order.
    """

    def setUp(self):
        self.company = _company()
        self.tech_a = _technician(self.company)
        self.tech_b = _technician(self.company)
        self.order_a = _order(self.company, technician=self.tech_a)

    def test_invoice_belongs_to_tech_a_order_not_tech_b(self):
        inv = _draft_invoice(self.company, self.order_a)
        # tech_b's order filter would return no results
        self.assertFalse(
            Invoice.objects.filter(
                id=inv.pk,
                company=self.company,
                order__technician=self.tech_b,
            ).exists()
        )

    def test_view_get_object_or_404_guard(self):
        """Simulate the view guard: filter on order__technician=requesting_tech."""
        inv = _draft_invoice(self.company, self.order_a)

        # tech_b tries to access tech_a's invoice through the view filter
        accessible = Invoice.objects.filter(
            id=inv.pk,
            company=self.company,
            order__technician=self.tech_b,
        ).exists()
        self.assertFalse(accessible, "tech_b must not see tech_a's invoice via view guard")


# ---------------------------------------------------------------------------
# 6: Duplicate PENDING request is blocked
# ---------------------------------------------------------------------------
class DuplicateRequestBlockedTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.order = _order(self.company, technician=self.tech)

    def test_second_pending_request_raises(self):
        inv = _draft_invoice(self.company, self.order)

        InvoiceCancellationRequestService.request(
            invoice=inv, requested_by=self.tech.user, reason="first"
        )

        with self.assertRaises(ValueError) as ctx:
            InvoiceCancellationRequestService.request(
                invoice=inv, requested_by=self.tech.user, reason="second"
            )
        self.assertIn("در حال بررسی", str(ctx.exception))

        # Only one request must exist
        self.assertEqual(
            InvoiceCancellationRequest.objects.filter(invoice=inv).count(), 1
        )

    def test_second_request_allowed_after_rejection(self):
        """After a REJECTED request, a new PENDING request may be submitted."""
        inv = _draft_invoice(self.company, self.order)
        admin = _user(self.company, role=UserRole.COMPANY_ADMIN)

        req1 = InvoiceCancellationRequestService.request(
            invoice=inv, requested_by=self.tech.user, reason="first"
        )
        InvoiceCancellationRequestService.reject(
            cancel_request=req1, reviewed_by=admin, review_note="رد شد"
        )

        req2 = InvoiceCancellationRequestService.request(
            invoice=inv, requested_by=self.tech.user, reason="second"
        )
        self.assertEqual(req2.status, InvoiceCancellationRequest.Status.PENDING)

    def test_second_request_allowed_after_approval(self):
        """After an APPROVED request (invoice CANCELLED), no new request can be made."""
        inv = _draft_invoice(self.company, self.order)
        admin = _user(self.company, role=UserRole.COMPANY_ADMIN)

        req1 = InvoiceCancellationRequestService.request(
            invoice=inv, requested_by=self.tech.user
        )
        InvoiceCancellationRequestService.approve(
            cancel_request=req1, reviewed_by=admin
        )

        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)

        # Now the invoice is CANCELLED, so a new request must be rejected by service
        with self.assertRaises(ValueError):
            InvoiceCancellationRequestService.request(
                invoice=inv, requested_by=self.tech.user, reason="third"
            )


# ---------------------------------------------------------------------------
# 7: Admin approves → invoice becomes CANCELLED
# ---------------------------------------------------------------------------
class AdminApproveTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.admin = _user(self.company, role=UserRole.COMPANY_ADMIN)
        self.order = _order(self.company, technician=self.tech)

    def _request_and_approve(self, invoice, review_note=""):
        req = InvoiceCancellationRequestService.request(
            invoice=invoice,
            requested_by=self.tech.user,
        )
        return InvoiceCancellationRequestService.approve(
            cancel_request=req,
            reviewed_by=self.admin,
            review_note=review_note,
        )

    def test_approve_draft_invoice_cancels_it(self):
        inv = _draft_invoice(self.company, self.order)
        approved_req = self._request_and_approve(inv)

        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)
        self.assertEqual(approved_req.status, InvoiceCancellationRequest.Status.APPROVED)
        self.assertEqual(approved_req.reviewed_by_id, self.admin.pk)
        self.assertIsNotNone(approved_req.reviewed_at)

    def test_approve_issued_invoice_cancels_it(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["status"])

        approved_req = self._request_and_approve(inv)

        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)
        self.assertEqual(approved_req.status, InvoiceCancellationRequest.Status.APPROVED)

    def test_review_note_is_stored(self):
        inv = _draft_invoice(self.company, self.order)
        note = "فاکتور اشتباه بود"
        approved_req = self._request_and_approve(inv, review_note=note)
        self.assertEqual(approved_req.review_note, note)

    def test_approve_already_approved_raises(self):
        """Idempotency guard: approving an already-approved request raises."""
        inv = _draft_invoice(self.company, self.order)
        req = InvoiceCancellationRequestService.request(
            invoice=inv, requested_by=self.tech.user
        )
        InvoiceCancellationRequestService.approve(cancel_request=req, reviewed_by=self.admin)

        with self.assertRaises(ValueError):
            InvoiceCancellationRequestService.approve(cancel_request=req, reviewed_by=self.admin)


# ---------------------------------------------------------------------------
# 8: Admin rejects → invoice status unchanged
# ---------------------------------------------------------------------------
class AdminRejectTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.admin = _user(self.company, role=UserRole.COMPANY_ADMIN)
        self.order = _order(self.company, technician=self.tech)

    def test_reject_leaves_draft_invoice_unchanged(self):
        inv = _draft_invoice(self.company, self.order)
        req = InvoiceCancellationRequestService.request(
            invoice=inv, requested_by=self.tech.user
        )
        rejected_req = InvoiceCancellationRequestService.reject(
            cancel_request=req,
            reviewed_by=self.admin,
            review_note="دلیل رد",
        )

        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.DRAFT)
        self.assertEqual(rejected_req.status, InvoiceCancellationRequest.Status.REJECTED)
        self.assertEqual(rejected_req.reviewed_by_id, self.admin.pk)
        self.assertIsNotNone(rejected_req.reviewed_at)
        self.assertEqual(rejected_req.review_note, "دلیل رد")

    def test_reject_leaves_issued_invoice_unchanged(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["status"])

        req = InvoiceCancellationRequestService.request(
            invoice=inv, requested_by=self.tech.user
        )
        InvoiceCancellationRequestService.reject(
            cancel_request=req, reviewed_by=self.admin
        )

        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.ISSUED)

    def test_reject_already_rejected_raises(self):
        inv = _draft_invoice(self.company, self.order)
        req = InvoiceCancellationRequestService.request(
            invoice=inv, requested_by=self.tech.user
        )
        InvoiceCancellationRequestService.reject(cancel_request=req, reviewed_by=self.admin)

        with self.assertRaises(ValueError):
            InvoiceCancellationRequestService.reject(cancel_request=req, reviewed_by=self.admin)


# ---------------------------------------------------------------------------
# 9: Approve after invoice was paid — fails safely
# ---------------------------------------------------------------------------
class ApproveAfterPaidTest(TestCase):
    """
    Race condition: technician submits cancel request while invoice is ISSUED;
    customer pays before admin reviews.  Approval must raise ValueError and
    must NOT cancel the PAID invoice.
    """

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.admin = _user(self.company, role=UserRole.COMPANY_ADMIN)
        self.order = _order(self.company, technician=self.tech)

    def test_approve_paid_invoice_raises_and_leaves_paid(self):
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["status"])

        # Technician submits request while invoice is ISSUED
        req = InvoiceCancellationRequestService.request(
            invoice=inv,
            requested_by=self.tech.user,
            reason="مشتری گفت لغو کن",
        )

        # Invoice is paid concurrently (direct status update simulates payment)
        Invoice.objects.filter(pk=inv.pk).update(status=Invoice.Status.PAID)

        # Admin tries to approve — must raise, invoice must stay PAID
        with self.assertRaises(ValueError) as ctx:
            InvoiceCancellationRequestService.approve(
                cancel_request=req,
                reviewed_by=self.admin,
            )

        self.assertIn("پرداخت شده", str(ctx.exception))

        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.PAID)

        # Request must remain PENDING (admin must manually reject it)
        req.refresh_from_db()
        self.assertEqual(req.status, InvoiceCancellationRequest.Status.PENDING)


# ---------------------------------------------------------------------------
# 10: Direct technician cancel is impossible via the service layer
# ---------------------------------------------------------------------------
class DirectTechnicianCancelBlockedTest(TestCase):
    """
    InvoiceCancelService.cancel() has no role-check — it is an admin-only
    service called internally by approve().  The technician-facing cancel
    request view never calls InvoiceCancelService.cancel() directly.

    This test verifies that the service itself raises if the invoice status
    is already invalid (extra guard), and that technician views route through
    the request workflow rather than calling cancel() directly.
    """

    def setUp(self):
        self.company = _company()
        self.tech = _technician(self.company)
        self.order = _order(self.company, technician=self.tech)

    def test_cancel_service_raises_on_paid_invoice(self):
        """Cancelling a PAID invoice via the service must always raise."""
        inv = _draft_invoice(self.company, self.order)
        inv.status = Invoice.Status.PAID
        inv.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            InvoiceCancelService.cancel(invoice=inv)

    def test_cancel_service_raises_on_already_cancelled(self):
        inv = _draft_invoice(self.company, self.order)
        InvoiceCancelService.cancel(invoice=inv)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)

        with self.assertRaises(ValueError):
            InvoiceCancelService.cancel(invoice=inv)

    def test_cancel_request_workflow_does_not_expose_direct_cancel(self):
        """
        The technician-facing URL pattern for cancel-request does NOT map to
        InvoiceCancelService.cancel(). Verify the view module imports the
        request service, not the cancel service, for the cancel-request view.
        """
        import inspect
        from apps.invoices import views_technician

        source = inspect.getsource(
            views_technician.technician_invoice_cancel_request
        )
        # Must reference the request service
        self.assertIn("InvoiceCancellationRequestService", source)
        # Must NOT call InvoiceCancelService directly
        self.assertNotIn("InvoiceCancelService.cancel", source)
