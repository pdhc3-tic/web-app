"""Contexto da demanda: estado, território, cadeia do Plano de Trabalho, rubricas
e participantes previstos. Única parte do SGD que conhece o caminho até esses
dados no SGP.

Abrangência territorial (Issue #352): o estado e o território da demanda são os
do SOLICITANTE, gravados na criação em `Demand.estado_sigla`/`Demand.territorio`
e congelados — mudar a lotação do usuário depois não move as demandas já
criadas, e a atividade não entra no critério, onde quer que ela aconteça. Fila,
visibilidade, RLS, notificação e pool leem daqui. Ambos nulos = demanda de
nível nacional (solicitante sem território, como o super-admin): nenhum
Articulador é responsável por ela."""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import CharField, Exists, OuterRef, Q
from django.db.models.functions import Cast

CAMINHO_ESTADO = "activity__municipio__state"
CAMINHO_TERRITORIO = "territorio"
CAMINHOS_CADEIA = ("activity__acao__meta", "activity__acao__submeta", "activity__acao__indicador")
CAMINHO_RUBRICAS_PREVISTAS = "activity__acao__rubricas_previstas"
CAMPO_META = "activity__acao__meta_id"
CAMPO_SUBMETA = "activity__acao__submeta_id"
CAMPO_TERRITORIO = "territorio_id"


def da_solicitacao(*caminhos: str) -> tuple[str, ...]:
    """Os mesmos caminhos, partindo de `DemandRequest`."""
    return tuple(f"demanda__{caminho}" for caminho in caminhos)


def filtro_por_estado(siglas) -> Q:
    """Demandas do estado gravado nelas. A nacional (estado nulo) nunca entra."""
    return Q(estado_sigla__in=siglas)


def filtro_de_pedido_por_estado(siglas) -> Q:
    """Pedido de recurso extra: com demanda vinculada, vale o estado congelado
    nela; sem demanda, o da própria atividade. `demanda_id` é referência fraca
    (texto): compara com o pk como texto, para não quebrar com um valor que
    não seja número."""
    from apps.sgd.models import Demand

    demandas = Demand.objects.annotate(pk_texto=Cast("pk", CharField())).filter(pk_texto=OuterRef("demanda_id"))
    return Q(Exists(demandas.filter(estado_sigla__in=siglas))) | (
        ~Q(Exists(demandas)) & Q(**{f"{CAMINHO_ESTADO}__sigla__in": siglas})
    )


def estado_da_atividade(activity) -> str:
    return activity.municipio.state.sigla


def estado_da_demanda(demand) -> str | None:
    """`None` = demanda nacional."""
    return demand.estado_sigla or None


def territorio_da_demanda(demand):
    return demand.territorio if demand.territorio_id else None


def estado_do_pedido(pedido, demanda=None) -> str | None:
    """Estado do pedido de recurso extra, pela mesma regra de
    `filtro_de_pedido_por_estado`."""
    if demanda is not None:
        return estado_da_demanda(demanda)
    if pedido.activity_id is None:
        return None
    return estado_da_atividade(pedido.activity)


def calendario_da_demanda(demand) -> str:
    """UF do calendário de feriados: a da demanda; a nacional, sem estado, usa
    a da atividade."""
    return estado_da_demanda(demand) or estado_da_atividade(demand.activity)


def _uf_do_territorio(territorio) -> str | None:
    """Estado-sede do território (`estados[0]`), o mesmo critério que
    `resolver_nivel_do_usuario` usa para o Articulador."""
    estados = territorio.estados or []
    return estados[0] if estados else None


def abrangencia_para_nova_demanda(*, solicitante) -> tuple[str | None, object | None]:
    """(estado_sigla, territorio) a gravar na criação, a partir de
    `resolver_nivel_do_usuario(solicitante)` — o mesmo critério do pool;
    `PermissionDenied` do resolver sobe."""
    from apps.sgd.services import orcamento as orcamento_service

    nivel, estado_sigla, territorio = orcamento_service.resolver_nivel_do_usuario(solicitante)
    if nivel == orcamento_service.Nivel.TERRITORIAL:
        return _uf_do_territorio(territorio), territorio
    if nivel == orcamento_service.Nivel.ESTADUAL:
        return estado_sigla, None
    return None, None


def nivel_da_demanda(demand) -> tuple[str, str | None, object | None]:
    """No contrato de `resolver_nivel_do_usuario`, para o motor de saldo."""
    from apps.sgd.services import orcamento as orcamento_service

    if demand.territorio_id:
        return orcamento_service.Nivel.TERRITORIAL, None, demand.territorio
    if demand.estado_sigla:
        return orcamento_service.Nivel.ESTADUAL, demand.estado_sigla, None
    return orcamento_service.Nivel.NACIONAL, None, None


def atividade_fora_do_estado(estado_sigla: str | None, activity) -> bool:
    """A atividade acontece em outro estado que não `estado_sigla`. Sem estado
    (nível nacional), nunca está fora."""
    if estado_sigla is None:
        return False
    return estado_da_atividade(activity) != estado_sigla


def atividade_fora_do_territorio(demand) -> bool:
    return atividade_fora_do_estado(estado_da_demanda(demand), demand.activity)


def articuladores_do_estado(estado_sigla: str | None) -> list[dict]:
    """Quem pré-autoriza as demandas do estado, pelo mesmo critério que decide quem
    é notificado na submissão. Demanda nacional não tem Articulador."""
    if estado_sigla is None:
        return []
    from apps.sgd.services import orcamento as orcamento_service

    return list(
        orcamento_service.articuladores_dos_estados([estado_sigla]).order_by("nome", "pk").values("id", "nome")
    )


def articuladores_por_estado(siglas) -> dict[str, list[dict]]:
    """`articuladores_do_estado` de vários estados de uma vez, para a listagem: duas
    consultas, quantos estados forem. Todo estado pedido tem entrada, mesmo vazia."""
    from apps.core.models import UserProfile
    from apps.sgd.services import orcamento as orcamento_service

    siglas = sorted({sigla for sigla in siglas if sigla})
    por_estado: dict[str, list[dict]] = {sigla: [] for sigla in siglas}
    if not siglas:
        return por_estado
    usuarios = list(orcamento_service.articuladores_dos_estados(siglas).order_by("nome", "pk").values("id", "nome"))
    estados_do_usuario: dict[int, set[str]] = {}
    perfis = UserProfile.objects.filter(
        user_id__in=[usuario["id"] for usuario in usuarios], perfil__slug="articulador-estadual",
    ).values_list("user_id", "territorio_id", "territorio__estados")
    for user_id, territorio_id, estados in perfis:
        # Articulador sem território responde por todos os estados, como no critério da notificação.
        alcance = set(siglas) if territorio_id is None else set(estados or ()) & set(siglas)
        estados_do_usuario.setdefault(user_id, set()).update(alcance)
    for usuario in usuarios:
        for sigla in estados_do_usuario.get(usuario["id"], ()):
            por_estado[sigla].append(usuario)
    return por_estado


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
