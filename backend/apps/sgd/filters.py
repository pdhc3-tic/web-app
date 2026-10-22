from datetime import datetime, time, timedelta

import django_filters
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field

from apps.core.models.user import User
from apps.core.models.user_profile import UserProfile
from apps.sgd.models.demand import STATUS_CHOICES, Demand
from apps.sgd.models.demand_request import TIPO_CHOICES, DemandRequest
from apps.sgd.services.approval import demandas_aguardando_acao


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

    status = django_filters.MultipleChoiceFilter(choices=STATUS_CHOICES)
    # `Exists` em vez de join: não duplica linhas, então não precisa de `.distinct()`.
    tipo = django_filters.ChoiceFilter(choices=TIPO_CHOICES, method="filtrar_tipo")
    rubrica = django_filters.CharFilter(method="filtrar_rubrica")
    solicitante = django_filters.NumberFilter(field_name="solicitante_id")
    activity = django_filters.NumberFilter(field_name="activity_id")
    atividade = django_filters.NumberFilter(field_name="activity_id")
    acao = django_filters.NumberFilter(field_name="activity__acao_id")
    submeta = django_filters.NumberFilter(field_name="activity__acao__submeta_id")
    meta = django_filters.NumberFilter(field_name="activity__acao__meta_id")
    territorio = django_filters.NumberFilter(field_name="activity__municipio__territory_id")
    periodo_inicio = django_filters.DateFilter(method="filtrar_periodo_inicio")
    periodo_fim = django_filters.DateFilter(method="filtrar_periodo_fim")
    responsavel_etapa_atual = django_filters.NumberFilter(method="filtrar_responsavel_etapa_atual")
    aguardando_minha_acao = django_filters.TypedChoiceFilter(
        choices=[("true", "true"), ("false", "false")],
        coerce=lambda valor: valor == "true",
        method="filtrar_aguardando_minha_acao",
    )

    class Meta:
        model = Demand
        fields: list[str] = []

    @staticmethod
    def _solicitacoes_com(queryset, **filtros):
        return queryset.filter(Exists(DemandRequest.objects.filter(demanda=OuterRef("pk"), **filtros)))

    def filtrar_tipo(self, queryset, name, value):
        return self._solicitacoes_com(queryset, tipo=value)

    def filtrar_rubrica(self, queryset, name, value):
        return self._solicitacoes_com(queryset, rubrica__slug=value)

    # Intervalo de datetimes no fuso corrente (o mesmo do `__date`), para o
    # índice (status, -criado_em) continuar utilizável — `criado_em__date`
    # envolve a coluna numa função.
    def filtrar_periodo_inicio(self, queryset, name, value):
        return queryset.filter(criado_em__gte=timezone.make_aware(datetime.combine(value, time.min)))

    def filtrar_periodo_fim(self, queryset, name, value):
        return queryset.filter(criado_em__lt=timezone.make_aware(datetime.combine(value + timedelta(days=1), time.min)))

    def filtrar_responsavel_etapa_atual(self, queryset, name, value):
        user = User.objects.filter(pk=int(value)).first()
        if user is None:
            return queryset.none()
        return queryset.filter(_q_etapa_atual_do_usuario(user))

    @extend_schema_field(OpenApiTypes.BOOL)
    def filtrar_aguardando_minha_acao(self, queryset, name, value):
        # Mesma função da rota de contagem, para lista e total nunca divergirem.
        if not value:
            return queryset
        return demandas_aguardando_acao(self.request.user, queryset)
