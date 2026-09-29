import logging

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from apps.core.permissions import IsAuthenticatedActiveAccess
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import sentry_sdk

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsSuperAdmin, IsUGP
from apps.core.authentication import PowerBIServiceTokenAuthentication
from apps.core.throttling import PowerBIServiceTokenThrottle
from apps.core.services.permissions import user_has_role
from apps.sgp.filters_workplan import (
    IndicatorFilter,
    WorkPlanAcaoFilter,
    WorkPlanMetaFilter,
    WorkPlanSubmetaFilter,
)
from apps.sgp.models import ExportJob, Indicator, WorkPlanAcao, WorkPlanMeta, WorkPlanSubmeta
from apps.sgp.pagination import UPFPagination
from apps.sgp.serializers_workplan import (
    IndicatorSerializer,
    WorkPlanAcaoListSerializer,
    WorkPlanAcaoSerializer,
    WorkPlanDashboardAcaoSerializer,
    WorkPlanDashboardMetaSerializer,
    WorkPlanDashboardNodeSerializer,
    WorkPlanDashboardQuerySerializer,
    WorkPlanDashboardSubmetaSerializer,
    WorkPlanMetaDetailSerializer,
    WorkPlanMetaListSerializer,
    WorkPlanSubmetaDetailSerializer,
    WorkPlanSubmetaSerializer,
    VisaoPorIndicadorRespostaSerializer,
    WorkPlanVisaoIndicadorQuerySerializer,
)
from apps.sgp.cache import get_power_bi_snapshot
from apps.sgp.services import workplan_cadastro
from apps.sgp.services.exportacao import exportar_sincrono
from apps.sgp.views.exportacao import arquivo_response
from apps.sgp.services.workplan_access import (
    escopo_de_leitura_do_plano,
    filter_workplan_actions_for_user,
    filter_workplan_metas_for_user,
    filter_workplan_submetas_for_user,
)
from apps.sgp.tasks import refresh_power_bi_snapshot
from apps.sgp.services.workplan_dashboard import (
    apply_dashboard_filters,
    dashboard_actions_for_user,
    dashboard_tree,
    enrich_dashboard_action,
)
from apps.sgp.services import budget as budget_service
from apps.sgp.services.budget import limiares_semaforo
from apps.sgp.services.apuracao import RecorteAtividades
from apps.sgp.services.visao_indicador import visao_por_indicador
from apps.sgp.serializers_budget import BudgetRubricaOrcamentoSerializer

logger = logging.getLogger("apps.sgp.views.workplan")


class WorkPlanExportView(APIView):
    """Exporta o Plano de Trabalho no escopo territorial do usuário autenticado."""

    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        arquivo = exportar_sincrono(
            ExportJob.Tipo.PLANO_TRABALHO, user=request.user, params=request.query_params.dict()
        )
        return arquivo_response(arquivo)


class WorkPlanVisaoIndicadorView(APIView):
    """GET /api/v1/sgp/plano-trabalho/indicadores/ — consolidação por Indicador
    entre Ações de Metas e Submetas diferentes, no escopo do usuário."""

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        parameters=[WorkPlanVisaoIndicadorQuerySerializer],
        responses=VisaoPorIndicadorRespostaSerializer,
    )
    def get(self, request):
        query_serializer = WorkPlanVisaoIndicadorQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        dados = query_serializer.validated_data
        grupos = visao_por_indicador(
            request.user,
            recorte=RecorteAtividades(
                territorio_id=dados.get("territorio_id"),
                periodo_inicio=dados.get("periodo_inicio"),
                periodo_fim=dados.get("periodo_fim"),
            ),
            meta_id=dados.get("meta_id"),
            indicador_id=dados.get("indicador_id"),
            granularidade=dados["granularidade"],
        )
        return Response(VisaoPorIndicadorRespostaSerializer(
            {"granularidade": dados["granularidade"], "indicadores": grupos}
        ).data)


