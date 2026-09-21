from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DemandIndividualLimitViewSet, DemandViewSet, SaldoConsultaView

router = DefaultRouter()
router.register("demandas", DemandViewSet, basename="demanda")
router.register("limites-individuais", DemandIndividualLimitViewSet, basename="demanda-limite-individual")

urlpatterns = [
    path("sgd/", include(router.urls)),
    path("sgd/saldo/", SaldoConsultaView.as_view(), name="sgd-saldo"),
]
