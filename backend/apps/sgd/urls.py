from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArloFieldMappingViewSet,
    ArloViewSet,
    CustoPorAtividadeView,
    DemandIndividualLimitViewSet,
    DemandViewSet,
    PainelRubricasView,
    RemanejamentoViewSet,
    SaldoConsultaView,
)

router = DefaultRouter()
router.register("demandas", DemandViewSet, basename="demanda")
router.register("arlo", ArloViewSet, basename="arlo")
router.register("remanejamentos", RemanejamentoViewSet, basename="remanejamento")
router.register("config/arlo-mapping", ArloFieldMappingViewSet, basename="arlo-mapping")
router.register("limites-individuais", DemandIndividualLimitViewSet, basename="demanda-limite-individual")

urlpatterns = [
    path("sgd/", include(router.urls)),
    path("sgd/painel/rubricas/", PainelRubricasView.as_view(), name="sgd-painel-rubricas"),
    path("sgd/relatorios/custo-por-atividade/", CustoPorAtividadeView.as_view(), name="sgd-custo-por-atividade"),
    path("sgd/saldo/", SaldoConsultaView.as_view(), name="sgd-saldo"),
]
