# Project Knowledge

## Product

Rasti SaaS is a multi-tenant service dispatch platform.

It is not an online shop.

Each company is an independent service business.  
The platform owner provides the SaaS platform.

---

## Main Actors

- Platform Owner
- Company Admin
- Operator
- Technician
- Customer

---

## Main Domains

- Companies
- Users and permissions
- Orders
- Technicians
- Customers
- Invoices
- Payments
- Notifications
- SMS
- Financial reports
- Technician payout / ledger

---

## Core Principles

- Company isolation is mandatory.
- Every business action must respect tenant boundaries.
- Orders are the heart of the system.
- Financial history must be auditable.
- Notification and SMS must be configurable per company.
- Public pages must never render admin/company dashboard layout.
- Technician UI must be mobile-first.
- Business correctness is more important than technical elegance.

---

## Development Philosophy

ChatGPT designs, audits, reviews, and writes precise prompts.

Kiro reads the repository, audits implementation, proposes changes, implements approved work, runs tests, and commits.

The product owner tests manually and makes final product decisions.
