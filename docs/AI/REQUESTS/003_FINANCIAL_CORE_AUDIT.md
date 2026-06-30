# Request 003 — Financial Core Architecture Audit

Priority: Critical  
Mode: Audit only  
Implementation: Forbidden until audit approval

---

## Objective

Audit the existing financial implementation against the desired long-term architecture.

Do not rewrite the financial system.

Do not create migrations.

Do not modify models.

First understand what exists.

---

## Business Model

Rasti is a multi-company service dispatch SaaS.

The platform owner provides software.

Companies provide services.

Invoices belong to companies.

Customers should feel they are paying the company.

Online payments may be collected through platform owner gateway/account.

Internal financial engine must allocate shares.

Settlement happens after allocation.

---

## Desired Concepts

- generic recipient architecture
- company share
- technician share
- platform commission
- future recipients such as visitor, sales agent, affiliate
- discount funding policies
- allocation vs settlement separation
- immutable ledger
- frozen snapshots
- configurable settlement delay
- company bank account approval
- technician bank account support

---

## Existing Concepts To Inspect

- Invoice
- InvoiceItem
- Payment
- Platform fee calculation
- Technician wage calculation
- Payment split snapshots
- Technician ledger
- Company financial policy
- Merchant profile
- Payment settings
- Invoice locking
- Idempotency
- Financial tests

---

## Audit Questions

1. What already exists?
2. What partially exists?
3. What is missing?
4. What conflicts with desired architecture?
5. What should remain?
6. What should be deprecated?
7. What migration is safest?
8. What risks exist?
9. What minimal models/services are needed?
10. What tests remain valid?

---

## Deliverables

- Existing architecture report
- Gap analysis
- Reuse analysis
- Migration strategy
- Proposed minimal financial core
- Risk analysis
- Implementation roadmap

---

## Constraints

No destructive refactoring.

No unnecessary abstraction.

No overengineering.

Every recommendation must explain WHY.
