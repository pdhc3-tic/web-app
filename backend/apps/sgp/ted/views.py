from uuid import uuid4

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import SAFE_METHODS, IsAuthenticatedActiveAccess, _log_denial
from apps.core.services.audit import log_audit
from apps.core.services.permissions import user_role_slugs
from apps.core.storage import get_storage
from apps.sgp.models import TED, TEDVersion, TEDVersionRubrica
from apps.sgp.serializers.common import UploadURLRespostaSerializer
from apps.sgp.ted import services as ted_service
from apps.sgp.ted.serializers import (
    TEDCreateSerializer,
    TEDDocumentoUploadURLSerializer,
    TEDSerializer,
    TEDUpdateSerializer,
    TEDVersaoNovaEntradaSerializer,
    TEDVersaoDetalheSerializer,
    TEDVersaoSerializer,
)

VALIDADE_DO_LINK_DE_UPLOAD = 300
PERFIS_QUE_LEEM_O_TED = ("super-admin", "ugp", "articulador-estadual", "fgd")
PERFIS_QUE_ALTERAM_O_TED = ("super-admin", "ugp")


class AcessoAoTED(BasePermission):
    """Monitoramento do TED na matriz do Core: total para UGP e Super Admin,
    parcial (só leitura) para Articulador e FGD."""

    def has_permission(self, request, view):
        perfis = PERFIS_QUE_LEEM_O_TED if request.method in SAFE_METHODS else PERFIS_QUE_ALTERAM_O_TED
        if user_role_slugs(request.user, perfis):
            return True
        _log_denial(request.user, view, reason=f"perfil fora de {perfis}")
        return False


def _rubricas_da_versao(caminho: str = "rubricas") -> Prefetch:
    return Prefetch(
        caminho,
        queryset=TEDVersionRubrica.objects.select_related("rubrica").order_by("rubrica__ordem", "rubrica__nome"),
    )


def _teds():
    return TED.objects.select_related("versao_vigente__registrado_por").prefetch_related(
        _rubricas_da_versao("versao_vigente__rubricas"),
    ).order_by("pk")


def _versoes():
    return TEDVersion.objects.select_related("registrado_por").prefetch_related(_rubricas_da_versao())


class TEDViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Cadastro do TED. O projeto tem um TED só, que nasce com a versão original;
    aditivos e prorrogações entram como novas versões."""

    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]
    serializer_class = TEDSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return _teds()

    @extend_schema(request=TEDCreateSerializer, responses={201: TEDSerializer})
    def create(self, request):
        entrada = TEDCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data
        ted = ted_service.cadastrar_ted(
            numero=dados["numero"], participes=dados["participes"], objeto=dados["objeto"],
            versao=dados["versao"], usuario=request.user, request=request,
        )
        return Response(TEDSerializer(_teds().get(pk=ted.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=TEDUpdateSerializer, responses={200: TEDSerializer})
    def partial_update(self, request, pk=None):
        ted = self.get_object()
        entrada = TEDUpdateSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        ted_service.atualizar_ted(ted, dados=entrada.validated_data, usuario=request.user, request=request)
        return Response(TEDSerializer(_teds().get(pk=ted.pk)).data)


class TEDVersaoListaView(generics.ListCreateAPIView):
    """Versões do TED, da original em diante. Nenhuma se altera nem se remove."""

    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]
    serializer_class = TEDVersaoSerializer

    def _ted(self):
        return get_object_or_404(TED, pk=self.kwargs["ted_pk"])

    def get_queryset(self):
        return _versoes().filter(ted=self._ted()).order_by("numero_versao")

    @extend_schema(request=TEDVersaoNovaEntradaSerializer, responses={201: TEDVersaoDetalheSerializer})
    def post(self, request, *args, **kwargs):
        entrada = TEDVersaoNovaEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        versao = ted_service.registrar_versao(
            self._ted(), versao=entrada.validated_data, usuario=request.user, request=request,
        )
        return Response(
            TEDVersaoDetalheSerializer(_versoes().get(pk=versao.pk), context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class TEDVersaoDetalheView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]
    serializer_class = TEDVersaoDetalheSerializer

    def get_object(self):
        return get_object_or_404(_versoes(), ted_id=self.kwargs["ted_pk"], pk=self.kwargs["pk"])


class TEDDocumentoUploadURLView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]

    @extend_schema(request=TEDDocumentoUploadURLSerializer, responses={200: UploadURLRespostaSerializer})
    def post(self, request):
        entrada = TEDDocumentoUploadURLSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        key = f"ted/documentos/{uuid4()}.pdf"
        url = get_storage().generate_presigned_put(
            key, entrada.validated_data["content_type"], entrada.validated_data["size"], VALIDADE_DO_LINK_DE_UPLOAD,
        )
        if url.startswith("/"):
            url = request.build_absolute_uri(url)
        log_audit(
            user=request.user, acao="TED.upload_document", modulo="sgp", entidade="TED", entidade_id=key,
            valores_novos={"key": key, "size": entrada.validated_data["size"]}, request=request,
        )
        return Response({"url": url, "key": key, "expires_in": VALIDADE_DO_LINK_DE_UPLOAD})
