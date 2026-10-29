from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from apps.core.permissions import (
    IsADTInTerritory,
    IsArticuladorEstadual,
    IsAuthenticatedActiveAccess,
    IsFGD,
    IsSuperAdmin,
    IsUGP,
)
from apps.core.services.permissions import user_has_role, user_role_slugs, user_states
from apps.sgd.constants import PERFIS_NACIONAIS
from apps.sgd.serializers.remanejamento import (
    AtualizarRemanejamentoSerializer,
    BudgetIncreaseRequestSerializer,
    BudgetTransferSerializer,
    DecidirRemanejamentoSerializer,
    DevolverRemanejamentoSerializer,
    ParecerSerializer,
    SolicitarRecursoExtraSerializer,
)
from apps.sgd.services import recurso_extra as recurso_extra_service
from apps.sgp.models import BudgetIncreaseRequest, BudgetTransfer

PERFIS_DA_DECISAO = {"super-admin", "ugp"}


class RemanejamentoPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


def pedidos_visiveis(user):
    """UGP, FGD (leitura) e Super Admin veem tudo; o Articulador, os pedidos dos seus
    estados; os demais, só os próprios."""
    qs = BudgetIncreaseRequest.objects.select_related(
        "user", "rubrica", "parecer_por", "decidido_por", "activity__municipio__state",
    )
    perfis = user_role_slugs(user, ("super-admin", "ugp", "fgd", "articulador-estadual"))
    if perfis & PERFIS_NACIONAIS:
        return qs
    if "articulador-estadual" in perfis:
        return qs.filter(activity__municipio__state__sigla__in=user_states(user))
    return qs.filter(user=user)


def _exigir_dono(pedido, user) -> None:
    if pedido.user_id != user.pk and not user_has_role(user, "super-admin"):
        raise PermissionDenied("Só o solicitante pode alterar o pedido.")


class RecursoExtraMixin:
    """Atalho 'Solicitar recurso extra' da demanda bloqueada pelas duas travas (SGD §4.1)."""

    def get_permissions(self):
        if self.action == "solicitar_recurso_extra":
            return [IsAuthenticatedActiveAccess(), (IsADTInTerritory | IsSuperAdmin)()]
        return super().get_permissions()

    @action(detail=True, methods=["post"], url_path="solicitar-recurso-extra")
    def solicitar_recurso_extra(self, request, pk=None):
        demanda = get_object_or_404(self.get_queryset(), pk=pk)
        if demanda.solicitante_id != request.user.pk and not user_has_role(request.user, "super-admin"):
            raise PermissionDenied("Só o solicitante pode pedir recurso extra para a demanda.")
        entrada = SolicitarRecursoExtraSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        pedido = recurso_extra_service.criar(demanda=demanda, usuario=request.user, **entrada.validated_data)
        return Response(BudgetIncreaseRequestSerializer(pedido).data, status=status.HTTP_201_CREATED)


