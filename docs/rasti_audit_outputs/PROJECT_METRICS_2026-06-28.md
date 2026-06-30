# Project Metrics Report

**Date:** 2026-06-28  
**Source:** Static analysis of uploaded ZIP

---

## 1. File-Type Metrics

| Extension | Files | LOC / estimated lines |
|---|---:|---:|
| .bak | 15 | 1505 |
| .bak5 | 7 | 1154 |
| .css | 17 | 8317 |
| .example | 1 | 65 |
| .html | 198 | 20464 |
| .jpg | 6 | 6 |
| .js | 7 | 863 |
| .json | 2 | 19 |
| .md | 79 | 6436 |
| .ps1 | 5 | 113 |
| .py | 420 | 67748 |
| .sqlite3 | 3 | 9127 |
| .txt | 3 | 71 |
| .woff2 | 5 | 1942 |
| [noext] | 2 | 46 |

---

## 2. App Metrics

| App | Py files | LOC | Classes | Functions | Service files | View files | Migrations | Templates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accounts | 16 | 2654 | 42 | 103 | 1 | 3 | 7 | 8 |
| api | 7 | 990 | 42 | 31 | 0 | 1 | 0 | 0 |
| billing | 9 | 112 | 7 | 3 | 1 | 1 | 3 | 0 |
| common | 12 | 923 | 8 | 48 | 1 | 0 | 0 | 0 |
| dashboard | 11 | 349 | 5 | 13 | 1 | 1 | 0 | 3 |
| invoices | 17 | 2860 | 24 | 83 | 5 | 3 | 5 | 5 |
| notifications | 21 | 2586 | 28 | 81 | 2 | 1 | 3 | 2 |
| orders | 21 | 4176 | 41 | 94 | 2 | 1 | 5 | 8 |
| payments | 21 | 2199 | 34 | 47 | 3 | 2 | 3 | 5 |
| payouts | 16 | 2553 | 31 | 55 | 7 | 2 | 8 | 7 |
| platform_core | 39 | 8330 | 86 | 236 | 7 | 14 | 6 | 46 |
| public | 6 | 631 | 2 | 18 | 1 | 1 | 0 | 8 |
| reports | 10 | 1745 | 22 | 50 | 2 | 1 | 3 | 7 |
| sms | 35 | 4891 | 63 | 112 | 2 | 2 | 9 | 6 |
| tenants | 18 | 6239 | 60 | 184 | 2 | 6 | 6 | 62 |

---

## 3. Top 25 Largest Source/Template/Doc Files

| # | File | LOC |
|---:|---|---:|
| 1 | `apps/tenants/views_admin.py` | 3309 |
| 2 | `apps/platform_core/management/commands/smoke_regression.py` | 2194 |
| 3 | `static/css/pages.css` | 2143 |
| 4 | `static/css/dashboard.css` | 1574 |
| 5 | `static/css/components.css` | 1402 |
| 6 | `apps/orders/services.py` | 1201 |
| 7 | `docs/00_Project/MASTER_PROJECT_AUDIT_2026-06-28.md` | 938 |
| 8 | `apps/reports/views.py` | 916 |
| 9 | `static/css/layouts.css` | 823 |
| 10 | `apps/accounts/operator_access.py` | 809 |
| 11 | `apps/invoices/views_technician.py` | 806 |
| 12 | `tests/test_p7_verify.py` | 786 |
| 13 | `apps/sms/services.py` | 745 |
| 14 | `apps/notifications/event_catalog.py` | 721 |
| 15 | `apps/platform_core/management/commands/seed_full_demo.py` | 712 |
| 16 | `apps/tenants/models.py` | 710 |
| 17 | `static/css/responsive.css` | 704 |
| 18 | `apps/platform_core/models.py` | 673 |
| 19 | `templates/orders/technician_invoice_create.html` | 654 |
| 20 | `docs/00_Project/FUTURE_PLATFORM_RECOMMENDATIONS_2026-06-28.md` | 621 |
| 21 | `tests/test_task010b_order_wage_posting.py` | 616 |
| 22 | `tests/test_p8_gateway_safety.py` | 609 |
| 23 | `tests/test_task011a_fix1_backfill_direct_settlement.py` | 568 |
| 24 | `tests/test_task008_backfill.py` | 549 |
| 25 | `apps/sms/views.py` | 539 |

---

## 4. Interpretation

- The two major maintainability hotspots are `apps/tenants/views_admin.py` and `apps/orders/services.py`.
- `platform_core` and `tenants` are broad modules and should be prevented from becoming permanent catch-all areas.
- Static assets include backup CSS and old template `.bak` files that should be quarantined.
- The repository contains local SQLite DBs in the ZIP; they should never be part of clean source exports.
