import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models.system_config import SystemConfig
from apps.core.permissions import (
    IsAuthenticatedActiveAccess,
    IsSuperAdmin,
    IsSuperAdminOrUGPReadOnly,
)
from apps.core.serializers import GoogleCalendarConfigSerializer, SystemConfigSerializer
from apps.sgp.models import Activity, GoogleCalendarSyncEvent


GOOGLE_CALENDAR_CONFIGS = {
    "calendario_destino_id": {
        "chave": "google_calendar_calendario_destino_id",
        "valor": "",
        "tipo": "string",
        "descricao": "ID do calendário destino da integração Google Calendar.",
    },
    "lembretes": {
        "chave": "google_calendar_lembretes",
        "valor": "[1440, 60]",
        "tipo": "json",
        "descricao": "Lembretes da integração Google Calendar em minutos antes do evento.",
    },
    "integracao_ativa": {
        "chave": "google_calendar_integracao_ativa",
        "valor": "False",
        "tipo": "boolean",
        "descricao": "Indica se novas sincronizações com Google Calendar estão ativas.",
    },
}


def _ensure_google_calendar_configs():
    configs = {}
    for field, defaults in GOOGLE_CALENDAR_CONFIGS.items():
        chave = defaults["chave"]
        config, _ = SystemConfig.objects.get_or_create(
            chave=chave,
            defaults=defaults,
        )
        configs[field] = config
    return configs


def _parse_config_value(config):
    if config.tipo == "boolean":
        return config.valor == "True"
    if config.tipo == "json":
        return json.loads(config.valor)
    return config.valor


def _format_config_value(field, value):
    if field == "lembretes":
        return json.dumps(value, ensure_ascii=False)
    if field == "integracao_ativa":
        return str(value)
    return str(value)


class SystemConfigListView(generics.ListAPIView):
    """GET /api/v1/system-config/ — lista configurações do sistema."""

    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdminOrUGPReadOnly]


class SystemConfigDetailView(generics.RetrieveUpdateAPIView):
    """GET|PATCH /api/v1/system-config/{chave}/ — detalhe ou atualização."""

    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    lookup_field = "chave"
    http_method_names = ["get", "patch"]
    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdminOrUGPReadOnly]

    def perform_update(self, serializer):
        serializer.save(atualizado_por=self.request.user)


class GoogleCalendarConfigView(APIView):
    """GET|PATCH /api/v1/core/config/google-calendar/ — configuração singleton."""

    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdmin]
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request):
        configs = _ensure_google_calendar_configs()
        return Response(self._payload(configs))

    @transaction.atomic
    def patch(self, request):
        configs = _ensure_google_calendar_configs()
        serializer = GoogleCalendarConfigSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            config = configs[field]
            new_value = _format_config_value(field, value)
            if config.valor == new_value:
                continue
            config.valor = new_value
            config.atualizado_por = request.user
            config.save(update_fields=["valor", "atualizado_por", "atualizado_em"])

        configs = _ensure_google_calendar_configs()
        return Response(self._payload(configs))

    def _payload(self, configs):
        return {
            field: _parse_config_value(config)
            for field, config in configs.items()
        }


class GoogleCalendarStatusView(APIView):
    """
    GET /api/v1/core/config/google-calendar/status/ — status agregado da
    integração, consumido por frontend/app/lib/integracoes.ts ::
    fetchGoogleCalendarStatus.

    `estado`: "pendente" se QUALQUER Activity tem
    google_calendar_sync_status="pendente" (sync enfileirada/em andamento);
    senão "nunca_executada" se nenhum GoogleCalendarSyncEvent existe; senão
    "ok"/"erro" conforme o evento mais recente.

    `ultima_sincronizacao` e `ultimo_erro` são calculados de forma
    independente do `estado` atual — refletem, respectivamente, o evento de
    sucesso mais recente e o evento de falha mais recente já ocorridos, ainda
    que o `estado` atual seja outro (ex.: em "erro", `ultima_sincronizacao`
    continua mostrando o último sucesso anterior; em "ok", `ultimo_erro` pode
    mostrar uma falha anterior à recuperação). São histórico, não status "ao
    vivo" do estado atual.

    `falhas_recentes`: janela ROLLING de 24h (`ocorrido_em` nas últimas 24h),
    não zera quando há um sucesso — decisão da Pendência 3 da issue #210.
    """

    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdmin]
    http_method_names = ["get", "head", "options"]

    JANELA_FALHAS_RECENTES = timedelta(hours=24)

    def get(self, request):
        if Activity.objects.filter(google_calendar_sync_status="pendente").exists():
            estado = "pendente"
        else:
            ultimo_evento = GoogleCalendarSyncEvent.objects.order_by("-ocorrido_em").first()
            if ultimo_evento is None:
                estado = "nunca_executada"
            else:
                estado = "ok" if ultimo_evento.sucesso else "erro"

        evento_sucesso = (
            GoogleCalendarSyncEvent.objects.filter(sucesso=True)
            .order_by("-ocorrido_em")
            .first()
        )
        evento_falha = (
            GoogleCalendarSyncEvent.objects.filter(sucesso=False)
            .order_by("-ocorrido_em")
            .first()
        )
        falhas_recentes = GoogleCalendarSyncEvent.objects.filter(
            sucesso=False,
            ocorrido_em__gte=timezone.now() - self.JANELA_FALHAS_RECENTES,
        ).count()

        return Response({
            "estado": estado,
            "ultima_sincronizacao": (
                timezone.localtime(evento_sucesso.ocorrido_em).isoformat()
                if evento_sucesso
                else None
            ),
            "ultimo_erro": evento_falha.mensagem_erro if evento_falha else None,
            "falhas_recentes": falhas_recentes,
        })
