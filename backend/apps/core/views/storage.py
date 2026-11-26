import mimetypes
import time
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_GET
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.storage.r2 import LocalStorage


class LocalStorageUploadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        parameters=[
            OpenApiParameter("key", OpenApiTypes.STR, required=True),
            OpenApiParameter("content_type", OpenApiTypes.STR, required=True),
            OpenApiParameter("size", OpenApiTypes.INT, required=True),
            OpenApiParameter("expires", OpenApiTypes.INT, required=True),
            OpenApiParameter("signature", OpenApiTypes.STR, required=True),
        ],
        request={"application/octet-stream": OpenApiTypes.BINARY},
        responses={
            200: OpenApiResponse(description="Arquivo gravado."),
            400: OpenApiResponse(description="URL, tamanho ou key inválidos."),
            403: OpenApiResponse(description="Assinatura expirada ou inválida."),
        },
    )
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


@require_GET
def local_storage_download(request):
    """Entrega um arquivo do storage local para quem tem a URL assinada e ainda válida.

    Em produção quem lê o disco é o nginx (X-Accel-Redirect para a location
    interna /protected-media/); em DEBUG, sem nginx, o próprio Django entrega.
    """
    key = request.GET.get("key", "")
    try:
        expires = int(request.GET.get("expires", ""))
    except ValueError:
        return HttpResponseBadRequest("URL de download inválida.")
    if not LocalStorage.verify_get_signature(key, expires, request.GET.get("signature", "")):
        return HttpResponseForbidden("URL de download expirada ou inválida.")

    try:
        path = LocalStorage()._path_for_key(key)
    except ValueError:
        return HttpResponseBadRequest("Key de storage inválida.")
    if not path.is_file():
        raise Http404

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if settings.DEBUG:
        response = FileResponse(path.open("rb"), content_type=content_type)
    else:
        response = HttpResponse(content_type=content_type)
        response["X-Accel-Redirect"] = "/protected-media/" + quote(key)
    response["Cache-Control"] = f"private, max-age={max(expires - int(time.time()), 0)}"
    return response
