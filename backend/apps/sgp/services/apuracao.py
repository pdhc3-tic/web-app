"""Apuração da quantidade realizada e do valor executado das Ações (SGP §5.4/§5.5).

A quantidade realizada de uma Ação depende da forma de apuração do Indicador:

- contagem de atividades: Atividades concluídas;
- soma de UFPAs: UFPAs distintas vinculadas às Atividades concluídas;
- soma de participantes: membros distintos vinculados às Atividades concluídas;
- manual: valor lançado pela UGP, que o sistema nunca recalcula.

As expressões de quantidade aceitam um filtro sobre as Atividades (escopo
territorial, território, período) para que o painel, a exportação e a visão por
Indicador apurem só o que o usuário enxerga, com a mesma regra do campo
materializado. O valor executado é sempre da Ação inteira (SGP §5.5).
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Callable, Iterable

from django.apps import apps
from django.db import connection, transaction
from django.db.models import (
    Case,
    Count,
    DecimalField,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from apps.sgp.models import Activity, WorkPlanAcao
from apps.sgp.models.indicator import (
    FORMA_CONTAGEM_ATIVIDADES,
    FORMA_MANUAL,
    FORMA_SOMA_PARTICIPANTES,
    FORMA_SOMA_UFPAS,
)
from apps.sgp.services.workplan_access import activity_scope_for_user

# Recebe o prefixo do caminho até Activity ("" ou "activity__", como em
# `activity_scope_for_user`) e devolve o Q das Atividades que entram na conta.
FiltroAtividades = Callable[[str], Q]

# Formas por soma de participantes distintos: tabela de vínculo com a
# Atividade e coluna contada.
_VINCULOS_POR_FORMA = {
    FORMA_SOMA_UFPAS: (Activity.upfs_participantes.through, "upf_id"),
    FORMA_SOMA_PARTICIPANTES: (Activity.membros_participantes.through, "membrofamilia_id"),
}

FORMAS_RECALCULADAS = (FORMA_CONTAGEM_ATIVIDADES, *_VINCULOS_POR_FORMA)


@dataclass(frozen=True)
class RecorteAtividades:
    """Território e período pedidos explicitamente sobre as Atividades apuradas.
    O período vale pela data de término da Atividade."""

    territorio_id: int | None = None
    periodo_inicio: date | None = None
    periodo_fim: date | None = None

    @property
    def vazio(self) -> bool:
        return self.territorio_id is None and self.periodo_inicio is None and self.periodo_fim is None

    def q(self, prefixo: str) -> Q:
        q = Q()
        if self.territorio_id is not None:
            q &= Q(**{f"{prefixo}municipio__territory_id": self.territorio_id})
        if self.periodo_inicio is not None:
            q &= Q(**{f"{prefixo}data_fim__date__gte": self.periodo_inicio})
        if self.periodo_fim is not None:
            q &= Q(**{f"{prefixo}data_fim__date__lte": self.periodo_fim})
        return q


def filtro_de_atividades(
    user=None, recorte: RecorteAtividades = RecorteAtividades()
) -> FiltroAtividades | None:
    """Escopo territorial do usuário somado ao recorte pedido; None quando nada
    restringe (visão global, sem recorte). Sem usuário (Power BI), só o recorte."""
    com_escopo = user is not None and activity_scope_for_user(user) is not None
    if not com_escopo and recorte.vazio:
        return None

    def filtro(prefixo: str) -> Q:
        q = recorte.q(prefixo)
        if com_escopo:
            q &= activity_scope_for_user(user, prefix=prefixo)
        return q

    return filtro


def _concluidas(prefixo: str, filtro: FiltroAtividades | None) -> Q:
    q = Q(**{f"{prefixo}status": "concluido", f"{prefixo}ativo": True})
    return q & filtro(prefixo) if filtro else q


def _linhas_apuradas(forma: str, filtro: FiltroAtividades | None):
    """O que uma forma calculada conta: as linhas (Atividades concluídas ou os
    vínculos delas), o prefixo até a Atividade e o agregado."""
    if forma == FORMA_CONTAGEM_ATIVIDADES:
        return Activity.all_objects.filter(_concluidas("", filtro)), "", Count("pk")
    if forma in _VINCULOS_POR_FORMA:
        through, campo = _VINCULOS_POR_FORMA[forma]
        vinculos = through.objects.filter(_concluidas("activity__", filtro))
        return vinculos, "activity__", Count(campo, distinct=True)
    raise ValueError(f"Forma de apuração sem cálculo automático: {forma}")


def _por_acao(queryset, campo_acao: str, agregado, output_field) -> Coalesce:
    return Coalesce(
        Subquery(
            queryset.filter(**{campo_acao: OuterRef("pk")})
            .order_by()
            .values(campo_acao)
            .annotate(total=agregado)
            .values("total")[:1],
            output_field=output_field,
        ),
        Value(0, output_field=output_field),
    )


def expressao_por_forma(forma: str, filtro: FiltroAtividades | None = None):
    """Quantidade realizada de uma Ação (via OuterRef) para uma forma calculada."""
    linhas, prefixo, agregado = _linhas_apuradas(forma, filtro)
    return _por_acao(linhas, f"{prefixo}acao_id", agregado, IntegerField())


def expressao_quantidade_realizada(filtro: FiltroAtividades | None = None) -> Case:
    """Quantidade realizada de cada Ação num queryset de WorkPlanAcao, conforme
    o Indicador. Na forma manual vale o número lançado pela UGP, que não tem
    recorte territorial."""
    return Case(
        *[
            When(indicador__forma_apuracao=forma, then=expressao_por_forma(forma, filtro))
            for forma in FORMAS_RECALCULADAS
        ],
        default=F("quantidade_realizada"),
        output_field=IntegerField(),
    )


# Recebe o prefixo do caminho até Activity e devolve as expressões que formam
# a chave de cada grupo (ex.: território; ano e fatia do período).
ChavesDeGrupo = Callable[[str], dict]


def realizado_agrupado(
    acoes: Iterable[WorkPlanAcao],
    chaves: ChavesDeGrupo,
    filtro: FiltroAtividades | None = None,
) -> dict[int, dict[tuple, int]]:
    """Realizado de cada Ação (chave: pk) por grupo de Atividades, nas formas
    calculadas, com a mesma contagem distinta do total. A forma manual não tem
    Atividade de origem e fica de fora, assim como grupos com chave nula."""
    ids_por_forma: dict[str, list[int]] = defaultdict(list)
    for acao in acoes:
        if acao.indicador.forma_apuracao in FORMAS_RECALCULADAS:
            ids_por_forma[acao.indicador.forma_apuracao].append(acao.pk)

    por_acao: dict[int, dict[tuple, int]] = defaultdict(dict)
    for forma, ids in ids_por_forma.items():
        linhas, prefixo, agregado = _linhas_apuradas(forma, filtro)
        expressoes = chaves(prefixo)
        consulta = (
            linhas.filter(**{f"{prefixo}acao_id__in": ids})
            .values(id_acao=F(f"{prefixo}acao_id"), **expressoes)
            .annotate(total=agregado)
            .order_by()
        )
        for linha in consulta:
            chave = tuple(linha[nome] for nome in expressoes)
            if None not in chave:
                por_acao[linha["id_acao"]][chave] = linha["total"]
    return por_acao


def expressao_valor_executado() -> Coalesce:
    """Soma do valor pago nas demandas concluídas das Atividades ativas da Ação.

    O SGD é lido pelo registro de apps (sem import) porque é ele que depende do
    SGP, não o contrário."""
    DemandRequest = apps.get_model("sgd", "DemandRequest")
    return _por_acao(
        DemandRequest.objects.filter(
            demanda__status="concluida",
            demanda__activity__ativo=True,
            valor_pago__isnull=False,
        ),
        "demanda__activity__acao_id",
        Sum("valor_pago"),
        DecimalField(max_digits=14, decimal_places=2),
    )


@contextmanager
def _leitura_total_do_sgd():
    """`sgd_demand` tem RLS pelo papel da sessão: quem recalcula a partir de um
    ADT, de uma task ou de um comando veria só parte das demandas (ou nenhuma).
    O valor executado é da Ação, não de quem olha, então a leitura sobe para
    visão total só durante o recálculo e o papel anterior volta em seguida.

    `set_config(..., true)` vale até o fim da transação externa, e não só do
    savepoint, por isso o papel é restaurado explicitamente; se o bloco falhar,
    o rollback do savepoint já desfaz a troca."""
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.user_role', true)")
        anterior = cursor.fetchone()[0] or ""
        cursor.execute("SELECT set_config('app.user_role', 'super-admin', true)")
        yield
        cursor.execute("SELECT set_config('app.user_role', %s, true)", [anterior])


def recalcular_valor_executado(acao_ids: Iterable[int]) -> None:
    ids = {pk for pk in acao_ids if pk is not None}
    if not ids:
        return
    with _leitura_total_do_sgd():
        WorkPlanAcao.objects.filter(pk__in=ids).update(valor_executado=expressao_valor_executado())


def recalcular_quantidade_realizada(acao_ids: Iterable[int]) -> None:
    """Regrava a quantidade realizada materializada das Ações informadas.

    Um UPDATE por forma: o UPDATE não aceita o JOIN com o Indicador que a
    expressão com `Case` precisaria."""
    ids = {pk for pk in acao_ids if pk is not None}
    if not ids:
        return
    por_forma: dict[str, list[int]] = defaultdict(list)
    for pk, forma in WorkPlanAcao.objects.filter(pk__in=ids).values_list(
        "pk", "indicador__forma_apuracao"
    ):
        if forma != FORMA_MANUAL:
            por_forma[forma].append(pk)
    for forma, pks in por_forma.items():
        WorkPlanAcao.objects.filter(pk__in=pks).update(
            quantidade_realizada=expressao_por_forma(forma)
        )


def valores_esperados() -> list[WorkPlanAcao]:
    """Ações com a quantidade (`_esperado`) e o valor executado
    (`_valor_esperado`) calculados agora, ao lado dos materializados, para
    reconciliação. Na forma manual a quantidade esperada é a própria lançada."""
    with _leitura_total_do_sgd():
        return list(
            WorkPlanAcao.objects.select_related("indicador").annotate(
                _esperado=expressao_quantidade_realizada(),
                _valor_esperado=expressao_valor_executado(),
            )
        )
