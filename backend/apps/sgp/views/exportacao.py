from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgp.models import ExportJob
from apps.sgp.serializers.exportacao import ExportJobCreateSerializer, ExportJobSerializer
from apps.sgp.services.exportacao import (
    Arquivo,
    arquivo_do_job,
    repetir_exportacao,
    solicitar_exportacao,
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
        serializer = ExportJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = solicitar_exportacao(user=request.user, **serializer.validated_data)
        return Response(ExportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        return arquivo_response(arquivo_do_job(self.get_object()))

    @action(detail=True, methods=["post"])
    def repetir(self, request, pk=None):
        job = repetir_exportacao(self.get_object())
        return Response(ExportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
