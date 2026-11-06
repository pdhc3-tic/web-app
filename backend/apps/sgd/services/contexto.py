"""Contexto que a demanda herda da atividade: estado, território, cadeia do Plano
de Trabalho, rubricas e participantes previstos. Única parte do SGD que conhece o
caminho até esses dados no SGP."""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q

CAMINHO_ESTADO = "activity__municipio__state"
CAMINHO_TERRITORIO = "activity__municipio__territory"
CAMINHOS_CADEIA = ("activity__acao__meta", "activity__acao__submeta", "activity__acao__indicador")
CAMINHO_RUBRICAS_PREVISTAS = "activity__acao__rubricas_previstas"
CAMPO_META = "activity__acao__meta_id"
CAMPO_SUBMETA = "activity__acao__submeta_id"
CAMPO_TERRITORIO = "activity__municipio__territory_id"


def da_solicitacao(*caminhos: str) -> tuple[str, ...]:
    """Os mesmos caminhos, partindo de `DemandRequest`."""
    return tuple(f"demanda__{caminho}" for caminho in caminhos)


def filtro_por_estado(siglas) -> Q:
    return Q(**{f"{CAMINHO_ESTADO}__sigla__in": siglas})


def filtro_de_pedido_por_estado(siglas) -> Q:
    """O pedido de recurso extra responde pela própria atividade, não pela demanda."""
    return Q(**{f"{CAMINHO_ESTADO}__sigla__in": siglas})


def estado_da_atividade(activity) -> str:
    return activity.municipio.state.sigla


def estado_da_demanda(demand) -> str:
    return estado_da_atividade(demand.activity)


def territorio_da_demanda(demand):
    return demand.activity.municipio.territory


@dataclass(frozen=True)
class CadeiaPT:
    acao: object
    submeta: object
    meta: object
    indicador: object


def cadeia_pt(demand) -> CadeiaPT:
    acao = demand.activity.acao
    return CadeiaPT(acao=acao, submeta=acao.submeta, meta=acao.meta, indicador=acao.indicador)


def rubricas_previstas(demand) -> list:
    return list(demand.activity.acao.rubricas_previstas.all())


def participantes_previstos(demand) -> int:
    return demand.activity.membros_participantes.count()
