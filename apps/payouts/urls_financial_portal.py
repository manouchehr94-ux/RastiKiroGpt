"""
Payouts — Financial Portal URL Configuration.

Served under /<company_code>/admin/financial-portal/
Read-only browsing pages for the Financial Engine (Sprints 1-8).
"""
from django.urls import path

from . import views_financial_portal as views

app_name = "financial_portal"

urlpatterns = [
    path("", views.financial_portal_dashboard, name="dashboard"),
    path("technicians/", views.financial_portal_technician_list, name="technician_list"),
    path("technicians/<int:technician_id>/", views.financial_portal_technician_detail, name="technician_detail"),
    path("settlements/", views.financial_portal_settlement_list, name="settlement_list"),
    path("settlements/<int:batch_id>/", views.financial_portal_settlement_detail, name="settlement_detail"),
    path("escrows/", views.financial_portal_escrow_list, name="escrow_list"),
    path("adjustments/", views.financial_portal_adjustment_list, name="adjustment_list"),
    path("reconciliation/", views.financial_portal_reconciliation, name="reconciliation"),
    path("closing/", views.financial_portal_closing, name="closing"),
    path("reports/", views.financial_portal_reports, name="reports"),
]
