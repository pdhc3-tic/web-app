"""Curva S e projeções da execução do TED.

Na árvore do Plano de Trabalho (projeto, Meta, Submeta), o previsto sai do
snapshot da versão pedida, distribuído por dia entre o início e o fim de cada
Ação, e o realizado é o mesmo da aderência: Atividades concluídas e solicitações
pagas. Na rubrica, o previsto é o aprovado na versão, distribuído pela vigência,
e o realizado é a execução lançada no ledger do orçamento.

As projeções são por rubrica e estendem até o fim da vigência o ritmo dos
últimos 90 dias do ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal

from django.db.models import F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.core.utils import get_config
from apps.sgp.budget.alertas import meses_antes
from apps.sgp.budget.rls import visao_total
from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.models import (
    BudgetPool,
    BudgetRubrica,
    BudgetTransaction,
    TEDVersion,
    TEDVersionRubrica,
    WorkPlanMeta,
    WorkPlanSubmeta,
)
from apps.sgp.models.workplan import arredondar, percentual
from apps.sgp.services.apuracao import RecorteAtividades, mes_de, realizado_por_mes
from apps.sgp.ted.execucao import (
    AcaoDaVersao,
    _filtro,
    _solicitacoes_pagas,
    estados_do_escopo,
    execucao,
    versao_do_relatorio,
)

ZERO = Decimal("0")
CEM = Decimal("100")
JANELA_DO_RITMO = 90
DIAS_POR_MES = Decimal("30.4375")
ANTECEDENCIA_PADRAO = 12
LIMIAR_PADRAO_DO_SALDO_REMANESCENTE = 10
Tipo = BudgetTransaction.Tipo


class EscopoDaCurva:
    PROJETO = "projeto"
    META = "meta"
    SUBMETA = "submeta"
    RUBRICA = "rubrica"
    CHOICES = [(PROJETO, "Projeto"), (META, "Meta"), (SUBMETA, "Submeta"), (RUBRICA, "Rubrica")]


# ---------------------------------------------------------------------------
# Meses
# ---------------------------------------------------------------------------

def _proximo_mes(mes: date) -> date:
    return (mes.replace(day=28) + timedelta(days=4)).replace(day=1)


def _ultimo_dia(mes: date) -> date:
    return _proximo_mes(mes) - timedelta(days=1)


def _meses(inicio: date, fim: date) -> list[date]:
    meses, mes = [], inicio.replace(day=1)
    while mes <= fim:
        meses.append(mes)
        mes = _proximo_mes(mes)
    return meses


def _fracao_ate(dia: date, inicio: date, fim: date) -> Decimal:
    """Parte do intervalo [inicio, fim] decorrida até `dia`, inclusive."""
    total = (fim - inicio).days + 1
    if total <= 0:
        return Decimal(1) if dia >= fim else ZERO
    decorridos = min(max((dia - inicio).days + 1, 0), total)
    return Decimal(decorridos) / Decimal(total)


def _acumulado(por_mes: dict[date, Decimal], meses: list[date], mes_corrente: date) -> list[Decimal]:
    """Acumulado em cada mês da vigência. O que caiu antes do primeiro mês entra
    nele. O que caiu depois do mês corrente, como a Atividade concluída antes do
    término previsto, entra no mês corrente, para o último ponto com realizado
    fechar com o total."""
    if not meses:
        return []
    ultimo_com_realizado = min(mes_corrente, meses[-1])
    acumulados, total = [], ZERO
    pendentes = sorted(por_mes.items())
    for mes in meses:
        while pendentes and (mes >= ultimo_com_realizado or pendentes[0][0] <= mes):
            total += Decimal(pendentes.pop(0)[1])
        acumulados.append(total)
    return acumulados


def _meses_restantes(hoje: date, fim: date) -> Decimal | None:
    dias = (fim - hoje).days
    return Decimal(dias) / DIAS_POR_MES if dias > 0 else None


# ---------------------------------------------------------------------------
# Curva S
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PontoDaCurva:
    mes: date
    previsto_quantidade: Decimal | None
    realizado_quantidade: Decimal | None
    previsto_valor: Decimal
    realizado_valor: Decimal | None


@dataclass(frozen=True)
class RitmoNecessario:
    meses_restantes: Decimal | None
    quantidade_por_mes: Decimal | None
    valor_por_mes: Decimal | None


@dataclass(frozen=True)
class CurvaS:
    versao: TEDVersion
    escopo: str
    referencia_id: int | None
    nome: str
    data_base: date
    pontos: list[PontoDaCurva]
    ritmo_necessario: RitmoNecessario
    acoes_manuais_fora_da_quantidade: int = 0
    acoes_manuais_fora_do_recorte: int = 0
    acoes_fora_da_versao: int = 0
    acoes_da_versao_fora_do_plano: int = 0


def _referencia_invalida(nome: str):
    return ErroComCodigo("referencia_invalida", f"{nome} não encontrada.")


def _itens_do_escopo(escopo: str, referencia_id: int | None, itens: list[AcaoDaVersao]):
    if escopo == EscopoDaCurva.PROJETO:
        return itens, "Projeto"
    if escopo == EscopoDaCurva.META:
        meta = WorkPlanMeta.objects.filter(pk=referencia_id).first()
        if meta is None:
            raise _referencia_invalida("Meta")
        return [i for i in itens if i.meta_numero == meta.numero], f"Meta {meta.numero} — {meta.titulo}"
    submeta = WorkPlanSubmeta.objects.filter(pk=referencia_id).first()
    if submeta is None:
        raise _referencia_invalida("Submeta")
    return [i for i in itens if i.submeta_numero == submeta.numero], f"{submeta.numero} — {submeta.titulo}"


def _previsto_da_acao(item: AcaoDaVersao, fim_do_mes: date, ultimo_mes: bool) -> Decimal:
    """No último mês da vigência, o planejado inteiro: a versão não obriga as Ações
    a caberem na vigência, e um aditivo pode encurtá-la."""
    if ultimo_mes:
        return Decimal(1)
    return _fracao_ate(
        fim_do_mes, date.fromisoformat(item.planejado.data_inicio), date.fromisoformat(item.planejado.data_fim),
    )


def _somado_por_mes(linhas) -> dict[date, Decimal]:
    por_mes: dict[date, Decimal] = {}
    for linha in linhas:
        mes = mes_de(linha["mes"])
        por_mes[mes] = por_mes.get(mes, ZERO) + linha["total"]
    return por_mes


def _executado_por_mes(filtro, acao_ids: set[int]) -> dict[date, Decimal]:
    """Pelo mês em que a demanda foi concluída: são as mesmas solicitações pagas
    do valor executado da aderência."""
    if not acao_ids:
        return {}
    with visao_total():
        linhas = list(
            _solicitacoes_pagas(filtro).filter(demanda__activity__acao_id__in=acao_ids)
            .annotate(mes=TruncMonth("demanda__status_alterado_em")).order_by()
            .values("mes").annotate(total=Sum("valor_pago"))
        )
    return _somado_por_mes(linhas)


def _ritmo_necessario(hoje, fim, falta_quantidade, falta_valor) -> RitmoNecessario:
    meses = _meses_restantes(hoje, fim)
    if meses is None:
        return RitmoNecessario(None, None, None)

    def por_mes(falta):
        return None if falta is None else arredondar(max(falta, ZERO) / meses)

    return RitmoNecessario(arredondar(meses), por_mes(falta_quantidade), por_mes(falta_valor))


def curva_s(user, escopo: str, versao: TEDVersion, *, referencia_id: int | None = None,
            hoje: date | None = None) -> CurvaS:
    """Previsto e realizado acumulados, mês a mês, ao longo da vigência da versão.
    O realizado para no mês corrente: os meses seguintes vêm nulos."""
    hoje = hoje or timezone.localdate()
    if escopo == EscopoDaCurva.RUBRICA:
        return _curva_da_rubrica(versao, referencia_id, hoje)

    estados = estados_do_escopo(user)
    dados = execucao(user, versao)
    itens, nome = _itens_do_escopo(escopo, referencia_id, dados.acoes)
    calculados = [item for item in itens if not item.manual]
    filtro = _filtro(estados, RecorteAtividades())
    meses = _meses(versao.vigencia_inicio, versao.vigencia_fim)
    mes_corrente = hoje.replace(day=1)

    fisico = _acumulado(
        realizado_por_mes([item.acao for item in calculados if item.acao is not None], filtro),
        meses, mes_corrente,
    )
    financeiro = _acumulado(
        _executado_por_mes(filtro, {item.acao.pk for item in itens if item.acao is not None}),
        meses, mes_corrente,
    )
    pontos = []
    for posicao, mes in enumerate(meses):
        fim_do_mes, ultimo = _ultimo_dia(mes), posicao == len(meses) - 1
        futuro = mes > mes_corrente
        pontos.append(PontoDaCurva(
            mes=mes,
            previsto_quantidade=arredondar(sum(
                (item.planejado.quantidade * _previsto_da_acao(item, fim_do_mes, ultimo) for item in calculados),
                ZERO,
            )),
            realizado_quantidade=None if futuro else arredondar(fisico[posicao]),
            previsto_valor=arredondar(sum(
                (item.planejado.valor * _previsto_da_acao(item, fim_do_mes, ultimo) for item in itens), ZERO,
            )),
            realizado_valor=None if futuro else arredondar(financeiro[posicao]),
        ))

    if estados is None:
        ritmo = _ritmo_necessario(
            hoje, versao.vigencia_fim,
            sum((item.planejado.quantidade for item in calculados), ZERO) - (fisico[-1] if fisico else ZERO),
            sum((item.planejado.valor for item in itens), ZERO) - (financeiro[-1] if financeiro else ZERO),
        )
    else:
        # O ritmo necessário é do projeto: o previsto é nacional, e o realizado
        # do recorte o faria parecer maior do que é.
        ritmo = RitmoNecessario(_ritmo_necessario(hoje, versao.vigencia_fim, None, None).meses_restantes, None, None)
    return CurvaS(
        versao=versao, escopo=escopo, referencia_id=referencia_id, nome=nome, data_base=hoje, pontos=pontos,
        ritmo_necessario=ritmo,
        acoes_manuais_fora_da_quantidade=sum(1 for item in itens if item.manual),
        acoes_manuais_fora_do_recorte=dados.acoes_manuais_fora_do_recorte(por_territorio=False),
        acoes_fora_da_versao=dados.acoes_fora_da_versao,
        acoes_da_versao_fora_do_plano=sum(1 for item in itens if item.acao is None),
    )


def _curva_da_rubrica(versao: TEDVersion, referencia_id: int | None, hoje: date) -> CurvaS:
    """Só em R$: a rubrica não tem quantidade. É o agregado de todos os pools da
    rubrica, que só os perfis de leitura nacional do orçamento veem."""
    rubrica = BudgetRubrica.objects.filter(pk=referencia_id).first()
    if rubrica is None:
        raise _referencia_invalida("Rubrica")
    aprovado = TEDVersionRubrica.objects.filter(versao=versao, rubrica=rubrica).values_list(
        "valor_aprovado", flat=True,
    ).first() or ZERO
    with visao_total():
        linhas = list(
            BudgetTransaction.objects.filter(tipo=Tipo.EXECUCAO, pool__rubrica=rubrica)
            .annotate(mes=TruncMonth("criado_em")).order_by()
            .values("mes").annotate(total=Sum("valor"))
        )

    meses = _meses(versao.vigencia_inicio, versao.vigencia_fim)
    mes_corrente = hoje.replace(day=1)
    financeiro = _acumulado(_somado_por_mes(linhas), meses, mes_corrente)
    pontos = [
        PontoDaCurva(
            mes=mes, previsto_quantidade=None, realizado_quantidade=None,
            previsto_valor=arredondar(
                aprovado * _fracao_ate(_ultimo_dia(mes), versao.vigencia_inicio, versao.vigencia_fim),
            ),
            realizado_valor=None if mes > mes_corrente else arredondar(financeiro[posicao]),
        )
        for posicao, mes in enumerate(meses)
    ]
    return CurvaS(
        versao=versao, escopo=EscopoDaCurva.RUBRICA, referencia_id=rubrica.pk, nome=rubrica.nome,
        data_base=hoje, pontos=pontos,
        ritmo_necessario=_ritmo_necessario(
            hoje, versao.vigencia_fim, None, aprovado - (financeiro[-1] if financeiro else ZERO),
        ),
    )


# ---------------------------------------------------------------------------
# Projeções por rubrica
# ---------------------------------------------------------------------------

def _parametro_inteiro(chave: str, padrao: int, minimo: int, maximo: int) -> int:
    """Valor ausente, ilegível ou fora da faixa vale o padrão."""
    try:
        valor = int(get_config(chave, padrao))
    except (TypeError, ValueError):
        return padrao
    return valor if minimo <= valor <= maximo else padrao


def parametros_do_risco_de_devolucao() -> tuple[int, Decimal]:
    """Antecedência do alerta, em meses antes do fim da vigência, e limiar do saldo
    remanescente projetado, em percentual do aprovado."""
    return (
        _parametro_inteiro("budget_return_risk_alert_months", ANTECEDENCIA_PADRAO, 1, 24),
        Decimal(_parametro_inteiro("budget_return_risk_pct", LIMIAR_PADRAO_DO_SALDO_REMANESCENTE, 1, 100)),
    )


@dataclass(frozen=True)
class Projecao:
    rubrica_id: int | None
    nome: str
    slug: str | None
    valor_aprovado: Decimal
    valor_comprometido: Decimal
    valor_executado: Decimal
    perc_execucao_atual: Decimal | None
    ritmo_execucao_mensal: Decimal
    ritmo_comprometimento_mensal: Decimal
    valor_executado_projetado: Decimal
    perc_execucao_projetado: Decimal | None
    saldo_remanescente_projetado: Decimal
    perc_saldo_remanescente_projetado: Decimal | None
    data_esgotamento: date | None
    ja_esgotada: bool
    esgota_antes_do_fim: bool
    ritmo_necessario_mensal: Decimal | None
    risco_devolucao: bool


@dataclass(frozen=True)
class Projecoes:
    versao: TEDVersion
    data_base: date
    vigencia_fim: date
    janela_inicio: date
    janela_dias: int
    meses_restantes: Decimal | None
    antecedencia_meses: int
    limiar_saldo_remanescente_pct: Decimal
    alerta_a_partir_de: date
    rubricas: list[Projecao]
    projeto: Projecao

    @property
    def na_janela_do_alerta(self) -> bool:
        """A partir da antecedência e dentro da vigência: antes do início não há
        ritmo para projetar, e depois do fim não há mais como remanejar."""
        return max(self.alerta_a_partir_de, self.versao.vigencia_inicio) <= self.data_base <= self.vigencia_fim


@dataclass(frozen=True)
class _Base:
    hoje: date
    fim: date
    janela_dias: int
    dias_restantes: int
    meses_restantes: Decimal | None
    limiar: Decimal


def _projetar(base: _Base, *, rubrica_id, nome, slug, aprovado, comprometido, executado,
              executado_na_janela, comprometido_na_janela) -> Projecao:
    """`comprometido` inclui o executado: é o que já saiu do aprovado."""
    dias = Decimal(base.janela_dias)
    ritmo_execucao = executado_na_janela / dias if dias > ZERO else ZERO
    ritmo_comprometimento = comprometido_na_janela / dias if dias > ZERO else ZERO
    projetado = executado + ritmo_execucao * base.dias_restantes
    com_aprovado = aprovado > ZERO
    perc_projetado = arredondar(percentual(projetado, aprovado)) if com_aprovado else None
    perc_saldo = CEM - perc_projetado if perc_projetado is not None else None

    falta = aprovado - comprometido
    ja_esgotada = com_aprovado and falta <= ZERO
    data_esgotamento = None
    if com_aprovado and not ja_esgotada and ritmo_comprometimento > ZERO:
        dias_ate = int((falta / ritmo_comprometimento).to_integral_value(rounding=ROUND_CEILING))
        if dias_ate <= (date.max - base.hoje).days:
            data_esgotamento = base.hoje + timedelta(days=dias_ate)

    necessario = None
    if base.meses_restantes is not None:
        necessario = arredondar(max(aprovado - executado, ZERO) / base.meses_restantes)
    return Projecao(
        rubrica_id=rubrica_id, nome=nome, slug=slug,
        valor_aprovado=arredondar(aprovado), valor_comprometido=arredondar(comprometido),
        valor_executado=arredondar(executado),
        perc_execucao_atual=arredondar(percentual(executado, aprovado)) if com_aprovado else None,
        ritmo_execucao_mensal=arredondar(ritmo_execucao * DIAS_POR_MES),
        ritmo_comprometimento_mensal=arredondar(ritmo_comprometimento * DIAS_POR_MES),
        valor_executado_projetado=arredondar(projetado),
        perc_execucao_projetado=perc_projetado,
        saldo_remanescente_projetado=arredondar(aprovado - projetado),
        perc_saldo_remanescente_projetado=perc_saldo,
        data_esgotamento=data_esgotamento, ja_esgotada=ja_esgotada,
        esgota_antes_do_fim=ja_esgotada or (data_esgotamento is not None and data_esgotamento <= base.fim),
        ritmo_necessario_mensal=necessario,
        risco_devolucao=perc_saldo is not None and perc_saldo > base.limiar,
    )


def _movimento_na_janela(desde: date, ate: date, rubricas: Q) -> dict[int, dict[str, Decimal]]:
    """Lançamentos dos pools na janela (desde, ate], por rubrica e tipo. Na
    execução, `variacao` é o que ela comprometeu além do reservado: o pagamento
    acima da reserva não tem lançamento de ajuste."""
    with visao_total():
        linhas = list(
            BudgetTransaction.objects.filter(
                rubricas, pool__isnull=False,
                tipo__in=[Tipo.RESERVA, Tipo.AJUSTE, Tipo.LIBERACAO, Tipo.EXECUCAO],
                criado_em__date__gt=desde, criado_em__date__lte=ate,
            ).order_by().values("pool__rubrica_id", "tipo").annotate(
                total=Sum("valor"), variacao=Sum(F("saldo_anterior") - F("saldo_posterior")),
            )
        )
    movimento: dict[int, dict[str, Decimal]] = {}
    for linha in linhas:
        por_tipo = movimento.setdefault(linha["pool__rubrica_id"], {})
        por_tipo[linha["tipo"]] = linha["total"]
        if linha["tipo"] == Tipo.EXECUCAO:
            por_tipo["excedente_da_execucao"] = linha["variacao"]
    return movimento


def projecoes_por_rubrica(versao: TEDVersion | None = None, hoje: date | None = None, *,
                          rubrica_id: int | None = None) -> Projecoes:
    """Uma linha por rubrica aprovada na versão (a vigente, sem `versao`) e a do
    projeto, que soma todas. O executado e o comprometido são os de todos os pools
    da rubrica. Com `rubrica_id`, só a dessa rubrica."""
    hoje = hoje or timezone.localdate()
    versao = versao or versao_do_relatorio()
    antecedencia, limiar = parametros_do_risco_de_devolucao()
    janela_inicio = max(hoje - timedelta(days=JANELA_DO_RITMO), versao.vigencia_inicio)
    base = _Base(
        hoje=hoje, fim=versao.vigencia_fim, janela_dias=max((hoje - janela_inicio).days, 0),
        dias_restantes=max((versao.vigencia_fim - hoje).days, 0),
        meses_restantes=_meses_restantes(hoje, versao.vigencia_fim), limiar=limiar,
    )

    aprovados = TEDVersionRubrica.objects.filter(versao=versao).select_related("rubrica")
    pools = BudgetPool.objects.all()
    rubricas_do_ledger = Q()
    if rubrica_id is not None:
        aprovados = aprovados.filter(rubrica_id=rubrica_id)
        pools = pools.filter(rubrica_id=rubrica_id)
        rubricas_do_ledger = Q(pool__rubrica_id=rubrica_id)
    with visao_total():
        saldos = {
            linha["rubrica_id"]: linha
            for linha in pools.order_by().values("rubrica_id").annotate(
                comprometido=Sum("valor_comprometido"), executado=Sum("valor_executado"),
            )
        }
    movimento = _movimento_na_janela(janela_inicio, hoje, rubricas_do_ledger)

    linhas, soma = [], dict.fromkeys(
        ("aprovado", "comprometido", "executado", "executado_na_janela", "comprometido_na_janela"), ZERO,
    )
    for item in aprovados.order_by("rubrica__ordem", "rubrica__nome"):
        saldo = saldos.get(item.rubrica_id, {})
        lancado = movimento.get(item.rubrica_id, {})
        valores = {
            "aprovado": item.valor_aprovado,
            "comprometido": (saldo.get("comprometido") or ZERO) + (saldo.get("executado") or ZERO),
            "executado": saldo.get("executado") or ZERO,
            "executado_na_janela": lancado.get(Tipo.EXECUCAO, ZERO),
            "comprometido_na_janela": (
                lancado.get(Tipo.RESERVA, ZERO) + lancado.get(Tipo.AJUSTE, ZERO)
                - lancado.get(Tipo.LIBERACAO, ZERO) + lancado.get("excedente_da_execucao", ZERO)
            ),
        }
        for chave, valor in valores.items():
            soma[chave] += valor
        linhas.append(_projetar(
            base, rubrica_id=item.rubrica_id, nome=item.rubrica.nome, slug=item.rubrica.slug, **valores,
        ))
    return Projecoes(
        versao=versao, data_base=hoje, vigencia_fim=versao.vigencia_fim, janela_inicio=janela_inicio,
        janela_dias=base.janela_dias,
        meses_restantes=arredondar(base.meses_restantes) if base.meses_restantes else None,
        antecedencia_meses=antecedencia, limiar_saldo_remanescente_pct=limiar,
        alerta_a_partir_de=meses_antes(versao.vigencia_fim, antecedencia),
        rubricas=linhas,
        projeto=_projetar(base, rubrica_id=None, nome="Projeto", slug=None, **soma),
    )
