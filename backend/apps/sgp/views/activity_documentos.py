"""
View de documentos vinculados a atividades do SGP.

Fluxo de upload em duas etapas (mesmo padrão UPFDocumentViewSet):
  1. POST /api/v1/sgp/atividades/{id}/documentos/upload-url/
  2. POST /api/v1/sgp/atividades/{id}/documentos/confirm/

Endpoints:
  GET    /api/v1/sgp/atividades/{id}/documentos/
  POST   /api/v1/sgp/atividades/{id}/documentos/upload-url/
  POST   /api/v1/sgp/atividades/{id}/documentos/confirm/
  GET    /api/v1/sgp/atividades/{id}/documentos/{doc_id}/download/
  DELETE /api/v1/sgp/atividades/{id}/documentos/{doc_id}/

Restrições:
  - Apenas PDF (application/pdf)
  - Máximo 10 MB por arquivo
  - Máximo 5 documentos ativos por atividade
"""
import re
from uuid import uuid4

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.storage import StorageObjectNotFound, get_storage
from apps.sgp.models.activity_document import ActivityDocument
from apps.sgp.serializers import ActivityDocumentSerializer


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf": "pdf",
}
MAX_DOCUMENT_SIZE_BYTES = 10_485_760    # 10 MB
MAX_DOCUMENTS_PER_ACTIVITY = 5


# ---------------------------------------------------------------------------
# Serializers internos
# ---------------------------------------------------------------------------

class ActivityDocumentUploadURLSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size = serializers.IntegerField(min_value=1)

    def validate_content_type(self, value):
        if value not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Formato inválido. Apenas PDF é aceito para documentos de atividade."
            )
        return value

    def validate_size(self, value):
        if value > MAX_DOCUMENT_SIZE_BYTES:
            raise serializers.ValidationError(
                f"Arquivo excede o tamanho máximo de "
                f"{MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)} MB."
            )
        return value


class ActivityDocumentConfirmSerializer(serializers.Serializer):
    key = serializers.CharField()
    tipo = serializers.ChoiceField(choices=ActivityDocument.TIPO_CHOICES)
    descricao = serializers.CharField(required=False, allow_blank=True, default="")
    nome_original = serializers.CharField(max_length=255)
    data_documento = serializers.DateField()

    def validate_key(self, value):
        activity = self.context["activity"]
        pattern = rf"^atividades/{activity.pk}/documentos/[0-9a-f-]{{36}}\.pdf$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Key de upload inválida.")
        return value


# ---------------------------------------------------------------------------
# Mixin adicionado ao ActivityViewSet
# ---------------------------------------------------------------------------

