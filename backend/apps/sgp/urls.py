from rest_framework.routers import DefaultRouter

from .views import UPFViewSet

router = DefaultRouter()
router.register("upfs", UPFViewSet)

urlpatterns = router.urls
