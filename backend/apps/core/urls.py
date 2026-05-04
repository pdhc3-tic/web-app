from rest_framework.routers import DefaultRouter

from .views import ComunidadeViewSet, EstadoViewSet, MunicipioViewSet, TerritorioViewSet

router = DefaultRouter()
router.register("estados", EstadoViewSet)
router.register("territorios", TerritorioViewSet)
router.register("municipios", MunicipioViewSet)
router.register("comunidades", ComunidadeViewSet)

urlpatterns = router.urls
