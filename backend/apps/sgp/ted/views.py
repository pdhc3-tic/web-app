from uuid import uuid4

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import SAFE_METHODS, IsAuthenticatedActiveAccess, _log_denial
from apps.core.services.audit import log_audit
from apps.core.services.permissions import user_role_slugs
from apps.core.storage import get_storage
from apps.core.models import Territory
from apps.sgp.models import TED, AdherenceIndex, TEDVersion, TEDVersionRubrica
from apps.sgp.budget.rls import visao_total
from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.serializers.common import UploadURLRespostaSerializer
from apps.sgp.services.apuracao import RecorteAtividades
from apps.sgp.services.exportacao import CONTENT_TYPES, Arquivo, gerar_arquivo
from apps.sgp.views.exportacao import arquivo_response
from apps.sgp.tasks import calculate_adherence_index
from apps.sgp.ted import execucao as execucao_service
from apps.sgp.ted import services as ted_service
from apps.sgp.ted.serializers import (
    ERRO_DO_RELATORIO,
    AderenciaExportacaoQuerySerializer,
    AderenciaHistoricoQuerySerializer,
    AderenciaLinhaSerializer,
    AderenciaQuerySerializer,
    AderenciaRespostaSerializer,
    AdherenceIndexSerializer,
    ComparativoQuerySerializer,
    ComparativoRespostaSerializer,
    ComposicaoPorRubricaSerializer,
    ComposicaoQuerySerializer,
    ComposicaoRespostaSerializer,
    CustoPorEntregaExportacaoQuerySerializer,
    CustoPorEntregaLinhaSerializer,
    CustoPorEntregaQuerySerializer,
    CustoPorEntregaRespostaSerializer,
    RastreabilidadeQuerySerializer,
    RastreabilidadeSerializer,
    VersaoDoRelatorioSerializer,
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


# ---------------------------------------------------------------------------
# Monitoramento: aderência, custo por entrega, rastreabilidade e comparativo
# ---------------------------------------------------------------------------

def _recorte(dados) -> RecorteAtividades:
    return RecorteAtividades(
        territorio_id=dados.get("territorio_id"),
        periodo_inicio=dados.get("periodo_inicio"),
        periodo_fim=dados.get("periodo_fim"),
    )


def _query(serializer_class, request):
    entrada = serializer_class(data=request.query_params)
    entrada.is_valid(raise_exception=True)
    return entrada.validated_data


def _paginado(view, request, linhas, serializer_class, **cabecalho) -> dict:
    paginador = LimitOffsetPagination()
    pagina = paginador.paginate_queryset(linhas, request, view=view)
    return {
        **cabecalho,
        "count": paginador.count, "next": paginador.get_next_link(), "previous": paginador.get_previous_link(),
        "results": serializer_class(pagina, many=True).data,
    }


def _cabecalho(execucao, *, por_territorio: bool) -> dict:
    return {
        "versao": VersaoDoRelatorioSerializer(execucao.versao).data,
        "acoes_fora_da_versao": execucao.acoes_fora_da_versao,
        "acoes_da_versao_fora_do_plano": execucao.acoes_da_versao_fora_do_plano,
        "acoes_manuais_fora_do_recorte": execucao.acoes_manuais_fora_do_recorte(por_territorio=por_territorio),
    }


def _arquivo(nome: str, formato: str, colunas, linhas, titulo: str):
    conteudo = gerar_arquivo(colunas, linhas, formato, titulo)
    carimbo = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
    return arquivo_response(Arquivo(
        conteudo=conteudo, nome=f"{nome}_{carimbo}.{formato}", content_type=CONTENT_TYPES[formato],
    ))


def _aderencia(request, dados):
    versao = execucao_service.versao_do_relatorio(versao_id=dados.get("versao"), data=dados.get("data"))
    por_territorio = dados["escopo"] == AdherenceIndex.Escopo.TERRITORIO
    execucao = execucao_service.execucao(request.user, versao, _recorte(dados), por_territorio=por_territorio)
    return execucao, execucao_service.aderencia(dados["escopo"], execucao), por_territorio


def _custo(request, dados):
    versao = execucao_service.versao_do_relatorio(versao_id=dados.get("versao"), data=dados.get("data"))
    por_territorio = dados["agrupar"] == "territorio"
    execucao = execucao_service.execucao(request.user, versao, _recorte(dados), por_territorio=por_territorio)
    linhas = execucao_service.custo_por_entrega(dados["agrupar"], execucao, indicador_id=dados.get("indicador_id"))
    return execucao, linhas, por_territorio


COLUNAS_DA_ADERENCIA = (
    ("referencia_id", "Referência"), ("nome", "Nome"),
    ("quantidade_planejada", "Quantidade planejada"), ("quantidade_realizada", "Quantidade realizada"),
    ("valor_planejado", "Valor planejado (R$)"), ("valor_executado", "Valor executado (R$)"),
    ("perc_fisico", "% físico"), ("perc_financeiro", "% financeiro"), ("indice", "Índice"), ("faixa", "Faixa"),
)

COLUNAS_DO_CUSTO = (
    ("referencia_id", "Referência"), ("nome", "Nome"), ("territorio_nome", "Território"),
    ("quantidade_realizada", "Quantidade realizada"), ("valor_executado", "Valor executado (R$)"),
    ("custo_unitario_previsto", "Custo unitário previsto (R$)"),
    ("custo_unitario_realizado", "Custo unitário realizado (R$)"),
    ("desvio_percentual", "Desvio (%)"), ("faixa", "Faixa"),
)


class AderenciaView(APIView):
    """Índice de aderência calculado agora, contra a versão pedida do TED, no recorte
    de quem consulta."""

    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]

    @extend_schema(
        parameters=[AderenciaQuerySerializer],
        responses={200: AderenciaRespostaSerializer, 400: ERRO_DO_RELATORIO},
    )
    def get(self, request):
        dados = _query(AderenciaQuerySerializer, request)
        execucao, linhas, por_territorio = _aderencia(request, dados)
        return Response(_paginado(
            self, request, linhas, AderenciaLinhaSerializer,
            escopo=dados["escopo"], **_cabecalho(execucao, por_territorio=por_territorio),
        ))


