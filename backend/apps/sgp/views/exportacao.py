from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgp.models import ExportJob
from apps.sgp.serializers.exportacao import ExportJobCreateSerializer, ExportJobSerializer
from apps.sgp.services.access import resolver_escopo
from apps.sgp.services.exportacao import (
    Arquivo,
    arquivo_do_job,
    criar_exportacao,
    repetir_exportacao,
    validar_filtros,
)


def arquivo_response(arquivo: Arquivo) -> HttpResponse:
    response = HttpResponse(arquivo.conteudo, content_type=arquivo.content_type)
    response["Content-Disposition"] = f'attachment; filename="{arquivo.nome}"'
    return response


class ExportacaoViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Exportações assíncronas do SGP. Cada usuário só enxerga as próprias —
    as de outro usuário respondem 404, sem revelar que existem."""

    serializer_class = ExportJobSerializer
    permission_classes = [IsAuthenticatedActiveAccess]

    def get_queryset(self):
        qs = ExportJob.objects.filter(solicitante=self.request.user)
        if self.action != "download":
            qs = qs.defer("conteudo")
        return qs

    def create(self, request):
        tipo, _ = resolver_escopo(request.user)
        if tipo == "negado":
            raise PermissionDenied("Você não tem acesso ao módulo SGP.")

        serializer = ExportJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        job = criar_exportacao(
            user=request.user,
            tipo=dados["tipo"],
            formato=dados["formato"],
            filtros=validar_filtros(dados["tipo"], dados["formato"], dados["filtros"]),
        )
        return Response(ExportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        return arquivo_response(arquivo_do_job(self.get_object()))

    @action(detail=True, methods=["post"])
    def repetir(self, request, pk=None):
        job = repetir_exportacao(self.get_object())
        return Response(ExportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
