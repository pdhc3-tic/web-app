from django.urls import path

from apps.sca.views import (
    ConflictLogViewSet,
    ScaAuthRefreshView,
    SyncDeviceDetailView,
    SyncDeviceListView,
    SyncEventViewSet,
    SyncFormsView,
    SyncPullView,
    SyncPushView,
    SyncStatusView,
    TecnicoListView,
)

urlpatterns = [
    path("sca/sync/push/", SyncPushView.as_view(), name="sca-sync-push"),
    path("sca/sync/pull/", SyncPullView.as_view(), name="sca-sync-pull"),
    path("sca/sync/forms/", SyncFormsView.as_view(), name="sca-sync-forms"),
    path("sca/sync/status/", SyncStatusView.as_view(), name="sca-sync-status"),
    path("sca/auth/refresh/", ScaAuthRefreshView.as_view(), name="sca-auth-refresh"),
    # Endpoints administrativos (#156, #157, #158)
    path("sca/tecnicos/", TecnicoListView.as_view(), name="sca-tecnicos-list"),
    path("sca/devices/", SyncDeviceListView.as_view(), name="sca-devices-list"),
    path(
        "sca/devices/<int:pk>/",
        SyncDeviceDetailView.as_view(),
        name="sca-devices-detail",
    ),
    path(
        "sca/sync-events/",
        SyncEventViewSet.as_view({"get": "list"}),
        name="sca-sync-events-list",
    ),
    path(
        "sca/sync-events/<int:pk>/",
        SyncEventViewSet.as_view({"get": "retrieve"}),
        name="sca-sync-events-detail",
    ),
    path("sca/conflicts/", ConflictLogViewSet.as_view({"get": "list"}), name="sca-conflicts-list"),
    path(
        "sca/conflicts/<int:pk>/",
        ConflictLogViewSet.as_view({"get": "retrieve"}),
        name="sca-conflicts-detail",
    ),
    path(
        "sca/conflicts/<int:pk>/resolver/",
        ConflictLogViewSet.as_view({"post": "resolver"}),
        name="sca-conflicts-resolver",
    ),
]
