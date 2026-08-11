from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from apps.core.permissions import IsAuthenticatedActiveAccess

from apps.core.models.audit_log import AuditLog
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.models import Production, UPF
from apps.sgp.serializers import ProductionSerializer


class ProductionViewSet(viewsets.ModelViewSet):
    serializer_class = ProductionSerializer
    permission_classes = [IsAuthenticatedActiveAccess]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_upf(self):
        if not hasattr(self, "_upf"):
            self._upf = get_object_or_404(
                self._accessible_upf_queryset(),
                pk=self.kwargs["upf_pk"],
            )
        return self._upf

    def _accessible_upf_queryset(self):
        qs = UPF.objects.select_related("municipio", "municipio__state", "territorio")
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

    def get_queryset(self):
        return (
            Production.objects.filter(upf=self.get_upf())
            .select_related("upf", "cultura", "especie")
            .order_by("-criado_em")
        )

    def perform_create(self, serializer):
        upf = self.get_upf()
        if not upf.ativa:
            raise serializers.ValidationError(
                "Não é possível adicionar produção a uma UPF inativa."
            )
        instance = serializer.save(upf=upf)
        self._log_production_audit(
            "production.create",
            instance,
            valores_novos=self._production_snapshot(instance),
        )

    def perform_update(self, serializer):
        old = self.get_object()
        valores_anteriores = self._production_snapshot(old)
        instance = serializer.save()
        self._log_production_audit(
            "production.update",
            instance,
            valores_anteriores=valores_anteriores,
            valores_novos=self._production_snapshot(instance),
        )

    def perform_destroy(self, instance):
        valores_anteriores = self._production_snapshot(instance)
        self._log_production_audit(
            "production.delete",
            instance,
            valores_anteriores=valores_anteriores,
        )
        instance.delete()

    def _production_snapshot(self, production):
        return {
            "production_id": production.pk,
            "upf_id": production.upf_id,
            "tipo": production.tipo,
            "cultura_id": production.cultura_id,
            "area_ha": self._decimal_to_str(production.area_ha),
            "producao_estimada": self._decimal_to_str(production.producao_estimada),
            "unidade_producao": production.unidade_producao,
            "sementes_crioulas": production.sementes_crioulas,
            "especie_id": production.especie_id,
            "n_matrizes": production.n_matrizes,
            "n_reprodutores": production.n_reprodutores,
            "n_jovens": production.n_jovens,
            "area_pastejo_ha": self._decimal_to_str(production.area_pastejo_ha),
            "sistema_criacao": production.sistema_criacao,
            "tipo_outra": production.tipo_outra,
            "descricao_outra": production.descricao_outra,
            "quantidade_produzida": production.quantidade_produzida,
            "renda_estimada_mensal": self._decimal_to_str(
                production.renda_estimada_mensal
            ),
            "custo_anual": self._decimal_to_str(production.custo_anual),
            "observacoes": production.observacoes,
        }

    def _log_production_audit(
        self,
        acao,
        production,
        valores_anteriores=None,
        valores_novos=None,
    ):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="Production",
            entidade_id=str(production.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos=valores_novos or {},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )

    @staticmethod
    def _decimal_to_str(value):
        if value is None:
            return None
        return str(value)
