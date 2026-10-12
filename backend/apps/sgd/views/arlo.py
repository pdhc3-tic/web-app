from uuid import uuid4

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsAuthenticatedActiveAccess, IsFGD, IsSuperAdmin, IsUGP
from apps.core.storage import StorageObjectNotFound, get_storage
from apps.core.utils import get_client_ip
from apps.sgd.models.arlo_import import ArloImport
from apps.sgd.serializers.arlo_import import ArloImportSerializer
from apps.sgd.services import arlo_export
from apps.sgd.tasks import process_arlo_import

ALLOWED_IMPORT_CONTENT_TYPES = {
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}
MAX_IMPORT_SIZE_BYTES = 10_485_760


class ArloUploadURLSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.ChoiceField(choices=list(ALLOWED_IMPORT_CONTENT_TYPES))
    size = serializers.IntegerField(min_value=1, max_value=MAX_IMPORT_SIZE_BYTES)


class ArloImportConfirmSerializer(serializers.Serializer):
    key = serializers.RegexField(r"^arlo/importacoes/[0-9a-f-]{36}\.(csv|xlsx)$")
    nome_original = serializers.CharField(max_length=255)


class ArloViewSet(viewsets.ViewSet):
    """Integração com o Arlo (SGD-RF24/RF31/RF32). Operada pela equipe da FGD;
    o histórico também é consultável por UGP e Super Admin."""

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticatedActiveAccess(), (IsFGD | IsSuperAdmin | IsUGP)()]
        return [IsAuthenticatedActiveAccess(), (IsFGD | IsSuperAdmin)()]

    def list(self, request):
        qs = ArloImport.objects.select_related("operado_por")
        tipo = request.query_params.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)
        return Response(ArloImportSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        return Response(ArloImportSerializer(get_object_or_404(ArloImport, pk=pk)).data)

    @action(detail=False, methods=["post"], url_path="exportar")
    def exportar(self, request):
        importacao, conteudo = arlo_export.exportar(usuario=request.user)
        resposta = HttpResponse(conteudo, content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = f'attachment; filename="{importacao.nome_original}"'
        resposta["X-Arlo-Operacao-Id"] = str(importacao.pk)
        return resposta

    @action(detail=False, methods=["post"], url_path="importar/upload-url")
    def importar_upload_url(self, request):
        serializer = ArloUploadURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content_type = serializer.validated_data["content_type"]
        size = serializer.validated_data["size"]
        key = f"arlo/importacoes/{uuid4()}.{ALLOWED_IMPORT_CONTENT_TYPES[content_type]}"
        expires_in = 300

        url = get_storage().generate_presigned_put(key, content_type, size, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)
        return Response({"url": url, "key": key, "expires_in": expires_in})

    @action(detail=False, methods=["post"], url_path="importar")
    def importar(self, request):
        serializer = ArloImportConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["key"]

        storage = get_storage()
        try:
            metadata = storage.head_object(key)
        except StorageObjectNotFound:
            return Response(
                {"detail": "Upload não confirmado — arquivo não encontrado no storage."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (metadata.get("ContentLength") or 0) > MAX_IMPORT_SIZE_BYTES:
            storage.delete_object(key)
            return Response(
                {"detail": f"Arquivo excede {MAX_IMPORT_SIZE_BYTES // (1024 * 1024)} MB. Arquivo removido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            importacao = ArloImport.objects.create(
                tipo=ArloImport.Tipo.IMPORTACAO, status=ArloImport.Status.PENDENTE,
                arquivo_key=key, arquivo_url=storage.get_public_url(key),
                nome_original=serializer.validated_data["nome_original"], operado_por=request.user,
                ip_origem=get_client_ip(request),
            )
            AuditLog.objects.create(
                user=request.user, acao="arlo_import.enfileirada", modulo="sgd", entidade="ArloImport",
                entidade_id=str(importacao.pk), valores_novos={"key": key},
                ip=request.META.get("REMOTE_ADDR"), user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            transaction.on_commit(lambda: process_arlo_import.delay(importacao.pk))
        return Response(ArloImportSerializer(importacao).data, status=status.HTTP_202_ACCEPTED)
