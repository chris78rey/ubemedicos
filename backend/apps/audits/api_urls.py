from django.urls import path

from .api_views import (
    admin_audit_logs_collection_view,
    admin_audit_log_detail_view,
    admin_audit_logs_export_view,
    my_audit_events_view,
)

urlpatterns = [
    path(
        "admin/audits/access-logs",
        admin_audit_logs_collection_view,
        name="admin-audit-logs-collection",
    ),
    path(
        "admin/audits/access-logs/export.csv",
        admin_audit_logs_export_view,
        name="admin-audit-logs-export",
    ),
    path(
        "admin/audits/access-logs/<int:event_id>",
        admin_audit_log_detail_view,
        name="admin-audit-logs-detail",
    ),
    path(
        "users/me/audit-events",
        my_audit_events_view,
        name="users-me-audit-events",
    ),
]