class ActivityDocumentMixin:
    """
    Mixin que adiciona os endpoints de documentos ao ActivityViewSet.
    Pressupõe que self.get_queryset() retorna o queryset com RLS aplicado.
    """

    def _get_activity_for_doc(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    # -- GET /atividades/{id}/documentos/ -----------------------------------

    @action(detail=True, methods=["get"], url_path="documentos")
    def documentos_list(self, request, pk=None):
        activity = self._get_activity_for_doc(pk)
        docs = ActivityDocument.objects.filter(
            activity=activity, ativo=True
        ).order_by("-criado_em")
        serializer = ActivityDocumentSerializer(docs, many=True)
        return Response(serializer.data)

    # -- POST /atividades/{id}/documentos/upload-url/ -----------------------

    @action(detail=True, methods=["post"], url_path="documentos/upload-url")
    def documentos_upload_url(self, request, pk=None):
        activity = self._get_activity_for_doc(pk)

        count = ActivityDocument.objects.filter(activity=activity, ativo=True).count()
        if count >= MAX_DOCUMENTS_PER_ACTIVITY:
            return Response(
                {
                    "detail": (
                        f"Limite de {MAX_DOCUMENTS_PER_ACTIVITY} documentos por atividade atingido. "
                        f"Remova um documento antes de adicionar outro."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ActivityDocumentUploadURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content_type = serializer.validated_data["content_type"]
        size = serializer.validated_data["size"]
        ext = ALLOWED_DOCUMENT_CONTENT_TYPES[content_type]
        key = f"atividades/{activity.pk}/documentos/{uuid4()}.{ext}"
        expires_in = 300

        storage = get_storage()
        url = storage.generate_presigned_put(key, content_type, size, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)

        self._log_doc_audit(
            "activity_document.upload_url",
            activity,
            valores_novos={
                "activity_id": activity.pk,
                "key": key,
                "content_type": content_type,
                "size": size,
            },
        )
        return Response(
            {"url": url, "key": key, "expires_in": expires_in},
            status=status.HTTP_200_OK,
        )

    # -- POST /atividades/{id}/documentos/confirm/ --------------------------

    @action(detail=True, methods=["post"], url_path="documentos/confirm")
    def documentos_confirm(self, request, pk=None):
        activity = self._get_activity_for_doc(pk)

        count = ActivityDocument.objects.filter(activity=activity, ativo=True).count()
        if count >= MAX_DOCUMENTS_PER_ACTIVITY:
            return Response(
                {
                    "detail": (
                        f"Limite de {MAX_DOCUMENTS_PER_ACTIVITY} documentos por atividade atingido."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ActivityDocumentConfirmSerializer(
            data=request.data,
            context={"activity": activity},
        )
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

        # Revalidar após upload efetivo
        if content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            storage.delete_object(key)
            return Response(
                {"detail": "Formato inválido detectado após upload. Apenas PDF é aceito."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if tamanho_bytes > MAX_DOCUMENT_SIZE_BYTES:
            storage.delete_object(key)
            return Response(
                {
                    "detail": (
                        f"Documento excede {MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)} MB "
                        f"após upload. Arquivo removido."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        arquivo_url = storage.get_public_url(key)
        doc = ActivityDocument.objects.create(
            activity=activity,
            arquivo_key=key,
            arquivo_url=arquivo_url,
            tipo=serializer.validated_data["tipo"],
            descricao=serializer.validated_data.get("descricao", ""),
            nome_original=serializer.validated_data["nome_original"],
            content_type=content_type,
            tamanho_bytes=tamanho_bytes,
            data_documento=serializer.validated_data["data_documento"],
            criado_por=request.user,
        )

        self._log_doc_audit(
            "activity_document.created",
            activity,
            valores_novos=self._doc_snapshot(doc),
        )
        return Response(
            ActivityDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )

    # -- GET /atividades/{id}/documentos/{doc_id}/download/ -----------------

    @action(
        detail=True,
        methods=["get"],
        url_path=r"documentos/(?P<doc_id>\d+)/download",
    )
    def documentos_download(self, request, pk=None, doc_id=None):
        activity = self._get_activity_for_doc(pk)
        doc = get_object_or_404(
            ActivityDocument, pk=doc_id, activity=activity, ativo=True
        )
        expires_in = 300
        storage = get_storage()
        url = storage.generate_presigned_get(doc.arquivo_key, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)

        self._log_doc_audit(
            "activity_document.download",
            activity,
            valores_novos={"doc_id": doc.pk, "key": doc.arquivo_key},
        )
        return Response({"url": url, "expires_in": expires_in})

    # -- DELETE /atividades/{id}/documentos/{doc_id}/ -----------------------

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"documentos/(?P<doc_id>\d+)",
    )
    def documentos_delete(self, request, pk=None, doc_id=None):
        activity = self._get_activity_for_doc(pk)
        doc = get_object_or_404(
            ActivityDocument, pk=doc_id, activity=activity, ativo=True
        )
        snapshot = self._doc_snapshot(doc)

        # Soft-delete — mantém arquivo no R2
        doc.ativo = False
        doc.save(update_fields=["ativo"])

        self._log_doc_audit(
            "activity_document.deleted",
            activity,
            valores_anteriores=snapshot,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _doc_snapshot(doc) -> dict:
        return {
            "doc_id": doc.pk,
            "activity_id": doc.activity_id,
            "tipo": doc.tipo,
            "nome_original": doc.nome_original,
            "arquivo_key": doc.arquivo_key,
            "tamanho_bytes": doc.tamanho_bytes,
            "data_documento": str(doc.data_documento),
            "ativo": doc.ativo,
        }

    def _log_doc_audit(self, acao, activity, valores_anteriores=None, valores_novos=None):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="ActivityDocument",
            entidade_id=str(activity.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos=valores_novos or {},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
