"""
Payouts - Test Factories (Sprint 1 — Financial Foundation Models).

Lightweight builder functions for EscrowRecord, SettlementBatch,
SettlementItem, and AdjustmentDocument, plus the minimal upstream objects
(Company, Order, Invoice, Payment) they depend on.

The project does not use factory_boy; every existing test file
(e.g. tests/test_task008_backfill.py, tests/test_task011a_fix2_ledger_idempotency.py)
builds fixtures with plain functions calling `Model.objects.create(...)`.
This module follows that exact convention so it is consistent with the
rest of the codebase and requires no new dependency.

These factories create schema-only rows for testing. They do not invoke
any service, do not trigger any signal, and do not represent an
approved business workflow — they exist solely to support the model
unit tests required by this sprint.
"""
from __future__ import annotations

import itertools

from django.utils import timezone

from apps.accounts.models import CompanyUser, UserRole
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.tenants.models import Company

from .models import (
    AdjustmentDocument,
    EscrowRecord,
    SettlementBatch,
    SettlementItem,
)

_counter = itertools.count(1)


def _next_seq() -> int:
    return next(_counter)


# ---------------------------------------------------------------------------
# Upstream fixtures (Company / Order / Invoice / Payment)
# ---------------------------------------------------------------------------

def make_company(**overrides) -> Company:
    """Create a minimal, valid Company for tenant scoping."""
    tag = _next_seq()
    defaults = {
        "name": f"Escrow Test Co {tag}",
        "code": f"esc{tag}",
        "slug": f"escrow-test-{tag}",
        "is_active": True,
    }
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def make_company_user(company: Company, **overrides) -> CompanyUser:
    tag = _next_seq()
    defaults = {
        "username": f"escuser{tag}",
        "password": "pass",
        "company": company,
        "role": UserRole.COMPANY_ADMIN,
    }
    defaults.update(overrides)
    return CompanyUser.objects.create_user(**defaults)


def make_order(company: Company, **overrides) -> Order:
    tag = _next_seq()
    defaults = {
        "title": f"Escrow Test Order {tag}",
        "status": Order.Status.DONE,
    }
    defaults.update(overrides)
    return Order.objects.create(company=company, **defaults)


def make_invoice(company: Company, order: Order | None = None, **overrides) -> Invoice:
    """
    Create a minimal PAID invoice directly via the ORM.

    This intentionally bypasses InvoiceCreateService / InvoiceMarkPaidService:
    Sprint 1 factories must not exercise or depend on existing business
    services, only on the raw model shape needed for foreign keys.
    """
    tag = _next_seq()
    order = order or make_order(company)
    defaults = {
        "order": order,
        "invoice_number": f"INV-ESC-{tag:05d}",
        "status": Invoice.Status.PAID,
        "subtotal": 1_000_000,
        "total_amount": 1_000_000,
        "paid_at": timezone.now(),
    }
    defaults.update(overrides)
    return Invoice.objects.create(company=company, **defaults)


def make_payment_gateway(company: Company, **overrides) -> PaymentGateway:
    tag = _next_seq()
    defaults = {
        "name": f"Escrow Test Gateway {tag}",
        "gateway_type": PaymentGateway.GatewayType.FAKE,
        "owner_type": PaymentGateway.OwnerType.PLATFORM,
        "is_active": True,
        "is_default": True,
    }
    defaults.update(overrides)
    return PaymentGateway.objects.create(company=company, **defaults)


def make_payment(company: Company, invoice: Invoice | None = None, **overrides) -> Payment:
    invoice = invoice or make_invoice(company)
    gateway = overrides.pop("gateway", None) or make_payment_gateway(company)
    defaults = {
        "invoice": invoice,
        "gateway": gateway,
        "amount": invoice.total_amount,
        "status": Payment.Status.PAID,
        "paid_at": timezone.now(),
    }
    defaults.update(overrides)
    return Payment.objects.create(company=company, **defaults)


# ---------------------------------------------------------------------------
# EscrowRecord
# ---------------------------------------------------------------------------

def make_escrow_record(
    company: Company | None = None,
    payment: Payment | None = None,
    invoice: Invoice | None = None,
    **overrides,
) -> EscrowRecord:
    company = company or make_company()
    invoice = invoice or make_invoice(company)
    payment = payment or make_payment(company, invoice=invoice)
    defaults = {
        "payment": payment,
        "invoice": invoice,
        "amount_rial": int(invoice.total_amount),
    }
    defaults.update(overrides)
    return EscrowRecord.objects.create(company=company, **defaults)


# ---------------------------------------------------------------------------
# SettlementBatch / SettlementItem
# ---------------------------------------------------------------------------

def make_settlement_batch(company: Company | None = None, **overrides) -> SettlementBatch:
    company = company or make_company()
    now = timezone.now()
    defaults = {
        "level": SettlementBatch.Level.PLATFORM_TO_ORG,
        "period_start": now,
        "period_end": now,
    }
    defaults.update(overrides)
    return SettlementBatch.objects.create(company=company, **defaults)


def make_settlement_item(
    company: Company | None = None,
    batch: SettlementBatch | None = None,
    invoice: Invoice | None = None,
    **overrides,
) -> SettlementItem:
    company = company or make_company()
    batch = batch or make_settlement_batch(company)
    invoice = invoice if invoice is not None else make_invoice(company)
    defaults = {
        "batch": batch,
        "invoice": invoice,
        "amount_rial": 100_000,
    }
    defaults.update(overrides)
    return SettlementItem.objects.create(company=company, **defaults)


# ---------------------------------------------------------------------------
# AdjustmentDocument
# ---------------------------------------------------------------------------

def make_adjustment_document(
    company: Company | None = None,
    original_invoice: Invoice | None = None,
    **overrides,
) -> AdjustmentDocument:
    company = company or make_company()
    original_invoice = original_invoice or make_invoice(company)
    defaults = {
        "document_type": AdjustmentDocument.DocumentType.MANUAL_ADJUSTMENT,
        "amount_rial": 50_000,
        "reason": "Sprint 1 factory default reason",
    }
    defaults.update(overrides)
    return AdjustmentDocument.objects.create(
        company=company,
        original_invoice=original_invoice,
        **defaults,
    )
