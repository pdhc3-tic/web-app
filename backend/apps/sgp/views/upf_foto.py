import re
from uuid import uuid4

from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models.audit_log import AuditLog
from apps.core.storage import StorageObjectNotFound, get_storage


ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_PHOTO_SIZE = 5_242_880


class UploadURLSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size = serializers.IntegerField(min_value=1)

    def validate_content_type(self, value):
        if value not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Tipo de arquivo inválido. Envie JPEG, PNG ou WEBP."
            )
        return value

    def validate_size(self, value):
        if value > MAX_PHOTO_SIZE:
            raise serializers.ValidationError(
                "Arquivo excede o tamanho máximo de 5 MB."
            )
        return value


class ConfirmUploadSerializer(serializers.Serializer):
    key = serializers.CharField()

    def validate_key(self, value):
        upf = self.context["upf"]
        pattern = rf"^upfs/{upf.pk}/foto/[0-9a-f-]{{36}}\.(jpg|png|webp)$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Key de upload inválida.")
        return value


class UPFPhotoMixin:
    @action(detail=True, methods=["post"], url_path="foto/upload-url")
    def foto_upload_url(self, request, pk=None):
        upf = self.get_object()
        serializer = UploadURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content_type = serializer.validated_data["content_type"]
        size = serializer.validated_data["size"]
        ext = ALLOWED_CONTENT_TYPES[content_type]
        key = f"upfs/{upf.pk}/foto/{uuid4()}.{ext}"
        expires_in = 300

        storage = get_storage()
        url = storage.generate_presigned_put(key, content_type, size, expires_in)
        if url.startswith("/"):
            url = request.build_absolute_uri(url)

        self._log_photo_audit(
            "upload_photo",
            upf,
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

    @action(detail=True, methods=["post"], url_path="foto/confirm")
    def foto_confirm(self, request, pk=None):
        upf = self.get_object()
        serializer = ConfirmUploadSerializer(
            data=request.data,
            context={"upf": upf},
        )
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["key"]

        storage = get_storage()
        try:
            storage.head_object(key)
        except StorageObjectNotFound:
            return Response(
                {"detail": "Upload não confirmado — tente novamente"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_url = upf.foto_url
        new_url = storage.get_public_url(key)
        old_key = storage.get_key_from_url(old_url)
        if old_key and old_key != key:
            storage.delete_object(old_key)

        upf.foto_url = new_url
        upf.save(update_fields=["foto_url", "atualizado_em"])

        self._log_photo_audit(
            "confirm_photo",
            upf,
            valores_anteriores={"foto_url": old_url, "key": old_key},
            valores_novos={"foto_url": new_url, "key": key},
        )
        return Response({"foto_url": new_url}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], url_path="foto")
    def foto_delete(self, request, pk=None):
        upf = self.get_object()
        storage = get_storage()
        old_url = upf.foto_url
        old_key = storage.get_key_from_url(old_url)
        if old_key:
            storage.delete_object(old_key)

        upf.foto_url = ""
        upf.save(update_fields=["foto_url", "atualizado_em"])

        self._log_photo_audit(
            "delete_photo",
            upf,
            valores_anteriores={"foto_url": old_url, "key": old_key},
            valores_novos={"foto_url": ""},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _log_photo_audit(
        self,
        acao,
        upf,
        valores_anteriores=None,
        valores_novos=None,
    ):
        AuditLog.objects.create(
            user=self.request.user,
            acao=acao,
            modulo="sgp",
            entidade="UPF",
            entidade_id=str(upf.pk),
            valores_anteriores=valores_anteriores or {},
            valores_novos=valores_novos or {},
            ip=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
        )
