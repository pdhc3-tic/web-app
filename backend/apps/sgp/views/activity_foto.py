"""
View de fotos vinculadas a atividades do SGP.

Fluxo de upload em duas etapas (mesmo padrão UPFPhotoMixin):
  1. POST /api/v1/sgp/atividades/{id}/fotos/upload-url/
     → retorna URL presignada PUT para o R2
  2. POST /api/v1/sgp/atividades/{id}/fotos/confirm/
     → confirma o upload, persiste ActivityPhoto e retorna o objeto

Endpoints adicionais:
  GET    /api/v1/sgp/atividades/{id}/fotos/          → lista fotos ativas ordenadas
  DELETE /api/v1/sgp/atividades/{id}/fotos/{foto_id}/ → soft-delete
  PATCH  /api/v1/sgp/atividades/{id}/fotos/reordenar/ → reordena (drag-and-drop)
"""
import re
from uuid import uuid4

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.storage import StorageObjectNotFound, get_storage
from apps.sgp.models import Activity
from apps.sgp.models.activity_photo import ActivityPhoto
from apps.sgp.serializers import ActivityPhotoSerializer


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ALLOWED_PHOTO_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_PHOTO_SIZE_BYTES = 819_200        # 800 KB
MAX_PHOTOS_PER_ACTIVITY = 10


# ---------------------------------------------------------------------------
# Serializers internos
# ---------------------------------------------------------------------------

class ActivityPhotoUploadURLSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size = serializers.IntegerField(min_value=1)
    legenda = serializers.CharField(required=False, allow_blank=True, default="")
    data_hora_captura = serializers.DateTimeField(required=False, allow_null=True, default=None)
    latitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, required=False, allow_null=True, default=None
    )
    longitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, required=False, allow_null=True, default=None
    )

    def validate_content_type(self, value):
        if value not in ALLOWED_PHOTO_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Formato inválido. Envie JPEG, PNG ou WEBP."
            )
        return value

    def validate_size(self, value):
        if value > MAX_PHOTO_SIZE_BYTES:
            raise serializers.ValidationError(
                f"Arquivo excede o tamanho máximo de "
                f"{MAX_PHOTO_SIZE_BYTES // 1024} KB. "
                f"Comprima a imagem antes do upload."
            )
        return value


class ActivityPhotoConfirmSerializer(serializers.Serializer):
    key = serializers.CharField()
    legenda = serializers.CharField(required=False, allow_blank=True, default="")
    data_hora_captura = serializers.DateTimeField(required=False, allow_null=True, default=None)
    latitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, required=False, allow_null=True, default=None
    )
    longitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, required=False, allow_null=True, default=None
    )

    def validate_key(self, value):
        activity = self.context["activity"]
        pattern = rf"^atividades/{activity.pk}/fotos/[0-9a-f-]{{36}}\.(jpg|png|webp)$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Key de upload inválida.")
        return value


class ActivityPhotoReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
    )


# ---------------------------------------------------------------------------
# Mixin adicionado ao ActivityViewSet
# ---------------------------------------------------------------------------

