import logging
from datetime import datetime

from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsSuperAdmin, IsUGP
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.filters import UPFFilter
from apps.sgp.models import Comunidade, Cultura, EspecieAnimal, MembroFamilia, UPF
from apps.sgp.pagination import CatalogoPagination, HistoricoPagination, UPFPagination
from apps.sgp.serializers import (
    ComunidadeSerializer,
    CulturaSerializer,
    EspecieAnimalSerializer,
    HistoricoEntrySerializer,
    MembroDetailSerializer,
    MembroListSerializer,
    UPFDetailSerializer,
    UPFListSerializer,
)
from .upf_foto import UPFPhotoMixin
from .upf_documentos import UPFDocumentViewSet

logger = logging.getLogger("apps.sgp.views")


class QSearchFilter(filters.SearchFilter):
    search_param = 'q'


class CatalogoListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CatalogoPagination
    http_method_names = ["get", "head", "options"]
    model = None

    def get_queryset(self):
        qs = self.model.objects.all()

        ativa_param = self.request.query_params.get("ativa", "").lower()
        is_admin = user_has_role(self.request.user, "super-admin") or user_has_role(
            self.request.user, "ugp"
        )
        if ativa_param != "false" or not is_admin:
            qs = qs.filter(ativa=True)

        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(nome__icontains=q)

        categoria = self.request.query_params.get("categoria", "").strip()
        if categoria:
            qs = qs.filter(categoria=categoria)

        return qs


class CulturaListView(CatalogoListView):
    serializer_class = CulturaSerializer
    model = Cultura


class EspecieAnimalListView(CatalogoListView):
    serializer_class = EspecieAnimalSerializer
    model = EspecieAnimal


class ComunidadePagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 100


class UPFViewSet(UPFPhotoMixin, viewsets.ModelViewSet):
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

        user = self.request.user

        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            return qs

        if user_has_role(user, "articulador-estadual"):
            states = user_states(user)
            if not states:
                return qs.none()
            return qs.filter(municipio__state__sigla__in=states)

        if user_has_role(user, "adt-acr"):
            territories = user_territories(user)
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

        usuario_filter = request.query_params.get("usuario")
        if usuario_filter:
            q &= Q(user_id=usuario_filter)

        desde = request.query_params.get("desde")
        if desde:
            try:
                dt = datetime.fromisoformat(desde)
                q &= Q(timestamp__gte=dt)
            except (ValueError, TypeError):
                pass

        ate = request.query_params.get("ate")
        if ate:
            try:
                dt = datetime.fromisoformat(ate)
                q &= Q(timestamp__lte=dt)
            except (ValueError, TypeError):
                pass

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
                "comunidade_id": instance.comunidade_id,
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
            "comunidade_id": old.comunidade_id,
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
            "comunidade_id": instance.comunidade_id,
            "ativa": instance.ativa,
        }
        instance.ativa = False
        instance.save(update_fields=["ativa"])
        self._log_audit("UPF.deactivate", instance, valores_anteriores)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ComunidadeViewSet(viewsets.ModelViewSet):
    queryset = Comunidade.objects.all()
    serializer_class = ComunidadeSerializer
    pagination_class = ComunidadePagination
    filter_backends = [QSearchFilter]
    search_fields = ['nome']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [(IsSuperAdmin | IsUGP)()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Comunidade.objects.select_related(
            'municipio', 'municipio__state', 'criada_por',
        )

        municipio_id = self.kwargs.get('municipio_id')
        if municipio_id is not None:
            qs = qs.filter(municipio_id=municipio_id)

        ativa_param = self.request.query_params.get('ativa')
        if ativa_param is not None and ativa_param.lower() == 'false':
            user = self.request.user
            if (
                user.is_authenticated
                and (user_has_role(user, "super-admin") or user_has_role(user, "ugp"))
            ):
                return qs.filter(ativa=False)
        return qs.filter(ativa=True)

    def list(self, request, *args, **kwargs):
        if 'municipio_id' not in self.kwargs:
            return Response(
                {'detail': 'Listagem global não disponível. Use /api/v1/municipios/{id}/comunidades/.'},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if 'municipio_id' not in self.kwargs:
            return Response(
                {'detail': 'Criação global não disponível. Use /api/v1/municipios/{id}/comunidades/.'},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().create(request, *args, **kwargs)

    def get_serializer(self, *args, **kwargs):
        municipio_id = self.kwargs.get('municipio_id')
        if municipio_id is not None and self.action == 'create':
            data = kwargs.get('data')
            if data is not None:
                data = data.copy()
                data['municipio'] = int(municipio_id)
                kwargs['data'] = data
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        try:
            instance = serializer.save(criada_por=self.request.user, ativa=True)
        except (IntegrityError, DjangoValidationError):
            raise serializers.ValidationError({
                'nome': 'Já existe uma comunidade ativa com este nome neste município.',
            })
        AuditLog.objects.create(
            user=self.request.user,
            acao='comunidade.create',
            modulo='sgp',
            entidade='Comunidade',
            entidade_id=str(instance.pk),
            valores_novos={
                'id': instance.pk,
                'nome': instance.nome,
                'municipio_id': instance.municipio_id,
                'ativa': instance.ativa,
            },
            ip=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = {
            'nome': old.nome,
            'municipio_id': old.municipio_id,
            'lat': str(old.lat) if old.lat else None,
            'lng': str(old.lng) if old.lng else None,
            'ativa': old.ativa,
        }
        instance = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            acao='UPDATE',
            modulo='sgp',
            entidade='Comunidade',
            entidade_id=str(instance.pk),
            valores_anteriores=valores_anteriores,
            valores_novos={
                'nome': instance.nome,
                'municipio_id': instance.municipio_id,
                'lat': str(instance.lat) if instance.lat else None,
                'lng': str(instance.lng) if instance.lng else None,
                'ativa': instance.ativa,
            },
            ip=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )

    def perform_destroy(self, instance):
        valores_anteriores = {'nome': instance.nome, 'ativa': instance.ativa}
        instance.ativa = False
        instance.save(update_fields=['ativa'])
        AuditLog.objects.create(
            user=self.request.user,
            acao='comunidade.soft_delete',
            modulo='sgp',
            entidade='Comunidade',
            entidade_id=str(instance.pk),
            valores_novos={
                'id': instance.pk,
                'nome': instance.nome,
                'ativa': False,
            },
            ip=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )

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
