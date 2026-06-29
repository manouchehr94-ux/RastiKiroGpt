"""
Notifications - URL Configuration.

Served under /<company_code>/admin/notifications/
"""
from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("mark-all-read/", views.notification_mark_all_read, name="mark_all_read"),
    path("<int:notification_id>/read/", views.notification_mark_read, name="mark_read"),
]
