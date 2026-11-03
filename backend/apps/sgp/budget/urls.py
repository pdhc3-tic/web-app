from django.urls import path

from .views import (
    BudgetAllocationViewSet,
    BudgetPainelView,
    BudgetRubricaListView,
    RemanejamentoView,
    SaldoConsultaView,
)

urlpatterns = [
    path(
        "sgp/metas/<int:meta_pk>/orcamento/alocacoes/",
        BudgetAllocationViewSet.as_view({"post": "create"}),
        name="budget-alocacoes-create",
    ),
    path(
        "sgp/orcamento/alocacoes/<int:pk>/",
        BudgetAllocationViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="budget-alocacoes-detail",
    ),
    path(
        "sgp/orcamento/alocacoes/<int:pk>/transacoes/",
        BudgetAllocationViewSet.as_view({"get": "transacoes"}),
        name="budget-alocacoes-transacoes",
    ),
    path(
        "sgp/orcamento/saldo/",
        SaldoConsultaView.as_view(),
        name="budget-saldo",
    ),
    path(
        "sgp/orcamento/remanejamentos/",
        RemanejamentoView.as_view(),
        name="budget-remanejamentos",
    ),
    path(
        "sgp/orcamento/painel/",
        BudgetPainelView.as_view(),
        name="budget-painel",
    ),
    path(
        "sgp/rubricas/",
        BudgetRubricaListView.as_view(),
        name="budget-rubricas",
    ),
]
