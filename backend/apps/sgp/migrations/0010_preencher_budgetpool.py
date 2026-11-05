"""Agrega as alocações por rubrica e nível geográfico, sem a Meta, e reaponta o ledger e os
remanejamentos. Em arquivo próprio: o Postgres recusa ALTER TABLE na mesma transação que
atualizou FKs adiadas."""
from decimal import Decimal

from django.db import migrations
from django.db.models import Sum

ZERO = Decimal("0")
CAMPOS_DE_SALDO = ("valor_alocado", "valor_comprometido", "valor_executado")


def _somas_por_rubrica_e_nivel(modelo) -> dict:
    return {
        (linha["rubrica_id"], linha["nivel"]): tuple(linha[campo] or ZERO for campo in CAMPOS_DE_SALDO)
        for linha in modelo.objects.order_by().values("rubrica_id", "nivel").annotate(
            **{campo: Sum(campo) for campo in CAMPOS_DE_SALDO},
        )
    }


def _exigir_mesmas_somas(BudgetAllocation, BudgetPool) -> None:
    antes, depois = _somas_por_rubrica_e_nivel(BudgetAllocation), _somas_por_rubrica_e_nivel(BudgetPool)
    if antes != depois:
        raise RuntimeError(f"A soma por rubrica e nível mudou na migração: antes {antes}, depois {depois}.")


def _preencher_atividade_das_transacoes(BudgetTransaction, DemandRequest) -> None:
    """`demanda_id` guarda o pk da solicitação nas transações vindas do SGD."""
    por_solicitacao = dict(DemandRequest.objects.order_by().values_list("pk", "demanda__activity_id"))
    atualizadas = []
    for transacao in BudgetTransaction.objects.exclude(demanda_id=None).only("pk", "demanda_id"):
        if not transacao.demanda_id.isdigit():
            continue
        activity_id = por_solicitacao.get(int(transacao.demanda_id))
        if activity_id is not None:
            transacao.activity_id = activity_id
            atualizadas.append(transacao)
    BudgetTransaction.objects.bulk_update(atualizadas, ["activity"], batch_size=500)


def agregar(apps, schema_editor):
    BudgetAllocation = apps.get_model("sgp", "BudgetAllocation")
    BudgetPool = apps.get_model("sgp", "BudgetPool")
    BudgetTransaction = apps.get_model("sgp", "BudgetTransaction")
    BudgetTransfer = apps.get_model("sgp", "BudgetTransfer")
    DemandRequest = apps.get_model("sgd", "DemandRequest")

    grupos: dict[tuple, list] = {}
    for alocacao in BudgetAllocation.objects.order_by("pk"):
        # Território identifica o pool sozinho: com o estado na chave, o mesmo território
        # geraria duas linhas quando só uma das alocações informou o estado.
        estado_id = None if alocacao.nivel == "territorial" else alocacao.estado_id
        chave = (alocacao.rubrica_id, alocacao.nivel, estado_id, alocacao.territorio_id)
        grupos.setdefault(chave, []).append(alocacao)

    pool_da_alocacao = {}
    for (rubrica_id, nivel, estado_id, territorio_id), alocacoes in grupos.items():
        pool = BudgetPool.objects.create(
            rubrica_id=rubrica_id, nivel=nivel, estado_id=estado_id, territorio_id=territorio_id,
            valor_alocado=sum((a.valor_alocado for a in alocacoes), ZERO),
            valor_comprometido=sum((a.valor_comprometido for a in alocacoes), ZERO),
            valor_executado=sum((a.valor_executado for a in alocacoes), ZERO),
            # Uma reserva da UGP não recebe filhos: agregada a uma linha comum, deixa de ser reserva.
            reserva_ugp=all(a.reserva_ugp for a in alocacoes),
            criado_por_id=alocacoes[0].criado_por_id,
        )
        BudgetPool.objects.filter(pk=pool.pk).update(criado_em=alocacoes[0].criado_em)
        for alocacao in alocacoes:
            pool_da_alocacao[alocacao.pk] = pool.pk

    _exigir_mesmas_somas(BudgetAllocation, BudgetPool)

    for alocacao_id, pool_id in pool_da_alocacao.items():
        BudgetTransaction.objects.filter(allocation_id=alocacao_id).update(pool_id=pool_id)
        BudgetTransfer.objects.filter(allocation_origem_id=alocacao_id).update(pool_origem_id=pool_id)
        BudgetTransfer.objects.filter(allocation_destino_id=alocacao_id).update(pool_destino_id=pool_id)
    _preencher_atividade_das_transacoes(BudgetTransaction, DemandRequest)


def desagregar(apps, schema_editor):
    """Recria uma alocação por pool, preservando a soma por rubrica e nível. A divisão por Meta
    não existe mais: tudo volta para a primeira Meta do Plano de Trabalho."""
    BudgetAllocation = apps.get_model("sgp", "BudgetAllocation")
    BudgetPool = apps.get_model("sgp", "BudgetPool")
    BudgetTransaction = apps.get_model("sgp", "BudgetTransaction")
    BudgetTransfer = apps.get_model("sgp", "BudgetTransfer")
    WorkPlanMeta = apps.get_model("sgp", "WorkPlanMeta")

    if not BudgetPool.objects.exists():
        return
    meta = WorkPlanMeta.objects.order_by("numero", "pk").first()
    if meta is None:
        raise RuntimeError("Sem nenhuma Meta cadastrada, não há como recriar as alocações.")

    for pool in BudgetPool.objects.order_by("pk"):
        alocacao = BudgetAllocation.objects.create(
            meta=meta, rubrica_id=pool.rubrica_id, nivel=pool.nivel, estado_id=pool.estado_id,
            territorio_id=pool.territorio_id, valor_alocado=pool.valor_alocado,
            valor_comprometido=pool.valor_comprometido, valor_executado=pool.valor_executado,
            reserva_ugp=pool.reserva_ugp, criado_por_id=pool.criado_por_id,
        )
        BudgetAllocation.objects.filter(pk=alocacao.pk).update(criado_em=pool.criado_em)
        BudgetTransaction.objects.filter(pool_id=pool.pk).update(allocation_id=alocacao.pk)
        BudgetTransfer.objects.filter(pool_origem_id=pool.pk).update(allocation_origem_id=alocacao.pk)
        BudgetTransfer.objects.filter(pool_destino_id=pool.pk).update(allocation_destino_id=alocacao.pk)

    _exigir_mesmas_somas(BudgetAllocation, BudgetPool)


class Migration(migrations.Migration):

    dependencies = [
        ('sgd', '0018_preencher_totais_das_demandas'),
        ('sgp', '0009_budgetpool_esquema'),
    ]

    operations = [
        migrations.RunPython(agregar, desagregar),
    ]
