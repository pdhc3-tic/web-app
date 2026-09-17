from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.services.permissions import user_has_role
from apps.sgp.models import BudgetAllocation, WorkPlanMeta
from apps.sgp.serializers_budget import (
    BudgetAllocationCreateSerializer,
    BudgetAllocationSerializer,
    BudgetAllocationUpdateSerializer,
    BudgetPainelLinhaSerializer,
    BudgetPainelQuerySerializer,
    BudgetTransactionSerializer,
    RemanejamentoCreateSerializer,
    SaldoConsultaQuerySerializer,
    SaldoConsultaSerializer,
)
from apps.sgp.services import budget as budget_service


class BudgetAllocationViewSet(viewsets.ViewSet):
    """`create` aninhada em `metas/{id}/orcamento/alocacoes/`,
    `partial_update`/`destroy` em `orcamento/alocacoes/{id}/`. Wiring
    manual em urls.py, sem router."""

    permission_classes = [IsAuthenticatedActiveAccess]

    def _autorizar(self, request, *, nivel, estado, territorio):
        user = request.user
        if budget_service.is_global_budget_user(user):
            return

        if nivel != BudgetAllocation.Nivel.TERRITORIAL:
            raise PermissionDenied(
                "Só UGP/Super Admin criam ou alteram alocações nacionais/estaduais."
            )
        if not user_has_role(user, "articulador-estadual"):
            raise PermissionDenied("Você não tem permissão para gerenciar alocações.")

        estados_do_territorio = set((territorio.estados if territorio else []) or [])
        if not estados_do_territorio & budget_service.allowed_states_for_user(user):
            raise PermissionDenied("Este território não pertence ao seu estado.")

    @extend_schema(
        request=BudgetAllocationCreateSerializer,
        responses={201: BudgetAllocationSerializer},
    )
    def create(self, request, meta_pk=None):
        meta = get_object_or_404(WorkPlanMeta, pk=meta_pk)
        entrada = BudgetAllocationCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        self._autorizar(
            request, nivel=dados["nivel"],
            estado=dados.get("estado"), territorio=dados.get("territorio"),
        )

        allocation = budget_service.criar_alocacao(
            meta=meta, rubrica=dados["rubrica"], nivel=dados["nivel"],
            estado=dados.get("estado"), territorio=dados.get("territorio"),
            valor_alocado=dados["valor_alocado"], usuario=request.user,
            reserva_ugp=dados.get("reserva_ugp", False),
        )
        return Response(
            BudgetAllocationSerializer(allocation).data, status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=BudgetAllocationUpdateSerializer,
        responses={200: BudgetAllocationSerializer},
    )
    def partial_update(self, request, pk=None):
        allocation = get_object_or_404(BudgetAllocation, pk=pk)
        self._autorizar(
            request, nivel=allocation.nivel,
            estado=allocation.estado, territorio=allocation.territorio,
        )

        entrada = BudgetAllocationUpdateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        allocation = budget_service.atualizar_valor_alocado(
            allocation,
            novo_valor=entrada.validated_data["valor_alocado"],
            usuario=request.user,
        )
        return Response(BudgetAllocationSerializer(allocation).data)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        allocation = get_object_or_404(BudgetAllocation, pk=pk)
        self._autorizar(
            request, nivel=allocation.nivel,
            estado=allocation.estado, territorio=allocation.territorio,
        )
        budget_service.remover_alocacao(allocation)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=BudgetTransactionSerializer(many=True))
    def transacoes(self, request, pk=None):
        allocation = get_object_or_404(BudgetAllocation, pk=pk)
        escopo = budget_service.orcamento_detalhamento_scope(request.user)
        if escopo is not None and not BudgetAllocation.objects.filter(pk=pk).filter(escopo).exists():
            raise PermissionDenied("Você não tem acesso a esta alocação.")
        # BudgetTransaction.Meta.ordering já é -criado_em.
        qs = allocation.transactions.all()
        return Response(BudgetTransactionSerializer(qs, many=True).data)


class SaldoConsultaView(APIView):
    """GET .../orcamento/saldo/ — contrato que o formulário de demanda do
    SGD consulta. Nível/localização resolvidos do perfil, sem parâmetro."""

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        parameters=[
            OpenApiParameter("meta", OpenApiTypes.INT, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("rubrica", OpenApiTypes.STR, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("valor", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=True),
        ],
        responses=SaldoConsultaSerializer,
    )
    def get(self, request):
        query = SaldoConsultaQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        dados = query.validated_data

        nivel, estado_sigla, territorio = budget_service.resolver_nivel_do_usuario(request.user)
        check = budget_service.saldo_para_consulta(
            meta_id=dados["meta"], rubrica_slug=dados["rubrica"], nivel=nivel,
            estado_sigla=estado_sigla, territorio=territorio, valor=dados["valor"],
        )

        payload = {
            "disponivel": check.disponivel,
            "saldo": check.saldo,
            "nivel": nivel,
            "estado": check.allocation.estado if check.allocation else None,
            "territorio": check.allocation.territorio if check.allocation else None,
            "allocation_id": check.allocation.pk if check.allocation else None,
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
    """GET .../orcamento/painel/ — matriz Meta × Rubrica com semáforo (§5.3.3).

    Nível exibido por linha (nacional/estadual/territorial) resolvido pelo perfil do
    usuário — `estado`/`territorio` fazem drill-down dentro do que o RBAC permite, ver
    `services.budget.resolver_nivel_painel`.

    Sem filtro: 5 queries (4 pro ADT/ACR — nível padrão territorial, sem "distribuído").
    Cada `meta`/`rubrica`/`estado`/`territorio` informado soma +1 query de validação de
    FK (`BudgetPainelQuerySerializer`); pior caso, 9 (Articulador Estadual com
    `territorio`, que paga +1 confirmando posse em `resolver_nivel_painel` — 8 pros
    demais perfis)."""

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        parameters=[
            OpenApiParameter("meta", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("rubrica", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("estado", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("territorio", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
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

        linhas = budget_service.painel_orcamento_para_usuario(
            request.user,
            meta_id=meta.pk if meta else None,
            rubrica_slug=rubrica.slug if rubrica else None,
            estado_sigla=estado.sigla if estado else None,
            territorio_id=territorio.pk if territorio else None,
        )
        return Response(BudgetPainelLinhaSerializer(linhas, many=True).data)
