"""Limites de gasto por perfil e por usuário: a primeira das duas travas de saldo.

O padrão do perfil vale para todos os seus usuários. A linha individual do período guarda o
que a pessoa comprometeu e executou: nasce do padrão na primeira reserva (`herdado`) ou de uma
sobrescrita justificada. Uma reserva fica presa à linha em que foi feita, mesmo depois da
virada do período.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
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


def territorio_do_usuario(user_id) -> int | None:
    return (
        UserProfile.objects
        .filter(user_id=user_id, perfil__slug__in=PERFIS_OPERACIONAIS, territorio__isnull=False)
        .order_by("pk")
        .values_list("territorio_id", flat=True)
        .first()
    )


def territorio_do_pool(user_id) -> int | None:
    """O território cujo pool recebe as reservas do usuário. None para quem reserva em outro nível:
    Super Admin e UGP no nacional, Articulador no estadual."""
    perfis = UserProfile.objects.filter(user_id=user_id)
    if perfis.filter(
        Q(perfil__slug__in=("super-admin", "ugp"))
        | Q(perfil__slug="articulador-estadual", territorio__estados__len__gt=0)
    ).exists():
        return None
    return (
        perfis.filter(perfil__slug="adt-acr", territorio__isnull=False)
        .order_by("pk")
        .values_list("territorio_id", flat=True)
        .first()
    )


def _linha_que_termina_antes(user_id, rubrica_id, inicio: date):
    """Só o período imediatamente anterior acumula: pular um período não traz saldo de dois atrás."""
    return SpendingLimit.objects.filter(
        escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id, periodo_fim=inicio - timedelta(days=1),
    )


def _saldo_a_acumular(user_id, rubrica_id, inicio: date) -> Decimal:
    if not get_config("budget_limit_carry_over", False):
        return ZERO
    anterior = _linha_que_termina_antes(user_id, rubrica_id, inicio).first()
    return max(anterior.saldo_disponivel, ZERO) if anterior else ZERO


def _periodo_livre_entre(linhas, data: date) -> tuple[date, date]:
    """O período de `data`, encurtado para não cobrir uma sobrescrita de datas próprias que já terminou
    ou que ainda vai começar: duas linhas no mesmo dia dariam dois limites à mesma pessoa."""
    inicio, fim = periodo_de(data)
    antes = [linha.periodo_fim for linha in linhas if inicio <= linha.periodo_fim < data]
    depois = [linha.periodo_inicio for linha in linhas if data < linha.periodo_inicio <= fim]
    if antes:
        inicio = max(antes) + timedelta(days=1)
    if depois:
        fim = min(depois) - timedelta(days=1)
    return inicio, fim


def _periodo_livre(user_id, rubrica_id, data: date) -> tuple[date, date]:
    linhas = SpendingLimit.objects.filter(escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id)
    return _periodo_livre_entre(list(linhas), data)


def _montar_herdada(user_id, rubrica_id, *, padrao, acumulado, inicio, fim, territorio_id) -> SpendingLimit:
    return SpendingLimit(
        escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id, herdado=True,
        territorio_id=territorio_id, valor_limite=(padrao.valor_limite if padrao else ZERO) + acumulado,
        periodo_inicio=inicio, periodo_fim=fim,
    )


def _linha_herdada(user_id, rubrica_id, data: date) -> SpendingLimit | None:
    """A linha do período que o padrão do perfil e o saldo acumulado gerariam, sem gravar. None sem
    nenhum dos dois: quem só tinha sobrescrita e nada a acumular fica sem limite no período novo."""
    padrao = _padrao_do_usuario(user_id, rubrica_id, data)
    inicio, fim = _periodo_livre(user_id, rubrica_id, data)
    acumulado = _saldo_a_acumular(user_id, rubrica_id, inicio)
    if padrao is None and acumulado <= ZERO:
        return None
    return _montar_herdada(
        user_id, rubrica_id, padrao=padrao, acumulado=acumulado, inicio=inicio, fim=fim,
        territorio_id=territorio_do_usuario(user_id),
    )


def limite_efetivo(user_id, rubrica_id, data: date | None = None) -> SpendingLimit | None:
    """Somente leitura: a linha vigente ou, sem ela, a que o padrão do perfil geraria."""
    data = data or hoje()
    return _linha_vigente(user_id, rubrica_id, data) or _linha_herdada(user_id, rubrica_id, data)


def limites_efetivos(user_id, rubrica_ids, data: date | None = None) -> dict:
    """`limite_efetivo` de várias rubricas, sem consultar o banco por rubrica."""
    data = data or hoje()
    rubrica_ids = list(rubrica_ids)
    linhas_por_rubrica: dict = {}
    for linha in SpendingLimit.objects.filter(escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id__in=rubrica_ids):
        linhas_por_rubrica.setdefault(linha.rubrica_id, []).append(linha)
    padroes: dict = {}
    for padrao in (
        _vigentes_em(data)
        .filter(
            escopo=Escopo.PERFIL, rubrica_id__in=rubrica_ids,
            perfil__in=UserProfile.objects.filter(user_id=user_id).values("perfil"),
        )
        .order_by("-valor_limite", "pk")
    ):
        padroes.setdefault(padrao.rubrica_id, padrao)
    acumula = get_config("budget_limit_carry_over", False)
    territorio_id = territorio_do_usuario(user_id)

    efetivos = {}
    for rubrica_id in rubrica_ids:
        linhas = linhas_por_rubrica.get(rubrica_id, [])
        vigentes = [linha for linha in linhas if linha.periodo_inicio <= data <= linha.periodo_fim]
        if vigentes:
            efetivos[rubrica_id] = max(vigentes, key=lambda linha: linha.periodo_inicio)
            continue
        padrao = padroes.get(rubrica_id)
        inicio, fim = _periodo_livre_entre(linhas, data)
        anterior = next((linha for linha in linhas if linha.periodo_fim == inicio - timedelta(days=1)), None)
        acumulado = max(anterior.saldo_disponivel, ZERO) if acumula and anterior else ZERO
        if padrao is None and acumulado <= ZERO:
            continue
        efetivos[rubrica_id] = _montar_herdada(
            user_id, rubrica_id, padrao=padrao, acumulado=acumulado, inicio=inicio, fim=fim,
            territorio_id=territorio_id,
        )
    return efetivos


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


def _criar_ou_travar(linha: SpendingLimit, *, justificativa: str) -> SpendingLimit:
    """Duas transações podem criar a mesma linha: o savepoint deixa a segunda esperar a primeira
    no índice único e, no IntegrityError, reler a linha já travada. Quem cria abre o ledger dela."""
    try:
        with transaction.atomic():
            linha.save()
            criada = SpendingLimit.objects.select_for_update(of=("self",)).get(pk=linha.pk)
            if criada.valor_limite > ZERO:
                registrar_movimento(
                    limite=criada, tipo=Tipo.AUMENTO_LIMITE, valor=criada.valor_limite, usuario=criada.criado_por,
                    justificativa=justificativa,
                )
            return criada
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
    anterior = _travar_linha_a_acumular(user_id, rubrica_id, data)
    if anterior is not None:
        # Quem esperou este lock pode encontrar a linha já criada por quem o segurava.
        linha = _vigente_travada(user_id, rubrica_id, data)
        if linha is not None:
            return linha
    nova = _linha_herdada(user_id, rubrica_id, data)
    if nova is None:
        return None
    criada = _criar_ou_travar(nova, justificativa="Linha do período: padrão do perfil e saldo acumulado.")
    if anterior is not None and criada.pk == nova.pk:
        _debitar_o_acumulado(anterior)
    return criada


def _travar_linha_a_acumular(user_id, rubrica_id, data: date) -> SpendingLimit | None:
    if not get_config("budget_limit_carry_over", False):
        return None
    inicio = _periodo_livre(user_id, rubrica_id, data)[0]
    return _linha_que_termina_antes(user_id, rubrica_id, inicio).select_for_update(of=("self",)).first()


def _debitar_o_acumulado(anterior: SpendingLimit) -> None:
    """O saldo passa para a linha nova: sem o débito, existiria nas duas, e um ajuste na reserva presa
    à linha antiga gastaria de novo o que já foi acumulado."""
    acumulado = anterior.saldo_disponivel
    if acumulado <= ZERO:
        return
    anterior.valor_limite -= acumulado
    anterior.save(update_fields=["valor_limite", "atualizado_em"])
    registrar_movimento(
        limite=anterior, tipo=Tipo.AUMENTO_LIMITE, valor=-acumulado, usuario=None,
        justificativa="Saldo acumulado para o período seguinte.",
    )


def travar_limite_para_elevar(*, user_id, rubrica_id, justificativa: str, usuario) -> SpendingLimit:
    """Recurso extra de quem ainda não tem limite: a linha nasce zerada, e a elevação a preenche."""
    linha = travar_limite_vigente(user_id=user_id, rubrica_id=rubrica_id, criar=True)
    if linha is not None:
        return linha
    inicio, fim = _periodo_livre(user_id, rubrica_id, hoje())
    return _criar_ou_travar(SpendingLimit(
        escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id, valor_limite=ZERO,
        territorio_id=territorio_do_usuario(user_id), justificativa=justificativa,
        periodo_inicio=inicio, periodo_fim=fim, criado_por=usuario,
    ), justificativa=justificativa)


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
    """Só quem reserva no pool do território: o Articulador reserva no pool estadual, mesmo com o
    perfil vinculado a um território."""
    usuarios = (
        UserProfile.objects
        .filter(territorio_id=territorio_id, perfil__slug="adt-acr")
        .order_by()
        .values_list("user_id", flat=True)
        .distinct()
    )
    soma = ZERO
    for user_id in usuarios:
        if territorio_do_pool(user_id) != territorio_id:
            continue
        limite = limite_efetivo(user_id, rubrica_id, data)
        if limite is not None:
            soma += limite.valor_limite
    return soma


def exigir_dentro_do_pool(rubrica_id, territorio_ids, data: date | None = None, *, ajuste: Decimal = ZERO) -> None:
    """Com a sobrealocação desligada, a soma dos limites do território não passa do pool. Os pools ficam
    travados até o commit, em ordem de pk: sem isso, dois aumentos simultâneos passariam, cada um sem
    ver o outro. Território sem pool fica de fora: lá nenhuma reserva passa na segunda trava, e contá-lo
    como zero recusaria o padrão do perfil inteiro. `ajuste` é o que ainda não foi gravado, para quem
    confere antes de salvar."""
    if get_config("budget_overallocation_allowed", True):
        return
    data = data or hoje()
    pools = (
        BudgetPool.objects.select_for_update(of=("self",))
        .filter(rubrica_id=rubrica_id, nivel=BudgetPool.Nivel.TERRITORIAL, territorio_id__in=set(territorio_ids))
        .order_by("pk")
    )
    for pool in pools:
        soma = _soma_no_territorio(rubrica_id, pool.territorio_id, data) + ajuste
        if soma > pool.valor_alocado:
            raise DRFValidationError({
                "valor_limite": (
                    f"A soma dos limites do território ({formatar_brl(soma)}) passa do pool "
                    f"({formatar_brl(pool.valor_alocado)}), e a sobrealocação está desligada."
                ),
                "soma_limites": str(soma),
                "valor_pool": str(pool.valor_alocado),
                "territorio": pool.territorio_id,
            })


def _territorios_do_perfil(perfil_id) -> list[int]:
    return list(
        UserProfile.objects
        .filter(perfil_id=perfil_id, perfil__slug="adt-acr", territorio__isnull=False)
        .order_by()
        .values_list("territorio_id", flat=True)
        .distinct()
    )


def exigir_sem_sobreposicao(user_id, rubrica_id, inicio: date, fim: date) -> None:
    """Duas linhas no mesmo dia dariam ao usuário um limite novo sobre o que já esgotou."""
    sobrepostas = SpendingLimit.objects.filter(
        escopo=Escopo.INDIVIDUAL, user_id=user_id, rubrica_id=rubrica_id,
        periodo_inicio__lte=fim, periodo_fim__gte=inicio,
    )
    if sobrepostas.exists():
        raise DRFValidationError({"rubrica": "Já existe um limite individual deste solicitante nesta rubrica."})


@transaction.atomic
def criar_sobrescrita(*, user, rubrica, valor_limite: Decimal, justificativa: str, usuario,
                      periodo_inicio: date | None = None, periodo_fim: date | None = None) -> SpendingLimit:
    justificativa = _exigir_justificativa(justificativa)
    if (periodo_inicio is None) != (periodo_fim is None):
        raise DRFValidationError({"periodo_fim": "Informe o início e o fim do período, ou nenhum dos dois."})
    if periodo_inicio is None:
        periodo_inicio, periodo_fim = _periodo_livre(user.pk, rubrica.pk, hoje())
    existente = _vigente_travada(user.pk, rubrica.pk, periodo_inicio)
    if (
        existente is not None and existente.herdado
        and (existente.periodo_inicio, existente.periodo_fim) == (periodo_inicio, periodo_fim)
    ):
        # A linha herdada já guarda reservas: vira sobrescrita, em vez de abrir uma segunda.
        return alterar_sobrescrita(
            existente.pk, valor_limite=valor_limite, justificativa=justificativa, usuario=usuario,
            virar_sobrescrita=True,
        )
    exigir_sem_sobreposicao(user.pk, rubrica.pk, periodo_inicio, periodo_fim)
    # O que a pessoa já teria pelo padrão do perfil: uma sobrescrita menor reduz, não aumenta.
    efetivo = limite_efetivo(user.pk, rubrica.pk, periodo_inicio)
    valor_efetivo = efetivo.valor_limite if efetivo else ZERO
    try:
        with transaction.atomic():
            limite = SpendingLimit.objects.create(
                escopo=Escopo.INDIVIDUAL, user=user, rubrica=rubrica, valor_limite=valor_limite,
                territorio_id=territorio_do_usuario(user.pk), justificativa=justificativa,
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
    territorio_id = territorio_do_pool(user.pk)
    if territorio_id and valor_limite > valor_efetivo:
        exigir_dentro_do_pool(rubrica.pk, [territorio_id], periodo_inicio)
    return limite


@transaction.atomic
def alterar_sobrescrita(pk: int, *, valor_limite: Decimal, justificativa: str, usuario,
                        virar_sobrescrita: bool = False) -> SpendingLimit:
    """Reduzir não invalida o que já foi autorizado: o comprometido fica como está, e o novo teto vale
    para as próximas reservas, mesmo que o saldo fique negativo. Com `virar_sobrescrita`, a linha herdada
    passa a ser sobrescrita mesmo com o valor igual: ela deixa de seguir o padrão do perfil."""
    limite = travar_linha(pk)
    valor_anterior = limite.valor_limite
    delta = valor_limite - valor_anterior
    if delta == ZERO and not (virar_sobrescrita and limite.herdado):
        return limite
    justificativa = _exigir_justificativa(justificativa)
    limite.valor_limite = valor_limite
    limite.justificativa = justificativa
    limite.herdado = False
    limite.save(update_fields=["valor_limite", "justificativa", "herdado", "atualizado_em"])
    if delta != ZERO:
        registrar_movimento(
            limite=limite, tipo=Tipo.AUMENTO_LIMITE, valor=delta, usuario=usuario, justificativa=justificativa,
        )
    auditar_alteracao(limite, valor_anterior=valor_anterior, usuario=usuario)
    # Só o aumento: com a soma já acima do pool, reduzir um limite ajuda e não pode ser recusado.
    territorio_id = territorio_do_pool(limite.user_id)
    if territorio_id and delta > ZERO:
        exigir_dentro_do_pool(limite.rubrica_id, [territorio_id], limite.periodo_inicio)
    return limite


@transaction.atomic
def criar_padrao(*, perfil, rubrica, valor_limite: Decimal, usuario, justificativa: str = "",
                 periodo_inicio: date | None = None) -> SpendingLimit:
    """O padrão vale até ser substituído: sem período informado, começa no período vigente."""
    periodo_inicio = periodo_inicio or periodo_de(hoje())[0]
    # Conflita também com um padrão já agendado para depois.
    conflito = SpendingLimit.objects.filter(
        escopo=Escopo.PERFIL, perfil=perfil, rubrica=rubrica, periodo_fim__gte=periodo_inicio,
    ).exists()
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


def _sucessor_do_padrao(limite: SpendingLimit) -> SpendingLimit | None:
    """A linha já agendada para o período seguinte a este padrão, que é o valor em vigor depois dele."""
    if limite.periodo_fim >= FIM_EM_ABERTO:
        return None
    return SpendingLimit.objects.select_for_update(of=("self",)).filter(
        escopo=Escopo.PERFIL, perfil_id=limite.perfil_id, rubrica_id=limite.rubrica_id,
        periodo_inicio=limite.periodo_fim + timedelta(days=1),
    ).first()


@transaction.atomic
def alterar_padrao(pk: int, *, valor_limite: Decimal, justificativa: str, usuario) -> SpendingLimit:
    """A mudança de um padrão já em uso só vale a partir do período seguinte: quem já tem a linha
    do período fica como está. Sem uso, ainda dá para corrigir o valor no próprio registro. Com um
    sucessor agendado, é sobre ele que a alteração vale, e é o valor dele que se compara."""
    limite = travar_linha(pk)
    sucessor = _sucessor_do_padrao(limite)
    atual = sucessor or limite
    valor_anterior = atual.valor_limite
    if valor_limite == valor_anterior:
        return atual
    justificativa = _exigir_justificativa(justificativa)
    if limite.periodo_fim < hoje():
        raise DRFValidationError({"periodo_fim": "Este padrão já foi encerrado. Altere o vigente."})
    fim_do_periodo = periodo_de(hoje())[1]

    # Na vigência do TED, período único, não existe período seguinte: vale a correção no registro.
    if sucessor is None and limite.periodo_inicio <= hoje() and _padrao_ja_foi_usado(limite) and fim_do_periodo < FIM_EM_ABERTO:
        inicio_seguinte = fim_do_periodo + timedelta(days=1)
        limite.periodo_fim = fim_do_periodo
        limite.save(update_fields=["periodo_fim", "atualizado_em"])
        atual = SpendingLimit.objects.create(
            escopo=Escopo.PERFIL, perfil_id=limite.perfil_id, rubrica_id=limite.rubrica_id,
            periodo_inicio=inicio_seguinte, periodo_fim=FIM_EM_ABERTO, valor_limite=valor_limite,
            justificativa=justificativa, criado_por=usuario,
        )
    else:
        atual.valor_limite = valor_limite
        atual.justificativa = justificativa
        atual.save(update_fields=["valor_limite", "justificativa", "atualizado_em"])

    auditar_alteracao(atual, valor_anterior=valor_anterior, usuario=usuario)
    if valor_limite > valor_anterior:
        data_da_conferencia = max(atual.periodo_inicio, hoje())
        exigir_dentro_do_pool(atual.rubrica_id, _territorios_do_perfil(atual.perfil_id), data_da_conferencia)
    return atual


def definir_limite_de_demonstracao(*, user, rubrica, valor_limite: Decimal) -> SpendingLimit:
    """Só para os dados de demonstração: grava a linha do período sem passar pelo cadastro."""
    inicio, fim = periodo_de(hoje())
    limite, _ = SpendingLimit.objects.update_or_create(
        escopo=Escopo.INDIVIDUAL, user=user, rubrica=rubrica, periodo_inicio=inicio,
        defaults={
            "valor_limite": valor_limite, "periodo_fim": fim, "justificativa": "Dados de demonstração.",
            "herdado": False, "territorio_id": territorio_do_usuario(user.pk),
        },
    )
    return limite
