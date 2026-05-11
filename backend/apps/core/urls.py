from rest_framework.routers import DefaultRouter

from .views import (
    RoleViewSet,
    StateViewSet,
    TerritoryViewSet,
    MunicipalityViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register("roles", RoleViewSet)
router.register("states", StateViewSet)
router.register("territories", TerritoryViewSet)
router.register("municipalities", MunicipalityViewSet)
router.register("users", UserViewSet)

urlpatterns = router.urls