class AderenciaExportacaoView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]

    @extend_schema(
        parameters=[AderenciaExportacaoQuerySerializer],
        responses={(200, "text/csv"): OpenApiTypes.BINARY, 400: ERRO_DO_RELATORIO},
    )
    def get(self, request):
        dados = _query(AderenciaExportacaoQuerySerializer, request)
        _, linhas, _ = _aderencia(request, dados)
        return _arquivo(
            f"aderencia_{dados['escopo']}", dados["formato"], COLUNAS_DA_ADERENCIA,
            [vars(linha) for linha in linhas], "Aderência",
        )


class AderenciaHistoricoView(generics.ListAPIView):
    """Série mensal gravada pela task diária. A série é do projeto inteiro: o
    Articulador lê só a dos territórios que ficam inteiros nos seus estados."""

    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]
    serializer_class = AdherenceIndexSerializer

    @extend_schema(parameters=[AderenciaHistoricoQuerySerializer])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        dados = _query(AderenciaHistoricoQuerySerializer, self.request)
        qs = AdherenceIndex.objects.filter(escopo=dados["escopo"]).select_related("ted_versao")
        if dados.get("referencia_id"):
            qs = qs.filter(referencia_id=dados["referencia_id"])
        if dados.get("periodo_inicio"):
            qs = qs.filter(periodo_ref__gte=dados["periodo_inicio"].replace(day=1))
        if dados.get("periodo_fim"):
            qs = qs.filter(periodo_ref__lte=dados["periodo_fim"])
        qs = qs.order_by("referencia_id", "periodo_ref")
        estados = execucao_service.estados_do_escopo(self.request.user)
        if estados is None:
            return qs
        if dados["escopo"] != AdherenceIndex.Escopo.TERRITORIO:
            raise PermissionDenied("A série desse escopo é do projeto inteiro; consulte a dos seus territórios.")
        territorios = Territory.objects.filter(estados__contained_by=sorted(estados)).values_list("pk", flat=True)
        return qs.filter(referencia_id__in=list(territorios))


