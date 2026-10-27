"""Máquina de estados da demanda.

`TRANSICOES` diz, para cada mudança de status, quem pode fazê-la, se exige
justificativa, o que acontece com o saldo, que etapa entra na timeline e quem é
notificado. `executar_transicao` é o único lugar que aplica uma linha dela.

Ordem de lock (`backend/docs/orcamento.md`): o efeito no saldo trava limite e
alocação; só então a `Demand` é travada e relida, e as solicitações são gravadas
por último. A decisão sobre a transição é tomada com o objeto que quem chama
leu; a releitura sob o lock recusa a transição se a demanda mudou nesse meio.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.services.permissions import user_role_slugs
from apps.core.utils import formatar_brl
from apps.sgd.exceptions import JustificativaObrigatoria, RegraDeNegocio, SaldoInsuficiente, TransicaoInvalida
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.demand import STATUS_CANCELAVEIS_PELO_SOLICITANTE, STATUS_CHOICES, Demand
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.services import auditoria as auditoria_service
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services.approval import PERFIS_QUE_CANCELAM_AUTORIZADA, exigir_pode_decidir_articulador
from apps.sgp.models import GlosaRisk
from apps.sgp.services.apuracao import recalcular_valor_executado

ORIGEM_USUARIO = "usuario"
ORIGEM_SISTEMA = "sistema"
ORIGEM_ARLO = "arlo"

# Pseudo-perfil: o dono da demanda, qualquer que seja o perfil dele.
SOLICITANTE = "solicitante"

RESERVAR = "reservar"
MANTER = "manter"
AJUSTAR = "ajustar"
LIBERAR = "liberar"
EXECUTAR = "executar"


@dataclass(frozen=True)
class Transicao:
    de: frozenset[str]
    para: str
    origem: str
    efeito_saldo: str
    # Vazio só nas origens `sistema` e `arlo`: quem age ali é a task ou quem enviou
    # a planilha, e o perfil já foi conferido na entrada.
    perfis: tuple[str, ...] = ()
    justificativa_obrigatoria: bool = False
    etapa: str | None = None
    acao: str | None = None
    notificacao: str | None = None
    # Regra de decisão além do perfil (`services/approval.py`); levanta PermissionDenied.
    regra: Callable | None = None


_PRE_AUTORIZACAO = {"perfis": ("articulador-estadual",), "regra": exigir_pode_decidir_articulador}
_ATENDIMENTO = {"etapa": "atendimento", "acao": "atendido"}
# Em atendimento fica de fora: a FGD já está atendendo, não é demanda não atendida.
CANCELAVEIS_PELO_SISTEMA = frozenset(STATUS_CANCELAVEIS_PELO_SOLICITANTE | {"autorizada"})

TRANSICOES: tuple[Transicao, ...] = (
    Transicao(
        de=frozenset({"rascunho", "devolvida"}), para="submetida", origem=ORIGEM_USUARIO,
        efeito_saldo=RESERVAR, perfis=(SOLICITANTE,), notificacao="submissao",
    ),
    Transicao(
        de=frozenset({"submetida"}), para="pre_autorizada", origem=ORIGEM_USUARIO, efeito_saldo=MANTER,
        etapa="pre_autorizacao", acao="aprovado", notificacao="pre_autorizacao", **_PRE_AUTORIZACAO,
    ),
    Transicao(
        de=frozenset({"submetida"}), para="devolvida", origem=ORIGEM_USUARIO, efeito_saldo=MANTER,
        justificativa_obrigatoria=True, etapa="pre_autorizacao", acao="devolvido", notificacao="devolucao",
        **_PRE_AUTORIZACAO,
    ),
    Transicao(
        de=frozenset({"pre_autorizada"}), para="autorizada", origem=ORIGEM_USUARIO, efeito_saldo=AJUSTAR,
        perfis=("ugp",), etapa="autorizacao", acao="aprovado", notificacao="autorizacao",
    ),
    Transicao(
        de=frozenset({"pre_autorizada"}), para="recusada", origem=ORIGEM_USUARIO, efeito_saldo=LIBERAR,
        perfis=("ugp",), justificativa_obrigatoria=True, etapa="autorizacao", acao="recusado",
        notificacao="recusa",
    ),
    Transicao(
        de=frozenset({"autorizada"}), para="em_atendimento", origem=ORIGEM_USUARIO, efeito_saldo=MANTER,
        perfis=("fgd",), notificacao="em_atendimento", **_ATENDIMENTO,
    ),
    Transicao(
        de=frozenset({"autorizada"}), para="em_atendimento", origem=ORIGEM_ARLO, efeito_saldo=MANTER,
        notificacao="em_atendimento", **_ATENDIMENTO,
    ),
    Transicao(
        de=frozenset({"em_atendimento"}), para="concluida", origem=ORIGEM_USUARIO, efeito_saldo=EXECUTAR,
        perfis=("fgd",), notificacao="conclusao", **_ATENDIMENTO,
    ),
    Transicao(
        de=frozenset({"em_atendimento"}), para="concluida", origem=ORIGEM_ARLO, efeito_saldo=EXECUTAR,
        notificacao="conclusao", **_ATENDIMENTO,
    ),
    Transicao(
        de=frozenset(STATUS_CANCELAVEIS_PELO_SOLICITANTE), para="cancelada", origem=ORIGEM_USUARIO,
        efeito_saldo=LIBERAR, perfis=(SOLICITANTE,),
    ),
    Transicao(
        de=frozenset({"autorizada"}), para="cancelada", origem=ORIGEM_USUARIO, efeito_saldo=LIBERAR,
        perfis=PERFIS_QUE_CANCELAM_AUTORIZADA, justificativa_obrigatoria=True,
        etapa="cancelamento", acao="cancelado",
    ),
    # Aplicada só por `cancelar_pelo_sistema`, que libera o saldo de todas as demandas em lote.
    Transicao(
        de=CANCELAVEIS_PELO_SISTEMA, para="cancelada", origem=ORIGEM_SISTEMA, efeito_saldo=LIBERAR,
        notificacao="cancelamento_automatico",
    ),
)

# Status em que a importação do Arlo aceita pagamento: os de partida das linhas dela.
STATUS_PAGAVEIS_PELO_ARLO = frozenset(de for t in TRANSICOES if t.origem == ORIGEM_ARLO for de in t.de)

_ROTULOS = dict(STATUS_CHOICES)

_JUSTIFICATIVA_PARA = {
    "devolvida": "devolver a demanda",
    "recusada": "recusar a demanda",
    "cancelada": "cancelar uma demanda autorizada",
}

_DADOS_DAS_ACOES = {"justificativa", "ajustes", "excedente_autorizado", "valores_pagos"}

# Além do estado da reserva, que todo efeito no saldo grava.
_OUTROS_CAMPOS = {AJUSTAR: ("valor_autorizado",), EXECUTAR: ("valor_pago",)}

MENSAGEM_DEMANDA_MUDOU = "A demanda mudou durante a operação. Recarregue e tente de novo."


def _destinos(status: str, origem: str) -> list[str]:
    return sorted({t.para for t in TRANSICOES if t.origem == origem and status in t.de})


def destinos_permitidos(status: str) -> list[str]:
    """`transicoes_permitidas` da API. O cancelamento tem ação própria e fica de fora."""
    return [destino for destino in _destinos(status, ORIGEM_USUARIO) if destino != "cancelada"]


def buscar_transicao(status: str, destino: str, origem: str = ORIGEM_USUARIO) -> Transicao:
    for transicao in TRANSICOES:
        if transicao.para == destino and transicao.origem == origem and status in transicao.de:
            return transicao
    if destino == "cancelada":
        raise TransicaoInvalida(f"Demanda em status '{_ROTULOS[status]}' não pode ser cancelada.")
    permitidos = _destinos(status, origem)
    raise TransicaoInvalida(
        f"Transição inválida: '{status}' → '{destino}'. "
        f"Transições permitidas: {permitidos if permitidos else ['nenhuma (estado terminal)']}"
    )


def _exigir_perfil(transicao: Transicao, demand, ator) -> None:
    if not transicao.perfis:
        return
    perfis = tuple(p for p in transicao.perfis if p != SOLICITANTE)
    e_solicitante = SOLICITANTE in transicao.perfis and ator is not None and demand.solicitante_id == ator.pk
    # `user_role_slugs` sem filtro devolve todos os perfis: só consulta com algum.
    if not e_solicitante and (ator is None or not perfis or not user_role_slugs(ator, perfis)):
        raise PermissionDenied(
            f"Seu perfil não pode levar a demanda de '{_ROTULOS[demand.status]}' para '{_ROTULOS[transicao.para]}'."
        )
    if transicao.regra is not None:
        transicao.regra(demand, ator)


def _solicitacoes(demand) -> list:
    return list(demand.solicitacoes.select_related("rubrica").order_by("rubrica_id", "pk"))


def _retrato(solicitacoes) -> dict:
    return {s.pk: (s.rubrica_id, s.valor_estimado, s.valor_pago) for s in solicitacoes}


def travar_e_ler_status(demand) -> str:
    """Trava a `Demand` e devolve o status da linha travada: quem segurava o lock
    pode tê-la mudado. Vem depois do saldo, na ordem de lock."""
    return Demand.objects.select_for_update().values_list("status", flat=True).get(pk=demand.pk)


def _travar_demanda(demand, retrato: dict | None = None) -> None:
    """Trava a `Demand` e confere que o status é o que estava em `demand` e, com
    `retrato`, que as solicitações são as mesmas de quando o saldo foi movido.
    Quem edita a demanda ou as solicitações trava a `Demand` antes de gravar,
    então nada muda até o commit."""
    if travar_e_ler_status(demand) != demand.status:
        raise TransicaoInvalida(MENSAGEM_DEMANDA_MUDOU)
    if retrato is None:
        return
    atual = DemandRequest.objects.filter(demanda_id=demand.pk).values_list(
        "pk", "rubrica_id", "valor_estimado", "valor_pago",
    )
    if {pk: tuple(campos) for pk, *campos in atual} != retrato:
        raise TransicaoInvalida(MENSAGEM_DEMANDA_MUDOU)


def _exigir_da_demanda(ids, solicitacoes, campo: str) -> None:
    desconhecidos = set(ids) - {s.pk for s in solicitacoes}
    if desconhecidos:
        raise RegraDeNegocio(
            f"Solicitação(ões) {sorted(desconhecidos)} não pertence(m) a esta demanda.", campo=campo,
        )


def _manter(demand, transicao, **_) -> tuple[list, dict | None]:
    return [], None


def _reservar(demand, transicao, *, ator, **_) -> tuple[list, dict | None]:
    solicitacoes = _solicitacoes(demand)
    if not solicitacoes:
        raise RegraDeNegocio("A demanda precisa ter ao menos uma solicitação de recurso.", campo="solicitacoes")
    retrato = _retrato(solicitacoes)

    # Tudo-ou-nada: verifica as duas travas de todas as solicitações antes de
    # reservar qualquer uma. Solicitações da mesma rubrica disputam o mesmo limite
    # e a mesma alocação: cada uma é conferida contra o saldo que sobra depois das
    # anteriores que passaram. As barradas não consomem — senão uma menor, que
    # ainda cabe, seria barrada por causa de uma maior que não coube.
    bloqueios = {}
    consumo_por_rubrica: dict[int, Decimal] = {}
    for solicitacao in solicitacoes:
        # Com reserva já ativa (ressubmissão de Devolvida), o saldo já a desconta.
        if solicitacao.reserva_ativa:
            continue
        consumo_previo = consumo_por_rubrica.get(solicitacao.rubrica_id, balance_service.ZERO)
        check = balance_service.verificar_duas_travas(
            solicitante=demand.solicitante, rubrica=solicitacao.rubrica, valor=solicitacao.valor_estimado,
            demand_request=solicitacao, consumo_previo=consumo_previo,
        )
        if not check.disponivel:
            bloqueios[solicitacao.pk] = check.bloqueio(solicitacao_id=solicitacao.pk)
        else:
            consumo_por_rubrica[solicitacao.rubrica_id] = consumo_previo + solicitacao.valor_estimado
    if bloqueios:
        raise SaldoInsuficiente.para_submissao(bloqueios)

    for solicitacao in solicitacoes:
        balance_service.reservar_duas_travas(demand_request=solicitacao, usuario=ator, adiar_gravacao=True)
    return solicitacoes, retrato


def _ajustar(demand, transicao, *, ator, ajustes: dict | None = None, excedente_autorizado: bool = False,
             justificativa: str = "", **_) -> tuple[list, dict | None]:
    """`ajustes`: {demand_request_id: novo_valor}; sem ajuste, autoriza o estimado."""
    if excedente_autorizado and not justificativa:
        raise JustificativaObrigatoria("Obrigatória para autorizar excedendo o limite individual.")
    ajustes = ajustes or {}
    solicitacoes = _solicitacoes(demand)
    _exigir_da_demanda(ajustes, solicitacoes, "ajustes")
    if any(valor <= 0 for valor in ajustes.values()):
        raise RegraDeNegocio(
            "O valor autorizado deve ser maior que zero. Para não autorizar, recuse a demanda.", campo="ajustes",
        )
    retrato = _retrato(solicitacoes)

    for solicitacao in solicitacoes:
        novo_valor = ajustes.get(solicitacao.pk, solicitacao.valor_estimado)
        if novo_valor != solicitacao.valor_reservado:
            balance_service.ajustar_duas_travas(
                demand_request=solicitacao, novo_valor=novo_valor, usuario=ator,
                ignorar_limite_individual=excedente_autorizado, adiar_gravacao=True,
            )
        solicitacao.valor_autorizado = novo_valor
    return solicitacoes, retrato


def _motivo_da_liberacao(transicao: Transicao, justificativa: str) -> str:
    if transicao.para == "recusada":
        return "Demanda recusada pela UGP."
    return justificativa or "Cancelada pelo solicitante."


def _liberar(demand, transicao, *, ator, justificativa: str = "", **_) -> tuple[list, dict | None]:
    solicitacoes = _solicitacoes(demand)
    retrato = _retrato(solicitacoes)
    balance_service.liberar_duas_travas_em_lote(
        solicitacoes, usuario=ator, motivo=_motivo_da_liberacao(transicao, justificativa), adiar_gravacao=True,
    )
    return solicitacoes, retrato


def _executar(demand, transicao, *, ator, valores_pagos: dict | None = None, **_) -> tuple[list, dict | None]:
    """`valores_pagos`: {demand_request_id: valor_pago}. As solicitações já pagas
    (pelo Arlo, linha a linha) ficam como estão: podem vir com o mesmo valor
    registrado, nunca com outro."""
    valores_pagos = valores_pagos or {}
    solicitacoes = _solicitacoes(demand)
    _exigir_da_demanda(valores_pagos, solicitacoes, "valores_pagos")
    for solicitacao in solicitacoes:
        informado = valores_pagos.get(solicitacao.pk)
        if solicitacao.valor_pago is not None and informado not in (None, solicitacao.valor_pago):
            raise RegraDeNegocio(
                f"Solicitação #{solicitacao.pk} já tem pagamento registrado de "
                f"{formatar_brl(solicitacao.valor_pago)}.", campo="valores_pagos",
            )
        if solicitacao.valor_pago is None and solicitacao.pk not in valores_pagos:
            raise RegraDeNegocio(
                f"Valor pago obrigatório para a solicitação #{solicitacao.pk}.", campo="valores_pagos",
            )
    retrato = _retrato(solicitacoes)

    for solicitacao in solicitacoes:
        if solicitacao.valor_pago is None:
            registrar_pagamento(
                solicitacao, valor_pago=valores_pagos[solicitacao.pk], origem=transicao.origem, usuario=ator,
            )
    return solicitacoes, retrato


_EFEITOS = {
    RESERVAR: _reservar,
    MANTER: _manter,
    AJUSTAR: _ajustar,
    LIBERAR: _liberar,
    EXECUTAR: _executar,
}


def _articuladores(demand, destinatarios: dict):
    """`destinatarios` guarda a consulta por estado: o cancelamento em lote notifica
    várias demandas da mesma atividade."""
    sigla = demand.activity.municipio.state.sigla
    if sigla not in destinatarios:
        destinatarios[sigla] = list(notifications_service.usuarios_articuladores_do_estado(sigla))
    return destinatarios[sigla]


_NOTIFICACOES = {
    "submissao": lambda d, cache: notifications_service.notificar_submissao(d, _articuladores(d, cache)),
    "pre_autorizacao": lambda d, cache: notifications_service.notificar_pre_autorizacao(
        d, notifications_service.usuarios_por_perfil("ugp"),
    ),
    "devolucao": lambda d, cache: notifications_service.notificar_devolucao(d),
    "autorizacao": lambda d, cache: notifications_service.notificar_autorizacao(
        d, notifications_service.usuarios_por_perfil("fgd"),
    ),
    "recusa": lambda d, cache: notifications_service.notificar_recusa(d),
    "em_atendimento": lambda d, cache: notifications_service.notificar_em_atendimento(d),
    "conclusao": lambda d, cache: notifications_service.notificar_conclusao(d),
    "cancelamento_automatico": lambda d, cache: notifications_service.notificar_cancelamento_automatico(
        d, _articuladores(d, cache),
    ),
}


def _aplicar(demand, transicao: Transicao, solicitacoes, *, ator, destinatarios: dict, justificativa: str = "",
             excedente_autorizado: bool = False, **_) -> None:
    status_anterior = demand.status
    demand.status = transicao.para
    demand.status_alterado_em = timezone.now()
    demand.save(update_fields=["status", "status_alterado_em", "atualizado_em"])
    auditoria_service.registrar_status(demand, de=status_anterior, para=transicao.para, usuario=ator)
    balance_service.gravar_estado_da_reserva(
        solicitacoes, outros_campos=_OUTROS_CAMPOS.get(transicao.efeito_saldo, ()),
    )
    if transicao.efeito_saldo == EXECUTAR:
        recalcular_valor_executado([demand.activity.acao_id])
    if transicao.etapa is not None:
        ApprovalStep.objects.create(
            demanda=demand, etapa=transicao.etapa, responsavel=ator, acao=transicao.acao,
            justificativa=justificativa, excedente_autorizado=excedente_autorizado,
        )
    if transicao.notificacao is not None:
        _NOTIFICACOES[transicao.notificacao](demand, destinatarios)
    # A view lê a demanda com as solicitações pré-carregadas, e elas foram gravadas por `update()`.
    getattr(demand, "_prefetched_objects_cache", {}).pop("solicitacoes", None)


@transaction.atomic
def executar_transicao(demand, destino: str, *, ator=None, origem: str = ORIGEM_USUARIO, **dados):
    """Leva `demand` a `destino`. `dados` são os da ação: `justificativa`;
    `ajustes`, `excedente_autorizado` (autorizar); `valores_pagos` (concluir)."""
    desconhecidos = set(dados) - _DADOS_DAS_ACOES
    if desconhecidos:
        raise TypeError(f"Dados desconhecidos para a transição: {sorted(desconhecidos)}.")
    dados["justificativa"] = (dados.get("justificativa") or "").strip()
    transicao = buscar_transicao(demand.status, destino, origem)
    _exigir_perfil(transicao, demand, ator)
    if transicao.justificativa_obrigatoria and not dados["justificativa"]:
        raise JustificativaObrigatoria(f"Obrigatória para {_JUSTIFICATIVA_PARA.get(destino, 'esta transição')}.")

    solicitacoes, retrato = _EFEITOS[transicao.efeito_saldo](demand, transicao, ator=ator, **dados)
    _travar_demanda(demand, retrato)
    _aplicar(demand, transicao, solicitacoes, ator=ator, destinatarios={}, **dados)
    return demand


@transaction.atomic
def cancelar_pelo_sistema(demandas, *, motivo: str) -> None:
    """Variante em lote de `executar_transicao` para a linha de origem `sistema`,
    usada quando a atividade é cancelada. Cancelar uma a uma travaria a alocação,
    que os solicitantes compartilham, antes do limite do solicitante seguinte: o
    saldo de todas sai antes (`liberar_duas_travas_em_lote`), e só então cada
    `Demand` é travada, em ordem de pk.

    A liberação relê cada reserva sob o lock do limite, mas trava o limite pela
    rubrica lida antes: na linha travada, confere que a demanda continua
    cancelável e que nenhuma solicitação entrou, saiu ou mudou de rubrica. Se não,
    a transação inteira volta com `TransicaoInvalida`."""
    demandas = sorted(demandas, key=lambda d: d.pk)
    solicitacoes = list(
        DemandRequest.objects.filter(demanda__in=demandas).select_related("rubrica", "demanda__solicitante")
    )
    rubricas = defaultdict(dict)
    for solicitacao in solicitacoes:
        rubricas[solicitacao.demanda_id][solicitacao.pk] = solicitacao.rubrica_id

    balance_service.liberar_duas_travas_em_lote(solicitacoes, usuario=None, motivo=motivo, adiar_gravacao=True)
    transicoes = {}
    for demand in demandas:
        demand.status = travar_e_ler_status(demand)
        atuais = dict(DemandRequest.objects.filter(demanda_id=demand.pk).values_list("pk", "rubrica_id"))
        if atuais != rubricas[demand.pk]:
            raise TransicaoInvalida(MENSAGEM_DEMANDA_MUDOU)
        transicoes[demand.pk] = buscar_transicao(demand.status, "cancelada", ORIGEM_SISTEMA)
    destinatarios = {}
    for demand in demandas:
        _aplicar(demand, transicoes[demand.pk], [], ator=None, destinatarios=destinatarios)
    balance_service.gravar_estado_da_reserva(solicitacoes)


def valor_autorizado(solicitacao) -> Decimal:
    """O autorizado pela UGP; antes da decisão, o estimado."""
    if solicitacao.valor_autorizado is not None:
        return solicitacao.valor_autorizado
    return solicitacao.valor_estimado


def registrar_pagamento(solicitacao, *, valor_pago: Decimal, origem: str, usuario, importacao=None,
                        **detalhes) -> None:
    """Pagamento de uma solicitação, pela conclusão da FGD ou pela importação do
    Arlo. Até o autorizado, executa o pago e devolve a diferença ao limite e ao
    pool. Acima dele, executa só o autorizado e registra o excedente como risco de
    glosa.

    Trava limite e alocação, mas a solicitação muda só em memória (`valor_pago` e
    o estado da reserva): quem chama a grava depois de travar a `Demand`."""
    autorizado = valor_autorizado(solicitacao)
    executou = balance_service.executar_duas_travas(
        demand_request=solicitacao, valor_pago=min(valor_pago, autorizado), usuario=usuario, adiar_gravacao=True,
    )
    if not executou:
        raise RegraDeNegocio(f"Solicitação #{solicitacao.pk} já tem pagamento registrado.", campo="valores_pagos")
    if valor_pago > autorizado:
        GlosaRisk.objects.create(
            demanda_id=str(solicitacao.demanda_id), demand_request_id=str(solicitacao.pk),
            arlo_import_id=str(importacao.pk) if importacao is not None else "",
            valor_autorizado=autorizado, valor_pago=valor_pago, excedente=valor_pago - autorizado,
            criado_por=usuario,
        )
    solicitacao.valor_pago = valor_pago

    novos = {"origem": origem, "valor_pago": str(valor_pago), "valor_autorizado": str(autorizado), **detalhes}
    if importacao is not None:
        novos["arlo_import_id"] = importacao.pk
    auditoria_service.registrar_evento(
        acao="pagamento", entidade="DemandRequest", entidade_id=solicitacao.pk, usuario=usuario, novos=novos,
    )
