import django_filters
from django.db.models import Q

from apps.core.models.user import User
from apps.core.models.user_profile import UserProfile
from apps.sgd.models.demand import STATUS_CHOICES, Demand
from apps.sgd.models.demand_request import TIPO_CHOICES


def _q_etapa_atual_do_usuario(user: User) -> Q:
    """Demandas em que `user` é um dos responsáveis pela etapa atual — o mesmo
    mapa status → responsáveis de `approval.responsaveis_pela_etapa_atual`,
    invertido para virar filtro de queryset (uma única query de perfis, em vez
    de resolver os responsáveis demanda a demanda)."""
    if not user.ativo:
        return Q(pk__in=[])

    q = Q(status__in=["rascunho", "devolvida"], solicitante=user)
    perfis = list(UserProfile.objects.filter(user=user).select_related("territorio", "perfil"))
    slugs = {p.perfil.slug for p in perfis}

    if "articulador-estadual" in slugs:
        # Perfil sem território = alcance global (mesma regra de
        # notifications.usuarios_articuladores_do_estado).
        if any(p.territorio_id is None for p in perfis if p.perfil.slug == "articulador-estadual"):
            q |= Q(status="submetida")
        else:
            siglas = {
                sigla
                for p in perfis if p.perfil.slug == "articulador-estadual"
                for sigla in (p.territorio.estados or [])
            }
            q |= Q(status="submetida", activity__municipio__state__sigla__in=siglas)
    if "ugp" in slugs:
        q |= Q(status="pre_autorizada")
    if "fgd" in slugs:
        q |= Q(status__in=["autorizada", "em_atendimento"])
    return q


class DemandFilter(django_filters.FilterSet):
    """Filtros combináveis da consulta de demandas (SGD-RF26). Todos se somam
    com AND; `tipo` e `rubrica` olham as solicitações da demanda."""

    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES)
    tipo = django_filters.ChoiceFilter(field_name="solicitacoes__tipo", choices=TIPO_CHOICES)
    rubrica = django_filters.CharFilter(field_name="solicitacoes__rubrica__slug")
    solicitante = django_filters.NumberFilter(field_name="solicitante_id")
    atividade = django_filters.NumberFilter(field_name="activity_id")
    acao = django_filters.NumberFilter(field_name="activity__acao_id")
    submeta = django_filters.NumberFilter(field_name="activity__acao__submeta_id")
    meta = django_filters.NumberFilter(field_name="activity__acao__meta_id")
    territorio = django_filters.NumberFilter(field_name="activity__municipio__territory_id")
    periodo_inicio = django_filters.DateFilter(field_name="criado_em", lookup_expr="date__gte")
    periodo_fim = django_filters.DateFilter(field_name="criado_em", lookup_expr="date__lte")
    responsavel_etapa_atual = django_filters.NumberFilter(method="filtrar_responsavel_etapa_atual")

    class Meta:
        model = Demand
        fields: list[str] = []

    def filtrar_responsavel_etapa_atual(self, queryset, name, value):
        user = User.objects.filter(pk=int(value)).first()
        if user is None:
            return queryset.none()
        return queryset.filter(_q_etapa_atual_do_usuario(user))
