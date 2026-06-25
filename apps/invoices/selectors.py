"""
Invoices - Selectors.

All read operations for invoices. ALWAYS company-scoped.
No invoice query may run without company filtering.
"""
from typing import Optional

from django.db.models import QuerySet

from apps.accounts.models import Customer

from .models import Invoice


class InvoiceSelector:
    """Read operations for Invoices. All queries enforce company isolation."""

    @staticmethod
    def get_for_company(*, company) -> QuerySet[Invoice]:
        """Get all invoices for a company (admin view)."""
        return Invoice.objects.filter(company=company)

    @staticmethod
    def get_by_id_for_company(*, invoice_id: int, company) -> Optional[Invoice]:
        """Get a single invoice by ID, company-scoped."""
        return Invoice.objects.filter(id=invoice_id, company=company).first()

    # Statuses that are visible to customers. DRAFT is internal-only and
    # must never be shown to the customer before the invoice is issued.
    CUSTOMER_VISIBLE_STATUSES = [
        Invoice.Status.ISSUED,
        Invoice.Status.PAID,
        Invoice.Status.CANCELLED,
    ]

    @staticmethod
    def get_for_customer(*, customer: Customer) -> QuerySet[Invoice]:
        """
        Get invoices visible to a specific customer.

        DRAFT invoices are excluded — they are internal working documents
        until the technician issues them. Customers see ISSUED, PAID, and
        CANCELLED invoices only.
        """
        return Invoice.objects.filter(
            company=customer.company,
            customer=customer,
            status__in=InvoiceSelector.CUSTOMER_VISIBLE_STATUSES,
        )

    @staticmethod
    def get_unpaid_for_company(*, company) -> QuerySet[Invoice]:
        """Get all issued (unpaid) invoices for a company."""
        return Invoice.objects.filter(
            company=company,
            status=Invoice.Status.ISSUED,
        )

    @staticmethod
    def get_by_status(*, company, status: str) -> QuerySet[Invoice]:
        """Get invoices filtered by status."""
        return Invoice.objects.filter(company=company, status=status)

    @staticmethod
    def get_by_invoice_number(*, company, invoice_number: str) -> Optional[Invoice]:
        """Get invoice by number within a company."""
        return Invoice.objects.filter(
            company=company,
            invoice_number=invoice_number,
        ).first()

    @staticmethod
    def get_by_public_code_for_company(*, company, public_code: str) -> Optional[Invoice]:
        """Get public invoice by short code within a company."""
        return Invoice.objects.filter(
            company=company,
            public_code=public_code,
        ).first()
