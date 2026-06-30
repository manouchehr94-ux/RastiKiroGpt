# Order Rules

Order is the heart of the platform.

---

## Core States

- pending operator review
- new
- waiting for service
- in progress
- completed
- cancellation requested
- canceled

---

## Cancellation

If cancellation is requested, dangerous downstream actions must be locked until resolution.

Technician invoice creation must be blocked when cancellation is active.
