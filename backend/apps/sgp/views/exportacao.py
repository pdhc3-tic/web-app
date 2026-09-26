from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.models import ExportJob
from apps.sgp.serializers.exportacao import ExportJobCreateSerializer, ExportJobSerializer
from apps.sgp.services.access import resolver_escopo
from apps.sgp.services.exportacao import criar_exportacao, repetir_exportacao


def arquivo_response(conteudo: bytes, nome_arquivo: str, content_type: str) -> HttpResponse:
    response = HttpResponse(conteudo, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
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
        job = criar_exportacao(user=request.user, **serializer.validated_data)
        return Response(ExportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        job = self.get_object()
        if job.status != ExportJob.Status.CONCLUIDA:
            raise ErroComCodigo(
                "exportacao_nao_concluida",
                "A exportação ainda não terminou.",
                status_code=status.HTTP_409_CONFLICT,
                status=job.status,
            )
        if job.conteudo is None or (job.expira_em and job.expira_em <= timezone.now()):
            raise ErroComCodigo(
                "exportacao_expirada",
                "O arquivo desta exportação expirou. Gere uma nova exportação.",
                status_code=status.HTTP_410_GONE,
            )
        return arquivo_response(bytes(job.conteudo), job.nome_arquivo, job.content_type)

    @action(detail=True, methods=["post"])
    def repetir(self, request, pk=None):
        job = repetir_exportacao(self.get_object())
        return Response(ExportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
