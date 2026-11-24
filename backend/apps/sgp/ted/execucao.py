"""Execução física e financeira do Plano de Trabalho contra uma versão do TED:
índice de aderência, custo por entrega, rastreabilidade da rubrica à evidência e
comparativo entre versões.

O planejado de cada Ação (quantidade e valor unitário) e a árvore Meta → Submeta →
Ação saem do snapshot da versão pedida: é o que o TED aprovou naquela versão. O
realizado e o executado são os de agora, no escopo de quem consulta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.apps import apps
from django.db import transaction
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.core.services.permissions import user_role_slugs
from apps.core.utils import get_config
from apps.sgp.budget.rls import visao_total
from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.models import (
    TED,
    Activity,
    ActivityDocument,
    ActivityPhoto,
    AdherenceIndex,
    Indicator,
    TEDVersion,
    WorkPlanAcao,
    WorkPlanMeta,
    WorkPlanSubmeta,
)
from apps.sgp.models.indicator import FORMA_MANUAL
from apps.sgp.models.workplan import arredondar, percentual
from apps.sgp.services.access import estados_do_articulador
from apps.sgp.services.apuracao import RecorteAtividades, expressao_quantidade_realizada, realizado_agrupado

ZERO = Decimal("0")
CEM = Decimal("100")
INDICE = Decimal("0.01")
LIMIAR_PADRAO_DO_DESVIO_DE_CUSTO = Decimal("20")
PERFIS_COM_LEITURA_TOTAL = ("super-admin", "ugp", "fgd")

Escopo = AdherenceIndex.Escopo
Faixa = AdherenceIndex.Faixa


class FaixaDeCusto:
    DENTRO = "dentro_do_limiar"
    ACIMA = "acima_do_previsto"
    ABAIXO = "abaixo_do_previsto"
    CHOICES = [
        (DENTRO, "Dentro do limiar"),
        (ACIMA, "Acima do previsto"),
        (ABAIXO, "Abaixo do previsto"),
    ]


AGRUPAMENTOS_DE_CUSTO = ("acao", "indicador", "territorio")


# ---------------------------------------------------------------------------
# Escopo de quem consulta
# ---------------------------------------------------------------------------

def estados_do_escopo(user) -> set[str] | None:
    """`None` para quem lê o projeto inteiro (Super Admin, UGP e FGD, e a task, sem
    usuário). Para o Articulador, os estados dos territórios do perfil dele. Outros
    papéis do mesmo usuário, como ADT, não ampliam o recorte: o ADT não lê o TED."""
    if user is None or user_role_slugs(user, PERFIS_COM_LEITURA_TOTAL):
        return None
    return estados_do_articulador(user)


def _filtro(estados: set[str] | None, recorte: RecorteAtividades):
    """Q das Atividades que entram na conta, no formato de `apuracao` (recebe o
    prefixo até a Atividade); `None` quando nada restringe."""
    if estados is None and recorte.vazio:
        return None

    def filtro(prefixo: str) -> Q:
        q = recorte.q(prefixo)
        if estados is not None:
            q &= Q(**{f"{prefixo}ativo": True, f"{prefixo}municipio__state__sigla__in": sorted(estados)})
        return q

    return filtro


# ---------------------------------------------------------------------------
# Versão e planejado
# ---------------------------------------------------------------------------

def versao_do_relatorio(*, versao_id: int | None = None, data: date | None = None) -> TEDVersion:
    """A versão pedida, a vigente numa data (a última registrada até ela) ou a vigente agora."""
    if versao_id is not None and data is not None:
        raise ErroComCodigo("versao_e_data", "Informe a versão ou a data, não as duas.")
    ted = TED.objects.order_by("pk").first()
    if ted is None or ted.versao_vigente_id is None:
        raise ErroComCodigo("ted_nao_cadastrado", "Cadastre o TED antes de emitir os relatórios de execução.")
    versoes = TEDVersion.objects.filter(ted=ted)
    if versao_id is not None:
        versao = versoes.filter(pk=versao_id).first()
        if versao is None:
            raise ErroComCodigo("versao_invalida", "Versão do TED não encontrada.")
        return versao
    if data is not None:
        versao = versoes.filter(registrado_em__date__lte=data).order_by("-numero_versao").first()
        if versao is None:
            raise ErroComCodigo("sem_versao_na_data", "Nenhuma versão do TED estava vigente nessa data.")
        return versao
    return versoes.get(pk=ted.versao_vigente_id)


@dataclass(frozen=True)
class Planejado:
    quantidade: Decimal
    valor_unitario: Decimal
    data_inicio: str
    data_fim: str

    @property
    def valor(self) -> Decimal:
        return self.quantidade * self.valor_unitario


@dataclass
class AcaoDaVersao:
    """Uma Ação como está no snapshot da versão, com a correspondente do plano atual
    (pelo número) quando ela ainda existe."""

    numero: str
    descricao: str
    submeta_numero: str
    submeta_titulo: str
    meta_numero: int
    meta_titulo: str
    indicador_codigo: str
    indicador_nome: str
    planejado: Planejado
    acao: WorkPlanAcao | None = None

    @property
    def manual(self) -> bool:
        return self.acao is not None and self.acao.indicador.forma_apuracao == FORMA_MANUAL


def plano_da_versao(versao: TEDVersion) -> dict[str, AcaoDaVersao]:
    return {
        acao["numero"]: AcaoDaVersao(
            numero=acao["numero"], descricao=acao["descricao"],
            submeta_numero=submeta["numero"], submeta_titulo=submeta["titulo"],
            meta_numero=meta["numero"], meta_titulo=meta["titulo"],
            indicador_codigo=acao["indicador"]["codigo"], indicador_nome=acao["indicador"]["nome"],
            planejado=Planejado(
                Decimal(acao["quantidade_planejada"]), Decimal(acao["valor_unitario"]),
                acao["data_inicio"], acao["data_fim"],
            ),
        )
        for meta in versao.plano_snapshot.get("metas", [])
        for submeta in meta.get("submetas", [])
        for acao in submeta.get("acoes", [])
    }


# ---------------------------------------------------------------------------
# Realizado e executado
# ---------------------------------------------------------------------------

def _solicitacoes_pagas(filtro):
    """Solicitações pagas das demandas concluídas de Atividades ativas: a mesma
    regra do valor executado da Ação. O SGD é lido pelo registro de apps, porque
    é ele que depende do SGP."""
    DemandRequest = apps.get_model("sgd", "DemandRequest")
    qs = DemandRequest.objects.filter(
        demanda__status="concluida", demanda__activity__ativo=True, valor_pago__isnull=False,
    )
    return qs.filter(filtro("demanda__activity__")) if filtro else qs


def _executado(filtro, *grupos: str) -> dict[tuple, Decimal]:
    """Valor pago somado por Ação e pelos grupos pedidos. Os relatórios recortam
    pela Atividade, e não pelo solicitante, então a leitura do SGD sobe para visão
    total e o escopo de quem consulta entra pelo `filtro`."""
    campos = ["demanda__activity__acao_id", *grupos]
    with visao_total():
        linhas = list(
            _solicitacoes_pagas(filtro).order_by().values(*campos).annotate(total=Sum("valor_pago"))
        )
    return {tuple(linha[c] for c in campos): linha["total"] for linha in linhas}


@dataclass
class Execucao:
    versao: TEDVersion
    acoes: list[AcaoDaVersao]
    com_recorte: bool
    acoes_fora_da_versao: int
    acoes_da_versao_fora_do_plano: int
    acoes_manuais: int
    realizado: dict[str, Decimal] = field(default_factory=dict)
    executado: dict[str, Decimal] = field(default_factory=dict)
    realizado_por_territorio: dict[int, dict[str, Decimal]] = field(default_factory=dict)
    executado_por_territorio: dict[int, dict[str, Decimal]] = field(default_factory=dict)

    def acoes_manuais_fora_do_recorte(self, *, por_territorio: bool) -> int:
        """A quantidade lançada à mão pela UGP não tem território nem período: com
        recorte, ou na quebra por território, essas Ações ficam fora da conta."""
        return self.acoes_manuais if (self.com_recorte or por_territorio) else 0


def execucao(user, versao: TEDVersion, recorte: RecorteAtividades = RecorteAtividades(), *,
             por_territorio: bool = False) -> Execucao:
    estados = estados_do_escopo(user)
    filtro = _filtro(estados, recorte)
    plano = plano_da_versao(versao)

    atuais = WorkPlanAcao.objects.select_related("meta", "submeta", "indicador")
    if estados is not None:
        atuais = atuais.filter(
            atividades__ativo=True, atividades__municipio__state__sigla__in=sorted(estados),
        ).distinct()
    atuais = {a.numero: a for a in atuais.annotate(_quantidade_realizada=expressao_quantidade_realizada(filtro))}

    for numero, item in plano.items():
        item.acao = atuais.get(numero)
    itens = list(plano.values())
    if estados is not None:
        itens = [item for item in itens if item.acao is not None]
    manuais = sum(1 for item in itens if item.manual)
    if filtro is not None:
        itens = [item for item in itens if not item.manual]

    resultado = Execucao(
        versao=versao, acoes=itens, com_recorte=filtro is not None,
        acoes_fora_da_versao=sum(1 for numero in atuais if numero not in plano),
        acoes_da_versao_fora_do_plano=sum(1 for item in itens if item.acao is None),
        acoes_manuais=manuais,
    )
    por_id = {item.acao.pk: item.numero for item in itens if item.acao is not None}
    for item in itens:
        if item.acao is not None:
            resultado.realizado[item.numero] = Decimal(item.acao._quantidade_realizada or 0)
    for (id_acao,), total in _executado(filtro).items():
        if id_acao in por_id:
            resultado.executado[por_id[id_acao]] = total

    if por_territorio:
        calculadas = [item.acao for item in itens if item.acao is not None and not item.manual]
        territorio = "municipio__territory_id"
        for id_acao, grupos in realizado_agrupado(
            calculadas, lambda prefixo: {"grupo_territorio": F(f"{prefixo}{territorio}")}, filtro,
        ).items():
            for (id_territorio,), total in grupos.items():
                resultado.realizado_por_territorio.setdefault(id_territorio, {})[por_id[id_acao]] = Decimal(total)
        ids_calculadas = {a.pk for a in calculadas}
        for (id_acao, id_territorio), total in _executado(filtro, f"demanda__activity__{territorio}").items():
            if id_territorio is not None and id_acao in ids_calculadas:
                resultado.executado_por_territorio.setdefault(id_territorio, {})[por_id[id_acao]] = total
    return resultado


@dataclass(frozen=True)
class _Referencias:
    """Ids atuais das entidades nomeadas no snapshot, pelo número ou código."""

    submetas: dict[str, int]
    metas: dict[int, int]
    indicadores: dict[str, int]

    @classmethod
    def de(cls, itens: list[AcaoDaVersao]) -> "_Referencias":
        return cls(
            submetas=dict(WorkPlanSubmeta.objects.filter(
                numero__in={i.submeta_numero for i in itens},
            ).values_list("numero", "pk")),
            metas=dict(WorkPlanMeta.objects.filter(numero__in={i.meta_numero for i in itens}).values_list("numero", "pk")),
            indicadores=dict(Indicator.objects.filter(
                codigo__in={i.indicador_codigo for i in itens},
            ).values_list("codigo", "pk")),
        )

    def chave(self, escopo: str, item: AcaoDaVersao) -> tuple[tuple, int | None, str]:
        if escopo == Escopo.ACAO:
            return ("acao", item.numero), item.acao.pk if item.acao else None, f"{item.numero} — {item.descricao}"
        if escopo == Escopo.SUBMETA:
            return (
                ("submeta", item.submeta_numero), self.submetas.get(item.submeta_numero),
                f"{item.submeta_numero} — {item.submeta_titulo}",
            )
        if escopo == Escopo.META:
            return (
                ("meta", item.meta_numero), self.metas.get(item.meta_numero),
                f"Meta {item.meta_numero} — {item.meta_titulo}",
            )
        if escopo == Escopo.INDICADOR:
            return (
                ("indicador", item.indicador_codigo), self.indicadores.get(item.indicador_codigo),
                f"{item.indicador_codigo} — {item.indicador_nome}",
            )
        return ("projeto",), None, "Projeto"


# ---------------------------------------------------------------------------
# Aderência
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Aderencia:
    escopo: str
    referencia_id: int | None
    nome: str
    quantidade_planejada: Decimal
    quantidade_realizada: Decimal
    valor_planejado: Decimal
    valor_executado: Decimal
    perc_fisico: Decimal
    perc_financeiro: Decimal
    indice: Decimal | None
    faixa: str | None


def faixa_de_aderencia(perc_fisico: Decimal, perc_financeiro: Decimal) -> tuple[Decimal | None, str | None]:
    """Índice com duas casas, como as faixas (0,80 a 0,94; a partir de 0,95), e a
    faixa dele. Entrega sem gasto é subexecução financeira, sem índice; sem
    entrega nem gasto, não há índice nem faixa."""
    if perc_financeiro <= ZERO:
        return None, (Faixa.SUBEXECUCAO_FINANCEIRA if perc_fisico > ZERO else None)
    indice = (perc_fisico / perc_financeiro).quantize(INDICE, rounding=ROUND_HALF_UP)
    if indice > Decimal("1.20"):
        return indice, Faixa.SUBEXECUCAO_FINANCEIRA
    if indice >= Decimal("0.95"):
        return indice, Faixa.EQUILIBRADA
    if indice >= Decimal("0.80"):
        return indice, Faixa.ATENCAO
    return indice, Faixa.CRITICA


def _aderencia(escopo, referencia_id, nome, planejado_qtd, realizado_qtd, planejado_valor, executado_valor):
    fisico = percentual(realizado_qtd, planejado_qtd)
    financeiro = percentual(executado_valor, planejado_valor)
    if planejado_qtd > ZERO and planejado_valor > ZERO:
        indice, faixa = faixa_de_aderencia(fisico, financeiro)
    else:
        indice, faixa = None, None
    return Aderencia(
        escopo=escopo, referencia_id=referencia_id, nome=nome,
        quantidade_planejada=planejado_qtd, quantidade_realizada=realizado_qtd,
        valor_planejado=arredondar(planejado_valor), valor_executado=arredondar(executado_valor),
        perc_fisico=arredondar(fisico), perc_financeiro=arredondar(financeiro), indice=indice, faixa=faixa,
    )


def aderencia(escopo: str, dados: Execucao) -> list[Aderencia]:
    """Índice por escopo. Submeta, Meta, Indicador e projeto somam quantidades e
    valores das Ações da versão, como a árvore do Plano de Trabalho consolida. No
    território, o planejado não tem recorte: o denominador é o das Ações com
    atividade nele."""
    if escopo == Escopo.TERRITORIO:
        return _aderencia_por_territorio(dados)
    referencias = _Referencias.de(dados.acoes)
    grupos: dict[tuple, list] = {}
    for item in dados.acoes:
        chave, referencia_id, nome = referencias.chave(escopo, item)
        soma = grupos.setdefault(chave, [referencia_id, nome, ZERO, ZERO, ZERO, ZERO])
        soma[2] += item.planejado.quantidade
        soma[3] += dados.realizado.get(item.numero, ZERO)
        soma[4] += item.planejado.valor
        soma[5] += dados.executado.get(item.numero, ZERO)
    return [
        _aderencia(escopo, referencia_id, nome, q, r, v, e)
        for referencia_id, nome, q, r, v, e in sorted(grupos.values(), key=lambda soma: soma[1])
    ]


def _territorios(dados: Execucao) -> dict[int, str]:
    Territory = apps.get_model("core", "Territory")
    ids = set(dados.realizado_por_territorio) | set(dados.executado_por_territorio)
    return dict(Territory.objects.filter(pk__in=ids).values_list("pk", "nome"))


def _aderencia_por_territorio(dados: Execucao) -> list[Aderencia]:
    por_numero = {item.numero: item for item in dados.acoes}
    linhas = []
    for id_territorio, nome in _territorios(dados).items():
        realizado = dados.realizado_por_territorio.get(id_territorio, {})
        executado = dados.executado_por_territorio.get(id_territorio, {})
        envolvidas = [por_numero[n] for n in set(realizado) | set(executado) if n in por_numero]
        linhas.append(_aderencia(
            Escopo.TERRITORIO, id_territorio, nome,
            sum((i.planejado.quantidade for i in envolvidas), ZERO),
            sum((realizado.get(i.numero, ZERO) for i in envolvidas), ZERO),
            sum((i.planejado.valor for i in envolvidas), ZERO),
            sum((executado.get(i.numero, ZERO) for i in envolvidas), ZERO),
        ))
    return sorted(linhas, key=lambda linha: linha.nome)


def mes_da_serie(hoje: date) -> date:
    """A task roda às 4h: o cálculo do dia 1º fecha o mês anterior com o último
    dia inteiro dentro dele."""
    return (hoje - timedelta(days=1)).replace(day=1)


def gravar_serie_do_mes(hoje: date | None = None) -> int:
    """Grava o índice de todos os escopos na versão vigente. Entidades que não
    existem mais no plano atual ficam de fora da série, que é por id."""
    try:
        versao = versao_do_relatorio()
    except ErroComCodigo:
        return 0
    dados = execucao(None, versao, por_territorio=True)
    mes = mes_da_serie(hoje or date.today())
    gravados = 0
    with transaction.atomic():
        for escopo in Escopo.values:
            for linha in aderencia(escopo, dados):
                if linha.referencia_id is None and escopo != Escopo.PROJETO:
                    continue
                AdherenceIndex.objects.update_or_create(
                    escopo=escopo, referencia_id=linha.referencia_id, periodo_ref=mes,
                    defaults={
                        "ted_versao": versao, "perc_fisico": linha.perc_fisico,
                        "perc_financeiro": linha.perc_financeiro, "indice": linha.indice,
                        "faixa": linha.faixa or "",
                    },
                )
                gravados += 1
    return gravados


# ---------------------------------------------------------------------------
# Custo por entrega
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CustoPorEntrega:
    agrupamento: str
    referencia_id: int | None
    nome: str
    territorio_id: int | None
    territorio_nome: str | None
    quantidade_realizada: Decimal
    valor_executado: Decimal
    custo_unitario_previsto: Decimal | None
    custo_unitario_realizado: Decimal | None
    desvio_percentual: Decimal | None
    faixa: str | None


def limiar_do_desvio_de_custo() -> Decimal:
    """Parâmetro `cost_deviation_alert_pct`, em pontos percentuais. Valor ausente,
    ilegível ou negativo vale o padrão."""
    bruto = get_config("cost_deviation_alert_pct", LIMIAR_PADRAO_DO_DESVIO_DE_CUSTO)
    try:
        limiar = Decimal(str(bruto).strip().replace(",", "."))
    except InvalidOperation:
        return LIMIAR_PADRAO_DO_DESVIO_DE_CUSTO
    return limiar if limiar.is_finite() and limiar >= ZERO else LIMIAR_PADRAO_DO_DESVIO_DE_CUSTO


def _custo(agrupamento, referencia_id, nome, territorio, planejado_qtd, planejado_valor,
           realizado_qtd, executado_valor, limiar) -> CustoPorEntrega:
    previsto = arredondar(planejado_valor / planejado_qtd) if planejado_qtd > ZERO else None
    realizado = arredondar(executado_valor / realizado_qtd) if realizado_qtd > ZERO else None
    desvio = faixa = None
    if previsto and realizado is not None:
        desvio = arredondar((realizado - previsto) / previsto * CEM)
        faixa = (
            FaixaDeCusto.ACIMA if desvio > limiar
            else FaixaDeCusto.ABAIXO if desvio < -limiar
            else FaixaDeCusto.DENTRO
        )
    return CustoPorEntrega(
        agrupamento=agrupamento, referencia_id=referencia_id, nome=nome,
        territorio_id=territorio[0] if territorio else None, territorio_nome=territorio[1] if territorio else None,
        quantidade_realizada=realizado_qtd, valor_executado=arredondar(executado_valor),
        custo_unitario_previsto=previsto, custo_unitario_realizado=realizado,
        desvio_percentual=desvio, faixa=faixa,
    )


def custo_por_entrega(agrupamento: str, dados: Execucao, *, indicador_id: int | None = None) -> list[CustoPorEntrega]:
    """Custo unitário realizado (executado ÷ quantidade realizada) contra o previsto
    na versão do TED. Indicador e território consolidam as Ações: o previsto é o
    valor planejado sobre a quantidade planejada delas. Ordenado pelo maior desvio,
    para cima ou para baixo."""
    limiar = limiar_do_desvio_de_custo()
    referencias = _Referencias.de(dados.acoes)
    itens = [
        item for item in dados.acoes
        if indicador_id is None or referencias.indicadores.get(item.indicador_codigo) == indicador_id
    ]
    linhas: list[CustoPorEntrega] = []
    if agrupamento == "acao":
        for item in itens:
            _, referencia_id, nome = referencias.chave(Escopo.ACAO, item)
            linhas.append(_custo(
                "acao", referencia_id, nome, None, item.planejado.quantidade, item.planejado.valor,
                dados.realizado.get(item.numero, ZERO), dados.executado.get(item.numero, ZERO), limiar,
            ))
    else:
        if agrupamento == "indicador":
            fontes = [(None, dados.realizado, dados.executado)]
        else:
            fontes = [
                ((t, nome), dados.realizado_por_territorio.get(t, {}), dados.executado_por_territorio.get(t, {}))
                for t, nome in _territorios(dados).items()
            ]
        grupos: dict[tuple, list] = {}
        for territorio, realizado, executado in fontes:
            for item in itens:
                if territorio is not None and item.numero not in realizado and item.numero not in executado:
                    continue
                _, referencia_id, nome = referencias.chave(Escopo.INDICADOR, item)
                soma = grupos.setdefault((item.indicador_codigo, territorio), [referencia_id, nome, ZERO, ZERO, ZERO, ZERO])
                soma[2] += item.planejado.quantidade
                soma[3] += item.planejado.valor
                soma[4] += realizado.get(item.numero, ZERO)
                soma[5] += executado.get(item.numero, ZERO)
        for (_, territorio), (referencia_id, nome, q, v, r, e) in grupos.items():
            linhas.append(_custo(agrupamento, referencia_id, nome, territorio, q, v, r, e, limiar))
    return sorted(
        linhas,
        key=lambda linha: (linha.desvio_percentual is None, -abs(linha.desvio_percentual or ZERO), linha.nome),
    )


def composicao_por_rubrica(user, *, acao_id: int | None = None, indicador_id: int | None = None) -> list[dict]:
    """Participação de cada rubrica no valor executado de uma Ação ou de um Indicador."""
    if (acao_id is None) == (indicador_id is None):
        raise ErroComCodigo("acao_ou_indicador", "Informe a Ação ou o Indicador.")
    filtro = _filtro(estados_do_escopo(user), RecorteAtividades())
    alvo = (
        {"demanda__activity__acao_id": acao_id} if acao_id
        else {"demanda__activity__acao__indicador_id": indicador_id}
    )
    with visao_total():
        linhas = list(
            _solicitacoes_pagas(filtro).filter(**alvo).order_by()
            .values("rubrica_id", "rubrica__nome", "rubrica__slug").annotate(total=Sum("valor_pago"))
        )
    total = sum((linha["total"] for linha in linhas), ZERO)
    return sorted(
        (
            {
                "rubrica": {"id": linha["rubrica_id"], "nome": linha["rubrica__nome"], "slug": linha["rubrica__slug"]},
                "valor_executado": arredondar(linha["total"]),
                "participacao_percentual": arredondar(percentual(linha["total"], total)),
            }
            for linha in linhas
        ),
        key=lambda item: -item["valor_executado"],
    )


# ---------------------------------------------------------------------------
# Rastreabilidade
# ---------------------------------------------------------------------------

def _contagem(queryset, campo_da_atividade: str):
    return Coalesce(
        Subquery(
            queryset.filter(**{campo_da_atividade: OuterRef("demanda__activity_id")})
            .order_by().values(campo_da_atividade).annotate(total=Count("pk")).values("total"),
            output_field=IntegerField(),
        ),
        0,
    )


def rastreabilidade(user, *, rubrica, recorte: RecorteAtividades = RecorteAtividades(), acao_id: int | None = None):
    """Solicitações pagas da rubrica até a evidência de campo da Atividade, pelo
    mesmo recorte do custo e da composição: o estado da Atividade. Quem avalia o
    queryset precisa estar dentro de `visao_total()`, porque o RLS do SGD recorta
    pelo estado do solicitante."""
    filtro = _filtro(estados_do_escopo(user), recorte)
    qs = _solicitacoes_pagas(filtro).filter(rubrica=rubrica)
    if acao_id is not None:
        qs = qs.filter(demanda__activity__acao_id=acao_id)
    atividade = "demanda__activity__"
    documentos = ActivityDocument.objects.filter(ativo=True)
    return (
        qs.select_related(
            f"{atividade}municipio__territory", f"{atividade}acao__meta",
            f"{atividade}acao__submeta", f"{atividade}acao__indicador",
        )
        .annotate(
            evidencia_fotos=_contagem(ActivityPhoto.objects.filter(ativo=True), "activity_id"),
            evidencia_documentos=_contagem(documentos, "activity_id"),
            evidencia_listas_presenca=_contagem(
                documentos.filter(tipo=ActivityDocument.TIPO_LISTA_PRESENCA), "activity_id",
            ),
            evidencia_ufpas=_contagem(Activity.ufpas_participantes.through.objects.all(), "activity_id"),
            evidencia_membros=_contagem(Activity.membros_participantes.through.objects.all(), "activity_id"),
        )
        .order_by("-demanda__atualizado_em", "-pk")
    )


# ---------------------------------------------------------------------------
# Comparativo entre versões
# ---------------------------------------------------------------------------

def _consolidado(itens: list[AcaoDaVersao]) -> dict:
    datas_inicio = [i.planejado.data_inicio for i in itens]
    datas_fim = [i.planejado.data_fim for i in itens]
    return {
        "quantidade_planejada": sum((i.planejado.quantidade for i in itens), ZERO),
        "valor_planejado": arredondar(sum((i.planejado.valor for i in itens), ZERO)),
        "data_inicio": min(datas_inicio) if datas_inicio else None,
        "data_fim": max(datas_fim) if datas_fim else None,
    }


def _comparar(elemento: str, chave, nome: str, antes: list, depois: list) -> dict | None:
    a, d = (_consolidado(antes) if antes else None), (_consolidado(depois) if depois else None)
    if a == d:
        return None
    situacao = "incluida" if a is None else "removida" if d is None else "alterada"
    campos = [] if a is None or d is None else [c for c in a if a[c] != d[c]]
    return {"elemento": elemento, "chave": str(chave), "nome": nome, "situacao": situacao,
            "campos_alterados": campos, "antes": a, "depois": d}


def comparar_versoes(de: TEDVersion, para: TEDVersion) -> list[dict]:
    """O que mudou de uma versão para a outra em quantidade, valor e prazo, por Meta,
    Submeta e Ação. Só aparecem as entidades que mudaram."""
    plano_de, plano_para = plano_da_versao(de), plano_da_versao(para)
    elementos = (
        ("meta", lambda i: i.meta_numero, lambda i: f"Meta {i.meta_numero} — {i.meta_titulo}"),
        ("submeta", lambda i: i.submeta_numero, lambda i: f"{i.submeta_numero} — {i.submeta_titulo}"),
        ("acao", lambda i: i.numero, lambda i: f"{i.numero} — {i.descricao}"),
    )
    diferencas = []
    for elemento, chave_de, nome_de in elementos:
        grupos: dict = {}
        for lado, plano in ((0, plano_de), (1, plano_para)):
            for item in plano.values():
                grupo = grupos.setdefault(chave_de(item), [nome_de(item), [], []])
                grupo[1 + lado].append(item)
                if lado:
                    grupo[0] = nome_de(item)
        for chave in sorted(grupos, key=str):
            nome, antes, depois = grupos[chave]
            diferenca = _comparar(elemento, chave, nome, antes, depois)
            if diferenca:
                diferencas.append(diferenca)
    return diferencas
