---
Title: Technician Business Rules
Layer: Business Rules
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Verified Against: apps/orders/models.py, apps/payouts/models.py, apps/orders/views.py
Source of Truth: Code
Depends On: []
Related Documents: PAYOUT_RULES.md, ORDER_RULES.md, ../07_ADR/ADR-005-Technician-Service-Pricing.md
Reusable Across Projects: No
---

# Technician Business Rules

---

## Technician Role

A Technician is a user with role `TECHNICIAN`. They:
- Belong to exactly one company
- Execute service orders
- Issue invoices for completed orders
- Receive wages via ledger

---

## Order Assignment Rules

- One active technician per order at any time
- A technician can only be assigned to orders within their company
- Admin assigns technician at `/<code>/admin/orders/<id>/assign/`
- Assignment puts order in `WAITING` status
- Technician sees available orders at `/<code>/tech/orders/available/`

---

## Technician Acceptance

- Technician accepts an order → status becomes `IN_PROGRESS`
- Acceptance is final — technician must complete or request to abort
- A technician cannot reject an order (they can only request cancellation)

---

## Order Completion

- Technician completes order at `/<code>/tech/orders/<id>/complete/`
- Order status → `DONE`
- Technician can then create an invoice for the order

---

## Technician Panel (Mobile-First)

URL: `/<code>/tech/`

Bottom navigation (5 items, always visible on mobile):
1. داشبورد — `/<code>/tech/`
2. سفارش جدید — `/<code>/tech/orders/available/`
3. سفارش‌های من — `/<code>/tech/orders/my/`
4. فاکتورها — `/<code>/tech/invoices/`
5. اعلان‌ها — `/<code>/tech/notifications/`

The technician panel is designed for mobile phones.

---

## Technician Wage Calculation

See [../07_ADR/ADR-005-Technician-Service-Pricing.md](../07_ADR/ADR-005-Technician-Service-Pricing.md).

Wage is calculated based on `CompanyFinancialPolicy`:
- Fixed wage per service type
- Percentage of invoice amount
- Custom wage overrides per technician

Wage is credited to `TechnicianLedgerEntry` when invoice is paid.

---

## Technician Financial Verification

Platform Owner can verify technician financial history at:
`/owner-platform/technician-financial-verifications/`

Note: This page is NOT linked in the platform sidebar (orphan page). Must access via direct URL.

---

## SMS Notification to Technicians

**Known Bug (P0-6):** `apps/orders/technician_notifications.py:147` contains:
```python
if False and send_sms and ...
```

This permanently disables SMS notifications for new orders to technicians, regardless of company settings. This must be fixed before relying on SMS notifications.