class WorkPlanPowerBIView(APIView):
    """Fornece o último snapshot consolidado ao conector Power BI."""

    authentication_classes = [PowerBIServiceTokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [PowerBIServiceTokenThrottle]

    def get(self, request):
        snapshot = get_power_bi_snapshot()
        if snapshot is None:
            # Após um flush do Redis, a primeira chamada recompõe o snapshot.
            snapshot = refresh_power_bi_snapshot()
        return Response(snapshot)


class WorkPlanDashboardView(APIView):
    """GET /api/v1/sgp/plano-trabalho/painel/ com indicadores e semáforo das Ações."""

    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        query_serializer = WorkPlanDashboardQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        try:
            actions = dashboard_actions_for_user(request.user)
            actions = apply_dashboard_filters(actions, **{
                key: value
                for key, value in query_serializer.validated_data.items()
                if key in {"meta_id", "territorio_id"}
            })
            limiares = limiares_semaforo()
            actions = [enrich_dashboard_action(action, limiares=limiares) for action in actions]

            status_execucao = query_serializer.validated_data.get("status_execucao")
            if status_execucao:
                actions = [
                    action for action in actions
                    if action.dashboard_status_execucao == status_execucao
                ]

            return Response({
                "metas": [
                    {
                        "meta": WorkPlanDashboardMetaSerializer(grupo["meta"]).data,
                        "resumo": grupo["resumo"],
                        "consolidado": WorkPlanDashboardNodeSerializer(grupo["consolidado"]).data,
                        "submetas": [
                            {
                                "submeta": WorkPlanDashboardSubmetaSerializer(no["submeta"]).data,
                                "consolidado": WorkPlanDashboardNodeSerializer(no["consolidado"]).data,
                                "acoes": no["acoes"],
                            }
                            for no in grupo["submetas"]
                        ],
                        "acoes": WorkPlanDashboardAcaoSerializer(
                            grupo["acoes"], many=True
                        ).data,
                    }
                    for grupo in dashboard_tree(actions, limiares)
                ],
            })
        except PermissionDenied:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.exception("Falha ao gerar painel do Plano de Trabalho.")
            return Response(
                {"detail": "Não foi possível gerar o painel do Plano de Trabalho."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# WorkPlanMeta ViewSet
# ---------------------------------------------------------------------------

class WorkPlanMetaViewSet(viewsets.ModelViewSet):
    pagination_class = UPFPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = WorkPlanMetaFilter
    ordering_fields = ["numero", "criado_em"]
    ordering = ["numero"]
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return WorkPlanMetaListSerializer
        return WorkPlanMetaDetailSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]

    def get_queryset(self):
        qs = WorkPlanMeta.objects.all()
        if self.action in ("list", "retrieve"):
            # Totais e status da Meta somam as Submetas e as Ações delas.
            submetas = WorkPlanSubmeta.objects.all()
            if self.action == "retrieve":
                # O detalhe serializa cada Submeta, com quem a criou.
                submetas = submetas.select_related("criado_por")
            qs = qs.select_related("criado_por").prefetch_related(
                Prefetch("submetas", queryset=submetas), "submetas__acoes"
            )

        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        return filter_workplan_metas_for_user(qs, user)

    @extend_schema(responses=BudgetRubricaOrcamentoSerializer(many=True))
    def orcamento(self, request, pk=None):
        """Sem `@action`: exposta só via `path()` manual em urls.py, pra não
        duplicar rota pelo router (metas já é registrado nele).

        get_object_or_404 direto, não self.get_object() — get_queryset()
        filtra por visibilidade de Atividade, uma política diferente da de
        orçamento.
        """
        meta = get_object_or_404(WorkPlanMeta, pk=pk)
        dados = budget_service.orcamento_por_meta(meta, request.user)
        return Response(BudgetRubricaOrcamentoSerializer(dados, many=True).data)

    def perform_create(self, serializer):
        instance = serializer.save(criado_por=self.request.user)
        AuditLog.objects.create(
            user=self.request.user,
            acao="WorkPlanMeta.create",
            modulo="sgp",
            entidade="WorkPlanMeta",
            entidade_id=str(instance.pk),
            valores_novos={
                "numero": instance.numero,
                "titulo": instance.titulo,
                "data_inicio": str(instance.data_inicio),
                "data_fim": str(instance.data_fim),
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            "numero": old.numero,
            "titulo": old.titulo,
            "descricao": old.descricao,
            "ods_ids": old.ods_ids,
            "data_inicio": str(old.data_inicio),
            "data_fim": str(old.data_fim),
        }
        instance = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            acao="WorkPlanMeta.update",
            modulo="sgp",
            entidade="WorkPlanMeta",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores,
            valores_novos={
                "numero": instance.numero,
                "titulo": instance.titulo,
                "descricao": instance.descricao,
                "ods_ids": instance.ods_ids,
                "data_inicio": str(instance.data_inicio),
                "data_fim": str(instance.data_fim),
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.acoes.exists():
            return Response(
                {
                    "detail": (
                        "Não é possível excluir esta Meta: "
                        "existem Ações vinculadas a ela."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        AuditLog.objects.create(
            user=request.user,
            acao="WorkPlanMeta.delete",
            modulo="sgp",
            entidade="WorkPlanMeta",
            entidade_id=str(instance.pk),
            valores_anteriores={
                "numero": instance.numero,
                "titulo": instance.titulo,
            },
            valores_novos={},
            ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# WorkPlanAcao ViewSet
# ---------------------------------------------------------------------------

class WorkPlanAcaoViewSet(viewsets.ModelViewSet):
    pagination_class = UPFPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = WorkPlanAcaoFilter
    ordering_fields = ["numero", "criado_em"]
    ordering = ["numero"]
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return WorkPlanAcaoListSerializer
        return WorkPlanAcaoSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]

    def get_queryset(self):
        qs = WorkPlanAcao.objects.select_related("meta", "submeta", "indicador").prefetch_related(
            "rubricas_previstas"
        )

        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        return filter_workplan_actions_for_user(qs, user)

    def perform_create(self, serializer):
        workplan_cadastro.criar_acao(serializer, request=self.request)

    def perform_update(self, serializer):
        workplan_cadastro.atualizar_acao(serializer, request=self.request)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            has_atividades = instance.atividades.exists()
        except Exception:
            has_atividades = False
        if has_atividades:
            return Response(
                {
                    "detail": (
                        "Não é possível excluir esta Ação: "
                        "existem Atividades de Campo vinculadas a ela."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        AuditLog.objects.create(
            user=request.user,
            acao="WorkPlanAcao.delete",
            modulo="sgp",
            entidade="WorkPlanAcao",
            entidade_id=str(instance.pk),
            valores_anteriores={
                "numero": instance.numero,
                "descricao": instance.descricao,
            },
            valores_novos={},
            ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# WorkPlanSubmeta ViewSet
# ---------------------------------------------------------------------------

class WorkPlanSubmetaViewSet(viewsets.ModelViewSet):
    pagination_class = UPFPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = WorkPlanSubmetaFilter
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WorkPlanSubmetaDetailSerializer
        return WorkPlanSubmetaSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]

    def get_queryset(self):
        qs = WorkPlanSubmeta.objects.select_related("meta", "responsavel").prefetch_related(
            "acoes"
        )

        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        return filter_workplan_submetas_for_user(qs, user)

    def perform_create(self, serializer):
        workplan_cadastro.criar_submeta(serializer, request=self.request)

    def perform_update(self, serializer):
        workplan_cadastro.atualizar_submeta(serializer, request=self.request)

    def perform_destroy(self, instance):
        workplan_cadastro.excluir_submeta(instance, request=self.request)


# ---------------------------------------------------------------------------
# Indicator ViewSet
# ---------------------------------------------------------------------------

class IndicatorViewSet(viewsets.ModelViewSet):
    """Catálogo institucional de Indicadores (SGP §5.4). Não tem escopo
    territorial: é lido por todo perfil que lê o Plano de Trabalho (matriz de
    permissões do Core §2.1); o Agricultor não lê."""

    serializer_class = IndicatorSerializer
    pagination_class = UPFPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = IndicatorFilter
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess()]

    def get_queryset(self):
        qs = Indicator.objects.all()

        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        # O catálogo não tem recorte territorial: só a checagem de quem lê o PT (403).
        escopo_de_leitura_do_plano(user)
        return qs

    def perform_create(self, serializer):
        workplan_cadastro.criar_indicador(serializer, request=self.request)

    def perform_update(self, serializer):
        workplan_cadastro.atualizar_indicador(serializer, request=self.request)

    def perform_destroy(self, instance):
        workplan_cadastro.excluir_indicador(instance, request=self.request)
