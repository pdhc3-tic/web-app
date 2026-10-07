from django.db import transaction
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin
from apps.core.utils import get_client_ip
from apps.sgd.models.arlo_field_mapping import ArloFieldMapping
from apps.sgd.serializers.arlo_field_mapping import ArloFieldMappingSerializer
from apps.sgd.services.arlo_mapping import validar_ativos_obrigatorios


class ReordenarSerializer(serializers.Serializer):
    direcao = serializers.ChoiceField(choices=ArloFieldMapping.Direcao.choices)
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class ArloFieldMappingViewSet(viewsets.ModelViewSet):
    """Painel de configuração do mapeamento Arlo <-> SGD (SGD §6). Só Super Admin."""

    queryset = ArloFieldMapping.objects.all()
    serializer_class = ArloFieldMappingSerializer
    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdmin]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        direcao = self.request.query_params.get("direcao")
        return qs.filter(direcao=direcao) if direcao else qs

    def _auditar(self, acao, instancia, anteriores=None, novos=None):
        AuditLog.objects.create(
            user=self.request.user, acao=f"arlo_mapping.{acao}", modulo="sgd", entidade="ArloFieldMapping",
            entidade_id=str(instancia.pk), valores_anteriores=anteriores or {}, valores_novos=novos or {},
            ip=get_client_ip(self.request), user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @staticmethod
    def _dados(instancia):
        return ArloFieldMappingSerializer(instancia).data

    def _ativos_apos(self, direcao, *, excluindo=None, incluindo=None):
        qs = ArloFieldMapping.objects.filter(direcao=direcao, ativo=True)
        if excluindo is not None:
            qs = qs.exclude(pk=excluindo)
        ativos = set(qs.values_list("campo_sgd", flat=True))
        return ativos | ({incluindo} if incluindo else set())

    @transaction.atomic
    def perform_create(self, serializer):
        instancia = serializer.save()
        self._auditar("criado", instancia, novos=self._dados(instancia))

    @transaction.atomic
    def perform_update(self, serializer):
        instancia = serializer.instance
        anteriores = self._dados(instancia)
        if serializer.validated_data.get("ativo") is False:
            validar_ativos_obrigatorios(instancia.direcao, self._ativos_apos(instancia.direcao, excluindo=instancia.pk))
        instancia = serializer.save()
        self._auditar("alterado", instancia, anteriores=anteriores, novos=self._dados(instancia))

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.ativo:
            validar_ativos_obrigatorios(instance.direcao, self._ativos_apos(instance.direcao, excluindo=instance.pk))
        anteriores = self._dados(instance)
        pk = instance.pk
        instance.delete()
        AuditLog.objects.create(
            user=self.request.user, acao="arlo_mapping.removido", modulo="sgd", entidade="ArloFieldMapping",
            entidade_id=str(pk), valores_anteriores=anteriores,
            ip=get_client_ip(self.request), user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @action(detail=False, methods=["post"], url_path="reordenar")
    @transaction.atomic
    def reordenar(self, request):
        """Define a ordem das colunas de uma direção conforme a lista de ids."""
        serializer = ReordenarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        direcao, ids = serializer.validated_data["direcao"], serializer.validated_data["ids"]

        linhas = {m.pk: m for m in ArloFieldMapping.objects.select_for_update().filter(direcao=direcao)}
        if len(set(ids)) != len(ids) or set(ids) != set(linhas):
            raise ValidationError({"ids": "Informe todos os ids da direção, sem repetições."})

        anteriores = {pk: m.ordem for pk, m in linhas.items()}
        for ordem, pk in enumerate(ids, start=1):
            if linhas[pk].ordem != ordem:
                linhas[pk].ordem = ordem
                linhas[pk].save(update_fields=["ordem"])
        AuditLog.objects.create(
            user=request.user, acao="arlo_mapping.reordenado", modulo="sgd", entidade="ArloFieldMapping",
            entidade_id=direcao, valores_anteriores=anteriores, valores_novos={"ids": ids},
            ip=get_client_ip(request), user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        qs = ArloFieldMapping.objects.filter(direcao=direcao)
        return Response(ArloFieldMappingSerializer(qs, many=True).data, status=status.HTTP_200_OK)