class AderenciaRecalculoView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]

    @extend_schema(request=None, responses={202: None})
    def post(self, request):
        transaction.on_commit(calculate_adherence_index.delay)
        return Response(status=status.HTTP_202_ACCEPTED)


class CustoPorEntregaView(APIView):
    """Custo unitário realizado contra o previsto na versão do TED, do maior desvio
    para o menor, para cima ou para baixo."""

    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]

    @extend_schema(
        parameters=[CustoPorEntregaQuerySerializer],
        responses={200: CustoPorEntregaRespostaSerializer, 400: ERRO_DO_RELATORIO},
    )
    def get(self, request):
        dados = _query(CustoPorEntregaQuerySerializer, request)
        execucao, linhas, por_territorio = _custo(request, dados)
        return Response(_paginado(
            self, request, linhas, CustoPorEntregaLinhaSerializer,
            agrupamento=dados["agrupar"],
            limiar_desvio_percentual=f"{execucao_service.limiar_do_desvio_de_custo():.2f}",
            **_cabecalho(execucao, por_territorio=por_territorio),
        ))


class CustoPorEntregaExportacaoView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]

    @extend_schema(
        parameters=[CustoPorEntregaExportacaoQuerySerializer],
        responses={(200, "text/csv"): OpenApiTypes.BINARY, 400: ERRO_DO_RELATORIO},
    )
    def get(self, request):
        dados = _query(CustoPorEntregaExportacaoQuerySerializer, request)
        _, linhas, _ = _custo(request, dados)
        return _arquivo(
            f"custo_por_entrega_{dados['agrupar']}", dados["formato"], COLUNAS_DO_CUSTO,
            [vars(linha) for linha in linhas], "Custo por entrega",
        )


class ComposicaoPorRubricaView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]

    @extend_schema(
        parameters=[ComposicaoQuerySerializer],
        responses={200: ComposicaoRespostaSerializer, 400: ERRO_DO_RELATORIO},
    )
    def get(self, request):
        dados = _query(ComposicaoQuerySerializer, request)
        linhas = execucao_service.composicao_por_rubrica(
            request.user, acao_id=dados.get("acao_id"), indicador_id=dados.get("indicador_id"),
        )
        return Response(_paginado(self, request, linhas, ComposicaoPorRubricaSerializer))


class RastreabilidadeView(generics.ListAPIView):
    """Da rubrica à evidência de campo: cada solicitação paga com a demanda, a
    Atividade, a cadeia do Plano de Trabalho e as evidências. O recorte é o estado
    da Atividade, como no custo e na composição; por isso a leitura do SGD, que o
    RLS recorta pelo solicitante, roda em visão total."""

    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]
    serializer_class = RastreabilidadeSerializer

    @extend_schema(parameters=[RastreabilidadeQuerySerializer], responses={400: ERRO_DO_RELATORIO})
    def get(self, request, *args, **kwargs):
        with visao_total():
            return super().get(request, *args, **kwargs)

    def get_queryset(self):
        dados = _query(RastreabilidadeQuerySerializer, self.request)
        return execucao_service.rastreabilidade(
            self.request.user, rubrica=dados["rubrica"], recorte=_recorte(dados), acao_id=dados.get("acao_id"),
        )


class ComparativoDeVersoesView(APIView):
    """O que mudou entre duas versões do TED em quantidade, valor e prazo, por Meta,
    Submeta e Ação."""

    permission_classes = [IsAuthenticatedActiveAccess, AcessoAoTED]

    @extend_schema(
        parameters=[ComparativoQuerySerializer],
        responses={200: ComparativoRespostaSerializer, 400: ERRO_DO_RELATORIO},
    )
    def get(self, request, ted_pk):
        dados = _query(ComparativoQuerySerializer, request)
        versoes = {v.pk: v for v in TEDVersion.objects.filter(ted_id=ted_pk, pk__in=[dados["de"], dados["para"]])}
        if dados["de"] not in versoes or dados["para"] not in versoes:
            raise ErroComCodigo("versao_invalida", "Versão do TED não encontrada.")
        de, para = versoes[dados["de"]], versoes[dados["para"]]
        return Response(ComparativoRespostaSerializer({
            "de": de, "para": para, "diferencas": execucao_service.comparar_versoes(de, para),
        }).data)
