# Glossary — Rasti Service Business Dictionary

**Version:** RDOS v1.0 Stable

This glossary defines business concepts. For naming conventions, see `TERMINOLOGY.md`.

---

## Rasti Service

A multi-tenant SaaS platform for service-dispatch companies in Iran. Rasti Service provides software and may provide payment infrastructure. It does not sell the field service to end customers.

## Tenant Company

A company that subscribes to Rasti Service and uses it to manage customers, orders, technicians, invoices, payments, SMS, and reports. The tenant company owns the customer relationship and service liability.

## Customer

The person or business receiving service from a tenant company. The customer pays the tenant company, even when the payment UI is hosted by Rasti Service.

## Technician

The service worker assigned to an order. A technician may issue invoices according to company rules. A technician may receive wages through company settlement or future direct payout mechanisms.

## Order

The core operational object. It represents a service job/request after creation or approval. Every order belongs to one company and may have one active technician.

## Invoice

The financial document issued for an order/service. It is issued by the tenant company or its technician/user. It freezes financial snapshots when paid.

## Payment

A record of a customer payment attempt or completed payment. A payment becomes successful only after provider verification, not merely callback arrival.

## Payment Gateway

The gateway configuration used to initiate and verify online payments. The target canonical model is `PaymentGateway`. It must identify owner type: company-owned or platform-owned.

## CompanyPaymentSettings

The model responsible for payment activation and mode. It determines whether online payment is disabled, company-gateway, or platform-gateway. It is controlled by the platform owner.

## CompanyFinancialPolicy

The model responsible for financial behaviour: payout strategy, split policies, discount absorption, and platform fee percent. It is not responsible for payment activation.

## Platform Gateway

A gateway owned or controlled by Rasti Service or its approved payment facilitator. Platform commission may be created only for verified paid payments through this gateway and only when the company is in platform-gateway mode.

## Company Gateway

A gateway owned by the tenant company. Money goes through the company’s PSP arrangement. Rasti Service must not create platform commission for these payments.

## Platform Fee / Platform Commission

The percentage fee owed to Rasti Service. It is created only when all conditions are true:

1. Company payment mode is `platform_gateway`.
2. Payment is verified `PAID`.
3. Gateway `owner_type` is `platform`.
4. `platform_fee_percent > 0`.

During Phase 1, the system may enforce only the gateway/payment defensive guard before full `CompanyPaymentSettings` exists.

## Ledger Entry

An immutable financial row. Existing ledgers include technician ledger and platform fee ledger. Ledger entries are never edited; corrections are recorded as new reversing entries.

## NEEDS_RECONCILIATION

A payment status for ambiguous outcomes: expired pending payment, verify timeout, provider ambiguity, or amount mismatch. Such payments require platform-owner review and must not be auto-settled.

## KYC

Identity and banking verification for company owners and, when direct technician payout is used, technicians. KYC approval does not automatically activate payment mode.

## ADR

Architecture Decision Record. ADRs are the highest-priority documentation source after `SKILL.md` entry rules.
