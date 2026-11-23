from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import TEDDocumentoUploadURLView, TEDVersaoDetalheView, TEDVersaoListaView, TEDViewSet

router = SimpleRouter()
router.register("sgp/ted", TEDViewSet, basename="ted")

urlpatterns = [
    path("sgp/ted/documentos/upload-url/", TEDDocumentoUploadURLView.as_view(), name="ted-documento-upload-url"),
    path("sgp/ted/<int:ted_pk>/versoes/", TEDVersaoListaView.as_view(), name="ted-versoes"),
    path(
        "sgp/ted/<int:ted_pk>/versoes/<int:pk>/",
        TEDVersaoDetalheView.as_view(),
        name="ted-versao-detalhe",
    ),
] + router.urls
