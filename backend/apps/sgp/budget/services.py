"""Pools de saldo por rubrica e nível: distribuição, motor de reserva e painel."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q, QuerySet, Sum
from django.db.models.functions import Coalesce
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models import Territory
from apps.core.models.user_profile import UserProfile
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.core.utils import get_config
from apps.sgp.models import BudgetPool, BudgetRubrica, BudgetTransaction

Nivel = BudgetPool.Nivel
ZERO = Decimal("0")


def is_global_budget_user(user) -> bool:
    return user_has_role(user, "super-admin") or user_has_role(user, "ugp")


def allowed_states_for_user(user) -> set[str]:
    return user_states(user)


def allowed_territories_for_user(user) -> QuerySet[Territory]:
    return user_territories(user)


def _perfis_e_slugs(user) -> tuple[list[UserProfile], set[str]]:
    """Perfis do usuário (`perfil`/`territorio` pré-carregados) e o set de slugs de
    papel — 1 query, compartilhada por `orcamento_detalhamento_scope`,
    `resolver_nivel_do_usuario` e `resolver_nivel_painel`.

    Implementação de escopo territorial separada de `services/access.py`
    por necessidade, não por descuido: as três funções abaixo precisam do
    mesmo perfil pré-carregado várias vezes por request (evitando N
    queries) e, no caso de `resolver_nivel_do_usuario`/`resolver_nivel_painel`,
    resolvem "um único nível/localização" (drill-down, `estados[0]` de um
    território específico) — não "o conjunto de estados/territórios do
    usuário" que `resolver_escopo()` devolve. Os dois tratam
    `adt-acr`/`territorio=None` do mesmo jeito que `access.py` corrige
    (ignora o perfil, nunca vira acesso global) — `test_budget_motor.py`
    tem um teste dedicado a essa paridade.
    """
    perfis = list(
        UserProfile.objects.filter(user=user).select_related("perfil", "territorio")
    )
    return perfis, {p.perfil.slug for p in perfis}


def _estados_do_articulador(perfis: list[UserProfile], user) -> set[str]:
    """Estados de todos os perfis `articulador-estadual` do usuário — perfil sem
    território (papel "global") cai no fallback de `allowed_states_for_user`."""
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
        states.update(allowed_states_for_user(user))
    return states


def _territorios_do_adt(perfis: list[UserProfile]) -> set[int]:
    """Perfil `adt-acr` sem território (`territorio=None`) é ignorado — nunca
    concede acesso global. Mesma regra que `services/access.py::_territorios_do_papel`."""
    return {p.territorio_id for p in perfis if p.perfil.slug == "adt-acr" and p.territorio_id}


def orcamento_detalhamento_scope(user) -> Q | None:
    """Filtro do *detalhamento* (linhas estaduais/territoriais) visível ao usuário.

    `None` = visão global. Nacional nunca aparece aqui — entra nos agregados
    (valor_aprovado/valor_distribuido), não na lista.

    Uma query só (perfil + território via select_related), não user_has_role/
    user_states/user_territories encadeados — cada um faria a sua própria.
    """
    perfis, slugs = _perfis_e_slugs(user)

    if "super-admin" in slugs or "ugp" in slugs:
        return None

    if "articulador-estadual" in slugs:
        states = _estados_do_articulador(perfis, user)
        if not states:
            return Q(pk__in=[])
        return Q(nivel=Nivel.ESTADUAL, estado__sigla__in=states) | Q(
            nivel=Nivel.TERRITORIAL, territorio__estados__overlap=list(states)
        )

    if "adt-acr" in slugs:
        territorio_ids = _territorios_do_adt(perfis)
        if not territorio_ids:
            return Q(pk__in=[])
        return Q(nivel=Nivel.TERRITORIAL, territorio_id__in=territorio_ids)

    raise PermissionDenied("Você não tem acesso ao orçamento do SGP.")


def _saldo_disponivel_matriz(
    aprovado: Decimal, distribuido: Decimal, comprometido: Decimal, executado: Decimal,
) -> Decimal:
    """`saldo_disponivel` das 5 colunas de §5.3.3. Compartilhado por `orcamento_por_rubrica`,
    `painel_orcamento` e `matriz_orcamento`."""
    return aprovado - distribuido - comprometido - executado


def orcamento_por_rubrica(user) -> list[dict]:
    """Uma entrada por rubrica ativa — valores nacionais/distribuídos agregados
    globalmente (não é dado sensível por território) e `detalhamento`
    (linhas estaduais/territoriais) recortado pelo escopo do usuário.
    """
    detalhamento_scope = orcamento_detalhamento_scope(user)

    rubricas = list(
        BudgetRubrica.objects.filter(ativo=True)
        .annotate(
            valor_aprovado=Coalesce(
                Sum("pools__valor_alocado", filter=Q(pools__nivel=Nivel.NACIONAL)), ZERO,
            ),
            valor_distribuido=Coalesce(
                Sum("pools__valor_alocado", filter=Q(pools__nivel=Nivel.ESTADUAL)), ZERO,
            ),
            valor_comprometido=Coalesce(
                Sum("pools__valor_comprometido", filter=Q(pools__nivel=Nivel.NACIONAL)), ZERO,
            ),
            valor_executado=Coalesce(
                Sum("pools__valor_executado", filter=Q(pools__nivel=Nivel.NACIONAL)), ZERO,
            ),
        )
        .order_by("ordem")
    )

    detalhamento_qs = BudgetPool.objects.exclude(
        nivel=Nivel.NACIONAL
    ).select_related("rubrica", "estado", "territorio")
    if detalhamento_scope is not None:
        detalhamento_qs = detalhamento_qs.filter(detalhamento_scope)
    detalhamento_por_rubrica: dict[int, list[BudgetPool]] = {}
    for pool in detalhamento_qs:
        detalhamento_por_rubrica.setdefault(pool.rubrica_id, []).append(pool)

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
            "saldo_disponivel": _saldo_disponivel_matriz(
                rubrica.valor_aprovado, rubrica.valor_distribuido,
                rubrica.valor_comprometido, rubrica.valor_executado,
            ),
            "detalhamento": detalhamento_por_rubrica.get(rubrica.pk, []),
        })
    return resultado


# ---------------------------------------------------------------------------
# Distribuição — teto por nível, concorrência via select_for_update.
# ---------------------------------------------------------------------------

def _saldo_disponivel(pool: BudgetPool) -> Decimal:
    return pool.valor_alocado - pool.valor_comprometido - pool.valor_executado


def _linha_pai(*, rubrica, nivel: str, territorio=None, estado=None) -> BudgetPool | None:
    """O pool de nível imediatamente acima que 'financia' este.

    territorial → o estadual da mesma rubrica, no estado do território.
    estadual → o nacional da mesma rubrica.
    nacional → não tem pai (é o teto absoluto, o total aprovado no TED).
    """
    if nivel == Nivel.TERRITORIAL:
        estados_do_territorio = territorio.estados or []
        if not estados_do_territorio:
            return None
        # .first() com order_by explícito: só é ambíguo se o território
        # cobrir >1 estado com pool estadual próprio — caso raro, mas
        # sem UniqueConstraint que garanta 1 só aqui (ao contrário do nacional).
        return BudgetPool.objects.filter(
            rubrica=rubrica, nivel=Nivel.ESTADUAL,
            estado__sigla__in=estados_do_territorio,
        ).order_by("pk").first()
    if nivel == Nivel.ESTADUAL:
        # A UniqueConstraint de BudgetPool garante no máximo 1 linha nacional
        # por rubrica — .first() aqui nunca é ambíguo.
        return BudgetPool.objects.filter(rubrica=rubrica, nivel=Nivel.NACIONAL).first()
    return None


def _peers_sob_mesmo_pai(*, rubrica, nivel: str, pai: BudgetPool, exclude_pk=None) -> QuerySet:
    """Outros pools do mesmo nível que também consomem o saldo de `pai`.

    Para territorial isso é só os territórios do mesmo estado do `pai`
    (um território pode, em tese, cobrir mais de um estado) — para
    estadual, todas compartilham o mesmo pai nacional, sem filtro extra.
    """
    qs = BudgetPool.objects.filter(rubrica=rubrica, nivel=nivel)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if nivel == Nivel.TERRITORIAL:
        qs = qs.filter(territorio__estados__contains=[pai.estado.sigla])
    return qs


def _checar_teto(*, rubrica, nivel, pai, valor_total_pretendido: Decimal, exclude_pk=None) -> None:
    peers = _peers_sob_mesmo_pai(rubrica=rubrica, nivel=nivel, pai=pai, exclude_pk=exclude_pk)
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


def _travar_pai_e_checar_teto(*, rubrica, nivel, territorio, estado,
                               valor_pretendido: Decimal, exclude_pk=None) -> BudgetPool | None:
    pai = _linha_pai(rubrica=rubrica, nivel=nivel, territorio=territorio, estado=estado)
    if pai is None:
        return None
    pai = BudgetPool.objects.select_for_update().get(pk=pai.pk)
    if pai.reserva_ugp:
        raise DRFValidationError({
            "valor_alocado": "A reserva própria da UGP não pode receber alocações-filhas."
        })
    _checar_teto(
        rubrica=rubrica, nivel=nivel, pai=pai,
        valor_total_pretendido=valor_pretendido, exclude_pk=exclude_pk,
    )
    return pai


@transaction.atomic
def criar_pool(*, rubrica, nivel: str, valor_alocado: Decimal, usuario,
               estado=None, territorio=None, reserva_ugp: bool = False) -> BudgetPool:
    """Cria um pool validando o teto do nível pai.

    Só o nacional não tem pai — é o topo da hierarquia, o total aprovado no
    TED. Estadual/territorial sem pai (nível de cima ainda não distribuído)
    é rejeitado: sem pai não há teto contra o que validar.

    `reserva_ugp` só se aplica ao nível nacional — um pool marcado assim
    fica retido com a UGP e nunca pode receber pool-filho.

    O território identifica o pool sozinho: o estado informado junto só serve para
    achar o pai e não é gravado, senão o mesmo território poderia ter dois pools.
    """
    if reserva_ugp and nivel != Nivel.NACIONAL:
        raise DRFValidationError({
            "reserva_ugp": "Reserva própria da UGP só é aplicável ao nível nacional."
        })

    pai = _travar_pai_e_checar_teto(
        rubrica=rubrica, nivel=nivel, territorio=territorio, estado=estado,
        valor_pretendido=valor_alocado,
    )
    if pai is None and nivel != Nivel.NACIONAL:
        raise DRFValidationError({
            "nivel": (
                "Não existe pool do nível superior para esta combinação "
                "de Rubrica/Estado — distribua o nível acima primeiro."
            )
        })

    try:
        with transaction.atomic():
            pool = BudgetPool.objects.create(
                rubrica=rubrica, nivel=nivel,
                estado=None if nivel == Nivel.TERRITORIAL else estado, territorio=territorio,
                valor_alocado=valor_alocado, reserva_ugp=reserva_ugp, criado_por=usuario,
            )
    except IntegrityError as exc:
        raise DRFValidationError({
            "nivel": "Já existe um pool para esta rubrica neste nível. Altere o valor dele."
        }) from exc
    BudgetTransaction.objects.create(
        pool=pool, tipo=BudgetTransaction.Tipo.REMANEJAMENTO,
        valor=valor_alocado, criado_por=usuario,
        justificativa="Criação de pool.",
    )
    return pool


@transaction.atomic
def atualizar_valor_alocado(pool: BudgetPool, *, novo_valor: Decimal, usuario) -> BudgetPool:
    """Reduzir abaixo do já comprometido+executado é rejeitado."""
    pai = _linha_pai(
        rubrica=pool.rubrica, nivel=pool.nivel, territorio=pool.territorio, estado=pool.estado,
    )
    # O pool e o pai em ordem crescente de pk, como `remanejar`, que trava os dois
    # quando move saldo entre níveis: travar o filho antes do pai inverteria essa ordem.
    pks = sorted({pool.pk} | ({pai.pk} if pai is not None else set()))
    travados = {pk: BudgetPool.objects.select_for_update().get(pk=pk) for pk in pks}
    pool = travados[pool.pk]

    minimo = pool.valor_comprometido + pool.valor_executado
    if novo_valor < minimo:
        raise DRFValidationError({
            "valor_alocado": (
                f"Não é possível reduzir abaixo do já comprometido/executado (R$ {minimo})."
            )
        })

    _travar_pai_e_checar_teto(
        rubrica=pool.rubrica, nivel=pool.nivel, territorio=pool.territorio, estado=pool.estado,
        valor_pretendido=novo_valor, exclude_pk=pool.pk,
    )

    valor_delta = novo_valor - pool.valor_alocado
    pool.valor_alocado = novo_valor
    pool.save(update_fields=["valor_alocado"])
    BudgetTransaction.objects.create(
        pool=pool, tipo=BudgetTransaction.Tipo.REMANEJAMENTO,
        valor=valor_delta, criado_por=usuario,
        justificativa="Ajuste de pool.",
    )
    return pool


def remover_pool(pool: BudgetPool) -> None:
    """`BudgetTransaction.pool` é PROTECT — todo pool nasce com pelo menos a
    transaction da criação, então .delete() sempre bateria em ProtectedError.
    Traduz isso pra uma mensagem clara em vez de vazar 500.
    """
    try:
        pool.delete()
    except ProtectedError:
        raise DRFValidationError({
            "detail": (
                "Não é possível excluir: existem transações registradas "
                "para este pool."
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
    pool: BudgetPool | None
    motivo_bloqueio: str | None = None


def _pool_para(*, rubrica, nivel: str, estado=None, territorio=None) -> BudgetPool | None:
    filtros = {"rubrica": rubrica, "nivel": nivel}
    if nivel == Nivel.ESTADUAL:
        filtros["estado"] = estado
    elif nivel == Nivel.TERRITORIAL:
        filtros["territorio"] = territorio
    return BudgetPool.objects.filter(**filtros).first()


def _saldo_check_de_pool(
    pool: BudgetPool, valor: Decimal, consumo_previo: Decimal = ZERO,
) -> SaldoCheck:
    saldo = _saldo_disponivel(pool) - consumo_previo
    # Zerado só pelo consumo da própria operação, a rubrica ainda tem saldo:
    # cai no "insuficiente", que mostra disponível e solicitado.
    if saldo <= ZERO and consumo_previo <= ZERO:
        return SaldoCheck(disponivel=False, saldo=saldo, pool=pool, motivo_bloqueio=BLOQUEIO_SALDO_ZERO)
    if valor > saldo:
        return SaldoCheck(
            disponivel=False, saldo=saldo, pool=pool,
            motivo_bloqueio=f"Saldo insuficiente: R$ {saldo} disponível, R$ {valor} solicitado.",
        )
    return SaldoCheck(disponivel=True, saldo=saldo, pool=pool, motivo_bloqueio=None)


def verificar_saldo(*, rubrica, nivel: str, territorio=None, estado=None, valor: Decimal) -> SaldoCheck:
    """API pública do motor — recebe instâncias já resolvidas (rubrica,
    estado/território). `saldo_para_consulta`, mais abaixo, resolve o mesmo
    SaldoCheck mas a partir de ids/slugs crus e numa query só, pro endpoint
    HTTP caber no orçamento de queries — por isso as duas coexistem."""
    pool = _pool_para(rubrica=rubrica, nivel=nivel, estado=estado, territorio=territorio)
    if pool is None:
        return SaldoCheck(
            disponivel=False, saldo=ZERO, pool=None,
            motivo_bloqueio="Nenhuma alocação encontrada para este nível.",
        )
    return _saldo_check_de_pool(pool, valor)


def _transacoes_do_pool(demanda_id: str) -> QuerySet[BudgetTransaction]:
    """O limite individual lança no mesmo ledger, com a mesma chave: aqui só interessa o pool."""
    return BudgetTransaction.objects.filter(demanda_id=demanda_id, pool__isnull=False)


def _transacao_existente(demanda_id: str, tipo: str) -> BudgetTransaction | None:
    return _transacoes_do_pool(demanda_id).filter(tipo=tipo).first()


_VERBO_PASSADO = {
    BudgetTransaction.Tipo.EXECUCAO: "executada",
    BudgetTransaction.Tipo.LIBERACAO: "liberada",
}


def _rejeitar_se_finalizada(demanda_id: str, *, tipos_bloqueantes: list[str], acao: str) -> None:
    for tipo in tipos_bloqueantes:
        if _transacao_existente(demanda_id, tipo) is not None:
            raise DemandaInvalidaError(
                f"Demanda {demanda_id!r} já foi {_VERBO_PASSADO[tipo]} — não pode ser {acao}."
            )


def _valor_total_reservado(demanda_id: str) -> Decimal:
    """Reserva original + todo `ajustar_reserva` aplicado depois. `executar`/
    `liberar` usam isto, não `reserva.valor` puro, senão um ajuste ficaria
    fora da conta."""
    reserva = _transacao_existente(demanda_id, BudgetTransaction.Tipo.RESERVA)
    if reserva is None:
        return ZERO
    ajustes = _transacoes_do_pool(demanda_id).filter(
        tipo=BudgetTransaction.Tipo.AJUSTE,
    ).aggregate(total=Coalesce(Sum("valor"), ZERO))["total"]
    return reserva.valor + ajustes


@transaction.atomic
def reservar(*, pool: BudgetPool, valor: Decimal, demanda_id: str, usuario,
             justificativa: str = "", activity_id: int | None = None) -> BudgetTransaction:
    """Idempotente por demanda_id — a checagem roda depois do lock no
    pool, então duas chamadas concorrentes pro mesmo demanda_id
    serializam ali; a segunda, ao acordar, já encontra a transaction da
    primeira e não duplica o comprometimento."""
    if valor <= ZERO:
        # chamado direto pelo motor, sem o min_value=0 da serializer HTTP —
        # sem essa guarda, um valor negativo "reservaria" liberando saldo.
        raise ValueError(f"valor precisa ser positivo, recebi {valor}.")

    pool = BudgetPool.objects.select_for_update().get(pk=pool.pk)
    existente = _transacao_existente(demanda_id, BudgetTransaction.Tipo.RESERVA)
    if existente is not None:
        return existente

    saldo = _saldo_disponivel(pool)
    if valor > saldo:
        raise SaldoInsuficienteError(
            f"Saldo insuficiente: R$ {saldo} disponível, R$ {valor} solicitado."
        )

    pool.valor_comprometido += valor
    pool.save(update_fields=["valor_comprometido"])
    return BudgetTransaction.objects.create(
        pool=pool, tipo=BudgetTransaction.Tipo.RESERVA, valor=valor,
        demanda_id=demanda_id, activity_id=activity_id, justificativa=justificativa, criado_por=usuario,
    )


@transaction.atomic
def ajustar_reserva(*, demanda_id: str, novo_valor: Decimal, usuario, justificativa: str = "") -> BudgetTransaction:
    """Registra o delta como uma `BudgetTransaction` própria (`Tipo.AJUSTE`)
    em vez de reescrever a reserva original. Não é idempotente — ao
    contrário de reservar/executar/liberar, quem chama garante que só
    invoca isto uma vez por decisão."""
    reserva = _transacao_existente(demanda_id, BudgetTransaction.Tipo.RESERVA)
    if reserva is None:
        raise DemandaInvalidaError(f"Nenhuma reserva encontrada para a demanda {demanda_id!r}.")
    _rejeitar_se_finalizada(
        demanda_id,
        tipos_bloqueantes=[BudgetTransaction.Tipo.EXECUCAO, BudgetTransaction.Tipo.LIBERACAO],
        acao="ajustada",
    )

    pool = BudgetPool.objects.select_for_update().get(pk=reserva.pool_id)
    valor_atual = _valor_total_reservado(demanda_id)
    delta = novo_valor - valor_atual
    if delta > ZERO and delta > _saldo_disponivel(pool):
        raise SaldoInsuficienteError(
            f"Saldo insuficiente para o ajuste: R$ {_saldo_disponivel(pool)} disponível, "
            f"R$ {delta} a mais solicitado."
        )

    pool.valor_comprometido += delta
    pool.save(update_fields=["valor_comprometido"])
    return BudgetTransaction.objects.create(
        pool=pool, tipo=BudgetTransaction.Tipo.AJUSTE, valor=delta,
        demanda_id=demanda_id, activity_id=reserva.activity_id, criado_por=usuario, justificativa=justificativa or "Ajuste de valor autorizado.",
    )


@transaction.atomic
def executar(*, demanda_id: str, usuario, valor_executado: Decimal | None = None) -> BudgetTransaction:
    """`valor_executado=None` executa o valor reservado por inteiro. Um
    valor menor executa só essa parte e registra a diferença como uma
    `BudgetTransaction` de liberação própria."""
    valor_reservado = _valor_total_reservado(demanda_id)
    if valor_reservado <= ZERO:
        raise DemandaInvalidaError(f"Nenhuma reserva encontrada para a demanda {demanda_id!r}.")

    reserva = _transacao_existente(demanda_id, BudgetTransaction.Tipo.RESERVA)
    pool = BudgetPool.objects.select_for_update().get(pk=reserva.pool_id)
    existente = _transacao_existente(demanda_id, BudgetTransaction.Tipo.EXECUCAO)
    if existente is not None:
        return existente
    _rejeitar_se_finalizada(demanda_id, tipos_bloqueantes=[BudgetTransaction.Tipo.LIBERACAO], acao="executada")

    valor_final = valor_reservado if valor_executado is None else valor_executado
    diferenca = valor_reservado - valor_final

    pool.valor_comprometido -= valor_reservado
    pool.valor_executado += valor_final
    pool.save(update_fields=["valor_comprometido", "valor_executado"])
    execucao = BudgetTransaction.objects.create(
        pool=pool, tipo=BudgetTransaction.Tipo.EXECUCAO, valor=valor_final,
        demanda_id=demanda_id, activity_id=reserva.activity_id, criado_por=usuario, justificativa="Execução da demanda.",
    )
    if diferenca > ZERO:
        BudgetTransaction.objects.create(
            pool=pool, tipo=BudgetTransaction.Tipo.LIBERACAO, valor=diferenca,
            demanda_id=demanda_id, activity_id=reserva.activity_id, criado_por=usuario,
            justificativa="Diferença entre valor reservado e valor efetivamente pago na execução.",
        )
    return execucao


@transaction.atomic
def liberar(*, demanda_id: str, usuario, motivo: str) -> BudgetTransaction:
    """Devolve o valor reservado (reserva original + ajustes, se houver) ao
    comprometido do mesmo pool — como nunca toca no pai, a devolução ao
    nível do solicitante já sai correta por construção."""
    valor_reservado = _valor_total_reservado(demanda_id)
    if valor_reservado <= ZERO:
        raise DemandaInvalidaError(f"Nenhuma reserva encontrada para a demanda {demanda_id!r}.")

    reserva = _transacao_existente(demanda_id, BudgetTransaction.Tipo.RESERVA)
    pool = BudgetPool.objects.select_for_update().get(pk=reserva.pool_id)
    existente = _transacao_existente(demanda_id, BudgetTransaction.Tipo.LIBERACAO)
    if existente is not None:
        return existente
    _rejeitar_se_finalizada(demanda_id, tipos_bloqueantes=[BudgetTransaction.Tipo.EXECUCAO], acao="liberada")

    pool.valor_comprometido -= valor_reservado
    pool.save(update_fields=["valor_comprometido"])
    return BudgetTransaction.objects.create(
        pool=pool, tipo=BudgetTransaction.Tipo.LIBERACAO, valor=valor_reservado,
        demanda_id=demanda_id, activity_id=reserva.activity_id, justificativa=motivo, criado_por=usuario,
    )


# ---------------------------------------------------------------------------
# Remanejamento emergencial da UGP.
# ---------------------------------------------------------------------------

@transaction.atomic
def remanejar(*, origem: BudgetPool, destino: BudgetPool, valor: Decimal,
              usuario, justificativa: str) -> tuple[BudgetTransaction, BudgetTransaction]:
    """Move capacidade (valor_alocado) entre dois pools da mesma rubrica —
    mecanismo de exceção da UGP, não passa pela checagem de teto
    normal do nível pai (é o próprio propósito dele: furar a hierarquia)."""
    if origem.pk == destino.pk:
        raise DRFValidationError({"destino_allocation": "Origem e destino não podem ser a mesma alocação."})
    if origem.rubrica_id != destino.rubrica_id:
        raise DRFValidationError({
            "destino_allocation": "Origem e destino devem ser da mesma rubrica."
        })

    # trava sempre em ordem crescente de pk, não na ordem origem/destino do
    # payload — dois remanejamentos concorrentes com origem/destino trocados
    # (A→B e B→A) travariam em ordem invertida e um dos dois cairia em deadlock.
    primeiro_pk, segundo_pk = sorted([origem.pk, destino.pk])
    primeiro = BudgetPool.objects.select_for_update().get(pk=primeiro_pk)
    segundo = BudgetPool.objects.select_for_update().get(pk=segundo_pk)
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
        pool=origem, tipo=BudgetTransaction.Tipo.REMANEJAMENTO, valor=-valor,
        justificativa=justificativa, criado_por=usuario,
    )
    credito = BudgetTransaction.objects.create(
        pool=destino, tipo=BudgetTransaction.Tipo.REMANEJAMENTO, valor=valor,
        justificativa=justificativa, criado_por=usuario,
    )
    return debito, credito


# ---------------------------------------------------------------------------
# Consulta de saldo pro endpoint HTTP — resolve nível pelo perfil do usuário
# sem passar por instâncias de Rubrica/Estado separadas, pra caber em
# poucas queries (ver budget/views.py).
# ---------------------------------------------------------------------------

def resolver_nivel_do_usuario(user) -> tuple[str, str | None, Territory | None]:
    """(nivel, sigla_do_estado, território) a partir do perfil do usuário —
    1 query. Não resolve um `State` (só a sigla): o lookup de pool
    seguinte filtra `estado__sigla=` via join, sem precisar de outra query
    só pra ter a instância."""
    perfis, slugs = _perfis_e_slugs(user)

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


def saldo_para_consulta(*, rubrica_slug: str, nivel: str,
                         estado_sigla: str | None, territorio: Territory | None,
                         valor: Decimal, consumo_previo: Decimal = ZERO) -> SaldoCheck:
    """Mesma resposta de `verificar_saldo`, mas resolvendo tudo numa query só
    via join — rubrica inválida/inativa e o pool em si vêm do mesmo
    `.filter()`. Só o caminho de erro (nada encontrado) paga uma 2ª query,
    pra distinguir "rubrica não existe" de "rubrica ok, sem pool".

    `consumo_previo` é o que a mesma operação ainda vai reservar neste
    pool antes de `valor` — sai do saldo antes da comparação."""
    filtros = {"rubrica__slug": rubrica_slug, "rubrica__ativo": True, "nivel": nivel}
    if nivel == Nivel.ESTADUAL:
        filtros["estado__sigla"] = estado_sigla
    elif nivel == Nivel.TERRITORIAL:
        filtros["territorio"] = territorio

    pool = (
        BudgetPool.objects
        .select_related("rubrica", "estado", "territorio")
        .filter(**filtros)
        .first()
    )
    if pool is None:
        if not BudgetRubrica.objects.filter(slug=rubrica_slug, ativo=True).exists():
            raise DRFValidationError({
                "rubrica": f"Rubrica '{rubrica_slug}' não existe ou está inativa."
            })
        return SaldoCheck(
            disponivel=False, saldo=ZERO, pool=None,
            motivo_bloqueio="Nenhuma alocação encontrada para este nível.",
        )
    return _saldo_check_de_pool(pool, valor, consumo_previo)


# ---------------------------------------------------------------------------
# Painel de orçamento — Rubrica × Nível, com semáforo.
# ---------------------------------------------------------------------------

LIMIAR_SEMAFORO_AMARELO_PADRAO = 70
LIMIAR_SEMAFORO_VERMELHO_PADRAO = 90


def percentual_comprometido(comprometido: Decimal, total: Decimal) -> Decimal:
    if total <= ZERO:
        return ZERO
    return (comprometido / total) * Decimal("100")


@dataclass(frozen=True)
class LimiaresSemaforo:
    amarelo: Decimal
    vermelho: Decimal


def limiares_semaforo() -> LimiaresSemaforo:
    """Limiares globais `budget_alert_yellow_pct`/`budget_alert_red_pct` do
    Core. Quem classifica várias faixas na mesma operação (células do painel,
    antes/depois de uma reserva) lê uma vez e repassa — com o cache frio ou
    sem a linha no SystemConfig, cada leitura é uma query."""
    return LimiaresSemaforo(
        amarelo=Decimal(get_config("budget_alert_yellow_pct", LIMIAR_SEMAFORO_AMARELO_PADRAO)),
        vermelho=Decimal(get_config("budget_alert_red_pct", LIMIAR_SEMAFORO_VERMELHO_PADRAO)),
    )


def faixa_semaforo(percentual: Decimal, limiares: LimiaresSemaforo) -> str:
    """Faixa do semáforo orçamentário — a mesma pra todo nível (limite
    individual, pools, Meta/Submeta/Ação) e pra todo módulo que consome saldo."""
    if percentual >= limiares.vermelho:
        return "vermelho"
    if percentual >= limiares.amarelo:
        return "amarelo"
    return "verde"


def _sem_territorio(mensagem: str) -> PermissionDenied:
    """403 de quem tem o perfil, mas ainda sem estado ou território vinculado.
    O `code` distingue do "sem acesso": o frontend mostra o estado vazio em vez
    de "Conteúdo restrito"."""
    return PermissionDenied({"detail": mensagem, "code": "SEM_TERRITORIO"})


def resolver_nivel_painel(
    user, *, estado_sigla: str | None = None, territorio_id: int | None = None,
) -> tuple[str, str | None, int | None]:
    """(nivel, estado_sigla, territorio_id) do painel pro usuário — mesma política de
    RBAC de `orcamento_detalhamento_scope`/`resolver_nivel_do_usuario`, aplicada à
    escolha de qual nível é exibido (drill-down), não a uma lista de detalhamento.

    Devolve o id do território (não a instância — só é usado pra filtrar
    `BudgetPool.territorio_id`).

    1 query base (perfil), +1 só quando um Articulador Estadual pede um `territorio_id`
    explícito (confirma que pertence ao próprio estado). Se `estado_sigla` e
    `territorio_id` vierem os dois, `territorio_id` vence pra super-admin/ugp/
    articulador-estadual — ADT/ACR rejeita `estado_sigla` antes de olhar
    `territorio_id` (não tem nível estadual, ver bloco abaixo).
    """
    perfis, slugs = _perfis_e_slugs(user)

    if "super-admin" in slugs or "ugp" in slugs:
        if territorio_id is not None:
            return Nivel.TERRITORIAL, None, territorio_id
        if estado_sigla is not None:
            return Nivel.ESTADUAL, estado_sigla, None
        return Nivel.NACIONAL, None, None

    if "articulador-estadual" in slugs:
        states = _estados_do_articulador(perfis, user)
        if not states:
            raise _sem_territorio("Seu perfil de Articulador Estadual ainda não tem estado vinculado.")

        if territorio_id is not None:
            territorio = Territory.objects.filter(pk=territorio_id).only("estados").first()
            if territorio is None or not set(territorio.estados or []) & states:
                raise PermissionDenied("Este território não pertence ao seu estado.")
            return Nivel.TERRITORIAL, None, territorio_id
        if estado_sigla is not None:
            if estado_sigla not in states:
                raise PermissionDenied("Este estado não pertence ao seu escopo.")
            return Nivel.ESTADUAL, estado_sigla, None
        # Nacional não é dado sensível por território (§B2) — visível também sem filtro.
        return Nivel.NACIONAL, None, None

    if "adt-acr" in slugs:
        territorio_ids = _territorios_do_adt(perfis)
        if not territorio_ids:
            raise _sem_territorio("Seu perfil de ADT/ACR ainda não tem território vinculado.")
        if estado_sigla is not None:
            raise PermissionDenied("Você não tem acesso a dados no nível estadual.")
        if territorio_id is not None and territorio_id not in territorio_ids:
            raise PermissionDenied("Você não tem acesso a este território.")
        escolhido = territorio_id if territorio_id is not None else next(iter(territorio_ids))
        return Nivel.TERRITORIAL, None, escolhido

    raise PermissionDenied("Você não tem acesso ao orçamento do SGP.")


def _semaforo_orcamento(percentual: Decimal, limiares: LimiaresSemaforo) -> tuple[str, bool]:
    """(semaforo, alerta_80) — o alerta dispara no mesmo limiar de vermelho, uma
    fonte só pros dois campos. `alerta_80` mantém o nome por contrato com o
    front, mas segue o limiar configurado, não 80 fixo."""
    semaforo = faixa_semaforo(percentual, limiares)
    return semaforo, semaforo == "vermelho"


def pools_em_vermelho() -> list[BudgetPool]:
    """Todo `BudgetPool` (qualquer nível) com semáforo vermelho — usada por
    `tasks.check_budget_threshold_alert`. Nacional, estadual e territorial são linhas
    independentes, cada uma pode estar em vermelho por si só."""
    limiares = limiares_semaforo()
    vermelhos = []
    pools = (
        BudgetPool.objects
        .select_related("rubrica", "estado", "territorio")
        .filter(valor_alocado__gt=ZERO)
    )
    for pool in pools:
        percentual = percentual_comprometido(pool.valor_comprometido, pool.valor_alocado)
        if faixa_semaforo(percentual, limiares) == "vermelho":
            vermelhos.append(pool)
    return vermelhos


def _executado_por_pool_na_meta(meta_id: int) -> dict[int, Decimal]:
    """A Meta não tem saldo: o executado dela sai das execuções do ledger, pela cadeia
    Atividade → Ação → Meta."""
    return {
        linha["pool_id"]: linha["total"]
        for linha in BudgetTransaction.objects.filter(
            tipo=BudgetTransaction.Tipo.EXECUCAO, activity__acao__meta_id=meta_id,
        ).order_by().values("pool_id").annotate(total=Sum("valor"))
    }


def painel_orcamento(
    *, nivel: str, estado_sigla: str | None = None, territorio_id: int | None = None,
    rubrica_slug: str | None = None, meta_id: int | None = None,
) -> list[dict]:
    """Uma linha por rubrica ativa no `nivel` dado, com semáforo e alerta de vermelho:
    a soma que o painel do SGD e os alertas da home consomem. A matriz com o id de cada
    pool, para a tela do orçamento, é `matriz_orcamento`.

    Motor sem RBAC — quem chama já resolveu o nível/localização (ver
    `painel_orcamento_para_usuario`). `meta_id` não recorta o saldo: só acrescenta
    `valor_executado_meta`.

    3 queries (rubricas, próprios, distribuído; 2 se `nivel` for territorial, sem
    distribuído), +1 com `meta_id` e +2 só com o cache dos limiares do semáforo frio.
    """
    rubricas_qs = BudgetRubrica.objects.filter(ativo=True).order_by("ordem")
    if rubrica_slug is not None:
        rubricas_qs = rubricas_qs.filter(slug=rubrica_slug)
    rubricas = list(rubricas_qs)

    filtros_proprios = {"nivel": nivel}
    if nivel == Nivel.ESTADUAL:
        filtros_proprios["estado__sigla"] = estado_sigla
    elif nivel == Nivel.TERRITORIAL:
        filtros_proprios["territorio_id"] = territorio_id

    proprios = {
        linha["rubrica_id"]: linha
        for linha in (
            BudgetPool.objects.filter(**filtros_proprios)
            .order_by()
            .values("rubrica_id")
            .annotate(
                valor_alocado=Sum("valor_alocado"),
                valor_comprometido=Sum("valor_comprometido"),
                valor_executado=Sum("valor_executado"),
            )
        )
    }

    # "Distribuído" = soma do nível filho. Territorial é folha: sem filhos, sem query.
    distribuido_qs = None
    if nivel == Nivel.NACIONAL:
        distribuido_qs = BudgetPool.objects.filter(nivel=Nivel.ESTADUAL)
    elif nivel == Nivel.ESTADUAL:
        distribuido_qs = BudgetPool.objects.filter(
            nivel=Nivel.TERRITORIAL, territorio__estados__contains=[estado_sigla],
        )

    distribuido = {}
    if distribuido_qs is not None:
        distribuido = {
            linha["rubrica_id"]: linha["total"]
            for linha in distribuido_qs.order_by().values("rubrica_id").annotate(total=Sum("valor_alocado"))
        }

    executado_meta = {}
    if meta_id is not None:
        executado_meta = {
            linha["pool__rubrica_id"]: linha["total"]
            for linha in BudgetTransaction.objects.filter(
                tipo=BudgetTransaction.Tipo.EXECUCAO, activity__acao__meta_id=meta_id,
                **{f"pool__{campo}": valor for campo, valor in filtros_proprios.items()},
            ).order_by().values("pool__rubrica_id").annotate(total=Sum("valor"))
        }

    limiares = limiares_semaforo()
    resultado = []
    for rubrica in rubricas:
        proprio = proprios.get(rubrica.pk)
        valor_aprovado = proprio["valor_alocado"] if proprio else ZERO
        valor_comprometido = proprio["valor_comprometido"] if proprio else ZERO
        valor_executado = proprio["valor_executado"] if proprio else ZERO
        valor_distribuido = distribuido.get(rubrica.pk, ZERO)
        percentual = percentual_comprometido(valor_comprometido, valor_aprovado)
        semaforo, alerta_80 = _semaforo_orcamento(percentual, limiares)
        linha = {
            "rubrica": rubrica,
            "nivel": nivel,
            "valor_aprovado": valor_aprovado,
            "valor_distribuido": valor_distribuido,
            "valor_comprometido": valor_comprometido,
            "valor_executado": valor_executado,
            "saldo_disponivel": _saldo_disponivel_matriz(
                valor_aprovado, valor_distribuido, valor_comprometido, valor_executado,
            ),
            "semaforo": semaforo,
            "alerta_80": alerta_80,
            "limiares_semaforo": limiares,
        }
        if meta_id is not None:
            linha["valor_executado_meta"] = executado_meta.get(rubrica.pk, ZERO)
        resultado.append(linha)
    return resultado


def painel_orcamento_para_usuario(
    user, *, estado_sigla: str | None = None, territorio_id: int | None = None,
    rubrica_slug: str | None = None, meta_id: int | None = None,
) -> list[dict]:
    """Resolve o nível/localização pelo RBAC do usuário (`resolver_nivel_painel`) e
    delega o cálculo a `painel_orcamento`."""
    nivel, estado_sigla, territorio_id = resolver_nivel_painel(
        user, estado_sigla=estado_sigla, territorio_id=territorio_id,
    )
    return painel_orcamento(
        nivel=nivel, estado_sigla=estado_sigla, territorio_id=territorio_id,
        rubrica_slug=rubrica_slug, meta_id=meta_id,
    )


_ORDEM_DO_NIVEL = {Nivel.NACIONAL: 0, Nivel.ESTADUAL: 1, Nivel.TERRITORIAL: 2}


def _pools_da_matriz(user, *, estado_sigla, territorio_id, rubrica_slug, nivel) -> QuerySet[BudgetPool]:
    """Recorte de pools da matriz. `resolver_nivel_painel` já recusou o que o perfil não
    pode pedir, então um `estado` ou `territorio` informado está dentro do escopo."""
    pools = BudgetPool.objects.filter(rubrica__ativo=True).select_related("rubrica", "estado", "territorio")
    if territorio_id is not None:
        pools = pools.filter(nivel=Nivel.TERRITORIAL, territorio_id=territorio_id)
    elif estado_sigla is not None:
        pools = pools.filter(
            Q(nivel=Nivel.ESTADUAL, estado__sigla=estado_sigla)
            | Q(nivel=Nivel.TERRITORIAL, territorio__estados__contains=[estado_sigla])
        )
    else:
        escopo = orcamento_detalhamento_scope(user)
        if escopo is not None:
            # Nacional não é dado sensível por território: o Articulador também vê.
            if user_has_role(user, "articulador-estadual"):
                escopo |= Q(nivel=Nivel.NACIONAL)
            pools = pools.filter(escopo)
    if rubrica_slug is not None:
        pools = pools.filter(rubrica__slug=rubrica_slug)
    if nivel is not None:
        pools = pools.filter(nivel=nivel)
    return pools


def _distribuido_por_pool(pools: list[BudgetPool]) -> dict[int, Decimal]:
    """O que já desceu para o nível filho de cada pool: os estaduais da rubrica, para o
    nacional; os territoriais do estado na rubrica, para o estadual."""
    rubricas = {pool.rubrica_id for pool in pools if pool.nivel != Nivel.TERRITORIAL}
    if not rubricas:
        return {}
    filhos = list(
        BudgetPool.objects.filter(rubrica_id__in=rubricas, nivel__in=[Nivel.ESTADUAL, Nivel.TERRITORIAL])
        .order_by()
        .values("rubrica_id", "nivel", "valor_alocado", "territorio__estados")
    )
    distribuido = {}
    for pool in pools:
        if pool.nivel == Nivel.NACIONAL:
            distribuido[pool.pk] = sum(
                (f["valor_alocado"] for f in filhos if f["rubrica_id"] == pool.rubrica_id and f["nivel"] == Nivel.ESTADUAL),
                ZERO,
            )
        elif pool.nivel == Nivel.ESTADUAL:
            distribuido[pool.pk] = sum(
                (
                    f["valor_alocado"] for f in filhos
                    if f["rubrica_id"] == pool.rubrica_id and f["nivel"] == Nivel.TERRITORIAL
                    and pool.estado.sigla in (f["territorio__estados"] or [])
                ),
                ZERO,
            )
    return distribuido


def matriz_orcamento_para_usuario(
    user, *, estado_sigla: str | None = None, territorio_id: int | None = None,
    rubrica_slug: str | None = None, nivel: str | None = None, meta_id: int | None = None,
) -> list[dict]:
    """Matriz Rubrica × Nível: uma linha por pool no escopo do usuário, com o id que a
    origem do excedente e a do recurso extra enviam. `meta_id` não recorta o saldo: só
    acrescenta `valor_executado_meta`."""
    resolver_nivel_painel(user, estado_sigla=estado_sigla, territorio_id=territorio_id)
    pools = sorted(
        _pools_da_matriz(
            user, estado_sigla=estado_sigla, territorio_id=territorio_id, rubrica_slug=rubrica_slug, nivel=nivel,
        ),
        key=lambda pool: (
            pool.rubrica.ordem, pool.rubrica_id, _ORDEM_DO_NIVEL[pool.nivel],
            pool.estado.sigla if pool.estado else "", pool.territorio.nome if pool.territorio else "",
        ),
    )
    distribuido = _distribuido_por_pool(pools)
    executado_meta = _executado_por_pool_na_meta(meta_id) if meta_id is not None else {}
    limiares = limiares_semaforo()

    resultado = []
    for pool in pools:
        valor_distribuido = distribuido.get(pool.pk, ZERO)
        percentual = percentual_comprometido(pool.valor_comprometido, pool.valor_alocado)
        semaforo, alerta_80 = _semaforo_orcamento(percentual, limiares)
        linha = {
            "id": pool.pk,
            "rubrica": pool.rubrica,
            "nivel": pool.nivel,
            "estado": pool.estado,
            "territorio": pool.territorio,
            "reserva_ugp": pool.reserva_ugp,
            "valor_aprovado": pool.valor_alocado,
            "valor_distribuido": valor_distribuido,
            "valor_comprometido": pool.valor_comprometido,
            "valor_executado": pool.valor_executado,
            "saldo_disponivel": _saldo_disponivel_matriz(
                pool.valor_alocado, valor_distribuido, pool.valor_comprometido, pool.valor_executado,
            ),
            "saldo_pool": _saldo_disponivel(pool),
            "semaforo": semaforo,
            "alerta_80": alerta_80,
            "limiares_semaforo": limiares,
        }
        if meta_id is not None:
            linha["valor_executado_meta"] = executado_meta.get(pool.pk, ZERO)
        resultado.append(linha)
    return resultado
