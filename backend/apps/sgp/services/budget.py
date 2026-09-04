"""Agregação e regras de teto do orçamento por Meta/Rubrica."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import ProtectedError, Q, QuerySet, Sum
from django.db.models.functions import Coalesce
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models import Territory
from apps.core.models.user_profile import UserProfile
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.models import BudgetAllocation, BudgetRubrica, BudgetTransaction, WorkPlanMeta

Nivel = BudgetAllocation.Nivel
ZERO = Decimal("0")


def is_global_budget_user(user) -> bool:
    return user_has_role(user, "super-admin") or user_has_role(user, "ugp")


def allowed_states_for_user(user) -> set[str]:
    return user_states(user)


def allowed_territories_for_user(user) -> QuerySet[Territory]:
    return user_territories(user)


def orcamento_detalhamento_scope(user) -> Q | None:
    """Filtro do *detalhamento* (linhas estaduais/territoriais) visível ao usuário.

    `None` = visão global. Nacional nunca aparece aqui — entra nos agregados
    (valor_aprovado/valor_distribuido), não na lista.

    Uma query só (perfil + território via select_related), não user_has_role/
    user_states/user_territories encadeados — cada um faria a sua própria.
    """
    perfis = list(
        UserProfile.objects.filter(user=user).select_related("perfil", "territorio")
    )
    slugs = {p.perfil.slug for p in perfis}

    if "super-admin" in slugs or "ugp" in slugs:
        return None

    if "articulador-estadual" in slugs:
        states: set[str] = set()
        sem_territorio = False
        for p in perfis:
            if p.perfil.slug != "articulador-estadual":
                continue
            if p.territorio is None:
                sem_territorio = True
            else:
                states.update(p.territorio.estados or [])
        if sem_territorio:
            # perfil sem território = global no papel; única saída sem outra query.
            states.update(allowed_states_for_user(user))
        if not states:
            return Q(pk__in=[])
        return Q(nivel=Nivel.ESTADUAL, estado__sigla__in=states) | Q(
            nivel=Nivel.TERRITORIAL, territorio__estados__overlap=list(states)
        )

    if "adt-acr" in slugs:
        territorio_ids = {p.territorio_id for p in perfis if p.perfil.slug == "adt-acr" and p.territorio_id}
        if not territorio_ids:
            return Q(pk__in=[])
        return Q(nivel=Nivel.TERRITORIAL, territorio_id__in=territorio_ids)

    raise PermissionDenied("Você não tem acesso ao orçamento do SGP.")


def orcamento_por_meta(meta: WorkPlanMeta, user) -> list[dict]:
    """Uma entrada por rubrica ativa — valores nacionais/distribuídos agregados
    globalmente (não é dado sensível por território) e `detalhamento`
    (linhas estaduais/territoriais) recortado pelo escopo do usuário.
    """
    detalhamento_scope = orcamento_detalhamento_scope(user)

    rubricas = list(
        BudgetRubrica.objects.filter(ativo=True)
        .annotate(
            valor_aprovado=Coalesce(
                Sum(
                    "alocacoes__valor_alocado",
                    filter=Q(alocacoes__meta=meta, alocacoes__nivel=Nivel.NACIONAL),
                ),
                ZERO,
            ),
            valor_distribuido=Coalesce(
                Sum(
                    "alocacoes__valor_alocado",
                    filter=Q(alocacoes__meta=meta, alocacoes__nivel=Nivel.ESTADUAL),
                ),
                ZERO,
            ),
            valor_comprometido=Coalesce(
                Sum(
                    "alocacoes__valor_comprometido",
                    filter=Q(alocacoes__meta=meta, alocacoes__nivel=Nivel.NACIONAL),
                ),
                ZERO,
            ),
            valor_executado=Coalesce(
                Sum(
                    "alocacoes__valor_executado",
                    filter=Q(alocacoes__meta=meta, alocacoes__nivel=Nivel.NACIONAL),
                ),
                ZERO,
            ),
        )
        .order_by("ordem")
    )

    detalhamento_qs = BudgetAllocation.objects.filter(meta=meta).exclude(
        nivel=Nivel.NACIONAL
    ).select_related("rubrica", "estado", "territorio")
    if detalhamento_scope is not None:
        detalhamento_qs = detalhamento_qs.filter(detalhamento_scope)
    detalhamento_por_rubrica: dict[int, list[BudgetAllocation]] = {}
    for alocacao in detalhamento_qs:
        detalhamento_por_rubrica.setdefault(alocacao.rubrica_id, []).append(alocacao)

    resultado = []
    for rubrica in rubricas:
        resultado.append({
            "rubrica": rubrica,
            "valor_aprovado": rubrica.valor_aprovado,
            "valor_distribuido": rubrica.valor_distribuido,
            "valor_comprometido": rubrica.valor_comprometido,
            "valor_executado": rubrica.valor_executado,
            # aprovado/comprometido/executado são todos do nível nacional (a
            # única linha "nacional" possível por rubrica) — distribuído é o
            # que já desceu pra estados. Sem subtrair os dois, o saldo
            # pareceria maior do que o que realmente ainda cabe redistribuir.
            "saldo_disponivel": (
                rubrica.valor_aprovado - rubrica.valor_distribuido
                - rubrica.valor_comprometido - rubrica.valor_executado
            ),
            "detalhamento": detalhamento_por_rubrica.get(rubrica.pk, []),
        })
    return resultado


# ---------------------------------------------------------------------------
# Distribuição — teto por nível, concorrência via select_for_update.
# ---------------------------------------------------------------------------

def _saldo_disponivel(allocation: BudgetAllocation) -> Decimal:
    return allocation.valor_alocado - allocation.valor_comprometido - allocation.valor_executado


def _linha_pai(*, meta, rubrica, nivel: str, territorio=None, estado=None) -> BudgetAllocation | None:
    """A alocação de nível imediatamente acima que 'financia' esta.

    territorial → a estadual do mesmo (meta, rubrica, estado do território).
    estadual → a nacional do mesmo (meta, rubrica).
    nacional → não tem pai (é o teto absoluto, o total aprovado no TED).
    """
    if nivel == Nivel.TERRITORIAL:
        estados_do_territorio = territorio.estados or []
        if not estados_do_territorio:
            return None
        # .first() com order_by explícito: só é ambíguo se o território
        # cobrir >1 estado com alocação estadual própria — caso raro, mas
        # sem UniqueConstraint que garanta 1 só aqui (ao contrário do nacional).
        return BudgetAllocation.objects.filter(
            meta=meta, rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado__sigla__in=estados_do_territorio,
        ).order_by("pk").first()
    if nivel == Nivel.ESTADUAL:
        # UniqueConstraint de #219 garante no máximo 1 linha nacional por
        # (meta, rubrica) — .first() aqui nunca é ambíguo.
        return BudgetAllocation.objects.filter(
            meta=meta, rubrica=rubrica, nivel=Nivel.NACIONAL,
        ).first()
    return None


def _peers_sob_mesmo_pai(*, meta, rubrica, nivel: str, pai: BudgetAllocation, exclude_pk=None) -> QuerySet:
    """Outras alocações do mesmo nível que também consomem o saldo de `pai`.

    Para territorial isso é só os territórios do mesmo estado do `pai`
    (um território pode, em tese, cobrir mais de um estado) — para
    estadual, todas compartilham o mesmo pai nacional, sem filtro extra.
    """
    qs = BudgetAllocation.objects.filter(meta=meta, rubrica=rubrica, nivel=nivel)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if nivel == Nivel.TERRITORIAL:
        qs = qs.filter(territorio__estados__contains=[pai.estado.sigla])
    return qs


def _checar_teto(*, meta, rubrica, nivel, pai, valor_total_pretendido: Decimal, exclude_pk=None) -> None:
    peers = _peers_sob_mesmo_pai(meta=meta, rubrica=rubrica, nivel=nivel, pai=pai, exclude_pk=exclude_pk)
    soma_peers = peers.aggregate(total=Coalesce(Sum("valor_alocado"), ZERO))["total"]
    disponivel_no_pai = _saldo_disponivel(pai)
    if soma_peers + valor_total_pretendido > disponivel_no_pai:
        raise DRFValidationError({
            "valor_alocado": (
                f"Excede o saldo disponível no nível superior: "
                f"R$ {disponivel_no_pai} disponível, R$ {soma_peers + valor_total_pretendido} "
                f"seria o total alocado neste nível."
            )
        })


def _travar_pai_e_checar_teto(*, meta, rubrica, nivel, territorio, estado,
                               valor_pretendido: Decimal, exclude_pk=None) -> BudgetAllocation | None:
    pai = _linha_pai(meta=meta, rubrica=rubrica, nivel=nivel, territorio=territorio, estado=estado)
    if pai is None:
        return None
    pai = BudgetAllocation.objects.select_for_update().get(pk=pai.pk)
    if pai.reserva_ugp:
        raise DRFValidationError({
            "valor_alocado": "A reserva própria da UGP não pode receber alocações-filhas."
        })
    _checar_teto(
        meta=meta, rubrica=rubrica, nivel=nivel, pai=pai,
        valor_total_pretendido=valor_pretendido, exclude_pk=exclude_pk,
    )
    return pai


@transaction.atomic
def criar_alocacao(*, meta, rubrica, nivel: str, valor_alocado: Decimal, usuario,
                    estado=None, territorio=None, reserva_ugp: bool = False) -> BudgetAllocation:
    """Cria uma alocação validando o teto do nível pai.

    Só o nacional não tem pai — é o topo da hierarquia, o total aprovado no
    TED. Estadual/territorial sem pai (nível de cima ainda não distribuído)
    é rejeitado: sem pai não há teto contra o que validar.

    `reserva_ugp` só se aplica ao nível nacional — uma linha marcada assim
    fica retida com a UGP e nunca pode receber alocação-filha.
    """
    if reserva_ugp and nivel != Nivel.NACIONAL:
        raise DRFValidationError({
            "reserva_ugp": "Reserva própria da UGP só é aplicável ao nível nacional."
        })

    pai = _travar_pai_e_checar_teto(
        meta=meta, rubrica=rubrica, nivel=nivel, territorio=territorio, estado=estado,
        valor_pretendido=valor_alocado,
    )
    if pai is None and nivel != Nivel.NACIONAL:
        raise DRFValidationError({
            "nivel": (
                "Não existe alocação do nível superior para esta combinação "
                "de Meta/Rubrica/Estado — distribua o nível acima primeiro."
            )
        })

    allocation = BudgetAllocation.objects.create(
        meta=meta, rubrica=rubrica, nivel=nivel,
        estado=estado, territorio=territorio,
        valor_alocado=valor_alocado, reserva_ugp=reserva_ugp, criado_por=usuario,
    )
    BudgetTransaction.objects.create(
        allocation=allocation, tipo=BudgetTransaction.Tipo.REMANEJAMENTO,
        valor=valor_alocado, criado_por=usuario,
        justificativa="Criação de alocação.",
    )
    return allocation


@transaction.atomic
def atualizar_valor_alocado(allocation: BudgetAllocation, *, novo_valor: Decimal, usuario) -> BudgetAllocation:
    """Reduzir abaixo do já comprometido+executado é rejeitado."""
    allocation = BudgetAllocation.objects.select_for_update().get(pk=allocation.pk)

    minimo = allocation.valor_comprometido + allocation.valor_executado
    if novo_valor < minimo:
        raise DRFValidationError({
            "valor_alocado": (
                f"Não é possível reduzir abaixo do já comprometido/executado (R$ {minimo})."
            )
        })

    _travar_pai_e_checar_teto(
        meta=allocation.meta, rubrica=allocation.rubrica, nivel=allocation.nivel,
        territorio=allocation.territorio, estado=allocation.estado,
        valor_pretendido=novo_valor, exclude_pk=allocation.pk,
    )

    valor_delta = novo_valor - allocation.valor_alocado
    allocation.valor_alocado = novo_valor
    allocation.save(update_fields=["valor_alocado"])
    BudgetTransaction.objects.create(
        allocation=allocation, tipo=BudgetTransaction.Tipo.REMANEJAMENTO,
        valor=valor_delta, criado_por=usuario,
        justificativa="Ajuste de alocação.",
    )
    return allocation


def remover_alocacao(allocation: BudgetAllocation) -> None:
    """`BudgetTransaction.allocation` é PROTECT — toda alocação nasce com pelo
    menos a transaction da criação, então .delete() sempre bateria em
    ProtectedError. Traduz isso pra uma mensagem clara em vez de vazar 500.
    """
    try:
        allocation.delete()
    except ProtectedError:
        raise DRFValidationError({
            "detail": (
                "Não é possível excluir: existem transações registradas "
                "para esta alocação."
            )
        })


# ---------------------------------------------------------------------------
# Motor de saldo — reserva, execução, liberação. API pública consumida pelo
# SGD (que ainda não existe); nenhuma dependência de apps.sgd aqui.
# ---------------------------------------------------------------------------

BLOQUEIO_SALDO_ZERO = "Bloqueado para novas solicitações quando saldo da rubrica é zero."


class SaldoInsuficienteError(Exception):
    """Levantada por `reservar` quando o valor pedido excede o saldo disponível."""


class DemandaInvalidaError(Exception):
    """Levantada por `executar`/`liberar` quando o demanda_id não tem reserva
    correspondente, ou já foi finalizado pela operação oposta."""


@dataclass
class SaldoCheck:
    disponivel: bool
    saldo: Decimal
    allocation: BudgetAllocation | None
    motivo_bloqueio: str | None = None


def _allocation_para(*, meta, rubrica, nivel: str, estado=None, territorio=None) -> BudgetAllocation | None:
    filtros = {"meta": meta, "rubrica": rubrica, "nivel": nivel}
    if nivel == Nivel.ESTADUAL:
        filtros["estado"] = estado
    elif nivel == Nivel.TERRITORIAL:
        filtros["territorio"] = territorio
    return BudgetAllocation.objects.filter(**filtros).first()


def _saldo_check_de_allocation(allocation: BudgetAllocation, valor: Decimal) -> SaldoCheck:
    saldo = _saldo_disponivel(allocation)
    if saldo <= ZERO:
        return SaldoCheck(disponivel=False, saldo=saldo, allocation=allocation, motivo_bloqueio=BLOQUEIO_SALDO_ZERO)
    if valor > saldo:
        return SaldoCheck(
            disponivel=False, saldo=saldo, allocation=allocation,
            motivo_bloqueio=f"Saldo insuficiente: R$ {saldo} disponível, R$ {valor} solicitado.",
        )
    return SaldoCheck(disponivel=True, saldo=saldo, allocation=allocation, motivo_bloqueio=None)


def verificar_saldo(*, meta, rubrica, nivel: str, territorio=None, estado=None, valor: Decimal) -> SaldoCheck:
    """API pública do motor — recebe instâncias já resolvidas (meta, rubrica,
    estado/território). `saldo_para_consulta`, mais abaixo, resolve o mesmo
    SaldoCheck mas a partir de ids/slugs crus e numa query só, pro endpoint
    HTTP caber no orçamento de queries — por isso as duas coexistem."""
    allocation = _allocation_para(meta=meta, rubrica=rubrica, nivel=nivel, estado=estado, territorio=territorio)
    if allocation is None:
        return SaldoCheck(
            disponivel=False, saldo=ZERO, allocation=None,
            motivo_bloqueio="Nenhuma alocação encontrada para este nível.",
        )
    return _saldo_check_de_allocation(allocation, valor)


def _transacao_existente(demanda_id: str, tipo: str) -> BudgetTransaction | None:
    return BudgetTransaction.objects.filter(demanda_id=demanda_id, tipo=tipo).first()


@transaction.atomic
def reservar(*, allocation: BudgetAllocation, valor: Decimal, demanda_id: str, usuario,
             justificativa: str = "") -> BudgetTransaction:
    """Idempotente por demanda_id — a checagem roda depois do lock na
    alocação, então duas chamadas concorrentes pro mesmo demanda_id
    serializam ali; a segunda, ao acordar, já encontra a transaction da
    primeira e não duplica o comprometimento."""
    if valor <= ZERO:
        # chamado direto pelo motor, sem o min_value=0 da serializer HTTP —
        # sem essa guarda, um valor negativo "reservaria" liberando saldo.
        raise ValueError(f"valor precisa ser positivo, recebi {valor}.")

    allocation = BudgetAllocation.objects.select_for_update().get(pk=allocation.pk)
    existente = _transacao_existente(demanda_id, BudgetTransaction.Tipo.RESERVA)
    if existente is not None:
        return existente

    saldo = _saldo_disponivel(allocation)
    if valor > saldo:
        raise SaldoInsuficienteError(
            f"Saldo insuficiente: R$ {saldo} disponível, R$ {valor} solicitado."
        )

    allocation.valor_comprometido += valor
    allocation.save(update_fields=["valor_comprometido"])
    return BudgetTransaction.objects.create(
        allocation=allocation, tipo=BudgetTransaction.Tipo.RESERVA, valor=valor,
        demanda_id=demanda_id, justificativa=justificativa, criado_por=usuario,
    )


@transaction.atomic
def executar(*, demanda_id: str, usuario) -> BudgetTransaction:
    """Move o valor da reserva original (achada por demanda_id) de
    comprometido pra executado, na mesma alocação — nunca mexe no pai."""
    reserva = BudgetTransaction.objects.filter(
        demanda_id=demanda_id, tipo=BudgetTransaction.Tipo.RESERVA,
    ).first()
    if reserva is None:
        raise DemandaInvalidaError(f"Nenhuma reserva encontrada para a demanda {demanda_id!r}.")

    allocation = BudgetAllocation.objects.select_for_update().get(pk=reserva.allocation_id)
    existente = _transacao_existente(demanda_id, BudgetTransaction.Tipo.EXECUCAO)
    if existente is not None:
        return existente
    if _transacao_existente(demanda_id, BudgetTransaction.Tipo.LIBERACAO) is not None:
        raise DemandaInvalidaError(f"Demanda {demanda_id!r} já foi liberada — não pode ser executada.")

    allocation.valor_comprometido -= reserva.valor
    allocation.valor_executado += reserva.valor
    allocation.save(update_fields=["valor_comprometido", "valor_executado"])
    return BudgetTransaction.objects.create(
        allocation=allocation, tipo=BudgetTransaction.Tipo.EXECUCAO, valor=reserva.valor,
        demanda_id=demanda_id, criado_por=usuario, justificativa="Execução da demanda.",
    )


@transaction.atomic
def liberar(*, demanda_id: str, usuario, motivo: str) -> BudgetTransaction:
    """Devolve o valor reservado ao comprometido da mesma alocação da reserva
    original — como nunca toca no pai, a devolução ao nível do solicitante já
    sai correta por construção."""
    reserva = BudgetTransaction.objects.filter(
        demanda_id=demanda_id, tipo=BudgetTransaction.Tipo.RESERVA,
    ).first()
    if reserva is None:
        raise DemandaInvalidaError(f"Nenhuma reserva encontrada para a demanda {demanda_id!r}.")

    allocation = BudgetAllocation.objects.select_for_update().get(pk=reserva.allocation_id)
    existente = _transacao_existente(demanda_id, BudgetTransaction.Tipo.LIBERACAO)
    if existente is not None:
        return existente
    if _transacao_existente(demanda_id, BudgetTransaction.Tipo.EXECUCAO) is not None:
        raise DemandaInvalidaError(f"Demanda {demanda_id!r} já foi executada — não pode ser liberada.")

    allocation.valor_comprometido -= reserva.valor
    allocation.save(update_fields=["valor_comprometido"])
    return BudgetTransaction.objects.create(
        allocation=allocation, tipo=BudgetTransaction.Tipo.LIBERACAO, valor=reserva.valor,
        demanda_id=demanda_id, justificativa=motivo, criado_por=usuario,
    )


# ---------------------------------------------------------------------------
# Remanejamento emergencial da UGP.
# ---------------------------------------------------------------------------

@transaction.atomic
def remanejar(*, origem: BudgetAllocation, destino: BudgetAllocation, valor: Decimal,
              usuario, justificativa: str) -> tuple[BudgetTransaction, BudgetTransaction]:
    """Move capacidade (valor_alocado) entre duas alocações da mesma Meta e
    Rubrica — mecanismo de exceção da UGP, não passa pela checagem de teto
    normal do nível pai (é o próprio propósito dele: furar a hierarquia)."""
    if origem.pk == destino.pk:
        raise DRFValidationError({"destino_allocation": "Origem e destino não podem ser a mesma alocação."})
    if origem.meta_id != destino.meta_id or origem.rubrica_id != destino.rubrica_id:
        raise DRFValidationError({
            "destino_allocation": "Origem e destino devem ser da mesma Meta e Rubrica."
        })

    # trava sempre em ordem crescente de pk, não na ordem origem/destino do
    # payload — dois remanejamentos concorrentes com origem/destino trocados
    # (A→B e B→A) travariam em ordem invertida e um dos dois cairia em deadlock.
    primeiro_pk, segundo_pk = sorted([origem.pk, destino.pk])
    primeiro = BudgetAllocation.objects.select_for_update().get(pk=primeiro_pk)
    segundo = BudgetAllocation.objects.select_for_update().get(pk=segundo_pk)
    origem = primeiro if primeiro.pk == origem.pk else segundo
    destino = primeiro if primeiro.pk == destino.pk else segundo

    saldo_origem = _saldo_disponivel(origem)
    if valor > saldo_origem:
        raise DRFValidationError({
            "valor": f"Saldo insuficiente na origem: R$ {saldo_origem} disponível."
        })

    origem.valor_alocado -= valor
    origem.save(update_fields=["valor_alocado"])
    destino.valor_alocado += valor
    destino.save(update_fields=["valor_alocado"])

    debito = BudgetTransaction.objects.create(
        allocation=origem, tipo=BudgetTransaction.Tipo.REMANEJAMENTO, valor=-valor,
        justificativa=justificativa, criado_por=usuario,
    )
    credito = BudgetTransaction.objects.create(
        allocation=destino, tipo=BudgetTransaction.Tipo.REMANEJAMENTO, valor=valor,
        justificativa=justificativa, criado_por=usuario,
    )
    return debito, credito


# ---------------------------------------------------------------------------
# Consulta de saldo pro endpoint HTTP — resolve nível pelo perfil do usuário
# sem passar por instâncias de Meta/Rubrica/Estado separadas, pra caber em
# poucas queries (ver views/budget.py).
# ---------------------------------------------------------------------------

def resolver_nivel_do_usuario(user) -> tuple[str, str | None, Territory | None]:
    """(nivel, sigla_do_estado, território) a partir do perfil do usuário —
    1 query. Não resolve um `State` (só a sigla): o lookup de alocação
    seguinte filtra `estado__sigla=` via join, sem precisar de outra query
    só pra ter a instância."""
    perfis = list(
        UserProfile.objects.filter(user=user).select_related("perfil", "territorio")
    )
    slugs = {p.perfil.slug for p in perfis}

    if "super-admin" in slugs or "ugp" in slugs:
        return Nivel.NACIONAL, None, None

    for p in perfis:
        if p.perfil.slug == "articulador-estadual" and p.territorio is not None:
            estados = p.territorio.estados or []
            if estados:
                return Nivel.ESTADUAL, estados[0], None

    for p in perfis:
        if p.perfil.slug == "adt-acr" and p.territorio is not None:
            return Nivel.TERRITORIAL, None, p.territorio

    # articulador/adt "global" (territorio=None, config válida em
    # UserProfile.territorio) cai aqui — este endpoint responde o saldo de
    # UM nível/localização, e um perfil global abrange mais de um. Fail
    # closed, mas com mensagem que não sugira falta de acesso nenhum.
    if any(p.perfil.slug in ("articulador-estadual", "adt-acr") for p in perfis):
        raise PermissionDenied(
            "Perfil sem estado/território específico — não é possível "
            "resolver um único nível para a consulta de saldo."
        )
    raise PermissionDenied("Você não tem acesso ao orçamento do SGP.")


def saldo_para_consulta(*, meta_id: int, rubrica_slug: str, nivel: str,
                         estado_sigla: str | None, territorio: Territory | None,
                         valor: Decimal) -> SaldoCheck:
    """Mesma resposta de `verificar_saldo`, mas resolvendo tudo numa query só
    via join — rubrica inválida/inativa e a alocação em si vêm do mesmo
    `.filter()`. Só o caminho de erro (nada encontrado) paga uma 2ª query,
    pra distinguir "rubrica não existe" de "rubrica ok, sem alocação"."""
    filtros = {
        "meta_id": meta_id, "rubrica__slug": rubrica_slug, "rubrica__ativo": True,
        "nivel": nivel,
    }
    if nivel == Nivel.ESTADUAL:
        filtros["estado__sigla"] = estado_sigla
    elif nivel == Nivel.TERRITORIAL:
        filtros["territorio"] = territorio

    allocation = (
        BudgetAllocation.objects
        .select_related("rubrica", "estado", "territorio")
        .filter(**filtros)
        .first()
    )
    if allocation is None:
        if not BudgetRubrica.objects.filter(slug=rubrica_slug, ativo=True).exists():
            raise DRFValidationError({
                "rubrica": f"Rubrica '{rubrica_slug}' não existe ou está inativa."
            })
        return SaldoCheck(
            disponivel=False, saldo=ZERO, allocation=None,
            motivo_bloqueio="Nenhuma alocação encontrada para este nível.",
        )
    return _saldo_check_de_allocation(allocation, valor)
