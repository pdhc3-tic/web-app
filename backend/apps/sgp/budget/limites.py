"""Limites de gasto por perfil e por usuário: a primeira das duas travas de saldo.

O padrão do perfil vale para todos os seus usuários. A linha individual do período guarda o
que a pessoa comprometeu e executou: nasce do padrão na primeira reserva (`herdado`) ou de uma
sobrescrita justificada. Uma reserva fica presa à linha em que foi feita, mesmo depois da
virada do período.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models.user_profile import UserProfile
from apps.core.services.audit import log_audit
from apps.core.signals.audit import get_audit_context
from apps.core.utils import formatar_brl, get_config
from apps.sgp.budget.ledger import efeito_no_saldo, lancar
from apps.sgp.budget.models import BudgetPool, BudgetTransaction, SpendingLimit

ZERO = Decimal("0")

Escopo = SpendingLimit.Escopo
Tipo = BudgetTransaction.Tipo

PERIODO_PADRAO = "trimestral"
# Até existir a entidade do TED, a vigência é um período único e o padrão do perfil não expira.
INICIO_DA_VIGENCIA = date(2000, 1, 1)
FIM_EM_ABERTO = date(2099, 12, 31)
MESES_POR_PERIODO = {"mensal": 1, "trimestral": 3, "semestral": 6}

PERFIS_OPERACIONAIS = ("adt-acr", "articulador-estadual")

ENTIDADE_LIMITE = "SpendingLimit"


def hoje() -> date:
    return timezone.localdate()


def periodo_de(data: date, periodicidade: str | None = None) -> tuple[date, date]:
    """(início, fim) do período que contém `data`, pelo parâmetro global `budget_limit_period`."""
    periodicidade = periodicidade or get_config("budget_limit_period", PERIODO_PADRAO)
    if periodicidade == "vigencia":
        return INICIO_DA_VIGENCIA, FIM_EM_ABERTO
    meses = MESES_POR_PERIODO.get(periodicidade, MESES_POR_PERIODO[PERIODO_PADRAO])
    mes_inicial = ((data.month - 1) // meses) * meses + 1
    mes_final = mes_inicial + meses - 1
    return date(data.year, mes_inicial, 1), date(data.year, mes_final, calendar.monthrange(data.year, mes_final)[1])


def _vigentes_em(data: date):
    return SpendingLimit.objects.filter(periodo_inicio__lte=data, periodo_fim__gte=data)


def _linha_vigente(user_id, rubrica_id, data: date) -> SpendingLimit | None:
    return (
        _vigentes_em(data)
        .filter(escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id)
        .order_by("-periodo_inicio")
        .first()
    )


def _padrao_do_usuario(user_id, rubrica_id, data: date) -> SpendingLimit | None:
    """Com mais de um perfil, vale o maior padrão: nenhum perfil deve reduzir o que o outro concede."""
    return (
        _vigentes_em(data)
        .filter(
            escopo=Escopo.PERFIL, rubrica_id=rubrica_id,
            perfil__in=UserProfile.objects.filter(user_id=user_id).values("perfil"),
        )
        .order_by("-valor_limite", "pk")
        .first()
    )


def _territorio_do_usuario(user_id) -> int | None:
    return (
        UserProfile.objects
        .filter(user_id=user_id, perfil__slug__in=PERFIS_OPERACIONAIS, territorio__isnull=False)
        .order_by("pk")
        .values_list("territorio_id", flat=True)
        .first()
    )


def _saldo_a_acumular(user_id, rubrica_id, inicio: date) -> Decimal:
    if not get_config("budget_limit_carry_over", False):
        return ZERO
    anterior = (
        SpendingLimit.objects
        .filter(escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id, periodo_fim__lt=inicio)
        .order_by("-periodo_fim")
        .first()
    )
    return max(anterior.saldo_disponivel, ZERO) if anterior else ZERO


def _linha_herdada(user_id, rubrica_id, data: date) -> SpendingLimit | None:
    """A linha do período que o padrão do perfil geraria, sem gravar. None sem padrão."""
    padrao = _padrao_do_usuario(user_id, rubrica_id, data)
    if padrao is None:
        return None
    inicio, fim = periodo_de(data)
    return SpendingLimit(
        escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id, herdado=True,
        territorio_id=_territorio_do_usuario(user_id),
        valor_limite=padrao.valor_limite + _saldo_a_acumular(user_id, rubrica_id, inicio),
        periodo_inicio=inicio, periodo_fim=fim,
    )


def limite_efetivo(user_id, rubrica_id, data: date | None = None) -> SpendingLimit | None:
    """Somente leitura: a linha vigente ou, sem ela, a que o padrão do perfil geraria."""
    data = data or hoje()
    return _linha_vigente(user_id, rubrica_id, data) or _linha_herdada(user_id, rubrica_id, data)


def totais_por_rubrica(*, territorio_id: int | None = None, estados: set[str] | None = None) -> dict[int, dict]:
    """Limites individuais do período vigente, somados por rubrica. Só as linhas já criadas: quem
    ainda não reservou no período não tem o que somar. `estados` recorta pelo território da linha."""
    linhas = _vigentes_em(hoje()).filter(escopo=Escopo.INDIVIDUAL)
    if territorio_id is not None:
        linhas = linhas.filter(territorio_id=territorio_id)
    if estados is not None:
        linhas = linhas.filter(territorio__estados__overlap=sorted(estados))
    return {
        linha["rubrica_id"]: linha
        for linha in linhas.order_by().values("rubrica_id").annotate(
            total=Sum("valor_limite"), comprometido=Sum("valor_comprometido"), executado=Sum("valor_executado"),
        )
    }


def _vigente_travada(user_id, rubrica_id, data: date) -> SpendingLimit | None:
    # `of=("self",)`: sem ele, um JOIN traria a linha do usuário para dentro do FOR UPDATE, e o
    # commit de outra transação que gravou algo apontando para ele esperaria este lock.
    return (
        SpendingLimit.objects.select_for_update(of=("self",))
        .filter(
            escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id,
            periodo_inicio__lte=data, periodo_fim__gte=data,
        )
        .order_by("-periodo_inicio")
        .first()
    )


def _criar_ou_travar(linha: SpendingLimit) -> SpendingLimit:
    """Duas transações podem criar a mesma linha: o savepoint deixa a segunda esperar a primeira
    no índice único e, no IntegrityError, reler a linha já travada."""
    try:
        with transaction.atomic():
            linha.save()
            return SpendingLimit.objects.select_for_update(of=("self",)).get(pk=linha.pk)
    except IntegrityError:
        return SpendingLimit.objects.select_for_update(of=("self",)).get(
            escopo=Escopo.INDIVIDUAL, user_id=linha.user_id, rubrica_id=linha.rubrica_id,
            periodo_inicio=linha.periodo_inicio,
        )


def travar_limite_vigente(*, user_id, rubrica_id, criar: bool = False, data: date | None = None) -> SpendingLimit | None:
    """Trava a linha do período. Com `criar`, a primeira reserva a gera do padrão do perfil."""
    data = data or hoje()
    linha = _vigente_travada(user_id, rubrica_id, data)
    if linha is not None or not criar:
        return linha
    nova = _linha_herdada(user_id, rubrica_id, data)
    return _criar_ou_travar(nova) if nova is not None else None


def travar_limite_para_elevar(*, user_id, rubrica_id, justificativa: str, usuario) -> SpendingLimit:
    """Recurso extra de quem ainda não tem limite: a linha nasce zerada, e a elevação a preenche."""
    linha = travar_limite_vigente(user_id=user_id, rubrica_id=rubrica_id, criar=True)
    if linha is not None:
        return linha
    inicio, fim = periodo_de(hoje())
    return _criar_ou_travar(SpendingLimit(
        escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id, valor_limite=ZERO,
        territorio_id=_territorio_do_usuario(user_id), justificativa=justificativa,
        periodo_inicio=inicio, periodo_fim=fim, criado_por=usuario,
    ))


def linha_da_reserva(chave_da_reserva: str) -> int | None:
    """Id da linha em que a reserva foi feita: a mais recente, já que uma reserva liberada pode
    ser refeita em outro período."""
    return (
        BudgetTransaction.objects
        .filter(demand_request_id=chave_da_reserva, tipo=Tipo.RESERVA, spending_limit__isnull=False)
        .order_by("-pk")
        .values_list("spending_limit_id", flat=True)
        .first()
    )


def travar_linha(pk: int) -> SpendingLimit:
    return SpendingLimit.objects.select_for_update(of=("self",)).get(pk=pk)


def travar_linhas_do_lote(*, rubrica_id, user_ids, chaves_das_reservas, data: date | None = None) -> None:
    """Trava, em ordem de pk, as linhas das reservas e as do período de todos os usuários do lote.
    Só as das reservas não bastam: o lote travaria o pool sem esperar quem segura o limite de um
    solicitante ainda sem reserva, e pararia no limite dele já segurando o pool que o outro quer."""
    data = data or hoje()
    list(
        SpendingLimit.objects.select_for_update(of=("self",))
        .filter(
            Q(pk__in=BudgetTransaction.objects.filter(
                tipo=Tipo.RESERVA, demand_request_id__in=list(chaves_das_reservas), spending_limit__isnull=False,
            ).values("spending_limit_id"))
            | Q(
                escopo=Escopo.INDIVIDUAL, rubrica_id=rubrica_id, user_id__in=list(user_ids),
                periodo_inicio__lte=data, periodo_fim__gte=data,
            )
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def registrar_movimento(
    *, limite: SpendingLimit, tipo: str, valor: Decimal, usuario, demand_request_id: str | None = None,
    demanda_id: str | None = None, activity_id: int | None = None, justificativa: str = "",
    saldo_posterior: Decimal | None = None,
) -> BudgetTransaction:
    """Chamado depois de mover o limite. `saldo_posterior` só precisa ser informado quando um
    movimento vira mais de um lançamento (execução com diferença), porque o saldo em memória já
    é o final."""
    if saldo_posterior is None:
        saldo_posterior = limite.saldo_disponivel
    return lancar(
        spending_limit=limite, tipo=tipo, valor=valor, usuario=usuario, saldo_posterior=saldo_posterior,
        saldo_anterior=saldo_posterior - efeito_no_saldo(tipo, valor), demand_request_id=demand_request_id,
        demanda_id=demanda_id, activity_id=activity_id, justificativa=justificativa,
    )


# ---------------------------------------------------------------------------
# Cadastro: padrão por perfil e sobrescrita individual.
# ---------------------------------------------------------------------------

def _auditar(acao: str, limite: SpendingLimit, usuario, *, anteriores=None, novos=None) -> None:
    contexto = get_audit_context()
    log_audit(
        user=usuario or contexto["user"], acao=acao, modulo="sgp", entidade=ENTIDADE_LIMITE, entidade_id=limite.pk,
        valores_anteriores=anteriores or {}, valores_novos=novos or {},
        _ip=contexto["ip"], _user_agent=contexto["user_agent"],
    )


def auditar_criacao(limite: SpendingLimit, usuario) -> None:
    _auditar(
        "limite_individual.criado", limite, usuario,
        novos={
            "solicitante": limite.user_id, "perfil": limite.perfil_id, "rubrica": limite.rubrica.slug,
            "valor_limite": str(limite.valor_limite),
        },
    )


def auditar_alteracao(limite: SpendingLimit, *, valor_anterior, usuario) -> None:
    _auditar(
        "limite_individual.alterado", limite, usuario,
        anteriores={"valor_limite": str(valor_anterior)},
        novos={
            "valor_limite": str(limite.valor_limite),
            "valor_comprometido": str(limite.valor_comprometido),
            "valor_executado": str(limite.valor_executado),
        },
    )


def _exigir_justificativa(justificativa: str) -> str:
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise DRFValidationError({"justificativa": "Obrigatória em limite individual e em alteração de valor."})
    return justificativa


def _soma_no_territorio(rubrica_id, territorio_id, data: date) -> Decimal:
    usuarios = (
        UserProfile.objects
        .filter(territorio_id=territorio_id, perfil__slug__in=PERFIS_OPERACIONAIS)
        .order_by()
        .values_list("user_id", flat=True)
        .distinct()
    )
    soma = ZERO
    for user_id in usuarios:
        if _territorio_do_usuario(user_id) != territorio_id:
            continue
        limite = limite_efetivo(user_id, rubrica_id, data)
        if limite is not None:
            soma += limite.valor_limite
    return soma


def exigir_dentro_do_pool(rubrica_id, territorio_ids, data: date | None = None) -> None:
    """Com a sobrealocação desligada, a soma dos limites do território não passa do pool."""
    if get_config("budget_overallocation_allowed", True):
        return
    data = data or hoje()
    for territorio_id in territorio_ids:
        pool = BudgetPool.objects.filter(
            rubrica_id=rubrica_id, nivel=BudgetPool.Nivel.TERRITORIAL, territorio_id=territorio_id,
        ).first()
        alocado = pool.valor_alocado if pool else ZERO
        soma = _soma_no_territorio(rubrica_id, territorio_id, data)
        if soma > alocado:
            raise DRFValidationError({
                "valor_limite": (
                    f"A soma dos limites do território ({formatar_brl(soma)}) passa do pool "
                    f"({formatar_brl(alocado)}), e a sobrealocação está desligada."
                ),
                "soma_limites": str(soma),
                "valor_pool": str(alocado),
                "territorio": territorio_id,
            })


def _territorios_do_perfil(perfil_id) -> list[int]:
    return list(
        UserProfile.objects
        .filter(perfil_id=perfil_id, territorio__isnull=False)
        .order_by()
        .values_list("territorio_id", flat=True)
        .distinct()
    )


@transaction.atomic
def criar_sobrescrita(*, user, rubrica, valor_limite: Decimal, justificativa: str, usuario,
                      periodo_inicio: date | None = None, periodo_fim: date | None = None) -> SpendingLimit:
    justificativa = _exigir_justificativa(justificativa)
    if (periodo_inicio is None) != (periodo_fim is None):
        raise DRFValidationError({"periodo_fim": "Informe o início e o fim do período, ou nenhum dos dois."})
    if periodo_inicio is None:
        periodo_inicio, periodo_fim = periodo_de(hoje())
    existente = _vigente_travada(user.pk, rubrica.pk, periodo_inicio)
    if existente is not None and existente.herdado:
        # A linha herdada já guarda reservas: vira sobrescrita, em vez de abrir uma segunda.
        return alterar_sobrescrita(
            existente.pk, valor_limite=valor_limite, justificativa=justificativa, usuario=usuario,
        )
    try:
        with transaction.atomic():
            limite = SpendingLimit.objects.create(
                escopo=Escopo.INDIVIDUAL, user=user, rubrica=rubrica, valor_limite=valor_limite,
                territorio_id=_territorio_do_usuario(user.pk), justificativa=justificativa,
                periodo_inicio=periodo_inicio, periodo_fim=periodo_fim, criado_por=usuario,
            )
    except IntegrityError as exc:
        raise DRFValidationError(
            {"rubrica": "Já existe um limite individual deste solicitante nesta rubrica."}
        ) from exc
    registrar_movimento(
        limite=limite, tipo=Tipo.AUMENTO_LIMITE, valor=valor_limite, usuario=usuario, justificativa=justificativa,
    )
    auditar_criacao(limite, usuario)
    if limite.territorio_id:
        exigir_dentro_do_pool(rubrica.pk, [limite.territorio_id], periodo_inicio)
    return limite


@transaction.atomic
def alterar_sobrescrita(pk: int, *, valor_limite: Decimal, justificativa: str, usuario) -> SpendingLimit:
    """Reduzir nunca invalida o que já foi autorizado: abaixo do comprometido e executado, é recusado."""
    limite = travar_linha(pk)
    erro = limite.erro_de_reducao(valor_limite)
    if erro:
        raise DRFValidationError({"valor_limite": erro})
    valor_anterior = limite.valor_limite
    if valor_limite == valor_anterior:
        return limite
    justificativa = _exigir_justificativa(justificativa)
    limite.valor_limite = valor_limite
    limite.justificativa = justificativa
    limite.herdado = False
    limite.save(update_fields=["valor_limite", "justificativa", "herdado", "atualizado_em"])
    registrar_movimento(
        limite=limite, tipo=Tipo.AUMENTO_LIMITE, valor=valor_limite - valor_anterior, usuario=usuario,
        justificativa=justificativa,
    )
    auditar_alteracao(limite, valor_anterior=valor_anterior, usuario=usuario)
    if limite.territorio_id:
        exigir_dentro_do_pool(limite.rubrica_id, [limite.territorio_id], limite.periodo_inicio)
    return limite


@transaction.atomic
def criar_padrao(*, perfil, rubrica, valor_limite: Decimal, usuario, justificativa: str = "",
                 periodo_inicio: date | None = None) -> SpendingLimit:
    """O padrão vale até ser substituído: sem período informado, começa no período vigente."""
    periodo_inicio = periodo_inicio or periodo_de(hoje())[0]
    conflito = (
        _vigentes_em(periodo_inicio)
        .filter(escopo=Escopo.PERFIL, perfil=perfil, rubrica=rubrica)
        .exists()
    )
    if conflito:
        raise DRFValidationError({"rubrica": "Já existe um padrão deste perfil nesta rubrica. Altere o valor dele."})
    try:
        with transaction.atomic():
            limite = SpendingLimit.objects.create(
                escopo=Escopo.PERFIL, perfil=perfil, rubrica=rubrica, valor_limite=valor_limite,
                justificativa=(justificativa or "").strip(), periodo_inicio=periodo_inicio,
                periodo_fim=FIM_EM_ABERTO, criado_por=usuario,
            )
    except IntegrityError as exc:
        raise DRFValidationError(
            {"rubrica": "Já existe um padrão deste perfil nesta rubrica. Altere o valor dele."}
        ) from exc
    auditar_criacao(limite, usuario)
    exigir_dentro_do_pool(rubrica.pk, _territorios_do_perfil(perfil.pk), periodo_inicio)
    return limite


def _padrao_ja_foi_usado(limite: SpendingLimit) -> bool:
    return SpendingLimit.objects.filter(
        escopo=Escopo.INDIVIDUAL, herdado=True, rubrica_id=limite.rubrica_id,
        periodo_fim__gte=limite.periodo_inicio,
        user__profiles__perfil_id=limite.perfil_id,
    ).exists()


@transaction.atomic
def alterar_padrao(pk: int, *, valor_limite: Decimal, justificativa: str, usuario) -> SpendingLimit:
    """A mudança de um padrão já em uso só vale a partir do período seguinte: quem já tem a linha
    do período fica como está. Sem uso, ainda dá para corrigir o valor no próprio registro."""
    limite = travar_linha(pk)
    if valor_limite == limite.valor_limite:
        return limite
    justificativa = _exigir_justificativa(justificativa)
    valor_anterior = limite.valor_limite

    if limite.periodo_inicio <= hoje() and _padrao_ja_foi_usado(limite):
        fim_do_periodo = periodo_de(hoje())[1]
        inicio_seguinte = date.fromordinal(fim_do_periodo.toordinal() + 1)
        limite.periodo_fim = fim_do_periodo
        limite.save(update_fields=["periodo_fim", "atualizado_em"])
        limite, _ = SpendingLimit.objects.update_or_create(
            escopo=Escopo.PERFIL, perfil_id=limite.perfil_id, rubrica_id=limite.rubrica_id,
            periodo_inicio=inicio_seguinte,
            defaults={
                "valor_limite": valor_limite, "justificativa": justificativa,
                "periodo_fim": FIM_EM_ABERTO, "criado_por": usuario,
            },
        )
        data_da_conferencia = inicio_seguinte
    else:
        limite.valor_limite = valor_limite
        limite.justificativa = justificativa
        limite.save(update_fields=["valor_limite", "justificativa", "atualizado_em"])
        data_da_conferencia = max(limite.periodo_inicio, hoje())

    auditar_alteracao(limite, valor_anterior=valor_anterior, usuario=usuario)
    exigir_dentro_do_pool(limite.rubrica_id, _territorios_do_perfil(limite.perfil_id), data_da_conferencia)
    return limite


def definir_limite_de_demonstracao(*, user, rubrica, valor_limite: Decimal) -> SpendingLimit:
    """Só para os dados de demonstração: grava a linha do período sem passar pelo cadastro."""
    inicio, fim = periodo_de(hoje())
    limite, _ = SpendingLimit.objects.update_or_create(
        escopo=Escopo.INDIVIDUAL, user=user, rubrica=rubrica, periodo_inicio=inicio,
        defaults={
            "valor_limite": valor_limite, "periodo_fim": fim, "justificativa": "Dados de demonstração.",
            "herdado": False, "territorio_id": _territorio_do_usuario(user.pk),
        },
    )
    return limite
