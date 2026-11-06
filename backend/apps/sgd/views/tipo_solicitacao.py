from django.db import transaction
from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin
from apps.core.services.audit import log_audit
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models.tipo_solicitacao import TipoSolicitacao
from apps.sgd.serializers.tipo_solicitacao import TipoRubricaSerializer, TipoSolicitacaoSerializer

_TAG = ["SGD - Configuração"]


class _CatalogoViewSet(viewsets.ModelViewSet):
    queryset = TipoSolicitacao.objects.select_related("rubrica")
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    prefixo_auditoria = ""

    def _auditar(self, acao, pk, anteriores=None, novos=None):
        log_audit(
            user=self.request.user, acao=f"{self.prefixo_auditoria}.{acao}", modulo="sgd", entidade="TipoSolicitacao",
            entidade_id=pk, valores_anteriores=anteriores or {}, valores_novos=novos or {}, request=self.request,
        )

    def _dados(self, instancia):
        return self.get_serializer_class()(instancia).data

    @transaction.atomic
    def perform_update(self, serializer):
        anteriores = self._dados(serializer.instance)
        instancia = serializer.save()
        self._auditar("alterado", instancia.pk, anteriores=anteriores, novos=self._dados(instancia))


@extend_schema_view(
    list=extend_schema(tags=_TAG, summary="Lista os tipos de solicitação"),
    create=extend_schema(tags=_TAG, summary="Cria um tipo de solicitação"),
    retrieve=extend_schema(tags=_TAG, summary="Detalha um tipo de solicitação"),
    partial_update=extend_schema(tags=_TAG, summary="Altera um tipo de solicitação"),
    destroy=extend_schema(tags=_TAG, summary="Remove um tipo de solicitação sem solicitações"),
)
class TipoSolicitacaoViewSet(_CatalogoViewSet):
    """Leitura para qualquer usuário autenticado; alterações só pelo Super Admin."""

    serializer_class = TipoSolicitacaoSerializer
    prefixo_auditoria = "tipo_solicitacao"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedActiveAccess()]
        return [IsAuthenticatedActiveAccess(), IsSuperAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        ativo = self.request.query_params.get("ativo")
        if ativo in ("true", "false"):
            qs = qs.filter(ativo=ativo == "true")
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        instancia = serializer.save()
        self._auditar("criado", instancia.pk, novos=self._dados(instancia))

    def perform_destroy(self, instance):
        anteriores, pk = self._dados(instance), instance.pk
        try:
            with transaction.atomic():
                instance.delete()
                self._auditar("removido", pk, anteriores=anteriores)
        except ProtectedError as exc:
            raise RegraDeNegocio(
                "Este tipo já tem solicitações e não pode ser removido. Desative-o.", campo="tipo",
            ) from exc


@extend_schema_view(
    list=extend_schema(tags=_TAG, summary="Lista os tipos com a rubrica de cada um"),
    create=extend_schema(tags=_TAG, summary="Reativa um tipo inativo com a rubrica informada"),
    retrieve=extend_schema(tags=_TAG, summary="Detalha um tipo com a sua rubrica"),
    partial_update=extend_schema(tags=_TAG, summary="Altera a rubrica ou a situação de um tipo"),
    destroy=extend_schema(tags=_TAG, summary="Desativa um tipo"),
)
class TipoRubricaViewSet(_CatalogoViewSet):
    """Alias da tela de mapeamento sobre o catálogo, só para o Super Admin. Não há mais
    histórico: cada tipo tem uma linha, e desativá-la desativa o tipo."""

    serializer_class = TipoRubricaSerializer
    permission_classes = [IsAuthenticatedActiveAccess, IsSuperAdmin]
    prefixo_auditoria = "tipo_rubrica"

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("tipo"):
            qs = qs.filter(slug=params["tipo"])
        if params.get("ativo") in ("true", "false"):
            qs = qs.filter(ativo=params["ativo"] == "true")
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        instancia = serializer.save()
        self._auditar("criado", instancia.pk, novos=self._dados(instancia))

    @transaction.atomic
    def perform_destroy(self, instance):
        anteriores = self._dados(instance)
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])
        self._auditar("removido", instance.pk, anteriores=anteriores, novos=self._dados(instance))
