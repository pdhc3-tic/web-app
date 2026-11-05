from django.urls import path

from .views import (
    BudgetAlertListView,
    BudgetPainelView,
    BudgetPoolViewSet,
    BudgetRubricaListView,
    MeuExtratoView,
    MeuSaldoView,
    RemanejamentoSimulacaoView,
    RemanejamentoView,
    SaldoConsultaView,
    SpendingLimitViewSet,
)

urlpatterns = [
    path(
        "sgp/orcamento/pools/",
        BudgetPoolViewSet.as_view({"post": "create"}),
        name="budget-pools-create",
    ),
    path(
        "sgp/orcamento/pools/<int:pk>/",
        BudgetPoolViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="budget-pools-detail",
    ),
    path(
        "sgp/orcamento/pools/<int:pk>/transacoes/",
        BudgetPoolViewSet.as_view({"get": "transacoes"}),
        name="budget-pools-transacoes",
    ),
    # Alias das três rotas acima, enquanto o front migra.
    path(
        "sgp/metas/<int:meta_pk>/orcamento/alocacoes/",
        BudgetPoolViewSet.as_view({"post": "create"}),
        name="budget-alocacoes-create",
    ),
    path(
        "sgp/orcamento/alocacoes/<int:pk>/",
        BudgetPoolViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="budget-alocacoes-detail",
    ),
    path(
        "sgp/orcamento/alocacoes/<int:pk>/transacoes/",
        BudgetPoolViewSet.as_view({"get": "transacoes"}),
        name="budget-alocacoes-transacoes",
    ),
    path(
        "sgp/orcamento/limites/",
        SpendingLimitViewSet.as_view({"get": "list", "post": "create"}),
        name="budget-limites",
    ),
    path(
        "sgp/orcamento/limites/<int:pk>/",
        SpendingLimitViewSet.as_view({"patch": "partial_update"}),
        name="budget-limites-detail",
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
        "sgp/orcamento/remanejamentos/simular/",
        RemanejamentoSimulacaoView.as_view(),
        name="budget-remanejamentos-simular",
    ),
    path(
        "sgp/orcamento/meu-saldo/",
        MeuSaldoView.as_view(),
        name="budget-meu-saldo",
    ),
    path(
        "sgp/orcamento/meu-saldo/<slug:rubrica>/extrato/",
        MeuExtratoView.as_view(),
        name="budget-meu-extrato",
    ),
    path(
        "sgp/orcamento/alertas/",
        BudgetAlertListView.as_view(),
        name="budget-alertas",
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
