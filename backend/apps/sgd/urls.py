from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArloFieldMappingViewSet,
    ArloViewSet,
    DemandIndividualLimitViewSet,
    DemandTypeRubricaMappingViewSet,
    DemandViewSet,
    CustoPorAtividadeView,
    PainelRubricasView,
    RemanejamentoViewSet,
    SaldoConsultaView,
    SgdDashboardView,
    SimularDiariasView,
)

router = DefaultRouter()
router.register("demandas", DemandViewSet, basename="demanda")
router.register("arlo", ArloViewSet, basename="arlo")
router.register("remanejamentos", RemanejamentoViewSet, basename="remanejamento")
router.register("config/arlo-mapping", ArloFieldMappingViewSet, basename="arlo-mapping")
router.register("config/tipo-rubrica", DemandTypeRubricaMappingViewSet, basename="tipo-rubrica")
router.register("limites-individuais", DemandIndividualLimitViewSet, basename="demanda-limite-individual")

urlpatterns = [
    path("sgd/", include(router.urls)),
    path("sgd/painel/rubricas/", PainelRubricasView.as_view(), name="sgd-painel-rubricas"),
    path("sgd/relatorios/custo-por-atividade/", CustoPorAtividadeView.as_view(), name="sgd-custo-por-atividade"),
    path("sgd/saldo/", SaldoConsultaView.as_view(), name="sgd-saldo"),
    path("sgd/dashboard/", SgdDashboardView.as_view(), name="sgd-dashboard"),
    path("sgd/config/diarias/simular/", SimularDiariasView.as_view(), name="sgd-diarias-simular"),
]
