from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef, Q

from apps.core.models.user import User
from apps.core.services.permissions import user_has_role, user_role_slugs, user_states
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.individual_limit import DemandIndividualLimit
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services import orcamento as orcamento_service


# Perfis que desfazem uma autorização já dada; o solicitante cancela só até a pré-autorização.
PERFIS_QUE_CANCELAM_AUTORIZADA = ("super-admin", "ugp")


def demand_visibility_scope(user) -> Q | None:
    if user_has_role(user, "super-admin") or user_has_role(user, "ugp") or user_has_role(user, "fgd"):
        return None

    if user_has_role(user, "articulador-estadual"):
        # RF18: só "Submetidas" do seu estado, além das próprias e das que
        # ele já decidiu (para manter acesso ao que já pré-autorizou/devolveu).
        # `user_states` já devolve todos os estados pra um perfil global (sem
        # território específico) — não precisa de ramo especial pra isso, e
        # com states vazio (nenhum território cadastrado) o `sigla__in` some
        # sozinho, mesmo resultado do notifications_service para esse perfil.
        states = user_states(user)
        # `Exists` em vez de join em `etapas`: não multiplica linhas, então a
        # listagem dispensa `.distinct()` (sort/hash sobre todas as colunas).
        decidiu = Exists(ApprovalStep.objects.filter(demanda=OuterRef("pk"), responsavel=user))
        return (
            Q(solicitante=user)
            | Q(decidiu)
            | Q(status="submetida", activity__municipio__state__sigla__in=states)
        )

    return Q(solicitante=user)


STATUS_AGUARDANDO_POR_PERFIL = {
    "articulador-estadual": ("submetida",),
    "ugp": ("pre_autorizada",),
    "fgd": ("autorizada", "em_atendimento"),
}


def status_aguardando_acao(user) -> list[str]:
    """Status em que a demanda espera uma decisão de algum perfil do usuário."""
    perfis = user_role_slugs(user, tuple(STATUS_AGUARDANDO_POR_PERFIL))
    return sorted({s for perfil in perfis for s in STATUS_AGUARDANDO_POR_PERFIL[perfil]})


def demandas_aguardando_acao(user, queryset):
    """Recorta `queryset` pelas demandas que aguardam a ação do usuário. O
    Articulador só decide as do seu estado; UGP e FGD decidem de qualquer
    território."""
    perfis = user_role_slugs(user, tuple(STATUS_AGUARDANDO_POR_PERFIL))
    if not perfis:
        return queryset.none()

    filtro = Q()
    if "articulador-estadual" in perfis:
        filtro |= Q(status="submetida", activity__municipio__state__sigla__in=user_states(user))
    status_globais = [
        s for perfil in perfis if perfil != "articulador-estadual"
        for s in STATUS_AGUARDANDO_POR_PERFIL[perfil]
    ]
    if status_globais:
        filtro |= Q(status__in=status_globais)
    return queryset.filter(filtro)


def responsaveis_pela_etapa_atual(demand):
    if demand.status in {"rascunho", "devolvida"}:
        return User.objects.filter(pk=demand.solicitante_id)
    if demand.status == "submetida":
        sigla = demand.activity.municipio.state.sigla
        return notifications_service.usuarios_articuladores_do_estado(sigla)
    if demand.status == "pre_autorizada":
        return notifications_service.usuarios_por_perfil("ugp")
    if demand.status in {"autorizada", "em_atendimento"}:
        return notifications_service.usuarios_por_perfil("fgd")
    return User.objects.none()


def preview_impacto(demand_request, valor: Decimal) -> dict:
    """`valor` é o novo valor proposto pelo aprovador — a solicitação já está
    reservada (pré-autorizada/autorizada) pelo valor atual, então só o delta
    entre os dois pesa no saldo; contar `valor` inteiro de novo dobraria a
    reserva já feita."""
    solicitante = demand_request.demanda.solicitante
    rubrica = demand_request.rubrica
    valor_reservado = demand_request.valor_autorizado or demand_request.valor_estimado
    delta = valor - valor_reservado

    with orcamento_service.pelo_solicitante():
        if delta > Decimal("0"):
            check = balance_service.verificar_duas_travas(
                solicitante=solicitante, rubrica=rubrica, valor=delta, demand_request=demand_request,
            )
            disponivel, trava_bloqueada = check.disponivel, check.trava_bloqueada
            allocation = check.territorial.allocation
        else:
            # Reduzir o valor autorizado nunca bloqueia — está liberando saldo.
            allocation = orcamento_service.consultar_pool(
                solicitante=solicitante, rubrica=rubrica, valor=Decimal("0"), demand_request=demand_request,
            ).allocation
            disponivel, trava_bloqueada = True, None

    limiares = orcamento_service.limiares_semaforo()
    limite = DemandIndividualLimit.objects.filter(solicitante=solicitante, rubrica=rubrica).first()
    individual = {"semaforo_antes": None, "semaforo_apos": None, "saldo_apos": None}
    if limite is not None:
        individual["semaforo_antes"], individual["semaforo_apos"] = balance_service.faixas_antes_e_depois(
            comprometido=limite.valor_comprometido, total=limite.valor_limite, delta=delta, limiares=limiares,
        )
        individual["saldo_apos"] = limite.saldo_disponivel - delta

    territorial = {"semaforo_antes": None, "semaforo_apos": None, "saldo_apos": None}
    if allocation is not None:
        territorial["semaforo_antes"], territorial["semaforo_apos"] = balance_service.faixas_antes_e_depois(
            comprometido=allocation.valor_comprometido, total=allocation.valor_alocado, delta=delta,
            limiares=limiares,
        )
        territorial["saldo_apos"] = allocation.valor_alocado - allocation.valor_comprometido - delta

    return {
        "disponivel": disponivel,
        "trava_bloqueada": trava_bloqueada,
        "individual": individual,
        "territorial": territorial,
    }


def alerta_rubrica_fora_do_previsto(demand_request) -> bool:
    previstas = demand_request.demanda.activity.acao.rubricas_previstas
    if "rubricas_previstas" in getattr(demand_request.demanda.activity.acao, "_prefetched_objects_cache", {}):
        # Listagem: M2M prefetchado, decide em memória em vez de 2 `exists()` por solicitação.
        ids_previstos = {r.pk for r in previstas.all()}
        return bool(ids_previstos) and demand_request.rubrica_id not in ids_previstos
    if not previstas.exists():
        # Sem previsão cadastrada na Ação — não é falso positivo, é "sem opinião".
        return False
    return not previstas.filter(pk=demand_request.rubrica_id).exists()


def exigir_pode_decidir_articulador(demand, responsavel) -> None:
    """Segrega quem submete de quem decide: o Articulador não
    pode pré-autorizar/devolver a própria demanda nem uma de fora do estado
    em que atua — mesmo estando no queryset de visibilidade dele (que
    inclui as próprias demandas, para ele continuar vendo o que já decidiu)."""
    if demand.solicitante_id == responsavel.pk:
        raise PermissionDenied("Você não pode decidir sobre a própria demanda.")
    estado_sigla = demand.activity.municipio.state.sigla
    if estado_sigla not in user_states(responsavel):
        raise PermissionDenied("Demanda fora do seu estado de atuação.")
