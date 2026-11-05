"""Alertas orçamentários: semáforo de pools e limites, subexecução e remanejamento excessivo.

Cada alvo tem no máximo um alerta aberto por tipo. A notificação sai só quando o alerta abre
ou a faixa piora, então a movimentação e a tarefa periódica podem avaliar o mesmo alvo sem
notificar duas vezes."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db.models import Max, Q, Sum
from django.utils import timezone

from apps.core.models.notifications import Notification, TipoNotificacao
from apps.core.models.user import User
from apps.core.models.user_profile import UserProfile
from apps.core.utils import formatar_brl, get_config
from apps.sgp.budget import limites
from apps.sgp.budget import services as budget_service
from apps.sgp.budget.rls import visao_total
from apps.sgp.models import (
    BudgetAlert,
    BudgetPool,
    BudgetRubrica,
    BudgetTransfer,
    SpendingLimit,
    WorkPlanMeta,
)

Escopo = BudgetAlert.Escopo
Faixa = BudgetAlert.Faixa
Tipo = BudgetAlert.Tipo
Nivel = BudgetPool.Nivel
ZERO = Decimal("0")
# O comprometido pode passar muito do total depois que um limite é reduzido.
_MAIOR_PERCENTUAL = Decimal("999999.99")

_ORDEM_DA_FAIXA = {Faixa.AMARELO: 1, Faixa.VERMELHO: 2}
EMAIL_E_IN_APP = (TipoNotificacao.EMAIL, TipoNotificacao.IN_APP)
SO_IN_APP = (TipoNotificacao.IN_APP,)

EVENTO_SEMAFORO = "budget_semaforo_mudou"
EVENTO_SUBEXECUCAO = "budget_subexecucao"
EVENTO_REMANEJAMENTO_EXCESSIVO = "budget_remanejamento_excessivo"
EVENTO_REMANEJAMENTO_EFETIVADO = "remanejamento_efetivado"
EVENTO_RECONCILIACAO = "budget_reconciliacao_divergente"

# Evento → (título, mensagem), com as variáveis entre chaves duplas.
MODELOS = {
    "semaforo": (
        "Saldo de {{rubrica}} entrou na faixa {{faixa}}",
        "O saldo da trava {{trava}} para a rubrica {{rubrica}} entrou na faixa {{faixa}}. "
        "Saldo disponível: {{saldo_disponivel}}.",
    ),
    "subexecucao": (
        "Subexecução em {{rubrica}}",
        "A rubrica {{rubrica}} executou {{percentual}}%, abaixo do mínimo de {{minimo}}%, e a vigência "
        "termina em {{fim_da_vigencia}}. Saldo disponível: {{saldo_disponivel}}.",
    ),
    "remanejamento_excessivo": (
        "Volume remanejado alto em {{rubrica}}",
        "O volume remanejado de {{rubrica}} chegou a {{percentual}}% do valor aprovado, acima de "
        "{{maximo}}%. Avalie a necessidade de aditivo. Saldo disponível: {{saldo_disponivel}}.",
    ),
    "remanejamento_efetivado": (
        "Remanejamento efetivado: {{valor}}",
        "{{valor}} foram remanejados em {{rubrica}}. Motivo: {{motivo}}. "
        "Saldo disponível na origem: {{saldo_disponivel}}.",
    ),
    "recurso_extra_submetido": (
        "Recurso extra aguardando parecer: {{valor}} em {{rubrica}}",
        "{{solicitante}} pediu {{valor}} em {{rubrica}} e aguarda o seu parecer. "
        "Saldo disponível no limite: {{saldo_disponivel}}.",
    ),
    "recurso_extra_devolvido": (
        "Recurso extra devolvido: {{valor}} em {{rubrica}}",
        "Seu pedido de recurso extra em {{rubrica}} foi devolvido para ajuste da justificativa ou do valor. "
        "Saldo disponível no limite: {{saldo_disponivel}}.",
    ),
    "recurso_extra_com_parecer": (
        "Recurso extra aguardando decisão: {{valor}} em {{rubrica}}",
        "O pedido de {{solicitante}} em {{rubrica}} recebeu parecer do Articulador e aguarda a decisão da UGP. "
        "Saldo disponível no limite: {{saldo_disponivel}}.",
    ),
    "recurso_extra_decidido": (
        "Recurso extra {{decisao}}: {{valor}} em {{rubrica}}",
        "Seu pedido de recurso extra em {{rubrica}} foi {{decisao}}. "
        "Saldo disponível no limite: {{saldo_disponivel}}.",
    ),
}


def renderizar(modelo: str, **variaveis) -> tuple[str, str]:
    titulo, mensagem = MODELOS[modelo]

    def preencher(texto: str) -> str:
        return re.sub(r"\{\{(\w+)\}\}", lambda achado: str(variaveis[achado[1]]), texto)

    return preencher(titulo), preencher(mensagem)


# ---------------------------------------------------------------------------
# Destinatários
# ---------------------------------------------------------------------------

def _do_perfil(slug: str):
    return User.objects.filter(ativo=True, profiles__perfil__slug=slug).distinct()


def _articuladores_dos_estados(siglas) -> list:
    if not siglas:
        return []
    return list(
        User.objects.filter(
            Q(profiles__territorio__isnull=True) | Q(profiles__territorio__estados__overlap=list(siglas)),
            ativo=True, profiles__perfil__slug="articulador-estadual",
        ).distinct()
    )


def _estados_do_pool(pool: BudgetPool) -> list[str]:
    if pool.nivel == Nivel.ESTADUAL:
        return [pool.estado.sigla] if pool.estado_id else []
    return list(pool.territorio.estados or []) if pool.territorio_id else []


def responsaveis_do_pool(pool: BudgetPool) -> list:
    if pool.nivel == Nivel.NACIONAL:
        return list(_do_perfil("ugp"))
    return _articuladores_dos_estados(_estados_do_pool(pool))


def _superiores_do_pool(pool: BudgetPool) -> list:
    return list(_do_perfil("super-admin" if pool.nivel == Nivel.NACIONAL else "ugp"))


def _estados_do_usuario(user_id) -> list[str]:
    por_territorio = UserProfile.objects.filter(user_id=user_id, territorio__isnull=False).values_list(
        "territorio__estados", flat=True,
    )
    return sorted({sigla for estados in por_territorio for sigla in estados or []})


def destinatarios(alvo, faixa: str) -> list:
    """O responsável pelo saldo e, no vermelho, também o nível superior."""
    if isinstance(alvo, SpendingLimit):
        responsaveis = [alvo.user] if alvo.user.ativo else []
        superiores = _articuladores_dos_estados(_estados_do_usuario(alvo.user_id))
    else:
        responsaveis = responsaveis_do_pool(alvo)
        superiores = _superiores_do_pool(alvo)
    selecionados = responsaveis + (superiores if faixa == Faixa.VERMELHO else [])
    return list({usuario.pk: usuario for usuario in selecionados}.values())


def canais_da_faixa(faixa: str) -> tuple:
    return EMAIL_E_IN_APP if faixa == Faixa.VERMELHO else SO_IN_APP


# ---------------------------------------------------------------------------
# Alerta aberto por alvo e tipo
# ---------------------------------------------------------------------------

def _no_campo(percentual: Decimal) -> Decimal:
    return min(percentual, _MAIOR_PERCENTUAL)


def _escopo_de(alvo) -> str:
    return Escopo.LIMITE if isinstance(alvo, SpendingLimit) else Escopo.POOL


def _aberto(alvo, tipo: str) -> BudgetAlert | None:
    return BudgetAlert.objects.filter(
        escopo=_escopo_de(alvo), referencia_id=alvo.pk, tipo=tipo, resolvido_em__isnull=True,
    ).first()


def saldo_do_alvo(alvo) -> Decimal:
    if isinstance(alvo, SpendingLimit):
        return alvo.saldo_disponivel
    return budget_service._saldo_disponivel(alvo)


@dataclass(frozen=True)
class MudancaDeFaixa:
    alerta: BudgetAlert
    faixa: str


def sincronizar_semaforo(alvo) -> MudancaDeFaixa | None:
    """Abre, atualiza ou resolve o alerta de semáforo. Quem chama já travou o alvo. Devolve a
    mudança só quando o alerta abriu ou a faixa piorou, que é quando se notifica."""
    if isinstance(alvo, SpendingLimit):
        percentual = budget_service.percentual_comprometido(alvo.valor_comprometido, alvo.valor_limite)
    else:
        percentual = budget_service.percentual_comprometido(alvo.valor_comprometido, alvo.valor_alocado)
    faixa = budget_service.faixa_semaforo(percentual, budget_service.limiares_semaforo())
    aberto = _aberto(alvo, Tipo.SEMAFORO)

    if faixa == "verde":
        if aberto is not None:
            aberto.resolvido_em = timezone.now()
            aberto.save(update_fields=["resolvido_em"])
        return None
    if aberto is None:
        alerta = BudgetAlert.objects.create(
            tipo=Tipo.SEMAFORO, escopo=_escopo_de(alvo), referencia_id=alvo.pk, rubrica_id=alvo.rubrica_id,
            faixa=faixa, percentual_atingido=_no_campo(percentual),
        )
        return MudancaDeFaixa(alerta, faixa)

    piorou = _ORDEM_DA_FAIXA[faixa] > _ORDEM_DA_FAIXA[aberto.faixa]
    aberto.faixa = faixa
    aberto.percentual_atingido = _no_campo(percentual)
    if piorou:
        aberto.alertado_em = timezone.now()
    aberto.save(update_fields=["faixa", "percentual_atingido", "alertado_em"])
    return MudancaDeFaixa(aberto, faixa) if piorou else None


def registrar_alertados(alerta: BudgetAlert, usuarios) -> None:
    alerta.usuarios_alertados_ids = sorted({*alerta.usuarios_alertados_ids, *(usuario.pk for usuario in usuarios)})
    alerta.save(update_fields=["usuarios_alertados_ids"])


def _link_do_painel() -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/sgp/orcamento"


def _notificar(usuarios, *, modelo: str, evento: str, canais, **variaveis) -> int:
    titulo, mensagem = renderizar(modelo, **variaveis)
    for usuario in usuarios:
        for canal in canais:
            Notification.objects.create(
                user=usuario, tipo=canal, titulo=titulo, mensagem=mensagem, link=_link_do_painel(),
                modulo_origem="sgp", evento=evento,
            )
    return len(usuarios) * len(canais)


def _trava_do_alvo(alvo) -> str:
    if isinstance(alvo, SpendingLimit):
        return "individual"
    local = alvo.territorio or alvo.estado
    nivel = alvo.get_nivel_display()
    return f"do pool {nivel} — {local.nome}" if local else f"do pool {nivel}"


def _travar(modelo, pk):
    relacionados = ("rubrica", "user") if modelo is SpendingLimit else ("rubrica", "estado", "territorio")
    return modelo.objects.select_for_update(of=("self",)).select_related(*relacionados).filter(pk=pk).first()


def avaliar_semaforo(modelo, pk) -> int:
    """Uma transação por alvo: a tarefa não segura uma trava enquanto espera a do alvo seguinte."""
    with visao_total():
        alvo = _travar(modelo, pk)
        if alvo is None:
            return 0
        mudanca = sincronizar_semaforo(alvo)
        if mudanca is None:
            return 0
        usuarios = destinatarios(alvo, mudanca.faixa)
        enviadas = _notificar(
            usuarios, modelo="semaforo", evento=EVENTO_SEMAFORO, canais=canais_da_faixa(mudanca.faixa),
            rubrica=alvo.rubrica.nome, faixa=mudanca.faixa, trava=_trava_do_alvo(alvo),
            saldo_disponivel=formatar_brl(saldo_do_alvo(alvo)),
        )
        registrar_alertados(mudanca.alerta, usuarios)
        return enviadas


def _resolver_alertas_de_limites_encerrados() -> None:
    encerrados = SpendingLimit.objects.filter(periodo_fim__lt=limites.hoje()).values("pk")
    BudgetAlert.objects.filter(
        escopo=Escopo.LIMITE, tipo=Tipo.SEMAFORO, resolvido_em__isnull=True, referencia_id__in=encerrados,
    ).update(resolvido_em=timezone.now())


def avaliar_todos_os_semaforos() -> int:
    with visao_total():
        _resolver_alertas_de_limites_encerrados()
        pools = list(BudgetPool.objects.values_list("pk", flat=True))
        hoje = limites.hoje()
        individuais = list(
            SpendingLimit.objects.filter(
                escopo=SpendingLimit.Escopo.INDIVIDUAL, periodo_inicio__lte=hoje, periodo_fim__gte=hoje,
            ).values_list("pk", flat=True)
        )
    return (
        sum(avaliar_semaforo(BudgetPool, pk) for pk in pools)
        + sum(avaliar_semaforo(SpendingLimit, pk) for pk in individuais)
    )


# ---------------------------------------------------------------------------
# Alertas por rubrica: o alvo é o pool nacional, que guarda o valor aprovado
# ---------------------------------------------------------------------------

def _pools_nacionais():
    return BudgetPool.objects.filter(nivel=Nivel.NACIONAL, rubrica__ativo=True)


def _abrir_ou_resolver(pool: BudgetPool, tipo: str, *, faixa: str, percentual: Decimal, abrir: bool) -> BudgetAlert | None:
    """Devolve o alerta só quando acabou de abrir."""
    aberto = _aberto(pool, tipo)
    if not abrir:
        if aberto is not None:
            aberto.resolvido_em = timezone.now()
            aberto.save(update_fields=["resolvido_em"])
        return None
    if aberto is not None:
        aberto.percentual_atingido = _no_campo(percentual)
        aberto.save(update_fields=["percentual_atingido"])
        return None
    return BudgetAlert.objects.create(
        tipo=tipo, escopo=Escopo.POOL, referencia_id=pool.pk, rubrica_id=pool.rubrica_id, faixa=faixa,
        percentual_atingido=_no_campo(percentual),
    )


def fim_da_vigencia() -> date | None:
    """Maior `data_fim` das Metas, até existir a vigência da entidade do TED."""
    return WorkPlanMeta.objects.aggregate(fim=Max("data_fim"))["fim"]


def _meses_antes(data: date, meses: int) -> date:
    ano, mes = divmod(data.year * 12 + data.month - 1 - meses, 12)
    mes += 1
    return date(ano, mes, min(data.day, calendar.monthrange(ano, mes)[1]))


def avaliar_subexecucao() -> int:
    fim = fim_da_vigencia()
    if fim is None:
        return 0
    meses = int(get_config("budget_subexec_alert_months", 6))
    minimo = Decimal(str(get_config("budget_subexec_min_pct", 60)))
    na_janela = limites.hoje() >= _meses_antes(fim, meses)

    with visao_total():
        pools = list(_pools_nacionais().filter(valor_alocado__gt=ZERO).values_list("pk", flat=True))

    enviadas = 0
    for pk in pools:
        with visao_total():
            pool = _travar(BudgetPool, pk)
            if pool is None or pool.valor_alocado <= ZERO:
                continue
            executado = (
                BudgetPool.objects.filter(rubrica_id=pool.rubrica_id).aggregate(total=Sum("valor_executado"))["total"]
                or ZERO
            )
            percentual = executado / pool.valor_alocado * Decimal("100")
            aberto = _abrir_ou_resolver(
                pool, Tipo.SUBEXECUCAO, faixa=Faixa.SUBEXECUCAO, percentual=percentual,
                abrir=na_janela and percentual < minimo,
            )
            if aberto is None:
                continue
            usuarios = list(_do_perfil("ugp"))
            enviadas += _notificar(
                usuarios, modelo="subexecucao", evento=EVENTO_SUBEXECUCAO, canais=EMAIL_E_IN_APP,
                rubrica=pool.rubrica.nome, percentual=f"{percentual:.1f}", minimo=minimo,
                fim_da_vigencia=fim.strftime("%d/%m/%Y"), saldo_disponivel=formatar_brl(saldo_do_alvo(pool)),
            )
            registrar_alertados(aberto, usuarios)
    return enviadas


def _valor_aprovado_original(pool: BudgetPool) -> Decimal:
    """O alocado no pool nacional, desfeitos os remanejamentos que entraram nele e saíram dele."""
    entrou = BudgetTransfer.objects.filter(pool_destino=pool).aggregate(total=Sum("valor"))["total"] or ZERO
    saiu = BudgetTransfer.objects.filter(pool_origem=pool).aggregate(total=Sum("valor"))["total"] or ZERO
    return pool.valor_alocado - entrou + saiu


def avaliar_remanejamento_excessivo(rubrica_id) -> int:
    maximo = Decimal(str(get_config("budget_transfer_alert_pct", 25)))
    with visao_total():
        pk = _pools_nacionais().filter(rubrica_id=rubrica_id).values_list("pk", flat=True).first()
        pool = _travar(BudgetPool, pk) if pk else None
        if pool is None:
            return 0
        original = _valor_aprovado_original(pool)
        if original <= ZERO:
            return 0
        volume = (
            BudgetTransfer.objects.filter(pool_origem__rubrica_id=rubrica_id).aggregate(total=Sum("valor"))["total"]
            or ZERO
        )
        percentual = volume / original * Decimal("100")
        aberto = _abrir_ou_resolver(
            pool, Tipo.REMANEJAMENTO_EXCESSIVO, faixa="", percentual=percentual, abrir=percentual > maximo,
        )
        if aberto is None:
            return 0
        usuarios = list(_do_perfil("ugp"))
        enviadas = _notificar(
            usuarios, modelo="remanejamento_excessivo", evento=EVENTO_REMANEJAMENTO_EXCESSIVO, canais=EMAIL_E_IN_APP,
            rubrica=pool.rubrica.nome, percentual=f"{percentual:.1f}", maximo=maximo,
            saldo_disponivel=formatar_brl(saldo_do_alvo(pool)),
        )
        registrar_alertados(aberto, usuarios)
        return enviadas


def avaliar_todos_os_remanejamentos() -> int:
    rubricas = BudgetRubrica.objects.filter(ativo=True).values_list("pk", flat=True)
    return sum(avaliar_remanejamento_excessivo(pk) for pk in list(rubricas))


def notificar_remanejamento_efetivado(transferencia: BudgetTransfer) -> int:
    origem, destino = transferencia.pool_origem, transferencia.pool_destino
    usuarios = list({
        usuario.pk: usuario for pool in (origem, destino) for usuario in responsaveis_do_pool(pool)
    }.values())
    return _notificar(
        usuarios, modelo="remanejamento_efetivado", evento=EVENTO_REMANEJAMENTO_EFETIVADO, canais=EMAIL_E_IN_APP,
        valor=formatar_brl(transferencia.valor), rubrica=origem.rubrica.nome, motivo=transferencia.motivo,
        saldo_disponivel=formatar_brl(transferencia.saldo_origem_depois),
    )


# ---------------------------------------------------------------------------
# Reconciliação
# ---------------------------------------------------------------------------

def notificar_divergencias(divergencias: list[str]) -> int:
    usuarios = list(_do_perfil("super-admin"))
    for usuario in usuarios:
        for canal in EMAIL_E_IN_APP:
            Notification.objects.create(
                user=usuario, tipo=canal, titulo=f"Reconciliação do orçamento: {len(divergencias)} divergência(s)",
                mensagem="\n".join(divergencias[:20]), link=_link_do_painel(), modulo_origem="sgp",
                evento=EVENTO_RECONCILIACAO,
            )
    return len(usuarios) * len(EMAIL_E_IN_APP)


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------

def _limites_do_escopo(user) -> Q:
    perfis, slugs = budget_service._perfis_e_slugs(user)
    filtro = Q(user=user)
    if "articulador-estadual" in slugs:
        estados = budget_service._estados_do_articulador(perfis, user)
        if estados:
            filtro |= Q(user__profiles__territorio__estados__overlap=list(estados))
    return filtro


def alertas_visiveis(user):
    """Sem RLS na tabela: o recorte é o mesmo do detalhamento do orçamento. Perfil sem acesso ao
    orçamento recebe `PermissionDenied`."""
    escopo = budget_service.orcamento_detalhamento_scope(user)
    alertas = BudgetAlert.objects.select_related("rubrica")
    if escopo is None:
        return alertas
    with visao_total():
        pools = list(BudgetPool.objects.filter(escopo).values_list("pk", flat=True))
        individuais = list(
            SpendingLimit.objects.filter(_limites_do_escopo(user)).distinct().values_list("pk", flat=True)
        )
    return alertas.filter(
        Q(escopo=Escopo.POOL, referencia_id__in=pools) | Q(escopo=Escopo.LIMITE, referencia_id__in=individuais)
    )
