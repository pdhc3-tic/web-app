from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArloFieldMappingViewSet,
    ArloViewSet,
    DemandIndividualLimitViewSet,
    TipoRubricaViewSet,
    TipoSolicitacaoViewSet,
    DemandViewSet,
    FaixaDestinoDiariaViewSet,
    CustoPorAtividadeView,
    OpcoesUsuariosView,
    PainelRubricasView,
    ParametrosDiariasView,
    RemanejamentoViewSet,
    SaldoConsultaView,
    SgdDashboardView,
    SimularDiariasView,
    TabelaDiariaViewSet,
)

router = DefaultRouter()
router.register("demandas", DemandViewSet, basename="demanda")
router.register("arlo", ArloViewSet, basename="arlo")
router.register("remanejamentos", RemanejamentoViewSet, basename="remanejamento")
router.register("config/arlo-mapping", ArloFieldMappingViewSet, basename="arlo-mapping")
router.register("config/tipo-rubrica", TipoRubricaViewSet, basename="tipo-rubrica")
router.register("config/tipos-solicitacao", TipoSolicitacaoViewSet, basename="tipo-solicitacao")
router.register("config/diarias/faixas", FaixaDestinoDiariaViewSet, basename="diaria-faixa")
router.register("config/diarias/tabela", TabelaDiariaViewSet, basename="diaria-tabela")
router.register("limites-individuais", DemandIndividualLimitViewSet, basename="demanda-limite-individual")

urlpatterns = [
    path("sgd/", include(router.urls)),
    path("sgd/painel/rubricas/", PainelRubricasView.as_view(), name="sgd-painel-rubricas"),
    path("sgd/relatorios/custo-por-atividade/", CustoPorAtividadeView.as_view(), name="sgd-custo-por-atividade"),
    path("sgd/saldo/", SaldoConsultaView.as_view(), name="sgd-saldo"),
    path("sgd/opcoes/usuarios/", OpcoesUsuariosView.as_view(), name="sgd-opcoes-usuarios"),
    path("sgd/dashboard/", SgdDashboardView.as_view(), name="sgd-dashboard"),
    path(
        "sgd/config/diarias/parametros/", ParametrosDiariasView.as_view(), name="sgd-diarias-parametros",
    ),
    path("sgd/config/diarias/simular/", SimularDiariasView.as_view(), name="sgd-diarias-simular"),
]
