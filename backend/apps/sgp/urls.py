from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ComunidadeViewSet

router = DefaultRouter()
router.register('comunidades', ComunidadeViewSet, basename='comunidade')

comunidade_list = ComunidadeViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

urlpatterns = router.urls + [
    path(
        'municipios/<int:municipio_id>/comunidades/',
        comunidade_list,
        name='comunidade-list-by-municipio',
    ),
]
