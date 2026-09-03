"""Agregação e regras de teto do orçamento por Meta/Rubrica."""

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
    _checar_teto(
        meta=meta, rubrica=rubrica, nivel=nivel, pai=pai,
        valor_total_pretendido=valor_pretendido, exclude_pk=exclude_pk,
    )
    return pai


@transaction.atomic
def criar_alocacao(*, meta, rubrica, nivel: str, valor_alocado: Decimal, usuario,
                    estado=None, territorio=None) -> BudgetAllocation:
    """Cria uma alocação validando o teto do nível pai.

    Só o nacional não tem pai — é o topo da hierarquia, o total aprovado no
    TED. Estadual/territorial sem pai (nível de cima ainda não distribuído)
    é rejeitado: sem pai não há teto contra o que validar.
    """
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
        valor_alocado=valor_alocado, criado_por=usuario,
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
