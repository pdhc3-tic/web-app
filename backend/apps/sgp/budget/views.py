import logging

from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess, IsSuperAdmin, IsUGP
from apps.core.services.permissions import user_has_role
from apps.sgp.budget import limites as limites_service
from apps.sgp.filters import BudgetRubricaFilter
from apps.sgp.models import BudgetPool, BudgetRubrica, SpendingLimit, WorkPlanMeta
from apps.sgp.budget.serializers import (
    BudgetPainelLinhaSerializer,
    BudgetPainelQuerySerializer,
    BudgetPoolCreateSerializer,
    BudgetPoolSerializer,
    BudgetPoolUpdateSerializer,
    BudgetRubricaSerializer,
    BudgetTransactionSerializer,
    RemanejamentoCreateSerializer,
    SaldoConsultaQuerySerializer,
    SaldoConsultaSerializer,
    SpendingLimitCreateSerializer,
    SpendingLimitQuerySerializer,
    SpendingLimitSerializer,
    SpendingLimitUpdateSerializer,
)
from apps.sgp.budget import services as budget_service


logger = logging.getLogger(__name__)


class BudgetPoolViewSet(viewsets.ViewSet):
    """`create` em `orcamento/pools/`, `partial_update`/`destroy` em `orcamento/pools/{id}/`.
    As rotas antigas, `metas/{id}/orcamento/alocacoes/` e `orcamento/alocacoes/{id}/`,
    continuam como alias enquanto o front migra. Wiring manual em urls.py, sem router."""

    permission_classes = [IsAuthenticatedActiveAccess]

    def _autorizar(self, request, *, nivel, estado, territorio):
        user = request.user
        if budget_service.is_global_budget_user(user):
            return

        if nivel != BudgetPool.Nivel.TERRITORIAL:
            raise PermissionDenied(
                "Só UGP/Super Admin criam ou alteram alocações nacionais/estaduais."
            )
        if not user_has_role(user, "articulador-estadual"):
            raise PermissionDenied("Você não tem permissão para gerenciar alocações.")

        estados_do_territorio = set((territorio.estados if territorio else []) or [])
        if not estados_do_territorio & budget_service.allowed_states_for_user(user):
            raise PermissionDenied("Este território não pertence ao seu estado.")

    @extend_schema(
        request=BudgetPoolCreateSerializer,
        responses={201: BudgetPoolSerializer},
    )
    def create(self, request, meta_pk=None):
        if meta_pk is not None:
            # O alias segue devolvendo 404 para a Meta inexistente; o saldo não depende dela.
            get_object_or_404(WorkPlanMeta, pk=meta_pk)
        entrada = BudgetPoolCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        self._autorizar(
            request, nivel=dados["nivel"],
            estado=dados.get("estado"), territorio=dados.get("territorio"),
        )

        pool = budget_service.criar_pool(
            rubrica=dados["rubrica"], nivel=dados["nivel"],
            estado=dados.get("estado"), territorio=dados.get("territorio"),
            valor_alocado=dados["valor_alocado"], usuario=request.user,
            reserva_ugp=dados.get("reserva_ugp", False),
        )
        return Response(BudgetPoolSerializer(pool).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=BudgetPoolUpdateSerializer,
        responses={200: BudgetPoolSerializer},
    )
    def partial_update(self, request, pk=None):
        pool = get_object_or_404(BudgetPool, pk=pk)
        self._autorizar(request, nivel=pool.nivel, estado=pool.estado, territorio=pool.territorio)

        entrada = BudgetPoolUpdateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        pool = budget_service.atualizar_valor_alocado(
            pool,
            novo_valor=entrada.validated_data["valor_alocado"],
            usuario=request.user,
        )
        return Response(BudgetPoolSerializer(pool).data)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        pool = get_object_or_404(BudgetPool, pk=pk)
        self._autorizar(request, nivel=pool.nivel, estado=pool.estado, territorio=pool.territorio)
        budget_service.remover_pool(pool)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=BudgetTransactionSerializer(many=True))
    def transacoes(self, request, pk=None):
        pool = get_object_or_404(BudgetPool, pk=pk)
        escopo = budget_service.orcamento_detalhamento_scope(request.user)
        if escopo is not None and not BudgetPool.objects.filter(pk=pk).filter(escopo).exists():
            raise PermissionDenied("Você não tem acesso a esta alocação.")
        # BudgetTransaction.Meta.ordering já é -criado_em.
        qs = pool.transactions.all()
        return Response(BudgetTransactionSerializer(qs, many=True).data)


class SaldoConsultaView(APIView):
    """GET .../orcamento/saldo/ — contrato que o formulário de demanda do
    SGD consulta. Nível/localização resolvidos do perfil, sem parâmetro."""

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        parameters=[
            OpenApiParameter("rubrica", OpenApiTypes.STR, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("valor", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=True),
            OpenApiParameter(
                "meta", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False, deprecated=True,
                description="Ignorado: o saldo não depende da Meta.",
            ),
        ],
        responses=SaldoConsultaSerializer,
    )
    def get(self, request):
        if "meta" in request.query_params:
            logger.warning("orcamento.saldo.meta_depreciado user_id=%s", request.user.pk)
        query = SaldoConsultaQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        dados = query.validated_data

        nivel, estado_sigla, territorio = budget_service.resolver_nivel_do_usuario(request.user)
        check = budget_service.saldo_para_consulta(
            rubrica_slug=dados["rubrica"], nivel=nivel,
            estado_sigla=estado_sigla, territorio=territorio, valor=dados["valor"],
        )

        payload = {
            "disponivel": check.disponivel,
            "saldo": check.saldo,
            "nivel": nivel,
            "estado": check.pool.estado if check.pool else None,
            "territorio": check.pool.territorio if check.pool else None,
            "pool_id": check.pool.pk if check.pool else None,
            "motivo_bloqueio": check.motivo_bloqueio,
        }
        return Response(SaldoConsultaSerializer(payload).data)


