# 17 — ماتریس دسترسی (Permission Matrix)

**Version:** v1.0 — Draft — Pending Clarification
**Rule:** R48

---

## نقش‌ها

| Role | Code | Level |
|---|---|---|
| Platform Owner | `PLATFORM_OWNER` | System-wide |
| Company Admin | `COMPANY_ADMIN` | Organization-scoped |
| Company Staff (Operator) | `COMPANY_STAFF` | Organization-scoped |
| Technician | `TECHNICIAN` | Organization-scoped |
| Customer | `CUSTOMER` | Organization-scoped |

---

## ماتریس عملیات مالی

### Invoice Operations

| Operation | PLATFORM_OWNER | COMPANY_ADMIN | COMPANY_STAFF | TECHNICIAN | CUSTOMER |
|---|---|---|---|---|---|
| Create invoice | ❌ | ✅ | ✅ | ✅ (own orders) | ❌ |
| Edit draft invoice | ❌ | ✅ | ✅ | ✅ (own) | ❌ |
| Issue invoice | ❌ | ✅ | ✅ | ✅ (own) | ❌ |
| Cancel invoice | ❌ | ✅ | ✅ | ❌ (request only) | ❌ |
| Request cancellation | ❌ | ❌ | ❌ | ✅ | ❌ |
| Approve/reject cancellation | ❌ | ✅ | ✅ | ❌ | ❌ |
| View invoice (admin) | ✅ | ✅ | ✅ | ✅ (own) | ❌ |
| View invoice (public) | — | — | — | — | ✅ (ISSUED/PAID) |
| Record cash payment | ❌ | ✅ | ✅ | ✅ (own) | ❌ |

### Payment Operations

| Operation | PLATFORM_OWNER | COMPANY_ADMIN | COMPANY_STAFF | TECHNICIAN | CUSTOMER |
|---|---|---|---|---|---|
| Initiate online payment | ❌ | ❌ | ❌ | ❌ | ✅ |
| View payment status | ✅ | ✅ | ✅ | ❌ | ✅ (own) |
| Resolve NEEDS_RECONCILIATION | ✅ | ❌ | ❌ | ❌ | ❌ |

### Settlement Operations

| Operation | PLATFORM_OWNER | COMPANY_ADMIN | COMPANY_STAFF | TECHNICIAN | CUSTOMER |
|---|---|---|---|---|---|
| View technician ledger | ✅ (cross-company) | ✅ | ✅ | ❌ (future) | ❌ |
| Record manual settlement | ❌ | ✅ | ✅ | ❌ | ❌ |
| View technician statement | ✅ | ✅ | ✅ | ❌ (future) | ❌ |
| Export statement (CSV/PDF) | ❌ | ✅ | ✅ | ❌ | ❌ |
| Create settlement batch | ✅ | ❌ | ❌ | ❌ | ❌ |
| Execute settlement | ✅ | ❌ | ❌ | ❌ | ❌ |

### Financial Policy Operations (R48)

| Operation | PLATFORM_OWNER | COMPANY_ADMIN | COMPANY_STAFF | TECHNICIAN | CUSTOMER |
|---|---|---|---|---|---|
| View financial policy | ✅ | ✅ | ✅ | ❌ | ❌ |
| Change platform_fee_percent | ✅ | ❌ | ❌ | ❌ | ❌ |
| Change discount policies | ✅ | ❌ | ❌ | ❌ | ❌ |
| Change payout_strategy | ✅ | ❌ | ❌ | ❌ | ❌ |
| Change payment_mode | ✅ | ❌ | ❌ | ❌ | ❌ |
| Activate/suspend gateway | ✅ | ❌ | ❌ | ❌ | ❌ |
| Change rounding discount | ❌ | ✅ | ❌ | ❌ | ❌ |
| Change settlement frequency | ✅ | ❌ | ❌ | ❌ | ❌ |
| Set technician wage % | ❌ | ✅ | ✅ | ❌ | ❌ |
| Set technician service rates | ❌ | ✅ | ✅ | ❌ | ❌ |

### IBAN / KYC Operations

| Operation | PLATFORM_OWNER | COMPANY_ADMIN | COMPANY_STAFF | TECHNICIAN | CUSTOMER |
|---|---|---|---|---|---|
| Submit company KYC | ❌ | ✅ | ❌ | ❌ | ❌ |
| Approve/reject company KYC | ✅ | ❌ | ❌ | ❌ | ❌ |
| Register technician IBAN | ❌ | ✅ | ✅ | ❌ | ❌ |
| Verify technician IBAN | ❌ | ✅ | ✅ | ❌ | ❌ |
| Assign sub_merchant_id | ✅ | ❌ | ❌ | ❌ | ❌ |

### Reporting

| Operation | PLATFORM_OWNER | COMPANY_ADMIN | COMPANY_STAFF | TECHNICIAN | CUSTOMER |
|---|---|---|---|---|---|
| Platform commission report | ✅ | ❌ | ❌ | ❌ | ❌ |
| Company financial dashboard | ✅ | ✅ | ✅ | ❌ | ❌ |
| Technician liability report | ✅ | ✅ | ✅ | ❌ | ❌ |
| Settlement status report | ✅ | ✅ | ❌ | ❌ | ❌ |
| Provider personal statement | ❌ | ❌ | ❌ | ✅ (own, future) | ❌ |

---

## Implementation

**Current:** `@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")` decorator pattern.

**Platform Owner:** `@require_platform_owner` decorator.

**R48 Compliance:** فقط Admin + authorized Operators مجاز به تغییر policies. ✅ Partial — platform_fee فقط platform owner. Discount policies باید صریحاً محدود شوند.
