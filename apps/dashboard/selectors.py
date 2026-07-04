"""
Dashboard - Selectors.

Aggregation queries for dashboard widgets.
Each selector is role-scoped to prevent cross-tenant leaks.

IMPORTANT: All tenant-level queries MUST filter by company.
"""
from django.db.models import Count, F, Sum, Q
from django.utils import timezone

from apps.accounts.models import Customer, Technician
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.orders.selectors import OrderSelector
from apps.tenants.models import Company, ServiceRequest


class PlatformDashboardSelector:
    """
    Dashboard data for PLATFORM_OWNER.
    Shows global platform statistics.
    NOT tenant-scoped — shows data across all companies.
    """

    @staticmethod
    def get_stats() -> dict:
        """Get platform-level statistics."""
        total = Company.objects.count()
        active = Company.objects.filter(is_active=True).count()
        inactive = Company.objects.filter(is_active=False).count()

        from apps.platform_core.models import Subscription
        subscription_count = Subscription.objects.count()

        return {
            "total_companies": total,
            "active_companies": active,
            "inactive_companies": inactive,
            "subscription_count": subscription_count,
        }

    @staticmethod
    def get_recent_companies(*, limit: int = 10):
        """Get recently created companies."""
        return Company.objects.order_by("-created_at")[:limit]


