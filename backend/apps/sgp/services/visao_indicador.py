"""Visão consolidada por Indicador (SGP §5.4/§5.6, RF22).

Soma planejado e realizado de todas as Ações que referenciam o mesmo
Indicador, inclusive de Metas diferentes, com quebra por Meta, Submeta e
território, no escopo territorial do usuário.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from apps.core.models import Territory
from apps.sgp.models import WorkPlanAcao
from apps.sgp.models.indicator import FORMA_MANUAL
from apps.sgp.models.workplan import arredondar, percentual
from apps.sgp.services.apuracao import (
    RecorteAtividades,
    expressao_quantidade_realizada,
    filtro_de_atividades,
    realizado_por_territorio,
)
from apps.sgp.services.workplan_access import filter_workplan_actions_for_user

ZERO = Decimal("0")


@dataclass
class _Soma:
    """Planejado e realizado acumulados de um nó (Indicador, Meta ou Submeta)."""

    alvo: object = None
    planejado: Decimal = ZERO
    realizado: Decimal = ZERO

    def somar(self, acao: WorkPlanAcao) -> None:
        self.planejado += Decimal(acao.quantidade_planejada)
        self.realizado += Decimal(acao._realizado)


def _quantidades(soma: _Soma, sem_realizado: bool) -> dict:
    realizado = None if sem_realizado else soma.realizado
    return {
        "quantidade_planejada": soma.planejado,
        "quantidade_realizada": realizado,
        "percentual_realizado": (
            None if realizado is None else arredondar(percentual(realizado, soma.planejado))
        ),
    }


def _quebra(somas: dict[int, _Soma], sem_realizado: bool) -> list[dict]:
    return [
        {
            "id": soma.alvo.pk,
            "numero": soma.alvo.numero,
            "titulo": soma.alvo.titulo,
            **_quantidades(soma, sem_realizado),
        }
        for soma in somas.values()
    ]


def visao_por_indicador(
    user,
    *,
    recorte: RecorteAtividades = RecorteAtividades(),
    meta_id: int | None = None,
    indicador_id: int | None = None,
) -> list[dict]:
    filtro = filtro_de_atividades(user, recorte)
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
    realizado_territorial = realizado_por_territorio(acoes, filtro)

    grupos: dict[int, dict] = {}
    for acao in acoes:
        grupo = grupos.setdefault(acao.indicador_id, {
            "indicador": acao.indicador,
            "total": _Soma(),
            "por_meta": {},
            "por_submeta": {},
            "por_territorio": defaultdict(int),
        })
        grupo["total"].somar(acao)
        grupo["por_meta"].setdefault(acao.meta_id, _Soma(alvo=acao.meta)).somar(acao)
        grupo["por_submeta"].setdefault(acao.submeta_id, _Soma(alvo=acao.submeta)).somar(acao)
        for territorio, total in realizado_territorial.get(acao.pk, {}).items():
            grupo["por_territorio"][territorio] += total

    nomes = dict(
        Territory.objects.filter(
            pk__in={t for g in grupos.values() for t in g["por_territorio"]}
        ).values_list("pk", "nome")
    )

    visao = []
    for grupo in grupos.values():
        # Lançamento manual é um número único por Ação, sem território nem data:
        # sob recorte explícito não há como dizer quanto dele cabe no recorte.
        sem_realizado = not recorte.vazio and grupo["indicador"].forma_apuracao == FORMA_MANUAL
        visao.append({
            "indicador": grupo["indicador"],
            **_quantidades(grupo["total"], sem_realizado),
            "por_meta": _quebra(grupo["por_meta"], sem_realizado),
            "por_submeta": _quebra(grupo["por_submeta"], sem_realizado),
            "por_territorio": [
                {"id": territorio, "nome": nomes.get(territorio, ""), "quantidade_realizada": total}
                for territorio, total in sorted(
                    grupo["por_territorio"].items(), key=lambda item: nomes.get(item[0], "")
                )
            ],
        })
    return visao
