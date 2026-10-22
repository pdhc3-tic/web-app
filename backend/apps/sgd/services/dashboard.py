"""Painel consolidado do SGD (Issue 315 / SGD-BE-11) — a visão "home".

Tudo parte de `demand_visibility_scope` (mesmo recorte do RBAC/RLS de
`sgd_demand`); nada aqui abre o universo de demandas por conta própria.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.core.models.user_profile import UserProfile
from apps.core.services.permissions import user_role_slugs, user_states
from apps.sgd.models.demand import STATUS_CHOICES, STATUS_TERMINAIS, Demand
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.services import business_days
from apps.sgd.services.approval import demand_visibility_scope, demandas_aguardando_acao
from apps.sgp.models.budget import BudgetAllocation
from apps.sgp.services import budget as budget_service

ZERO = Decimal("0")
LIMITE_FILA = 50
LIMITE_SEM_MOVIMENTACAO = 50

# Status que cada perfil acompanha nos contadores. Perfis sem entrada aqui
# (super-admin, ADT/ACR) veem todos os status.
STATUS_RELEVANTES_POR_PERFIL = {
    "articulador-estadual": ("submetida", "devolvida", "pre_autorizada"),
    "ugp": ("pre_autorizada", "autorizada", "recusada"),
    "fgd": ("autorizada", "em_atendimento", "concluida"),
}
TODOS_OS_STATUS = tuple(valor for valor, _ in STATUS_CHOICES)
ROTULOS_STATUS = dict(STATUS_CHOICES)

PERFIS_NACIONAIS = {"super-admin", "ugp", "fgd"}


def _demandas_do_escopo(user):
    """Subquery por `pk__in` em vez de `.distinct()`: o escopo do Articulador
    junta `etapas`, e um join duplicaria linhas em qualquer `Sum`/`Count`."""
    scope = demand_visibility_scope(user)
    if scope is None:
        return Demand.objects.all()
    return Demand.objects.filter(pk__in=Demand.objects.filter(scope).values("pk"))


def _valor_estimado_subquery():
    return Coalesce(
        Subquery(
            DemandRequest.objects.filter(demanda=OuterRef("pk"))
            .order_by()
            .values("demanda")
            .annotate(total=Sum("valor_estimado"))
            .values("total")[:1],
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
        ZERO,
    )


def fila_aguardando_acao(user, base_qs, *, limite: int = LIMITE_FILA) -> dict:
    """Mais antiga primeiro; em empate (mesmo dia de espera), maior valor
    primeiro. O empate é por dia — comparar o timestamp exato nunca empataria."""
    qs = (
        demandas_aguardando_acao(user, base_qs)
        .annotate(valor_estimado=_valor_estimado_subquery(), dia_da_espera=TruncDate("status_alterado_em"))
        .select_related("activity__municipio__state", "activity__municipio__territory")
        .order_by("dia_da_espera", "-valor_estimado", "status_alterado_em", "pk")
    )
    total = qs.count()
    hoje = timezone.localdate()
    itens = []
    for demanda in qs[:limite]:
        municipio = demanda.activity.municipio
        itens.append({
            "id": demanda.pk,
            "titulo": demanda.titulo,
            "status": demanda.status,
            "status_alterado_em": demanda.status_alterado_em,
            "dias_em_espera": (hoje - timezone.localdate(demanda.status_alterado_em)).days,
            "valor_estimado": demanda.valor_estimado,
            "atividade_id": demanda.activity_id,
            "atividade_titulo": demanda.activity.titulo,
            "estado": municipio.state.sigla,
            "territorio": municipio.territory.nome if municipio.territory else None,
        })
    return {"total": total, "itens": itens}


def contagem_por_status(user, base_qs) -> list[dict]:
    slugs = user_role_slugs(user, tuple(STATUS_RELEVANTES_POR_PERFIL))
    relevantes = (
        {s for slug in slugs for s in STATUS_RELEVANTES_POR_PERFIL[slug]} if slugs else set(TODOS_OS_STATUS)
    )
    contagens = {
        linha["status"]: linha["total"]
        for linha in base_qs.filter(status__in=relevantes).values("status").annotate(total=Count("pk"))
    }
    return [
        {"status": status, "rotulo": ROTULOS_STATUS[status], "total": contagens.get(status, 0)}
        for status in TODOS_OS_STATUS if status in relevantes
    ]


def _territorios_do_adt(user) -> list[int]:
    """Todos os territórios dos perfis `adt-acr` do usuário. Perfil sem
    território é ignorado — nunca vira acesso global (mesma regra de
    `budget._territorios_do_adt`)."""
    return sorted(set(
        UserProfile.objects.filter(
            user=user, perfil__slug="adt-acr", territorio__isnull=False,
        ).values_list("territorio_id", flat=True)
    ))


def _linhas_orcamento_do_escopo(user) -> list[tuple[dict, str | None, int | None]]:
    """Matriz meta × rubrica no nível do usuário, como `(linha, estado_sigla,
    territorio_id)` — o local acompanha cada linha, senão linhas iguais de
    estados/territórios diferentes ficam indistinguíveis: nacional
    (UGP/FGD/super-admin), estadual (Articulador, um bloco por estado) ou
    territorial (ADT/ACR, um bloco por território)."""
    slugs = user_role_slugs(user, PERFIS_NACIONAIS | {"articulador-estadual", "adt-acr"})
    if slugs & PERFIS_NACIONAIS:
        return [
            (linha, None, None)
            for linha in budget_service.painel_orcamento(
                nivel=BudgetAllocation.Nivel.NACIONAL, estado_sigla=None, territorio_id=None, meta_id=None,
            )
        ]
    if "articulador-estadual" in slugs:
        return [
            (linha, sigla, None)
            for sigla in sorted(user_states(user))
            for linha in budget_service.painel_orcamento(
                nivel=BudgetAllocation.Nivel.ESTADUAL, estado_sigla=sigla, territorio_id=None, meta_id=None,
            )
        ]
    if "adt-acr" in slugs:
        # `painel_orcamento_para_usuario` resolveria um único território (o
        # primeiro do perfil) e esconderia os alertas dos demais.
        return [
            (linha, None, territorio_id)
            for territorio_id in _territorios_do_adt(user)
            for linha in budget_service.painel_orcamento(
                nivel=BudgetAllocation.Nivel.TERRITORIAL, estado_sigla=None,
                territorio_id=territorio_id, meta_id=None,
            )
        ]
    return []


def alertas_de_saldo(user) -> list[dict]:
    """Células meta × rubrica em faixa amarela/vermelha; vermelho primeiro."""
    alertas = []
    for linha, estado_sigla, territorio_id in _linhas_orcamento_do_escopo(user):
        if linha["semaforo"] not in {"amarelo", "vermelho"}:
            continue
        alertas.append({
            "meta_id": linha["meta"].pk,
            "meta_numero": linha["meta"].numero,
            "rubrica_id": linha["rubrica"].pk,
            "rubrica_slug": linha["rubrica"].slug,
            "rubrica_nome": linha["rubrica"].nome,
            "nivel": linha["nivel"],
            "estado_sigla": estado_sigla,
            "territorio_id": territorio_id,
            "faixa": linha["semaforo"],
            "percentual_comprometido": budget_service.percentual_comprometido(
                linha["valor_comprometido"], linha["valor_aprovado"],
            ),
            "valor_aprovado": linha["valor_aprovado"],
            "valor_comprometido": linha["valor_comprometido"],
            "saldo_disponivel": linha["saldo_disponivel"],
        })
    ordem_faixa = {"vermelho": 0, "amarelo": 1}
    alertas.sort(key=lambda a: (
        ordem_faixa[a["faixa"]], -a["percentual_comprometido"], a["rubrica_nome"],
        a["estado_sigla"] or "", a["territorio_id"] or 0,
    ))
    return alertas


def sem_movimentacao(user, base_qs, *, limite: int = LIMITE_SEM_MOVIMENTACAO) -> dict:
    """Demandas sob responsabilidade do usuário paradas há `DIAS_UTEIS_LIMITE`
    dias úteis ou mais. Responsável = quem aguarda a ação (aprovadores) ou o
    solicitante de uma demanda devolvida — o mesmo critério de
    `responsaveis_pela_etapa_atual`.

    O corte em dias corridos no SQL é seguro: dias úteis nunca passam dos dias
    corridos, então nada que atenda ao critério fica de fora."""
    hoje = timezone.localdate()
    corte = timezone.now() - timedelta(days=business_days.DIAS_UTEIS_LIMITE)
    qs = base_qs.exclude(status__in=STATUS_TERMINAIS | {"rascunho"}).filter(status_alterado_em__lte=corte)
    sob_responsabilidade = demandas_aguardando_acao(user, qs) | qs.filter(solicitante=user, status="devolvida")
    candidatas = list(
        sob_responsabilidade.select_related("activity__municipio__state").order_by("status_alterado_em", "pk")
    )

    calendarios: dict[str | None, object] = {}
    paradas = []
    if candidatas:
        mais_antiga = min(timezone.localdate(d.status_alterado_em) for d in candidatas)
        for demanda in candidatas:
            uf = demanda.activity.municipio.state.sigla
            if uf not in calendarios:
                calendarios[uf] = business_days.feriados(uf, mais_antiga, hoje)
            referencia = timezone.localdate(demanda.status_alterado_em)
            dias = business_days.dias_uteis_entre(referencia, hoje, feriados_do_periodo=calendarios[uf])
            if dias < business_days.DIAS_UTEIS_LIMITE:
                continue
            paradas.append({
                "id": demanda.pk,
                "titulo": demanda.titulo,
                "status": demanda.status,
                "status_alterado_em": demanda.status_alterado_em,
                "dias_uteis_parada": dias,
                "estado": uf,
            })
    paradas.sort(key=lambda p: (-p["dias_uteis_parada"], p["id"]))
    return {"total": len(paradas), "itens": paradas[:limite]}


def montar_dashboard(user) -> dict:
    base_qs = _demandas_do_escopo(user)
    return {
        "perfis": sorted(user_role_slugs(user)),
        "fila_aguardando_acao": fila_aguardando_acao(user, base_qs),
        "contagem_por_status": contagem_por_status(user, base_qs),
        "alertas_saldo": alertas_de_saldo(user),
        "sem_movimentacao": sem_movimentacao(user, base_qs),
    }
