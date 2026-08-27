import logging
import csv
from io import BytesIO, StringIO

from django.db.models import F, Sum
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
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
from apps.sgp.filters_workplan import WorkPlanAcaoFilter, WorkPlanMetaFilter
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta
from apps.sgp.pagination import UPFPagination
from apps.sgp.serializers_workplan import (
    WorkPlanAcaoListSerializer,
    WorkPlanAcaoSerializer,
    WorkPlanMetaDetailSerializer,
    WorkPlanMetaListSerializer,
    WorkPlanDashboardAcaoSerializer,
    WorkPlanDashboardMetaSerializer,
    WorkPlanDashboardQuerySerializer,
    WorkPlanExportQuerySerializer,
)
from apps.sgp.cache import get_power_bi_snapshot
from apps.sgp.services.workplan_export import EXPORT_COLUMNS, workplan_export_rows
from apps.sgp.services.workplan_access import (
    filter_workplan_actions_for_user,
    filter_workplan_metas_for_user,
)
from apps.sgp.tasks import refresh_power_bi_snapshot
from apps.sgp.services.workplan_dashboard import (
    apply_dashboard_filters,
    dashboard_actions_for_user,
    enrich_dashboard_action,
)

logger = logging.getLogger("apps.sgp.views.workplan")


class WorkPlanExportView(APIView):
    """Exporta o Plano de Trabalho no escopo territorial do usuário autenticado."""

    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        query_serializer = WorkPlanExportQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        options = query_serializer.validated_data
        formato = options.pop("formato")
        rows = workplan_export_rows(user=request.user, **options)
        timestamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"plano_trabalho_{timestamp}.{formato}"

        if formato == "csv":
            return self._csv_response(rows, filename)
        return self._xlsx_response(rows, filename)

    @staticmethod
    def _csv_response(rows, filename):
        content = StringIO()
        writer = csv.writer(content)
        writer.writerow([label for _, label in EXPORT_COLUMNS])
        for row in rows:
            writer.writerow([row[key] for key, _ in EXPORT_COLUMNS])
        response = HttpResponse(
            "\ufeff" + content.getvalue(),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @staticmethod
    def _xlsx_response(rows, filename):
        from openpyxl import Workbook

        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet("Plano de Trabalho")
        worksheet.append([label for _, label in EXPORT_COLUMNS])
        for row in rows:
            worksheet.append([row[key] for key, _ in EXPORT_COLUMNS])
        content = BytesIO()
        workbook.save(content)
        response = HttpResponse(
            content.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


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
            actions = [enrich_dashboard_action(action) for action in actions]

            status_execucao = query_serializer.validated_data.get("status_execucao")
            if status_execucao:
                actions = [
                    action for action in actions
                    if action.dashboard_status_execucao == status_execucao
                ]

            metas = {}
            for action in actions:
                grupo = metas.setdefault(action.meta_id, {
                    "meta": action.meta,
                    "resumo": {
                        "total_acoes": 0,
                        "verde": 0,
                        "amarelo": 0,
                        "vermelho": 0,
                    },
                    "acoes": [],
                })
                grupo["resumo"]["total_acoes"] += 1
                grupo["resumo"][action.dashboard_semaforo] += 1
                grupo["acoes"].append(action)

            return Response({
                "metas": [
                    {
                        "meta": WorkPlanDashboardMetaSerializer(grupo["meta"]).data,
                        "resumo": grupo["resumo"],
                        "acoes": WorkPlanDashboardAcaoSerializer(
                            grupo["acoes"], many=True
                        ).data,
                    }
                    for grupo in metas.values()
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
        qs = WorkPlanMeta.objects.annotate(
            _valor_total=Sum(F("acoes__quantidade_planejada") * F("acoes__valor_unitario"))
        ).all()

        user = self.request.user
        if not user.is_authenticated:
            return qs.none()

        return filter_workplan_metas_for_user(qs, user)

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

        return filter_workplan_actions_for_user(qs, user)

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
