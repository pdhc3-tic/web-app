from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AderenciaExportacaoView,
    AderenciaHistoricoView,
    AderenciaRecalculoView,
    AderenciaView,
    ComparativoDeVersoesView,
    ComposicaoPorRubricaView,
    CustoPorEntregaExportacaoView,
    CustoPorEntregaView,
    CurvaSView,
    ProjecoesView,
    RankingTerritorioExportacaoView,
    RankingTerritorioView,
    RastreabilidadeView,
    TEDDocumentoUploadURLView,
    TEDVersaoDetalheView,
    TEDVersaoListaView,
    TEDViewSet,
)

router = SimpleRouter()
router.register("sgp/ted", TEDViewSet, basename="ted")

urlpatterns = [
    path("sgp/ted/aderencia/", AderenciaView.as_view(), name="ted-aderencia"),
    path("sgp/ted/aderencia/exportar/", AderenciaExportacaoView.as_view(), name="ted-aderencia-exportar"),
    path("sgp/ted/aderencia/historico/", AderenciaHistoricoView.as_view(), name="ted-aderencia-historico"),
    path("sgp/ted/aderencia/recalcular/", AderenciaRecalculoView.as_view(), name="ted-aderencia-recalcular"),
    path("sgp/ted/custo-por-entrega/", CustoPorEntregaView.as_view(), name="ted-custo-por-entrega"),
    path(
        "sgp/ted/custo-por-entrega/exportar/", CustoPorEntregaExportacaoView.as_view(),
        name="ted-custo-exportar",
    ),
    path(
        "sgp/ted/custo-por-entrega/composicao/", ComposicaoPorRubricaView.as_view(),
        name="ted-custo-composicao",
    ),
    path("sgp/ted/rastreabilidade/", RastreabilidadeView.as_view(), name="ted-rastreabilidade"),
    path("sgp/ted/curva-s/", CurvaSView.as_view(), name="ted-curva-s"),
    path("sgp/ted/projecoes/", ProjecoesView.as_view(), name="ted-projecoes"),
    path("sgp/ted/ranking-territorios/", RankingTerritorioView.as_view(), name="ted-ranking-territorios"),
    path(
        "sgp/ted/ranking-territorios/exportar/", RankingTerritorioExportacaoView.as_view(),
        name="ted-ranking-territorios-exportar",
    ),
    path("sgp/ted/documentos/upload-url/", TEDDocumentoUploadURLView.as_view(), name="ted-documento-upload-url"),
    path("sgp/ted/<int:ted_pk>/versoes/", TEDVersaoListaView.as_view(), name="ted-versoes"),
    path(
        "sgp/ted/<int:ted_pk>/versoes/comparar/", ComparativoDeVersoesView.as_view(),
        name="ted-versoes-comparar",
    ),
    path(
        "sgp/ted/<int:ted_pk>/versoes/<int:pk>/",
        TEDVersaoDetalheView.as_view(),
        name="ted-versao-detalhe",
    ),
] + router.urls