class CompanyDashboardSelector:
    """
    Dashboard data for COMPANY_ADMIN / COMPANY_STAFF.
    Shows statistics for ONE company only.
    """

    @staticmethod
    def get_stats(*, company) -> dict:
        """Get company-level dashboard statistics."""
        today = timezone.now().date()

        orders_qs = Order.objects.filter(company=company)
        invoices_qs = Invoice.objects.filter(company=company)

        today_orders = orders_qs.filter(created_at__date=today).count()
        new_orders = orders_qs.filter(status=Order.Status.NEW).count()
        in_progress_orders = orders_qs.filter(status=Order.Status.IN_PROGRESS).count()
        done_orders = orders_qs.filter(status=Order.Status.DONE).count()

        unpaid_invoices = invoices_qs.filter(status=Invoice.Status.ISSUED).count()
        paid_invoices = invoices_qs.filter(status=Invoice.Status.PAID).count()

        total_revenue = invoices_qs.filter(
            status=Invoice.Status.PAID
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        active_technicians = Technician.objects.filter(
            company=company, is_available=True
        ).count()

        return {
            "today_orders": today_orders,
            "new_orders": new_orders,
            "in_progress_orders": in_progress_orders,
            "done_orders": done_orders,
            "unpaid_invoices": unpaid_invoices,
            "paid_invoices": paid_invoices,
            "total_revenue": total_revenue,
            "active_technicians": active_technicians,
        }

    @staticmethod
    def get_recent_orders(*, company, limit: int = 10):
        """Get recent orders for the company."""
        return Order.objects.filter(company=company).order_by("-created_at")[:limit]

    @staticmethod
    def get_chart_data(*, company) -> dict:
        """Get data for dashboard charts: last 7 days orders + status distribution."""
        import json
        from datetime import timedelta
        from apps.common.jalali import gregorian_to_jalali
        today = timezone.now().date()

        # Last 7 days — orders per day
        days = []
        counts = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            count = Order.objects.filter(company=company, created_at__date=day).count()
            _, _, jalali_day = gregorian_to_jalali(day.year, day.month, day.day)
            days.append(str(jalali_day))  # Jalali day number for RTL display
            counts.append(count)

        # Status distribution for donut chart
        orders_qs = Order.objects.filter(company=company)
        waiting = orders_qs.filter(status=Order.Status.WAITING).count()
        in_progress = orders_qs.filter(status=Order.Status.IN_PROGRESS).count()
        done = orders_qs.filter(status=Order.Status.DONE).count()
        new_orders = orders_qs.filter(status=Order.Status.NEW).count()
        cancelled = orders_qs.filter(status=Order.Status.CANCELLED).count()

        return {
            "line_labels": json.dumps(days),
            "line_data": json.dumps(counts),
            "donut_data": json.dumps([new_orders, waiting, in_progress, done, cancelled]),
            "donut_labels": json.dumps(["جدید", "در انتظار", "در حال انجام", "انجام شده", "لغو شده"]),
        }


class TechnicianDashboardSelector:
    """
    Dashboard data for TECHNICIAN.
    Shows only the technician's own data.
    """

    @staticmethod
    def get_stats(*, technician: Technician) -> dict:
        """Get technician-specific statistics."""
        from datetime import date as _date
        from apps.common.jalali import gregorian_to_jalali, jalali_to_gregorian
        from apps.orders.selectors import TechnicianOrderVisibilitySelector
        from apps.orders.eligibility import is_order_accept_allowed_by_service_date

        visible = TechnicianOrderVisibilitySelector.get_available_orders(
            technician=technician,
        )
        # Count only orders that are currently acceptable (not future-gated)
        acceptable_count = sum(
            1 for order in visible[:100]
            if is_order_accept_allowed_by_service_date(order=order)
        )
        waiting = Order.objects.filter(
            company=technician.company,
            technician=technician,
            status=Order.Status.WAITING,
        )
        in_progress = Order.objects.filter(
            company=technician.company,
            technician=technician,
            status=Order.Status.IN_PROGRESS,
        )
        completed = Order.objects.filter(
            company=technician.company,
            technician=technician,
            status=Order.Status.DONE,
        )

        # Current Jalali month boundaries (Gregorian dates), reusing the
        # existing gregorian_to_jalali/jalali_to_gregorian conversion helpers.
        today = timezone.now().date()
        jy, jm, _jd = gregorian_to_jalali(today.year, today.month, today.day)
        month_start_y, month_start_m, month_start_d = jalali_to_gregorian(jy, jm, 1)
        month_start = _date(month_start_y, month_start_m, month_start_d)
        next_jy, next_jm = (jy + 1, 1) if jm == 12 else (jy, jm + 1)
        next_month_start_y, next_month_start_m, next_month_start_d = jalali_to_gregorian(next_jy, next_jm, 1)
        next_month_start = _date(next_month_start_y, next_month_start_m, next_month_start_d)

        completed_this_month_qs = completed.filter(
            created_at__date__gte=month_start,
            created_at__date__lt=next_month_start,
        )
        completed_this_month = completed_this_month_qs.count()

        # Completed SERVICE line items (InvoiceItem rows, not orders) for
        # this technician's completed orders this Jalali month. A single
        # aggregate query (no per-order loop) to avoid N+1.
        from apps.invoices.models import InvoiceItem

        completed_service_items_this_month = InvoiceItem.objects.filter(
            company=technician.company,
            row_type=InvoiceItem.RowType.SERVICE,
            invoice__order__in=completed_this_month_qs,
        ).exclude(
            invoice__status=Invoice.Status.CANCELLED,
        ).count()

        # Completed totals grouped by ORDER item definition title (the
        # service/order item system — OrderItemDefinition/OrderItemValue —
        # NOT invoice line items) for this technician's completed orders
        # this Jalali month. Single aggregate GROUP BY query, no per-order
        # loop, so it does not scale with order count (no N+1). Only
        # NUMBER-kind item values are summed as "quantities"; MONEY-kind
        # values are pricing data (out of scope here — no financial logic
        # is touched), and TEXT/BOOL kinds have no meaningful sum.
        from apps.orders.models import OrderItemDefinition, OrderItemValue

        completed_item_totals_this_month = list(
            OrderItemValue.objects.filter(
                order__in=completed_this_month_qs,
                item__kind=OrderItemDefinition.Kind.NUMBER,
                item__is_active=True,
                value_number__isnull=False,
            )
            .values(title=F("item__title"))
            .annotate(total=Sum("value_number"))
            .filter(total__gt=0)
            .order_by("-total", "title")
        )

        return {
            "visible_orders": acceptable_count,
            "waiting_orders": waiting.count(),
            "in_progress_orders": in_progress.count(),
            "active_orders": waiting.count() + in_progress.count(),
            "completed_orders": completed.count(),
            "completed_orders_this_month": completed_this_month,
            "completed_service_items_this_month": completed_service_items_this_month,
            "completed_item_totals_this_month": completed_item_totals_this_month,
        }

    @staticmethod
    def get_recent_assigned(*, technician: Technician, limit: int = 10):
        """Get recent orders assigned to this technician."""
        return Order.objects.filter(
            company=technician.company,
            technician=technician,
        ).order_by("-created_at")[:limit]


class CustomerDashboardSelector:
    """
    Dashboard data for CUSTOMER.
    Shows only the customer's own data.
    """

    @staticmethod
    def get_stats(*, customer: Customer) -> dict:
        """Get customer-specific statistics."""
        orders_qs = Order.objects.filter(
            company=customer.company, customer=customer
        )
        invoices_qs = Invoice.objects.filter(
            company=customer.company, customer=customer
        )

        return {
            "total_orders": orders_qs.count(),
            "unpaid_invoices": invoices_qs.filter(status=Invoice.Status.ISSUED).count(),
            "paid_invoices": invoices_qs.filter(status=Invoice.Status.PAID).count(),
        }

    @staticmethod
    def get_recent_orders(*, customer: Customer, limit: int = 10):
        """Get recent orders for this customer."""
        return Order.objects.filter(
            company=customer.company, customer=customer
        ).order_by("-created_at")[:limit]
