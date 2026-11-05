"""Prepara o ledger para ficar imutável. `demanda_id` guardava o pk da solicitação: ele passa para
`demand_request_id`, e `demanda_id` fica com o pk da demanda. Os saldos são preenchidos de trás para
frente, a partir do saldo materializado, o que garante `saldo_posterior` da última linha igual a ele
mesmo em dados criados sem passar pelo motor."""
from decimal import Decimal

from django.db import migrations
from django.db.models import F

ZERO = Decimal("0")
LOTE = 500


def _efeito_no_saldo(tipo, valor):
    if tipo in ("reserva", "ajuste"):
        return -valor
    if tipo == "execucao":
        return ZERO
    return valor


def _preencher_saldos(BudgetTransaction, *, filtro, saldo_atual) -> None:
    posterior = saldo_atual
    linhas = list(BudgetTransaction.objects.filter(**filtro).order_by("-pk"))
    for linha in linhas:
        linha.saldo_posterior = posterior
        linha.saldo_anterior = posterior - _efeito_no_saldo(linha.tipo, linha.valor)
        posterior = linha.saldo_anterior
    BudgetTransaction.objects.bulk_update(linhas, ["saldo_anterior", "saldo_posterior"], batch_size=LOTE)


def _separar_solicitacao_da_demanda(BudgetTransaction, DemandRequest) -> None:
    demanda_da_solicitacao = dict(DemandRequest.objects.order_by().values_list("pk", "demanda_id"))
    linhas = list(BudgetTransaction.objects.exclude(demanda_id=None))
    for linha in linhas:
        chave = linha.demanda_id
        demanda = demanda_da_solicitacao.get(int(chave)) if chave.isdigit() else None
        linha.demand_request_id = chave
        linha.demanda_id = str(demanda) if demanda is not None else None
    BudgetTransaction.objects.bulk_update(linhas, ["demand_request_id", "demanda_id"], batch_size=LOTE)


def _exigir_saldo_nao_negativo(BudgetPool) -> None:
    negativos = list(
        BudgetPool.objects.filter(valor_alocado__lt=F("valor_comprometido") + F("valor_executado"))
        .order_by("pk").values_list("pk", flat=True)
    )
    if negativos:
        raise RuntimeError(
            f"Pools com comprometido e executado acima do alocado: {negativos}. "
            "Corrija antes de migrar: a constraint de saldo não negativo recusaria esses dados."
        )


def preencher(apps, schema_editor):
    BudgetPool = apps.get_model("sgp", "BudgetPool")
    BudgetTransaction = apps.get_model("sgp", "BudgetTransaction")
    DemandRequest = apps.get_model("sgd", "DemandRequest")
    SpendingLimit = apps.get_model("sgp", "SpendingLimit")

    _exigir_saldo_nao_negativo(BudgetPool)
    _separar_solicitacao_da_demanda(BudgetTransaction, DemandRequest)
    for pool in BudgetPool.objects.order_by("pk"):
        _preencher_saldos(
            BudgetTransaction, filtro={"pool_id": pool.pk},
            saldo_atual=pool.valor_alocado - pool.valor_comprometido - pool.valor_executado,
        )
    for limite in SpendingLimit.objects.filter(escopo="individual").order_by("pk"):
        _preencher_saldos(
            BudgetTransaction, filtro={"spending_limit_id": limite.pk},
            saldo_atual=limite.valor_limite - limite.valor_comprometido - limite.valor_executado,
        )


def desfazer(apps, schema_editor):
    """Os saldos somem com as colunas: só a chave da reserva precisa voltar para `demanda_id`."""
    BudgetTransaction = apps.get_model("sgp", "BudgetTransaction")
    BudgetTransaction.objects.exclude(demand_request_id=None).update(demanda_id=F("demand_request_id"))


class Migration(migrations.Migration):

    dependencies = [
        ('sgd', '0018_preencher_totais_das_demandas'),
        ('sgp', '0014_ledger_esquema'),
    ]

    operations = [
        migrations.RunPython(preencher, desfazer),
    ]
