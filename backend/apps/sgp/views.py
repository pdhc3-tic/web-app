import logging
from datetime import datetime

from django.apps import apps
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.sgp.filters import UPFFilter
from apps.sgp.models import MembroFamilia, UPF
from apps.sgp.pagination import HistoricoPagination, UPFPagination
from apps.sgp.serializers import (
    HistoricoEntrySerializer,
    MembroDetailSerializer,
    MembroListSerializer,
    UPFDetailSerializer,
    UPFListSerializer,
)

logger = logging.getLogger("apps.sgp.views")


class UPFViewSet(viewsets.ModelViewSet):
    queryset = UPF.objects.select_related(
        "municipio", "municipio__state", "territorio", "projeto", "criado_por"
    ).all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    pagination_class = UPFPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = UPFFilter
    ordering_fields = ["criado_em", "nome_titular", "data_nasc"]
    ordering = ["-criado_em"]

    def get_serializer_class(self):
        if self.action == "list":
            return UPFListSerializer
        if self.action == "historico":
            return HistoricoEntrySerializer
        return UPFDetailSerializer

    def filter_queryset(self, queryset):
        if "ativa" not in self.request.query_params:
            queryset = queryset.filter(ativa=True)
        return super().filter_queryset(queryset)

    def get_queryset(self):
        qs = UPF.objects.select_related(
            "municipio", "municipio__state", "territorio", "projeto", "criado_por"
        ).all()

        role_slug = getattr(getattr(self.request.user, "role", None), "slug", None)

        if role_slug in ("super-admin", "ugp"):
            return qs

        if role_slug == "articulador-estadual":
            territories = self.request.user.territorios.all()
            if not territories.exists():
                return qs.none()
            states = set()
            for t in territories:
                states.update(t.estados)
            if not states:
                return qs.none()
            return qs.filter(municipio__state__sigla__in=states)

        if role_slug == "adt-acr":
            territories = self.request.user.territorios.all()
            if not territories.exists():
                return qs.none()
            return qs.filter(territorio__in=territories)

        raise PermissionDenied("Você não tem acesso ao módulo SGP.")

    @action(detail=True, methods=["get"], url_path="historico")
    def historico(self, request, pk=None):
        upf = self.get_object()
        q = Q(entidade="UPF", entidade_id=str(upf.pk))

        incluir_membros = request.query_params.get("incluir_membros") == "true"
        if incluir_membros:
            MembroFamilia = apps.get_model("sgp", "MembroFamilia")
            if MembroFamilia is not None:
                member_ids = list(
                    MembroFamilia.objects.filter(upf_id=upf.pk).values_list(
                        "pk", flat=True
                    )
                )
                if member_ids:
                    q |= Q(
                        entidade="MembroFamilia",
                        entidade_id__in=[str(m) for m in member_ids],
                    )

        logs = (
            AuditLog.objects.filter(q)
            .select_related("user")
            .order_by("-timestamp")
        )

        entries = []
        for log in logs:
            if log.acao.lower().endswith(".create"):
                entries.append(
                    self._build_entry(log, campo=None, valor_anterior=None, valor_novo=log.valores_novos)
                )
            elif log.acao.lower().endswith(".update"):
                old = log.valores_anteriores or {}
                new = log.valores_novos or {}
                all_keys = set(old.keys()) | set(new.keys())
                for key in sorted(all_keys):
                    old_val = old.get(key)
                    new_val = new.get(key)
                    if old_val != new_val:
                        entries.append(
                            self._build_entry(log, campo=key, valor_anterior=old_val, valor_novo=new_val, suffix=key)
                        )
            else:
                entries.append(
                    self._build_entry(log, campo=None, valor_anterior=log.valores_anteriores, valor_novo=log.valores_novos)
                )

        campo_filter = request.query_params.get("campo")
        if campo_filter:
            entries = [e for e in entries if e["campo"] == campo_filter]

        usuario_filter = request.query_params.get("usuario")
        if usuario_filter:
            entries = [
                e
                for e in entries
                if e.get("usuario_id") is not None
                and str(e["usuario_id"]) == usuario_filter
            ]

        desde = request.query_params.get("desde")
        if desde:
            try:
                dt = datetime.fromisoformat(desde)
            except (ValueError, TypeError):
                dt = None
            if dt:
                entries = [e for e in entries if e["timestamp"] >= dt]

        ate = request.query_params.get("ate")
        if ate:
            try:
                dt = datetime.fromisoformat(ate)
            except (ValueError, TypeError):
                dt = None
            if dt:
                entries = [e for e in entries if e["timestamp"] <= dt]

        entries.sort(key=lambda e: e["timestamp"], reverse=True)

        paginator = HistoricoPagination()
        page = paginator.paginate_queryset(entries, request)
        serializer = HistoricoEntrySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def _build_entry(self, log, campo, valor_anterior, valor_novo, suffix=None):
        eid = str(log.pk) if suffix is None else f"{log.pk}_{suffix}"
        return {
            "id": eid,
            "campo": campo,
            "valor_anterior": valor_anterior,
            "valor_novo": valor_novo,
            "usuario_id": log.user.pk if log.user else None,
            "usuario_nome": log.user.nome if log.user else None,
            "timestamp": log.timestamp,
        }

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
            "upf_id": old.pk,
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
            "upf_id": instance.pk,
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
            "membro_id": old.pk,
            "upf_id": old.upf_id,
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
                "upf_id": instance.upf_id,
                "nome_completo": instance.nome_completo,
                "parentesco": instance.parentesco,
            },
            valores_novos={},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
        instance.delete()
