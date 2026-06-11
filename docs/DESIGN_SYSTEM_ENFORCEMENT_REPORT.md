# گزارش اعمال سیستم طراحی — P30

## وضعیت فعلی

| متریک | قبل P30 | بعد P30 |
|--------|---------|---------|
| Inline styles | 626 | **565** |
| Hardcoded hex in templates | 841 | **806** |
| Templates with 0 inline | 83 | ~90 |

## معماری مرکزی CSS

```
base.html → theme.css
  ├── tokens.css (262 lines)
  ├── base.css (377 lines)
  ├── components.css (1060+ lines)
  ├── layouts.css (654 lines)
  ├── pages.css (1600+ lines)
  ├── dashboard.css (1392 lines — LEGACY)
  └── responsive.css (327 lines)
```

## قرارداد Component

### دکمه‌ها
`.btn .btn-primary .btn-secondary .btn-outline .btn-danger .btn-success .btn-warning .btn-ghost .btn-sm .btn-lg .btn-block .btn-icon`

### کارت‌ها
`.card .card-flush .report-card .stat-card .card-header .card-header-title .card-header-value`

### جدول‌ها
`.table-wrapper .data-table .ltr-cell .tfoot-row .tfoot-value`

### فرم‌ها
`.form-control .filter-input .form-stack .form-group .form-label`

### Badge/Status
`.badge .badge-success .badge-warning .badge-danger .badge-info .badge-neutral`

### Alert
`.alert .alert-success .alert-warning .alert-danger .alert-info .alert-body`

### Layout
`.page-header .page-header-subtitle .section-title .actions-row .detail-list .detail-row .detail-label .detail-value .empty-state .empty-state-healthy`

## وضعیت Sidebar/Topbar

- Company admin: `base_dashboard.html` + `includes/nav_admin.html` — Tailwind-like classes (bg-slate-900)
- Platform owner: `layouts/dashboard.html` + `includes/nav_platform.html` — Tailwind-like classes
- هر دو از theme.css load شده‌اند
- رنگ‌ها هنوز hardcoded Tailwind هستند — نیاز به migration آینده

## وضعیت dashboard.css

| متریک | مقدار |
|--------|-------|
| خطوط | 1392 |
| کلاس یکتا | 322 |
| Overlap با components.css | 30 |
| وابسته templates | ~60+ |
| وضعیت | Legacy — هنوز لازم |

## Remaining Exceptions

- RTL table cells: `text-align:left;direction:ltr` — **~100 مورد** (acceptable)
- `display:none` / `position:absolute` — **~20 مورد** (JS functionality)
- Grid layouts: `display:grid;grid-template-columns:...` — **~30 مورد** (page-specific)
- Sidebar Tailwind classes: `bg-slate-900`, `text-white` — **~100 مورد** (future migration)
- Hex colors in sidebar/topbar: **~400+** (hardcoded in layout includes)

## فازهای آینده

- P31: Sidebar/topbar token migration (Tailwind → token classes)
- P32: dashboard.css reduction (30 duplicate → remove)
- P33: Responsive/mobile final pass
- P34: Visual regression QA checklist
