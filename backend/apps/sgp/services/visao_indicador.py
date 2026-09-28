"""Visão consolidada por Indicador (SGP §5.4/§5.6, RF22).

Soma planejado e realizado de todas as Ações que referenciam o mesmo
Indicador, inclusive de Metas diferentes, com quebra por Meta, Submeta e
território, no escopo territorial do usuário.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Count, F, Q

from apps.core.models import Territory
from apps.sgp.models import Activity, WorkPlanAcao
from apps.sgp.models.indicator import (
    FORMA_CONTAGEM_ATIVIDADES,
    FORMA_SOMA_PARTICIPANTES,
    FORMA_SOMA_UFPAS,
)
from apps.sgp.services.apuracao import FiltroAtividades, expressao_quantidade_realizada
from apps.sgp.services.workplan_access import filter_workplan_actions_for_user
from apps.sgp.services.workplan_dashboard import filtro_de_escopo

ZERO = Decimal("0")


def _filtro(user, territorio_id, periodo_inicio, periodo_fim) -> FiltroAtividades:
    escopo = filtro_de_escopo(user)

    def filtro(prefixo: str) -> Q:
        q = Q()
        if escopo is not None:
            q &= escopo(prefixo)
        if territorio_id is not None:
            q &= Q(**{f"{prefixo}municipio__territory_id": territorio_id})
        if periodo_inicio is not None:
            q &= Q(**{f"{prefixo}data_fim__date__gte": periodo_inicio})
        if periodo_fim is not None:
            q &= Q(**{f"{prefixo}data_fim__date__lte": periodo_fim})
        return q

    return filtro


def _percentual(parte: Decimal, total: Decimal) -> Decimal:
    if total <= ZERO:
        return ZERO
    return (Decimal(parte) / total * 100).quantize(Decimal("0.01"))


def _realizado_por_territorio(acoes, filtro: FiltroAtividades) -> dict[int, dict[int, int]]:
    """Realizado de cada Ação (chave: pk) por território, nas formas calculadas.
    A forma manual não tem recorte territorial e fica de fora."""
    ids_por_forma: dict[str, list[int]] = defaultdict(list)
    for acao in acoes:
        ids_por_forma[acao.indicador.forma_apuracao].append(acao.pk)

    via_vinculo = Q(activity__status="concluido", activity__ativo=True) & filtro("activity__")
    consultas = []
    if ids_por_forma[FORMA_CONTAGEM_ATIVIDADES]:
        consultas.append(
            Activity.all_objects.filter(
                Q(status="concluido", ativo=True) & filtro(""),
                acao_id__in=ids_por_forma[FORMA_CONTAGEM_ATIVIDADES],
            )
            .values(acao=F("acao_id"), territorio=F("municipio__territory_id"))
            .annotate(total=Count("pk"))
        )
    for forma, through, campo in (
        (FORMA_SOMA_UFPAS, Activity.upfs_participantes.through, "upf_id"),
        (FORMA_SOMA_PARTICIPANTES, Activity.membros_participantes.through, "membrofamilia_id"),
    ):
        if ids_por_forma[forma]:
            consultas.append(
                through.objects.filter(via_vinculo, activity__acao_id__in=ids_por_forma[forma])
                .values(acao=F("activity__acao_id"), territorio=F("activity__municipio__territory_id"))
                .annotate(total=Count(campo, distinct=True))
            )

    por_acao: dict[int, dict[int, int]] = defaultdict(dict)
    for consulta in consultas:
        for linha in consulta.order_by():
            if linha["territorio"] is not None:
                por_acao[linha["acao"]][linha["territorio"]] = linha["total"]
    return por_acao


def visao_por_indicador(
    user,
    *,
    territorio_id: int | None = None,
    meta_id: int | None = None,
    indicador_id: int | None = None,
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
) -> list[dict]:
    filtro = _filtro(user, territorio_id, periodo_inicio, periodo_fim)
    acoes = filter_workplan_actions_for_user(
        WorkPlanAcao.objects.select_related("meta", "submeta", "indicador"), user
    )
    if meta_id is not None:
        acoes = acoes.filter(meta_id=meta_id)
    if indicador_id is not None:
        acoes = acoes.filter(indicador_id=indicador_id)
    acoes = list(acoes.annotate(_realizado=expressao_quantidade_realizada(filtro)).order_by(
        "indicador__codigo", "meta__numero", "numero"
    ))
    realizado_territorial = _realizado_por_territorio(acoes, filtro)

    grupos: dict[int, dict] = {}
    for acao in acoes:
        grupo = grupos.setdefault(acao.indicador_id, {
            "indicador": acao.indicador,
            "planejado": ZERO,
            "realizado": ZERO,
            "por_meta": {},
            "por_submeta": {},
            "por_territorio": defaultdict(int),
        })
        planejado = Decimal(acao.quantidade_planejada)
        realizado = Decimal(acao._realizado)
        grupo["planejado"] += planejado
        grupo["realizado"] += realizado
        for chave, alvo in (("por_meta", acao.meta), ("por_submeta", acao.submeta)):
            no = grupo[chave].setdefault(alvo.pk, {"alvo": alvo, "planejado": ZERO, "realizado": ZERO})
            no["planejado"] += planejado
            no["realizado"] += realizado
        for territorio, total in realizado_territorial.get(acao.pk, {}).items():
            grupo["por_territorio"][territorio] += total

    nomes = dict(
        Territory.objects.filter(
            pk__in={t for g in grupos.values() for t in g["por_territorio"]}
        ).values_list("pk", "nome")
    )

    def no(alvo_dict, campos):
        return {
            **campos,
            "quantidade_planejada": alvo_dict["planejado"],
            "quantidade_realizada": alvo_dict["realizado"],
            "percentual_realizado": _percentual(alvo_dict["realizado"], alvo_dict["planejado"]),
        }

    return [
        {
            "indicador": grupo["indicador"],
            "quantidade_planejada": grupo["planejado"],
            "quantidade_realizada": grupo["realizado"],
            "percentual_realizado": _percentual(grupo["realizado"], grupo["planejado"]),
            "por_meta": [
                no(item, {"id": item["alvo"].pk, "numero": item["alvo"].numero, "titulo": item["alvo"].titulo})
                for item in grupo["por_meta"].values()
            ],
            "por_submeta": [
                no(item, {"id": item["alvo"].pk, "numero": item["alvo"].numero, "titulo": item["alvo"].titulo})
                for item in grupo["por_submeta"].values()
            ],
            "por_territorio": [
                {"id": territorio, "nome": nomes.get(territorio, ""), "quantidade_realizada": total}
                for territorio, total in sorted(
                    grupo["por_territorio"].items(), key=lambda item: nomes.get(item[0], "")
                )
            ],
        }
        for grupo in grupos.values()
    ]