class ActivityPhotoMixin:
    """
    Mixin que adiciona os endpoints de foto ao ActivityViewSet.
    Pressupõe que self.get_object() retorna uma Activity.
    """

    def _get_activity_for_upload(self, pk):
        """Retorna a atividade respeitando o queryset (RLS) do ViewSet."""
        return get_object_or_404(self.get_queryset(), pk=pk)

    # -- GET /atividades/{id}/fotos/ ----------------------------------------

    @action(detail=True, methods=["get"], url_path="fotos")
    def fotos_list(self, request, pk=None):
        activity = self._get_activity_for_upload(pk)
        fotos = ActivityPhoto.objects.filter(
            activity=activity, ativa=True
        ).order_by("ordem", "criado_em")
        serializer = ActivityPhotoSerializer(fotos, many=True)
        return Response(serializer.data)

    # -- POST /atividades/{id}/fotos/upload-url/ ----------------------------

    @action(detail=True, methods=["post"], url_path="fotos/upload-url")
    def fotos_upload_url(self, request, pk=None):
        activity = self._get_activity_for_upload(pk)

        # Limite de 10 fotos ativas
        count = ActivityPhoto.objects.filter(activity=activity, ativa=True).count()
        if count >= MAX_PHOTOS_PER_ACTIVITY:
            return Response(
                {
                    "detail": (
                        f"Limite de {MAX_PHOTOS_PER_ACTIVITY} fotos por atividade atingido. "
                        f"Remova uma foto antes de adicionar outra."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ActivityPhotoUploadURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content_type = serializer.validated_data["content_type"]
        size = serializer.validated_data["size"]
        ext = ALLOWED_PHOTO_CONTENT_TYPES[content_type]
        key = f"atividades/{activity.pk}/fotos/{uuid4()}.{ext}"
        expires_in = 300

        storage = get_storage()
        url = storage.generate_presigned_put(key, content_type, size, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)

        self._log_foto_audit(
            "activity_photo.upload_url",
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

    # -- POST /atividades/{id}/fotos/confirm/ --------------------------------

    @action(detail=True, methods=["post"], url_path="fotos/confirm")
    def fotos_confirm(self, request, pk=None):
        activity = self._get_activity_for_upload(pk)

        # Verificar limite antes de confirmar
        count = ActivityPhoto.objects.filter(activity=activity, ativa=True).count()
        if count >= MAX_PHOTOS_PER_ACTIVITY:
            return Response(
                {
                    "detail": (
                        f"Limite de {MAX_PHOTOS_PER_ACTIVITY} fotos por atividade atingido."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ActivityPhotoConfirmSerializer(
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
        content_type = metadata.get("ContentType") or "image/jpeg"

        # Validar tipo e tamanho após o upload
        if content_type not in ALLOWED_PHOTO_CONTENT_TYPES:
            storage.delete_object(key)
            return Response(
                {"detail": "Formato inválido detectado após upload. Arquivo removido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if tamanho_bytes > MAX_PHOTO_SIZE_BYTES:
            storage.delete_object(key)
            return Response(
                {
                    "detail": (
                        f"Arquivo excede {MAX_PHOTO_SIZE_BYTES // 1024} KB após upload. "
                        f"Comprima a imagem e tente novamente. Arquivo removido."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calcular a próxima ordem (max + 1)
        ultima_ordem = (
            ActivityPhoto.objects.filter(activity=activity, ativa=True)
            .order_by("-ordem")
            .values_list("ordem", flat=True)
            .first()
        )
        proxima_ordem = (ultima_ordem + 1) if ultima_ordem is not None else 0

        arquivo_url = storage.get_public_url(key)
        data_hora_captura = (
            serializer.validated_data.get("data_hora_captura") or timezone.now()
        )

        foto = ActivityPhoto.objects.create(
            activity=activity,
            arquivo_key=key,
            arquivo_url=arquivo_url,
            legenda=serializer.validated_data.get("legenda", ""),
            data_hora_captura=data_hora_captura,
            latitude=serializer.validated_data.get("latitude"),
            longitude=serializer.validated_data.get("longitude"),
            ordem=proxima_ordem,
            content_type=content_type,
            tamanho_bytes=tamanho_bytes,
            criado_por=request.user,
        )

        self._log_foto_audit(
            "activity_photo.created",
            activity,
            valores_novos={
                "foto_id": foto.pk,
                "activity_id": activity.pk,
                "key": key,
                "ordem": foto.ordem,
            },
        )
        return Response(
            ActivityPhotoSerializer(foto).data,
            status=status.HTTP_201_CREATED,
        )

    # -- DELETE /atividades/{id}/fotos/{foto_id}/ ----------------------------

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"fotos/(?P<foto_id>\d+)",
    )
    def fotos_delete(self, request, pk=None, foto_id=None):
        activity = self._get_activity_for_upload(pk)
        foto = get_object_or_404(
            ActivityPhoto, pk=foto_id, activity=activity, ativa=True
        )

        snapshot = {
            "foto_id": foto.pk,
            "activity_id": activity.pk,
            "key": foto.arquivo_key,
            "ordem": foto.ordem,
        }

        # Soft-delete — mantém o arquivo no R2 por ora (pode ser GC depois)
        foto.ativa = False
        foto.save(update_fields=["ativa"])

        self._log_foto_audit(
            "activity_photo.deleted",
            activity,
            valores_anteriores=snapshot,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- PATCH /atividades/{id}/fotos/reordenar/ ----------------------------

    @action(detail=True, methods=["patch"], url_path="fotos/reordenar")
    def fotos_reordenar(self, request, pk=None):
        """
        Recebe {"ids": [3, 1, 2]} — a posição na lista define a nova ordem.
        O primeiro ID (índice 0) recebe ordem=0 e torna-se a foto de capa.
        """
        activity = self._get_activity_for_upload(pk)

        serializer = ActivityPhotoReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids_ordenados = serializer.validated_data["ids"]

        # Validar que todos os IDs pertencem a esta atividade
        fotos_ativas = ActivityPhoto.objects.filter(
            activity=activity, ativa=True, pk__in=ids_ordenados
        )
        ids_validos = set(fotos_ativas.values_list("pk", flat=True))
        ids_enviados = set(ids_ordenados)

        if ids_enviados != ids_validos:
            invalidos = ids_enviados - ids_validos
            return Response(
                {
                    "detail": f"IDs inválidos ou não pertencentes a esta atividade: {sorted(invalidos)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Persistir nova ordem usando bulk_update
        foto_map = {f.pk: f for f in fotos_ativas}
        fotos_para_salvar = []
        for nova_ordem, foto_id in enumerate(ids_ordenados):
            foto = foto_map[foto_id]
            foto.ordem = nova_ordem
            fotos_para_salvar.append(foto)

        ActivityPhoto.objects.bulk_update(fotos_para_salvar, ["ordem"])

        self._log_foto_audit(
            "activity_photo.reordered",
            activity,
            valores_novos={"ids_ordenados": ids_ordenados},
        )

        # Retornar fotos com a nova ordenação
        fotos_atualizadas = ActivityPhoto.objects.filter(
            activity=activity, ativa=True
        ).order_by("ordem", "criado_em")
        return Response(
            ActivityPhotoSerializer(fotos_atualizadas, many=True).data,
            status=status.HTTP_200_OK,
        )

    # -- Audit helper --------------------------------------------------------

    def _log_foto_audit(self, acao, activity, valores_anteriores=None, valores_novos=None):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="ActivityPhoto",
            entidade_id=str(activity.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos=valores_novos or {},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
