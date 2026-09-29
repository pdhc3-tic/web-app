"""Visão consolidada por Indicador (SGP §5.4/§5.6, RF22).

Soma planejado e realizado de todas as Ações que referenciam o mesmo
Indicador, inclusive de Metas diferentes, com quebra por Meta, Submeta,
território e período, no escopo territorial do usuário.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import F, IntegerField, Value
from django.db.models.functions import Cast, ExtractMonth, ExtractYear

from apps.core.models import Territory
from apps.sgp.models import WorkPlanAcao
from apps.sgp.models.indicator import FORMA_MANUAL
from apps.sgp.models.workplan import arredondar, percentual
from apps.sgp.services.apuracao import (
    RecorteAtividades,
    expressao_quantidade_realizada,
    filtro_de_atividades,
    realizado_agrupado,
)
from apps.sgp.services.workplan_access import filter_workplan_actions_for_user

ZERO = Decimal("0")


@dataclass(frozen=True)
class Granularidade:
    """Fatia do ano usada na quebra por período, pelo número de meses de cada
    fatia (1 = mês, 3 = trimestre...). O agrupamento é feito no banco, pela
    data de término da Atividade, para manter a contagem distinta de UFPAs e
    participantes dentro de cada fatia."""

    meses: int

    def __post_init__(self):
        if 12 % self.meses:
            raise ValueError("A fatia precisa dividir o ano em partes iguais.")

    def chaves(self, prefixo: str) -> dict:
        # EXTRACT devolve numeric no Postgres: o cast mantém a divisão inteira.
        ano = Cast(ExtractYear(f"{prefixo}data_fim"), IntegerField())
        mes = Cast(ExtractMonth(f"{prefixo}data_fim"), IntegerField())
        return {
            "grupo_ano": ano,
            "grupo_fatia": (mes - Value(1)) / Value(self.meses) + Value(1),
        }

    def periodo(self, ano: int, fatia: int, quantidade_realizada: int) -> dict:
        primeiro_mes = (fatia - 1) * self.meses + 1
        ultimo_mes = primeiro_mes + self.meses - 1
        return {
            "inicio": date(ano, primeiro_mes, 1),
            "fim": date(ano, ultimo_mes, calendar.monthrange(ano, ultimo_mes)[1]),
            "quantidade_realizada": quantidade_realizada,
        }


# A cadência mensal é a dos relatórios do SGP (curva S e fechamento mensal,
# §7.4–§7.6). Outra granularidade entra aqui com o tamanho da fatia em meses.
GRANULARIDADES = {
    "mes": Granularidade(meses=1),
    "trimestre": Granularidade(meses=3),
    "semestre": Granularidade(meses=6),
    "ano": Granularidade(meses=12),
}
GRANULARIDADE_PADRAO = "mes"


def _chaves_territorio(prefixo: str) -> dict:
    return {"grupo_territorio": F(f"{prefixo}municipio__territory_id")}


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
    granularidade: str = GRANULARIDADE_PADRAO,
) -> list[dict]:
    fatia = GRANULARIDADES[granularidade]
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
    realizado_territorial = realizado_agrupado(acoes, _chaves_territorio, filtro)
    realizado_por_fatia = realizado_agrupado(acoes, fatia.chaves, filtro)

    grupos: dict[int, dict] = {}
    for acao in acoes:
        grupo = grupos.setdefault(acao.indicador_id, {
            "indicador": acao.indicador,
            "total": _Soma(),
            "por_meta": {},
            "por_submeta": {},
            "por_territorio": defaultdict(int),
            "por_periodo": defaultdict(int),
        })
        grupo["total"].somar(acao)
        grupo["por_meta"].setdefault(acao.meta_id, _Soma(alvo=acao.meta)).somar(acao)
        grupo["por_submeta"].setdefault(acao.submeta_id, _Soma(alvo=acao.submeta)).somar(acao)
        for (territorio,), total in realizado_territorial.get(acao.pk, {}).items():
            grupo["por_territorio"][territorio] += total
        for ano_e_fatia, total in realizado_por_fatia.get(acao.pk, {}).items():
            grupo["por_periodo"][ano_e_fatia] += total

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
            "por_periodo": [
                fatia.periodo(ano, indice, total)
                for (ano, indice), total in sorted(grupo["por_periodo"].items())
            ],
        })
    return visao
