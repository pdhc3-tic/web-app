"""Consulta, painéis e relatórios do SGD (SGD-RF26 a RF30).

Tudo aqui parte do queryset já restrito pelo RBAC (`demand_visibility_scope`,
aplicado pelo `DemandViewSet.get_queryset`) — nenhuma função abre o universo
de demandas por conta própria.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.services.permissions import user_role_slugs
from apps.sgd.filters import DemandFilter
from apps.sgd.models.demand_request import DemandRequest
from apps.sgp.models.budget import BudgetAllocation, BudgetRubrica
from apps.sgp.services import budget as budget_service

ZERO = Decimal("0")

# Status em que a demanda representa recurso pedido / autorizado. Rascunho e
# devolvida ainda não foram decididas; recusada e cancelada não consomem nada.
STATUS_SOLICITADO = {"submetida", "pre_autorizada", "autorizada", "em_atendimento", "concluida"}
STATUS_AUTORIZADO = {"autorizada", "em_atendimento", "concluida"}
STATUS_COM_CUSTO = STATUS_SOLICITADO

PERFIS_DE_GESTAO = {"super-admin", "ugp", "fgd", "articulador-estadual"}


def filtrar_demandas(queryset, params):
    """Aplica `DemandFilter`; valor inválido vira 400 em vez de filtro ignorado
    (uma exportação "filtrada" que devolve tudo seria pior que um erro)."""
    filterset = DemandFilter(data=params, queryset=queryset)
    if not filterset.is_valid():
        raise ValidationError(filterset.errors.get_json_data())
    return filterset.qs


def exigir_perfil_de_gestao(user) -> set[str]:
    slugs = user_role_slugs(user, PERFIS_DE_GESTAO)
    if not slugs:
        raise PermissionDenied("Disponível apenas para perfis de gestão do SGD.")
    return slugs


def _inteiro_ou_none(valor):
    if valor in (None, ""):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValidationError({"detail": f"Valor numérico inválido: {valor!r}."})


def _painel_sgp(user, slugs: set[str], *, estado_sigla, territorio_id, meta_id):
    # FGD não tem nível próprio no `resolver_nivel_painel` do SGP; para o
    # painel do SGD enxerga o nacional, como a UGP.
    if "fgd" in slugs and not slugs & {"super-admin", "ugp", "articulador-estadual"}:
        nivel = BudgetAllocation.Nivel.NACIONAL
        if territorio_id is not None:
            nivel = BudgetAllocation.Nivel.TERRITORIAL
        elif estado_sigla is not None:
            nivel = BudgetAllocation.Nivel.ESTADUAL
        return budget_service.painel_orcamento(
            nivel=nivel, estado_sigla=estado_sigla, territorio_id=territorio_id, meta_id=meta_id,
        )
    return budget_service.painel_orcamento_para_usuario(
        user, estado_sigla=estado_sigla, territorio_id=territorio_id, meta_id=meta_id,
    )


def painel_por_rubrica(user, demandas, params) -> list[dict]:
    """Solicitado / autorizado / executado / disponível por rubrica (RF28).

    `solicitado` e `autorizado` saem das solicitações das demandas visíveis e
    filtradas; `executado` e `disponivel` são os do controle financeiro do SGP
    (`painel_orcamento`), somados por rubrica, para o painel nunca divergir
    do orçamento.
    """
    slugs = exigir_perfil_de_gestao(user)
    territorio_id = _inteiro_ou_none(params.get("territorio"))
    meta_id = _inteiro_ou_none(params.get("meta"))
    estado_sigla = params.get("estado") or None

    solicitacoes = (
        DemandRequest.objects.filter(demanda__in=demandas.values("pk"))
        .values("rubrica_id")
        .annotate(
            solicitado=Sum("valor_estimado", filter=Q(demanda__status__in=STATUS_SOLICITADO)),
            autorizado=Sum("valor_autorizado", filter=Q(demanda__status__in=STATUS_AUTORIZADO)),
        )
    )
    por_rubrica = {linha["rubrica_id"]: linha for linha in solicitacoes}

    orcamento: dict[int, dict] = {}
    for linha in _painel_sgp(
        user, slugs, estado_sigla=estado_sigla, territorio_id=territorio_id, meta_id=meta_id,
    ):
        acc = orcamento.setdefault(linha["rubrica"].pk, {"executado": ZERO, "disponivel": ZERO})
        acc["executado"] += linha["valor_executado"]
        acc["disponivel"] += linha["saldo_disponivel"]

    resultado = []
    for rubrica in BudgetRubrica.objects.filter(ativo=True).order_by("ordem"):
        demanda_linha = por_rubrica.get(rubrica.pk, {})
        fin = orcamento.get(rubrica.pk, {})
        resultado.append({
            "rubrica_id": rubrica.pk,
            "rubrica_slug": rubrica.slug,
            "rubrica_nome": rubrica.nome,
            "solicitado": demanda_linha.get("solicitado") or ZERO,
            "autorizado": demanda_linha.get("autorizado") or ZERO,
            "executado": fin.get("executado", ZERO),
            "disponivel": fin.get("disponivel", ZERO),
        })
    return resultado


def custo_por_atividade(user, demandas) -> list[dict]:
    """Custo por atividade, agrupado pela entrega (`WorkPlanAcao`) do Plano de
    Trabalho a que a atividade pertence (RF29). Recusadas, canceladas e
    demandas ainda em edição não entram no custo."""
    exigir_perfil_de_gestao(user)
    linhas = (
        DemandRequest.objects
        .filter(demanda__in=demandas.values("pk"), demanda__status__in=STATUS_COM_CUSTO)
        .values(
            "demanda__activity_id", "demanda__activity__titulo",
            "demanda__activity__acao_id", "demanda__activity__acao__numero",
            "demanda__activity__acao__descricao",
        )
        .annotate(
            demandas=Count("demanda_id", distinct=True),
            estimado=Sum("valor_estimado"),
            autorizado=Sum("valor_autorizado"),
            pago=Sum("valor_pago"),
        )
        .order_by("demanda__activity__acao__numero", "demanda__activity__titulo")
    )

    entregas: OrderedDict[int, dict] = OrderedDict()
    for linha in linhas:
        acao_id = linha["demanda__activity__acao_id"]
        entrega = entregas.setdefault(acao_id, {
            "acao_id": acao_id,
            "acao_numero": linha["demanda__activity__acao__numero"],
            "acao_descricao": linha["demanda__activity__acao__descricao"],
            "atividades": [],
            "demandas": 0, "estimado": ZERO, "autorizado": ZERO, "pago": ZERO,
        })
        atividade = {
            "atividade_id": linha["demanda__activity_id"],
            "atividade_titulo": linha["demanda__activity__titulo"],
            "demandas": linha["demandas"],
            "estimado": linha["estimado"] or ZERO,
            "autorizado": linha["autorizado"] or ZERO,
            "pago": linha["pago"] or ZERO,
        }
        entrega["atividades"].append(atividade)
        for campo in ("demandas", "estimado", "autorizado", "pago"):
            entrega[campo] += atividade[campo]
    return list(entregas.values())


COLUNAS_EXPORTACAO = (
    ("id", "ID"),
    ("titulo", "Título"),
    ("status", "Status"),
    ("solicitante", "Solicitante"),
    ("atividade", "Atividade"),
    ("meta", "Meta"),
    ("submeta", "Submeta"),
    ("acao", "Ação"),
    ("territorio", "Território"),
    ("tipos", "Tipos de solicitação"),
    ("rubricas", "Rubricas"),
    ("valor_estimado", "Valor estimado (R$)"),
    ("valor_autorizado", "Valor autorizado (R$)"),
    ("valor_pago", "Valor pago (R$)"),
    ("criado_em", "Criado em"),
)


def linhas_exportacao(demandas):
    """Uma linha por demanda, com os totais agregados no banco — sem N+1 nem
    carregar as solicitações em memória."""
    qs = (
        demandas.order_by("-criado_em", "-pk")
        .select_related(
            "solicitante", "activity__acao__meta", "activity__acao__submeta",
            "activity__municipio__territory",
        )
        .prefetch_related("solicitacoes__rubrica")
    )
    for demanda in qs.iterator(chunk_size=500):
        solicitacoes = list(demanda.solicitacoes.all())
        acao = demanda.activity.acao
        territorio = demanda.activity.municipio.territory
        yield {
            "id": demanda.pk,
            "titulo": demanda.titulo,
            "status": demanda.get_status_display(),
            "solicitante": demanda.solicitante.nome,
            "atividade": demanda.activity.titulo,
            "meta": f"{acao.meta.numero} — {acao.meta.titulo}",
            "submeta": f"{acao.submeta.numero} — {acao.submeta.titulo}",
            "acao": f"{acao.numero} — {acao.descricao}",
            "territorio": territorio.nome if territorio else "",
            "tipos": "; ".join(sorted({s.get_tipo_display() for s in solicitacoes})),
            "rubricas": "; ".join(sorted({s.rubrica.nome for s in solicitacoes})),
            "valor_estimado": f"{sum((s.valor_estimado for s in solicitacoes), ZERO):.2f}",
            "valor_autorizado": f"{sum((s.valor_autorizado or ZERO for s in solicitacoes), ZERO):.2f}",
            "valor_pago": f"{sum((s.valor_pago or ZERO for s in solicitacoes), ZERO):.2f}",
            "criado_em": demanda.criado_em.strftime("%Y-%m-%d %H:%M"),
        }
