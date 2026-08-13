import json

from django.db import transaction
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
