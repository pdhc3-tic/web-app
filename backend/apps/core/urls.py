from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    RoleViewSet,
    StateViewSet,
    TerritoryViewSet,
    MunicipalityViewSet,
    UserViewSet,
    OrganizationViewSet,
    NotificationListView,
    NotificationMarkReadView,
    mark_all_read,
    unread_count,
    AuditLogListView,
    LocalStorageUploadView,
    GoogleCalendarConfigView,
    GoogleCalendarStatusView,
    SystemConfigListView,
    SystemConfigDetailView,
    PowerBITokenView,
    PowerBITokenRegenerateView,
)

router = DefaultRouter()
router.register("roles", RoleViewSet)
router.register("states", StateViewSet)
router.register("territories", TerritoryViewSet)
router.register("municipalities", MunicipalityViewSet)
router.register("users", UserViewSet)
router.register("organizations", OrganizationViewSet, basename="organization")

urlpatterns = router.urls + [
    path("notifications/me/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification-read"),
    path("notifications/mark-all-read/", mark_all_read, name="notification-mark-all-read"),
    path("notifications/me/unread-count/", unread_count, name="notification-unread-count"),
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),
    path("storage/local-upload/", LocalStorageUploadView.as_view(), name="local-storage-upload"),
    path(
        "core/config/google-calendar/",
        GoogleCalendarConfigView.as_view(),
        name="google-calendar-config",
    ),
    path(
        "core/config/google-calendar/status/",
        GoogleCalendarStatusView.as_view(),
        name="google-calendar-status",
    ),
    path("system-config/", SystemConfigListView.as_view(), name="system-config-list"),
    path("system-config/<str:chave>/", SystemConfigDetailView.as_view(), name="system-config-detail"),
    path("admin/power-bi-token/", PowerBITokenView.as_view(), name="power-bi-token"),
    path(
        "admin/power-bi-token/regenerar/",
        PowerBITokenRegenerateView.as_view(),
        name="power-bi-token-regenerate",
    ),
]
