from django.urls import path

from apps.sca.views import (
    ScaAuthRefreshView,
    SyncFormsView,
    SyncPullView,
    SyncPushView,
    SyncStatusView,
)

urlpatterns = [
    path("sca/sync/push/", SyncPushView.as_view(), name="sca-sync-push"),
    path("sca/sync/pull/", SyncPullView.as_view(), name="sca-sync-pull"),
    path("sca/sync/forms/", SyncFormsView.as_view(), name="sca-sync-forms"),
    path("sca/sync/status/", SyncStatusView.as_view(), name="sca-sync-status"),
    path("sca/auth/refresh/", ScaAuthRefreshView.as_view(), name="sca-auth-refresh"),
]
