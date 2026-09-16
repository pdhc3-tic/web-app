import logging

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.utils import get_config
from apps.sgp.filters import ActivityFilter
from apps.sgp.models import Activity, ActivityDocument, ActivityPhoto, UPF
from apps.sgp.pagination import ActivityPagination
from apps.sgp.serializers import (
    ActivityCalendarioSerializer,
    ActivityDetailSerializer,
    ActivityListSerializer,
)
from apps.sgp.services.access import scope_queryset
from apps.sgp.tasks import sync_activity_to_google_calendar
from apps.sgp.views.activity_documentos import ActivityDocumentMixin
from apps.sgp.views.activity_foto import ActivityPhotoMixin

logger = logging.getLogger("apps.sgp.views")


class ActivityViewSet(ActivityPhotoMixin, ActivityDocumentMixin, viewsets.ModelViewSet):
    """
    ViewSet de Atividades do SGP.

    GET/POST    /api/v1/sgp/atividades/
    GET/PATCH/PUT/DELETE /api/v1/sgp/atividades/{id}/

    Isolamento territorial (RLS):
        - super-admin / ugp: visualizam tudo
        - articulador-estadual: atividades nos estados do seu escopo
        - adt-acr: atividades nos territórios vinculados
    """
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticatedActiveAccess]
    pagination_class = ActivityPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ActivityFilter
    ordering_fields = ["data_inicio", "data_fim", "criado_em", "titulo"]
    ordering = ["-data_inicio"]

    # Caminho do atributo territorio para _resolve_territorio_id das permissions
    _territorio_attr_path = "territorio_id"

    def get_serializer_class(self):
        if self.action == "list":
            return ActivityListSerializer
        return ActivityDetailSerializer

    def get_queryset(self):
        qs = Activity.objects.select_related(
            "acao", "acao__meta",
            "municipio", "municipio__territory", "municipio__state",
            "comunidade",
            "tecnico_responsavel",
            "criado_por",
        ).prefetch_related(
            "equipe_adicional",
            Prefetch(
                "upfs_participantes",
                queryset=UPF.objects.select_related(
                    "municipio", "municipio__state", "territorio", "titular"
                ),
            ),
            "membros_participantes",
            "parceiros_organizacoes",
            Prefetch(
                "fotos",
                queryset=ActivityPhoto.objects.filter(ativa=True).order_by(
                    "ordem", "criado_em"
                ),
            ),
            Prefetch(
                "documentos",
                queryset=ActivityDocument.objects.filter(ativo=True).order_by(
                    "-criado_em"
                ),
            ),
        ).filter(ativo=True)

        return scope_queryset(
            qs,
            self.request.user,
            state_lookup="municipio__state__sigla__in",
            territory_lookup="municipio__territory__in",
            deny_message="Você não tem acesso ao módulo de Atividades do SGP.",
        )

    def perform_create(self, serializer):
        instance = serializer.save(criado_por=self.request.user, ultima_origem="web")
        self._log_audit("activity.create", instance)
        self._enqueue_google_calendar_sync_if_needed(instance, created=True)

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = self._snapshot(old)
        google_calendar_anteriores = self._google_calendar_sync_snapshot(old)
        instance = serializer.save(ultima_origem="web")
        self._log_audit("activity.update", instance, valores_anteriores)
        self._enqueue_google_calendar_sync_if_needed(
            instance,
            created=False,
            valores_anteriores=google_calendar_anteriores,
        )

    def perform_destroy(self, instance):
        """Soft-delete via ativo=False."""
        valores_anteriores = self._snapshot(instance)
        instance.ativo = False
        instance.save(update_fields=["ativo"])
        self._log_audit("activity.soft_delete", instance, valores_anteriores)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _snapshot(instance) -> dict:
        return {
            "id": instance.pk,
            "titulo": instance.titulo,
            "status": instance.status,
            "tipo_atividade": instance.tipo_atividade,
            "municipio_id": instance.municipio_id,
            "acao_id": instance.acao_id,
            "tecnico_responsavel_id": instance.tecnico_responsavel_id,
            "data_inicio": instance.data_inicio.isoformat(),
            "data_fim": instance.data_fim.isoformat(),
            "ativo": instance.ativo,
        }

    def _log_audit(self, acao: str, instance, valores_anteriores: dict | None = None):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="Activity",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos=self._snapshot(instance),
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @staticmethod
    def _google_calendar_sync_snapshot(instance) -> dict:
        return {
            "status": instance.status,
            "data_inicio": instance.data_inicio.isoformat(),
            "data_fim": instance.data_fim.isoformat(),
            "municipio_id": instance.municipio_id,
            "comunidade_id": instance.comunidade_id,
            "equipe_adicional_ids": sorted(
                instance.equipe_adicional.values_list("pk", flat=True)
            ),
        }

    def _enqueue_google_calendar_sync_if_needed(
        self,
        instance,
        *,
        created: bool,
        valores_anteriores: dict | None = None,
    ):
        if not get_config("google_calendar_integracao_ativa", False):
            return

        valores_novos = self._google_calendar_sync_snapshot(instance)
        if not self._should_sync_google_calendar(
            created,
            valores_anteriores,
            valores_novos,
        ):
            return

        Activity.objects.filter(pk=instance.pk).update(
            google_calendar_sync_status="pendente",
        )
        instance.google_calendar_sync_status = "pendente"
        try:
            sync_activity_to_google_calendar.delay(instance.pk)
        except Exception:
            logger.exception(
                "Falha ao enfileirar sync Google Calendar activity_id=%s.",
                instance.pk,
            )

    @staticmethod
    def _should_sync_google_calendar(
        created: bool,
        valores_anteriores: dict | None,
        valores_novos: dict,
    ) -> bool:
        status_atual = valores_novos["status"]
        if status_atual in {"cancelada", "nao_realizada"}:
            return bool(
                valores_anteriores
                and valores_anteriores["status"] != status_atual
            )

        if status_atual != "agendado":
            return False

        if created or not valores_anteriores:
            return True

        if valores_anteriores["status"] != "agendado":
            return True

        campos_monitorados = [
            "data_inicio",
            "data_fim",
            "municipio_id",
            "comunidade_id",
            "equipe_adicional_ids",
        ]
        return any(
            valores_anteriores[campo] != valores_novos[campo]
            for campo in campos_monitorados
        )

    # ── Endpoint de Calendário ────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="calendario")
    def calendario(self, request):
        """
        GET /api/v1/sgp/atividades/calendario/?inicio=YYYY-MM-DD&fim=YYYY-MM-DD

        Retorna payload reduzido de todas as atividades cujo intervalo
        (data_inicio, data_fim) intersecciona com o período solicitado.
        Máximo de 90 dias entre inicio e fim (retorna 400 se excedido).

        Filtros opcionais via querystring:
            tecnico_id, projeto, acao, tipo_atividade, status
        """
        from datetime import date, datetime, time
        from django.utils import timezone
        from rest_framework.fields import DateField as DRFDateField

        # ── Validação dos parâmetros de intervalo ───────────────────────────────
        errors = {}

        inicio_raw = request.query_params.get("inicio")
        fim_raw = request.query_params.get("fim")

        if not inicio_raw:
            errors["inicio"] = "Parâmetro obrigatório."
        if not fim_raw:
            errors["fim"] = "Parâmetro obrigatório."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        date_field = DRFDateField()
        try:
            inicio: date = date_field.to_internal_value(inicio_raw)
        except Exception:
            return Response(
                {"inicio": "Data inválida. Use o formato YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            fim: date = date_field.to_internal_value(fim_raw)
        except Exception:
            return Response(
                {"fim": "Data inválida. Use o formato YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fim < inicio:
            return Response(
                {"fim": "'fim' deve ser maior ou igual a 'inicio'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delta = (fim - inicio).days
        if delta > 90:
            return Response(
                {
                    "detail": (
                        f"Intervalo de {delta} dias excede o máximo permitido de 90 dias. "
                        f"Reduza o período e faça múltiplas requisições se necessário."
                    ),
                    "code": "CALENDAR_INTERVAL_TOO_LARGE",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Queryset base (RLS já aplicado por get_queryset) ──────────────────────
        # Para o calendário não precisamos dos M2M pesados — override do QS
        qs = Activity.objects.select_related(
            "municipio",
            "municipio__state",
            "comunidade",
            "tecnico_responsavel",
        ).filter(ativo=True)

        qs = scope_queryset(
            qs,
            request.user,
            state_lookup="municipio__state__sigla__in",
            territory_lookup="municipio__territory__in",
            deny_message="Você não tem acesso ao módulo de Atividades do SGP.",
        )

        inicio_dt = timezone.make_aware(datetime.combine(inicio, time.min))
        fim_dt = timezone.make_aware(datetime.combine(fim, time.max))

        # Interseccão de intervalo: atividade toca o período se
        #   data_inicio <= fim  AND  data_fim >= inicio
        qs = qs.filter(data_inicio__lte=fim_dt, data_fim__gte=inicio_dt)

        # ── Filtros opcionais ──────────────────────────────────────────────────
        qp = request.query_params

        if tecnico_id := qp.get("tecnico_id"):
            qs = qs.filter(tecnico_responsavel_id=tecnico_id)

        if projeto := qp.get("projeto"):
            qs = qs.filter(acao__meta__projeto_id=projeto)

        if acao_id := qp.get("acao"):
            qs = qs.filter(acao_id=acao_id)

        if tipo_atividade := qp.get("tipo_atividade"):
            qs = qs.filter(tipo_atividade=tipo_atividade)

        if status_filter := qp.get("status"):
            qs = qs.filter(status=status_filter)

        # ── Serialização sem paginação ───────────────────────────────────────────
        qs = qs.order_by("data_inicio", "data_fim")
        serializer = ActivityCalendarioSerializer(qs, many=True)
        return Response(
            {
                "count": qs.count(),
                "inicio": str(inicio),
                "fim": str(fim),
                "results": serializer.data,
            }
        )
