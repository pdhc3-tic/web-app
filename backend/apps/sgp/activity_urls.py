"""
URLs das rotas de Atividades do SGP.
Montado em api/v1/sgp/ no setup/urls.py.

Endpoints resultantes:
    GET/POST    /api/v1/sgp/atividades/
    GET         /api/v1/sgp/atividades/calendario/
    GET/PATCH/PUT/DELETE /api/v1/sgp/atividades/{id}/
    GET         /api/v1/sgp/atividades/{id}/fotos/
    POST        /api/v1/sgp/atividades/{id}/fotos/upload-url/
    POST        /api/v1/sgp/atividades/{id}/fotos/confirm/
    DELETE      /api/v1/sgp/atividades/{id}/fotos/{foto_id}/
    PATCH       /api/v1/sgp/atividades/{id}/fotos/reordenar/
    GET         /api/v1/sgp/atividades/{id}/documentos/
    POST        /api/v1/sgp/atividades/{id}/documentos/upload-url/
    POST        /api/v1/sgp/atividades/{id}/documentos/confirm/
    GET         /api/v1/sgp/atividades/{id}/documentos/{doc_id}/download/
    DELETE      /api/v1/sgp/atividades/{id}/documentos/{doc_id}/
"""
from rest_framework.routers import DefaultRouter

from .views import ActivityViewSet

router = DefaultRouter()
router.register("atividades", ActivityViewSet, basename="atividade")

urlpatterns = router.urls
