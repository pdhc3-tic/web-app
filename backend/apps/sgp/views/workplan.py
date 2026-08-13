import logging

from django.db.models import F, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from apps.core.permissions import IsAuthenticatedActiveAccess
from rest_framework.response import Response
import sentry_sdk

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsSuperAdmin, IsUGP
from apps.core.services.permissions import user_has_role
from apps.sgp.filters_workplan import WorkPlanAcaoFilter, WorkPlanMetaFilter
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta
from apps.sgp.pagination import UPFPagination
from apps.sgp.serializers_workplan import (
    WorkPlanAcaoListSerializer,
    WorkPlanAcaoSerializer,
    WorkPlanMetaDetailSerializer,
    WorkPlanMetaListSerializer,
    WorkPlanDashboardAcaoSerializer,
    WorkPlanDashboardQuerySerializer,
)
from apps.sgp.services.workplan_dashboard import (
    apply_dashboard_filters,
    dashboard_actions_for_user,
    enrich_dashboard_action,
)

logger = logging.getLogger("apps.sgp.views.workplan")


class WorkPlanDashboardView(APIView):
    """GET /api/v1/sgp/plano-trabalho/painel/ com indicadores e semáforo das Ações."""

    permission_classes = [IsAuthenticated]

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
            actions = [enrich_dashboard_action(action) for action in actions]

            status_execucao = query_serializer.validated_data.get("status_execucao")
            if status_execucao:
                actions = [
                    action for action in actions
                    if action.dashboard_status_execucao == status_execucao
                ]

            resumo = {"total_acoes": len(actions), "verde": 0, "amarelo": 0, "vermelho": 0}
            for action in actions:
                resumo[action.dashboard_semaforo] += 1

            return Response({
                "resumo": resumo,
                "acoes": WorkPlanDashboardAcaoSerializer(actions, many=True).data,
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
        qs = WorkPlanMeta.objects.annotate(
            _valor_total=Sum(F("acoes__quantidade_planejada") * F("acoes__valor_unitario"))
        ).all()

        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            return qs

        if user_has_role(user, "articulador-estadual"):
            from apps.core.services.permissions import user_states
            states = user_states(user)
            if not states:
                return qs.none()
            return qs

        if user_has_role(user, "adt-acr"):
            from apps.core.services.permissions import user_territories
            territories = user_territories(user)
            if not territories.exists():
                return qs.none()
            return qs

        return qs

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
        qs = WorkPlanAcao.objects.select_related("meta").all()

        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            return qs

        if user_has_role(user, "articulador-estadual"):
            from apps.core.services.permissions import user_states
            states = user_states(user)
            if not states:
                return qs.none()
            return qs

        if user_has_role(user, "adt-acr"):
            from apps.core.services.permissions import user_territories
            territories = user_territories(user)
            if not territories.exists():
                return qs.none()
            return qs

        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            acao="WorkPlanAcao.create",
            modulo="sgp",
            entidade="WorkPlanAcao",
            entidade_id=str(instance.pk),
            valores_novos={
                "meta_id": instance.meta_id,
                "numero": instance.numero,
                "descricao": instance.descricao,
                "quantidade_planejada": str(instance.quantidade_planejada),
                "valor_unitario": str(instance.valor_unitario),
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            "meta_id": old.meta_id,
            "numero": old.numero,
            "descricao": old.descricao,
            "tipo_unidade": old.tipo_unidade,
            "quantidade_planejada": str(old.quantidade_planejada),
            "valor_unitario": str(old.valor_unitario),
        }
        instance = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            acao="WorkPlanAcao.update",
            modulo="sgp",
            entidade="WorkPlanAcao",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores,
            valores_novos={
                "meta_id": instance.meta_id,
                "numero": instance.numero,
                "descricao": instance.descricao,
                "tipo_unidade": instance.tipo_unidade,
                "quantidade_planejada": str(instance.quantidade_planejada),
                "valor_unitario": str(instance.valor_unitario),
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

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
