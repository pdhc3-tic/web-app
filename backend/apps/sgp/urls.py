from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ComunidadeViewSet, MembroViewSet, UPFViewSet

router = DefaultRouter()
router.register("upfs", UPFViewSet)
router.register('comunidades', ComunidadeViewSet, basename='comunidade')

comunidade_list = ComunidadeViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

urlpatterns = router.urls + [
    path(
        "upfs/<int:upf_pk>/membros/",
        MembroViewSet.as_view(
            {"get": "list", "post": "create"}
        ),
        name="upf-membros-list",
    ),
    path(
        "upfs/<int:upf_pk>/membros/<int:pk>/",
        MembroViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="upf-membros-detail",
    ),
    path(
        'municipios/<int:municipio_id>/comunidades/',
        comunidade_list,
        name='comunidade-list-by-municipio',
    ),
]
