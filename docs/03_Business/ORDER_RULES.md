# Order Rules

Order is the core operational entity.

## Statuses

- در انتظار تایید اپراتور
- جدید
- در انتظار انجام خدمت
- در حال انجام خدمت
- انجام شده
- درخواست لغو
- لغو شده

## Creation paths

Public request:
- starts as `در انتظار تایید اپراتور`

Operator/admin phone order:
- no technician → `جدید`
- technician assigned → `در انتظار انجام خدمت`

## Assignment

- One active technician per order.
- Assignment means acceptance.
- Removing technician returns order to `جدید`.

## Terminal rules

- Completed/cancelled orders are protected.
- Admin should not casually mutate completed/cancelled orders.