class RemanejamentoViewSet(viewsets.ViewSet):
    """Pedidos de recurso extra e a fila de decisão da UGP."""

    PERMISSAO_POR_ACAO = {
        "partial_update": (IsADTInTerritory | IsSuperAdmin),
        "submeter": (IsADTInTerritory | IsSuperAdmin),
        "parecer": (IsArticuladorEstadual | IsSuperAdmin),
        "devolver": (IsArticuladorEstadual | IsSuperAdmin),
        "decidir": (IsUGP | IsSuperAdmin),
        # Remanejamento é da coordenação; a FGD acompanha em leitura.
        "transferencias": (IsUGP | IsSuperAdmin | IsFGD),
    }

    def get_permissions(self):
        permissao = self.PERMISSAO_POR_ACAO.get(self.action)
        if permissao is None:
            return [IsAuthenticatedActiveAccess()]
        return [IsAuthenticatedActiveAccess(), permissao()]

    def _pedido(self, request, pk):
        return get_object_or_404(pedidos_visiveis(request.user), pk=pk)

    def list(self, request):
        qs = pedidos_visiveis(request.user)
        filtros = request.query_params.getlist("status")
        if not filtros and user_role_slugs(request.user, tuple(PERFIS_DA_DECISAO)):
            filtros = [BudgetIncreaseRequest.Status.COM_PARECER]
        if filtros and "todos" not in filtros:
            qs = qs.filter(status__in=filtros)
        demanda = request.query_params.get("demanda")
        if demanda:
            try:
                demanda_id = int(demanda)
            except ValueError:
                raise ValidationError({"demanda": "Informe o id numérico da demanda."})
            # `demanda_id` é texto no pedido: compara com o id normalizado ("041" → "41").
            qs = qs.filter(demanda_id=str(demanda_id))
        paginador = RemanejamentoPagination()
        pagina = paginador.paginate_queryset(qs.order_by("-criado_em", "-id"), request)
        return paginador.get_paginated_response(BudgetIncreaseRequestSerializer(pagina, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("demanda", OpenApiTypes.INT),
            OpenApiParameter("escopo", OpenApiTypes.STR, enum=sorted(BudgetTransfer.Escopo.values)),
            OpenApiParameter("rubrica", OpenApiTypes.STR, description="Slug da rubrica."),
        ],
        responses=BudgetTransferSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="transferencias")
    def transferencias(self, request):
        """Remanejamentos efetivados: o excedente autorizado na demanda (`pontual`) e o
        que cobriu o pool na decisão de recurso extra (`elevacao_limite`)."""
        qs = BudgetTransfer.objects.select_related(
            "allocation_origem__estado", "allocation_origem__territorio",
            "allocation_destino__estado", "allocation_destino__territorio", "allocation_destino__rubrica",
            "aprovado_por",
        )
        demanda = request.query_params.get("demanda")
        if demanda:
            try:
                qs = qs.filter(demanda_id=str(int(demanda)))
            except ValueError:
                raise ValidationError({"demanda": "Informe o id numérico da demanda."})
        escopo = request.query_params.get("escopo")
        if escopo:
            escopos = sorted(BudgetTransfer.Escopo.values)
            if escopo not in escopos:
                raise ValidationError({"escopo": f"Valor inválido. Esperado um de: {escopos}."})
            qs = qs.filter(escopo=escopo)
        rubrica = request.query_params.get("rubrica")
        if rubrica:
            qs = qs.filter(allocation_destino__rubrica__slug=rubrica)
        paginador = RemanejamentoPagination()
        pagina = paginador.paginate_queryset(qs.order_by("-criado_em", "-id"), request)
        return paginador.get_paginated_response(BudgetTransferSerializer(pagina, many=True).data)

    def retrieve(self, request, pk=None):
        return Response(BudgetIncreaseRequestSerializer(self._pedido(request, pk)).data)

    def partial_update(self, request, pk=None):
        pedido = self._pedido(request, pk)
        _exigir_dono(pedido, request.user)
        entrada = AtualizarRemanejamentoSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        pedido = recurso_extra_service.editar(pedido, usuario=request.user, **entrada.validated_data)
        return Response(BudgetIncreaseRequestSerializer(pedido).data)

    @action(detail=True, methods=["post"], url_path="submeter")
    def submeter(self, request, pk=None):
        pedido = self._pedido(request, pk)
        _exigir_dono(pedido, request.user)
        pedido = recurso_extra_service.submeter_pedido(pedido, usuario=request.user)
        return Response(BudgetIncreaseRequestSerializer(pedido).data)

    @action(detail=True, methods=["post"], url_path="parecer")
    def parecer(self, request, pk=None):
        pedido = self._pedido(request, pk)
        entrada = ParecerSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        pedido = recurso_extra_service.emitir_parecer(pedido, usuario=request.user, **entrada.validated_data)
        return Response(BudgetIncreaseRequestSerializer(pedido).data)

    @action(detail=True, methods=["post"], url_path="devolver")
    def devolver(self, request, pk=None):
        pedido = self._pedido(request, pk)
        entrada = DevolverRemanejamentoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        pedido = recurso_extra_service.devolver_pedido(pedido, usuario=request.user, **entrada.validated_data)
        return Response(BudgetIncreaseRequestSerializer(pedido).data)

    @action(detail=True, methods=["post"], url_path="decidir")
    def decidir(self, request, pk=None):
        pedido = self._pedido(request, pk)
        entrada = DecidirRemanejamentoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        resultado = recurso_extra_service.decidir(pedido, usuario=request.user, **entrada.validated_data)
        transferencia = resultado["transferencia"]
        return Response({
            **BudgetIncreaseRequestSerializer(resultado["pedido"]).data,
            "transferencia_id": transferencia.pk if transferencia else None,
        })
