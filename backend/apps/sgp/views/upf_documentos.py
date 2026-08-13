import re
from uuid import uuid4

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from apps.core.permissions import IsAuthenticatedActiveAccess
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.core.storage import StorageObjectNotFound, get_storage
from apps.sgp.models import UPF, UPFDocument
from apps.sgp.serializers import UPFDocumentCreateSerializer, UPFDocumentSerializer


ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}
CONTENT_TYPE_BY_EXTENSION = {
    ext: content_type
    for content_type, ext in ALLOWED_DOCUMENT_CONTENT_TYPES.items()
}
MAX_DOCUMENT_SIZE = 10_485_760


class UPFDocumentUploadURLSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size = serializers.IntegerField(min_value=1)

    def validate_content_type(self, value):
        if value not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Tipo de arquivo inválido. Envie PDF, JPEG ou PNG."
            )
        return value

    def validate_size(self, value):
        if value > MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError(
                "Arquivo excede o tamanho máximo de 10 MB."
            )
        return value


class UPFDocumentViewSet(viewsets.GenericViewSet):
    serializer_class = UPFDocumentSerializer
    permission_classes = [IsAuthenticatedActiveAccess]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_upf(self):
        if not hasattr(self, "_upf"):
            self._upf = get_object_or_404(
                self._accessible_upf_queryset(),
                pk=self.kwargs["upf_pk"],
            )
        return self._upf

    def _accessible_upf_queryset(self):
        qs = UPF.objects.select_related("municipio", "municipio__state", "territorio")
        user = self.request.user

        if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
            return qs

        if user_has_role(user, "articulador-estadual"):
            states = user_states(user)
            if not states:
                return qs.none()
            return qs.filter(municipio__state__sigla__in=states)

        if user_has_role(user, "adt-acr"):
            territories = user_territories(user)
            if not territories.exists():
                return qs.none()
            return qs.filter(territorio__in=territories)

        raise PermissionDenied("Você não tem acesso ao módulo SGP.")

    def get_queryset(self):
        return (
            UPFDocument.objects.filter(upf=self.get_upf())
            .select_related("upf", "criado_por")
            .order_by("-criado_em")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def upload_url(self, request, *args, **kwargs):
        upf = self.get_upf()
        serializer = UPFDocumentUploadURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content_type = serializer.validated_data["content_type"]
        size = serializer.validated_data["size"]
        ext = ALLOWED_DOCUMENT_CONTENT_TYPES[content_type]
        key = f"upfs/{upf.pk}/documentos/{uuid4()}.{ext}"
        expires_in = 300

        storage = get_storage()
        url = storage.generate_presigned_put(key, content_type, size, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)

        self._log_document_audit(
            "upload_document",
            upf=upf,
            valores_novos={
                "upf_id": upf.pk,
                "key": key,
                "content_type": content_type,
                "size": size,
            },
        )
        return Response(
            {"url": url, "key": key, "expires_in": expires_in},
            status=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        upf = self.get_upf()
        serializer = UPFDocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["key"]
        self._validate_document_key(key, upf)

        storage = get_storage()
        try:
            metadata = storage.head_object(key)
        except StorageObjectNotFound:
            return Response(
                {"detail": "Upload não confirmado — tente novamente"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tamanho_bytes = metadata.get("ContentLength") or 0
        content_type = metadata.get("ContentType") or self._content_type_from_key(key)
        self._validate_uploaded_object(content_type, tamanho_bytes)

        document = UPFDocument.objects.create(
            upf=upf,
            tipo=serializer.validated_data["tipo"],
            descricao=serializer.validated_data.get("descricao", ""),
            arquivo_key=key,
            nome_original=serializer.validated_data["nome_original"],
            content_type=content_type,
            tamanho_bytes=tamanho_bytes,
            data_documento=serializer.validated_data["data_documento"],
            criado_por=request.user,
        )

        self._log_document_audit(
            "create_document",
            upf=upf,
            document=document,
            valores_novos=self._document_snapshot(document),
        )
        return Response(
            self.get_serializer(document).data,
            status=status.HTTP_201_CREATED,
        )

    def download(self, request, *args, **kwargs):
        upf = self.get_upf()
        document = self.get_object()
        expires_in = 300
        storage = get_storage()
        url = storage.generate_presigned_get(document.arquivo_key, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)

        self._log_document_audit(
            "download_document",
            upf=upf,
            document=document,
            valores_novos={"document_id": document.pk, "key": document.arquivo_key},
        )
        return Response(
            {"url": url, "expires_in": expires_in},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        upf = self.get_upf()
        document = self.get_object()
        snapshot = self._document_snapshot(document)

        storage = get_storage()
        storage.delete_object(document.arquivo_key)
        document.delete()

        self._log_document_audit(
            "delete_document",
            upf=upf,
            document=document,
            valores_anteriores=snapshot,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _validate_document_key(self, key, upf):
        pattern = rf"^upfs/{upf.pk}/documentos/[0-9a-f-]{{36}}\.(pdf|jpg|png)$"
        if not re.match(pattern, key):
            raise serializers.ValidationError({"key": "Key de upload inválida."})

    def _content_type_from_key(self, key):
        ext = key.rsplit(".", 1)[-1]
        return CONTENT_TYPE_BY_EXTENSION.get(ext, "")

    def _validate_uploaded_object(self, content_type, size):
        if content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            raise serializers.ValidationError(
                {"content_type": "Tipo de arquivo inválido. Envie PDF, JPEG ou PNG."}
            )
        if size > MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError(
                {"tamanho_bytes": "Arquivo excede o tamanho máximo de 10 MB."}
            )

    def _document_snapshot(self, document):
        return {
            "document_id": document.pk,
            "upf_id": document.upf_id,
            "tipo": document.tipo,
            "descricao": document.descricao,
            "arquivo_key": document.arquivo_key,
            "nome_original": document.nome_original,
            "content_type": document.content_type,
            "tamanho_bytes": document.tamanho_bytes,
            "data_documento": document.data_documento.isoformat(),
        }

    def _log_document_audit(
        self,
        acao,
        upf,
        document=None,
        valores_anteriores=None,
        valores_novos=None,
    ):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="UPFDocument" if document else "UPF",
            entidade_id=str(document.pk if document else upf.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos=valores_novos or {},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
