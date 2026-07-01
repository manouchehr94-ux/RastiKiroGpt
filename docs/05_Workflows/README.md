---
Title: Workflows — README
Layer: Workflows
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code
Reusable Across Projects: No
---

# 05 — Workflows

End-to-end process flows for the Rasti platform.

---

## Files in This Folder

| File | Covers | Status |
|---|---|---|
| [ORDER_LIFECYCLE.md](ORDER_LIFECYCLE.md) | Complete order status machine and flow | Active |
| [INVOICE_PAYMENT_FLOW.md](INVOICE_PAYMENT_FLOW.md) | Invoice creation, online payment, cash payment | Active |
| [CANCELLATION_FLOW.md](CANCELLATION_FLOW.md) | Order cancellation request and resolution | Active |
| [NOTIFICATION_FLOW.md](NOTIFICATION_FLOW.md) | In-app and SMS notification trigger flow | Active |
| [PUBLIC_REQUEST_FLOW.md](PUBLIC_REQUEST_FLOW.md) | Public service request form to order creation | Active |
| [OPERATOR_REVIEW_FLOW.md](OPERATOR_REVIEW_FLOW.md) | Operator review of pending requests | Active |
| [TECHNICIAN_FLOW.md](TECHNICIAN_FLOW.md) | Technician daily workflow (accept, complete, invoice) | Active |
| [RELEASE_FLOW.md](RELEASE_FLOW.md) | How to deploy a release | Active |

---

## Reading Order

The order lifecycle is the central workflow. Read in this order:
1. [ORDER_LIFECYCLE.md](ORDER_LIFECYCLE.md) — the central flow all others reference
2. [PUBLIC_REQUEST_FLOW.md](PUBLIC_REQUEST_FLOW.md) — how orders enter the system
3. [OPERATOR_REVIEW_FLOW.md](OPERATOR_REVIEW_FLOW.md) — operator daily workflow
4. [TECHNICIAN_FLOW.md](TECHNICIAN_FLOW.md) — technician daily workflow
5. [INVOICE_PAYMENT_FLOW.md](INVOICE_PAYMENT_FLOW.md) — how payment is collected
6. [CANCELLATION_FLOW.md](CANCELLATION_FLOW.md) — order cancellation path

---

## Related Documents

- [../04_Business_Rules/ORDER_RULES.md](../04_Business_Rules/ORDER_RULES.md) — business rules underlying these flows
- [../04_Business_Rules/PAYMENT_RULES.md](../04_Business_Rules/PAYMENT_RULES.md) — payment rules
- [../09_Operations/RELEASE_FLOW.md](../09_Operations/DEPLOYMENT.md) — deployment guide

---

## Maintenance Notes

Update workflow diagrams when an order status transition changes, a payment flow changes, or a new notification event is added. Always verify Mermaid diagram syntax renders correctly.
