from datetime import date

from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsADTInTerritory, IsAuthenticatedActiveAccess, IsFGD, IsSuperAdmin
from apps.core.services.audit import log_audit
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models.diarias import FaixaDestinoDiaria, TabelaDiaria
from apps.sgd.serializers.diarias import (
    FaixaDestinoDiariaSerializer,
    NovaVigenciaSerializer,
    ParametrosDiariasSerializer,
    SimulacaoDiariasSerializer,
    SimularDiariasQuerySerializer,
    TabelaDiariaSerializer,
)
from apps.sgd.services import diarias as diarias_service
from apps.sgd.services.demand_request import calcular_diarias

_TAG = ["SGD - Configuração"]


class SimularDiariasView(APIView):
    """Valor das diárias para o formulário, com a mesma regra usada ao gravar a solicitação."""

    permission_classes = [IsAuthenticatedActiveAccess, IsADTInTerritory | IsSuperAdmin]

    @extend_schema(
        tags=_TAG,
        parameters=[SimularDiariasQuerySerializer],
        responses={200: SimulacaoDiariasSerializer, 400: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        query = SimularDiariasQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        diarias = calcular_diarias(**query.validated_data)
        return Response(SimulacaoDiariasSerializer({
            "faixa_destino": {"id": diarias.faixa.pk, "nome": diarias.faixa.nome},
            "tabela_diaria_id": diarias.tabela.pk,
            "valor_por_diaria": diarias.valor_por_diaria,
            "numero_diarias": diarias.numero,
            "adicional_embarque": diarias.adicional_embarque,
            "valor_total": diarias.valor_total,
        }).data)


class ParametrosDiariasView(APIView):
    """Regras de contagem e adicional de embarque. São parâmetros do Core, editáveis aqui
    pela FGD e pelo Super Admin para a fundação se afastar do padrão federal sem deploy.
    Só estas chaves: a tela geral de configurações do Core continua só do Super Admin."""

    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticatedActiveAccess()]
        return [IsAuthenticatedActiveAccess(), (IsSuperAdmin | IsFGD)()]

    @extend_schema(tags=_TAG, summary="Parâmetros de contagem de diárias", responses=ParametrosDiariasSerializer)
    def get(self, request):
        return Response(ParametrosDiariasSerializer(diarias_service.ler_parametros()).data)

    @extend_schema(
        tags=_TAG, summary="Altera os parâmetros de contagem de diárias",
        request=ParametrosDiariasSerializer, responses=ParametrosDiariasSerializer,
    )
    def patch(self, request):
        serializer = ParametrosDiariasSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        parametros = diarias_service.atualizar_parametros(serializer.validated_data, user=request.user)
        return Response(ParametrosDiariasSerializer(parametros).data)


class _ConfiguracaoDiariasMixin:
    """Leitura para qualquer usuário autenticado; alterações pelo Super Admin e pela FGD."""

    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedActiveAccess()]
        return [IsAuthenticatedActiveAccess(), (IsSuperAdmin | IsFGD)()]


@extend_schema_view(
    list=extend_schema(tags=_TAG, summary="Lista as faixas de destino de diária"),
    create=extend_schema(tags=_TAG, summary="Cria uma faixa de destino de diária"),
    retrieve=extend_schema(tags=_TAG, summary="Detalha uma faixa de destino de diária"),
    partial_update=extend_schema(tags=_TAG, summary="Altera uma faixa e, se enviado, o seu enquadramento"),
    destroy=extend_schema(tags=_TAG, summary="Remove uma faixa sem valores na tabela"),
)
class FaixaDestinoDiariaViewSet(_ConfiguracaoDiariasMixin, viewsets.ModelViewSet):
    queryset = FaixaDestinoDiaria.objects.prefetch_related("enquadramentos")
    serializer_class = FaixaDestinoDiariaSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def _auditar(self, acao, pk, anteriores=None, novos=None):
        log_audit(
            user=self.request.user, acao=f"faixa_destino_diaria.{acao}", modulo="sgd", entidade="FaixaDestinoDiaria",
            entidade_id=pk, valores_anteriores=anteriores or {}, valores_novos=novos or {}, request=self.request,
        )

    def get_queryset(self):
        qs = super().get_queryset()
        ativo = self.request.query_params.get("ativo")
        if ativo in ("true", "false"):
            qs = qs.filter(ativo=ativo == "true")
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        faixa = serializer.save()
        self._auditar("criado", faixa.pk, novos=FaixaDestinoDiariaSerializer(faixa).data)

    @transaction.atomic
    def perform_update(self, serializer):
        anteriores = FaixaDestinoDiariaSerializer(serializer.instance).data
        faixa = serializer.save()
        self._auditar("alterado", faixa.pk, anteriores=anteriores, novos=FaixaDestinoDiariaSerializer(faixa).data)

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.valores.exists():
            raise RegraDeNegocio(
                "Esta faixa já tem valores na tabela de diárias e não pode ser removida. Desative-a.",
                campo="faixa_destino",
            )
        anteriores, pk = FaixaDestinoDiariaSerializer(instance).data, instance.pk
        instance.delete()
        self._auditar("removido", pk, anteriores=anteriores)


@extend_schema_view(
    list=extend_schema(
        tags=_TAG, summary="Lista os valores da tabela de diárias",
        parameters=[
            OpenApiParameter("faixa_destino", OpenApiTypes.INT),
            OpenApiParameter("origem", OpenApiTypes.STR, enum=["federal", "fgd"]),
            OpenApiParameter("vigente_em", OpenApiTypes.DATE, description="Só os valores vigentes nesta data."),
        ],
    ),
    create=extend_schema(tags=_TAG, summary="Cadastra um valor de diária com vigência"),
    retrieve=extend_schema(tags=_TAG, summary="Detalha um valor da tabela de diárias"),
    partial_update=extend_schema(
        tags=_TAG, summary="Edita um valor: encerra a vigência atual e cria uma nova a partir de vigencia_inicio",
        request=NovaVigenciaSerializer, responses={201: TabelaDiariaSerializer},
    ),
)
class TabelaDiariaViewSet(_ConfiguracaoDiariasMixin, viewsets.ModelViewSet):
    queryset = TabelaDiaria.objects.select_related("faixa_destino", "criado_por")
    serializer_class = TabelaDiariaSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("faixa_destino"):
            qs = qs.filter(faixa_destino_id=params["faixa_destino"])
        if params.get("origem"):
            qs = qs.filter(origem=params["origem"])
        if params.get("vigente_em"):
            try:
                data = date.fromisoformat(params["vigente_em"])
            except ValueError as exc:
                raise RegraDeNegocio("Data inválida, use AAAA-MM-DD.", campo="vigente_em") from exc
            qs = qs.filter(vigencia_inicio__lte=data).exclude(vigencia_fim__lt=data)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        linha = diarias_service.criar_valor(
            faixa=dados["faixa_destino"], categoria=dados.get("categoria_beneficiario", "padrao"),
            inicio=dados["vigencia_inicio"], fim=dados.get("vigencia_fim"), valor=dados["valor"],
            origem=dados["origem"], user=request.user, request=request,
        )
        return Response(TabelaDiariaSerializer(linha).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        atual = self.get_object()
        serializer = NovaVigenciaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        nova = diarias_service.registrar_nova_vigencia(
            atual=atual, valor=dados["valor"], inicio=dados["vigencia_inicio"], origem=dados["origem"],
            user=request.user, request=request,
        )
        return Response(TabelaDiariaSerializer(nova).data, status=status.HTTP_201_CREATED)

