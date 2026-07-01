import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import filters, serializers, status, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsSuperAdmin, IsUGP

from .models import Comunidade
from .serializers import ComunidadeSerializer

logger = logging.getLogger('apps.sgp.views')


class QSearchFilter(filters.SearchFilter):
    search_param = 'q'


class ComunidadePagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 100


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
                and getattr(user, 'role', None)
                and user.role.slug in ('super-admin', 'ugp')
            ):
                return qs
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