class RemanejamentoView(APIView):
    """POST .../orcamento/remanejamentos/ — exceção da UGP pra furar a
    hierarquia normal de distribuição."""

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        request=RemanejamentoCreateSerializer,
        responses={201: BudgetTransactionSerializer(many=True)},
    )
    def post(self, request):
        if not budget_service.is_global_budget_user(request.user):
            raise PermissionDenied("Só UGP/Super Admin executam remanejamento.")

        entrada = RemanejamentoCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        debito, credito = budget_service.remanejar(
            origem=dados["origem_allocation"], destino=dados["destino_allocation"],
            valor=dados["valor"], usuario=request.user, justificativa=dados["justificativa"],
        )
        return Response(
            BudgetTransactionSerializer([debito, credito], many=True).data,
            status=status.HTTP_201_CREATED,
        )


class BudgetPainelView(APIView):
    """GET .../orcamento/painel/ — matriz Rubrica × Nível: uma linha por pool, com o
    semáforo e o id dele.

    Sem filtro, devolve os pools do escopo do perfil. `estado`/`territorio` fazem
    drill-down dentro do que o RBAC permite, ver `budget.services.resolver_nivel_painel`.
    `meta` não recorta o saldo: só acrescenta `valor_executado_meta` em cada linha."""

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        parameters=[
            OpenApiParameter("meta", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("rubrica", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("estado", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("territorio", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                "nivel", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False,
                enum=BudgetPool.Nivel.values,
            ),
        ],
        responses=BudgetPainelLinhaSerializer(many=True),
    )
    def get(self, request):
        query = BudgetPainelQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        dados = query.validated_data
        meta = dados.get("meta")
        rubrica = dados.get("rubrica")
        estado = dados.get("estado")
        territorio = dados.get("territorio")

        linhas = budget_service.matriz_orcamento_para_usuario(
            request.user,
            meta_id=meta.pk if meta else None,
            rubrica_slug=rubrica.slug if rubrica else None,
            estado_sigla=estado.sigla if estado else None,
            territorio_id=territorio.pk if territorio else None,
            nivel=dados.get("nivel"),
        )
        return Response(BudgetPainelLinhaSerializer(linhas, many=True).data)


class BudgetRubricaListView(generics.ListAPIView):
    """GET .../rubricas/ — catálogo de rubricas, sem valores de orçamento.

    Sem `ativo` devolve também as inativas: uma rubrica desativada ainda pode
    estar num mapeamento antigo, e a tela precisa mostrar o nome dela."""

    permission_classes = [IsAuthenticatedActiveAccess]
    serializer_class = BudgetRubricaSerializer
    queryset = BudgetRubrica.objects.order_by("nome", "id")
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = BudgetRubricaFilter


class SpendingLimitViewSet(viewsets.ViewSet):
    """GET/POST .../orcamento/limites/ e PATCH .../orcamento/limites/{id}/: padrão por perfil e
    sobrescrita individual. A lista traz os vigentes em `?data=`, ou hoje."""

    permission_classes = [IsSuperAdmin | IsUGP]

    @extend_schema(
        parameters=[SpendingLimitQuerySerializer],
        responses=SpendingLimitSerializer(many=True),
    )
    def list(self, request):
        query = SpendingLimitQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        dados = query.validated_data
        data = dados.get("data") or limites_service.hoje()
        limites = SpendingLimit.objects.select_related("rubrica", "perfil", "user").filter(
            periodo_inicio__lte=data, periodo_fim__gte=data,
        )
        for campo in ("escopo", "rubrica", "user", "perfil"):
            if campo in dados:
                limites = limites.filter(**{campo: dados[campo]})
        return Response(SpendingLimitSerializer(limites, many=True).data)

    @extend_schema(request=SpendingLimitCreateSerializer, responses={201: SpendingLimitSerializer})
    def create(self, request):
        entrada = SpendingLimitCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data
        if dados["escopo"] == SpendingLimit.Escopo.PERFIL:
            limite = limites_service.criar_padrao(
                perfil=dados["perfil"], rubrica=dados["rubrica"], valor_limite=dados["valor_limite"],
                justificativa=dados["justificativa"], usuario=request.user,
                periodo_inicio=dados.get("periodo_inicio"),
            )
        else:
            limite = limites_service.criar_sobrescrita(
                user=dados["user"], rubrica=dados["rubrica"], valor_limite=dados["valor_limite"],
                justificativa=dados["justificativa"], usuario=request.user,
                periodo_inicio=dados.get("periodo_inicio"), periodo_fim=dados.get("periodo_fim"),
            )
        return Response(SpendingLimitSerializer(limite).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=SpendingLimitUpdateSerializer, responses={200: SpendingLimitSerializer})
    def partial_update(self, request, pk=None):
        limite = get_object_or_404(SpendingLimit, pk=pk)
        entrada = SpendingLimitUpdateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data
        alterar = (
            limites_service.alterar_padrao if limite.escopo == SpendingLimit.Escopo.PERFIL
            else limites_service.alterar_sobrescrita
        )
        limite = alterar(limite.pk, valor_limite=dados["valor_limite"], justificativa=dados["justificativa"], usuario=request.user)
        return Response(SpendingLimitSerializer(limite).data)
