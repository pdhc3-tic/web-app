import logging

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import UPF
from apps.sgp.serializers import (
    UPFDetailSerializer,
    UPFListSerializer,
)

logger = logging.getLogger("apps.sgp.views")


class UPFViewSet(viewsets.ModelViewSet):
    queryset = UPF.objects.select_related(
        "municipio", "territorio", "projeto", "criado_por"
    ).all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return UPFListSerializer
        return UPFDetailSerializer

    def get_queryset(self):
        return UPF.objects.select_related(
            "municipio", "territorio", "projeto", "criado_por"
        ).all()

    def _log_audit(self, acao, instance, valores_anteriores=None):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="UPF",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos={
                "upf_id": instance.pk,
                "nome_titular": instance.nome_titular,
                "cpf": instance.cpf,
                "projeto_id": instance.projeto_id,
                "municipio_id": instance.municipio_id,
                "territorio_id": instance.territorio_id,
                "ativa": instance.ativa,
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_create(self, serializer):
        instance = serializer.save(criado_por=self.request.user)
        self._log_audit("UPF.create", instance)

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            "nome_titular": old.nome_titular,
            "cpf": old.cpf,
            "projeto_id": old.projeto_id,
            "municipio_id": old.municipio_id,
            "territorio_id": old.territorio_id,
            "ativa": old.ativa,
        }
        instance = serializer.save()
        self._log_audit("UPF.update", instance, valores_anteriores)

    def perform_destroy(self, instance):
        valores_anteriores = {
            "nome_titular": instance.nome_titular,
            "cpf": instance.cpf,
            "projeto_id": instance.projeto_id,
            "municipio_id": instance.municipio_id,
            "territorio_id": instance.territorio_id,
            "ativa": instance.ativa,
        }
        instance.ativa = False
        instance.save(update_fields=["ativa"])
        self._log_audit(
            "UPF.deactivate", instance, valores_anteriores
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
