import re
from uuid import uuid4

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.storage import StorageObjectNotFound, get_storage
from apps.sgd.models.demand_document import DemandDocument
from apps.sgd.serializers.demand_document import DemandDocumentSerializer

ALLOWED_DOCUMENT_CONTENT_TYPES = {"application/pdf": "pdf"}
MAX_DOCUMENT_SIZE_BYTES = 10_485_760
MAX_DOCUMENTS_PER_DEMAND = 10


class DemandDocumentUploadURLSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size = serializers.IntegerField(min_value=1)

    def validate_content_type(self, value):
        if value not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            raise serializers.ValidationError("Formato inválido. Apenas PDF é aceito para documentos de demanda.")
        return value

    def validate_size(self, value):
        if value > MAX_DOCUMENT_SIZE_BYTES:
            raise serializers.ValidationError(
                f"Arquivo excede o tamanho máximo de {MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)} MB."
            )
        return value


class DemandDocumentConfirmSerializer(serializers.Serializer):
    key = serializers.CharField()
    tipo = serializers.ChoiceField(choices=DemandDocument._meta.get_field("tipo").choices)
    descricao = serializers.CharField(required=False, allow_blank=True, default="")
    nome_original = serializers.CharField(max_length=255)

    def validate_key(self, value):
        demand = self.context["demand"]
        pattern = rf"^demandas/{demand.pk}/documentos/[0-9a-f-]{{36}}\.pdf$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Key de upload inválida.")
        return value


class DemandDocumentMixin:
    """Pressupõe que `self.get_queryset()` devolve o queryset com o escopo de
    visibilidade já aplicado (`demand_visibility_scope`)."""

    def _get_demand_for_doc(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    @action(detail=True, methods=["get"], url_path="documentos")
    def documentos_list(self, request, pk=None):
        demand = self._get_demand_for_doc(pk)
        docs = DemandDocument.objects.filter(demanda=demand, ativo=True).order_by("-enviado_em")
        return Response(DemandDocumentSerializer(docs, many=True).data)

    @action(detail=True, methods=["post"], url_path="documentos/upload-url")
    def documentos_upload_url(self, request, pk=None):
        demand = self._get_demand_for_doc(pk)
        count = DemandDocument.objects.filter(demanda=demand, ativo=True).count()
        if count >= MAX_DOCUMENTS_PER_DEMAND:
            return Response(
                {"detail": f"Limite de {MAX_DOCUMENTS_PER_DEMAND} documentos por demanda atingido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DemandDocumentUploadURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content_type = serializer.validated_data["content_type"]
        size = serializer.validated_data["size"]
        ext = ALLOWED_DOCUMENT_CONTENT_TYPES[content_type]
        key = f"demandas/{demand.pk}/documentos/{uuid4()}.{ext}"
        expires_in = 300

        storage = get_storage()
        url = storage.generate_presigned_put(key, content_type, size, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)
        return Response({"url": url, "key": key, "expires_in": expires_in})

    @action(detail=True, methods=["post"], url_path="documentos/confirm")
    def documentos_confirm(self, request, pk=None):
        demand = self._get_demand_for_doc(pk)
        count = DemandDocument.objects.filter(demanda=demand, ativo=True).count()
        if count >= MAX_DOCUMENTS_PER_DEMAND:
            return Response(
                {"detail": f"Limite de {MAX_DOCUMENTS_PER_DEMAND} documentos por demanda atingido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DemandDocumentConfirmSerializer(data=request.data, context={"demand": demand})
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

        tamanho_bytes = metadata.get("ContentLength") or 0
        content_type = metadata.get("ContentType") or "application/pdf"
        if content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            storage.delete_object(key)
            return Response(
                {"detail": "Formato inválido detectado após upload. Apenas PDF é aceito."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if tamanho_bytes > MAX_DOCUMENT_SIZE_BYTES:
            storage.delete_object(key)
            return Response(
                {"detail": f"Documento excede {MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)} MB. Arquivo removido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc = DemandDocument.objects.create(
            demanda=demand, arquivo_key=key, arquivo_url=storage.get_public_url(key),
            tipo=serializer.validated_data["tipo"], descricao=serializer.validated_data.get("descricao", ""),
            nome_original=serializer.validated_data["nome_original"],
            content_type=content_type, tamanho_bytes=tamanho_bytes, enviado_por=request.user,
        )
        return Response(DemandDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path=r"documentos/(?P<doc_id>\d+)/download")
    def documentos_download(self, request, pk=None, doc_id=None):
        demand = self._get_demand_for_doc(pk)
        doc = get_object_or_404(DemandDocument, pk=doc_id, demanda=demand, ativo=True)
        expires_in = 300
        storage = get_storage()
        url = storage.generate_presigned_get(doc.arquivo_key, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)
        return Response({"url": url, "expires_in": expires_in})

    @action(detail=True, methods=["delete"], url_path=r"documentos/(?P<doc_id>\d+)")
    def documentos_delete(self, request, pk=None, doc_id=None):
        demand = self._get_demand_for_doc(pk)
        doc = get_object_or_404(DemandDocument, pk=doc_id, demanda=demand, ativo=True)
        doc.ativo = False
        doc.save(update_fields=["ativo"])
        return Response(status=status.HTTP_204_NO_CONTENT)
