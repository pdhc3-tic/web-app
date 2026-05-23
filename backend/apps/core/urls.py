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
    AuditLogListView
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
]
