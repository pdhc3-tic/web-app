from django.core.exceptions import RequestDataTooBig
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.storage.r2 import LocalStorage


class LocalStorageUploadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def put(self, request):
        key = request.query_params.get("key", "")
        content_type = request.query_params.get("content_type", "")
        size = request.query_params.get("size", "")
        expires = request.query_params.get("expires", "")
        signature = request.query_params.get("signature", "")

        try:
            size_int = int(size)
            expires_int = int(expires)
        except (TypeError, ValueError):
            return Response(
                {"detail": "URL de upload local inválida."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not LocalStorage.verify_signature(
            key, content_type, size_int, expires_int, signature
        ):
            return Response(
                {"detail": "URL de upload local expirada ou inválida."},
                status=status.HTTP_403_FORBIDDEN,
            )

        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                if int(content_length) > size_int:
                    return Response(
                        {"detail": "Arquivo excede o tamanho autorizado."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except ValueError:
                return Response(
                    {"detail": "Tamanho do arquivo inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            body = request._request.body
        except RequestDataTooBig:
            return Response(
                {"detail": "Arquivo excede o tamanho autorizado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(body) > size_int:
            return Response(
                {"detail": "Arquivo excede o tamanho autorizado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            LocalStorage().save_from_bytes(key, body)
        except ValueError:
            return Response(
                {"detail": "Key de storage inválida."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_200_OK)
