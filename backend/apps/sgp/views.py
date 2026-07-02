import logging

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import MembroFamilia, UPF
from apps.sgp.serializers import (
    MembroDetailSerializer,
    MembroListSerializer,
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
        self._log_audit("UPF.deactivate", instance, valores_anteriores)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MembroViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_upf(self):
        return get_object_or_404(UPF, pk=self.kwargs["upf_pk"])

    def get_queryset(self):
        return MembroFamilia.objects.filter(upf=self.kwargs["upf_pk"])

    def get_serializer_class(self):
        if self.action == "list":
            return MembroListSerializer
        return MembroDetailSerializer

    def perform_create(self, serializer):
        upf = self.get_upf()
        if not upf.ativa:
            raise serializers.ValidationError(
                "Não é possível adicionar membros a uma UPF inativa"
            )
        instance = serializer.save(upf=upf, criado_por=self.request.user)
        AuditLog.objects.create(
            user=self.request.user,
            acao="MEMBRO.create",
            modulo="sgp",
            entidade="MembroFamilia",
            entidade_id=str(instance.pk),
            valores_novos={
                "membro_id": instance.pk,
                "nome_completo": instance.nome_completo,
                "parentesco": instance.parentesco,
                "upf_id": instance.upf_id,
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            "nome_completo": old.nome_completo,
            "parentesco": old.parentesco,
            "cpf": old.cpf,
        }
        instance = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            acao="MEMBRO.update",
            modulo="sgp",
            entidade="MembroFamilia",
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores,
            valores_novos={
                "membro_id": instance.pk,
                "nome_completo": instance.nome_completo,
                "parentesco": instance.parentesco,
                "upf_id": instance.upf_id,
            },
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    def perform_destroy(self, instance):
        AuditLog.objects.create(
            user=self.request.user,
            acao="MEMBRO.delete",
            modulo="sgp",
            entidade="MembroFamilia",
            entidade_id=str(instance.pk),
            valores_anteriores={
                "membro_id": instance.pk,
                "nome_completo": instance.nome_completo,
                "parentesco": instance.parentesco,
                "upf_id": instance.upf_id,
            },
            valores_novos={},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
        instance.delete()
