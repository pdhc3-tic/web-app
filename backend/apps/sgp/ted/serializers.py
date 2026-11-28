from drf_spectacular.utils import OpenApiResponse, extend_schema_field, inline_serializer
from rest_framework import serializers

from apps.core.serializers import UsuarioRefSerializer
from apps.core.storage import get_storage
from apps.sgp.budget.serializers import BudgetRubricaNestedSerializer
from apps.sgp.models import TED, AdherenceIndex, BudgetRubrica, TEDVersion, TEDVersionRubrica
from apps.sgp.serializers.common import PlanoTrabalhoSerializer, plano_trabalho_da_acao
from apps.sgp.ted.execucao import AGRUPAMENTOS_DE_CUSTO, FaixaDeCusto
from apps.sgp.ted.services import erro_no_documento

VALIDADE_DO_LINK_DO_DOCUMENTO = 300
TIPOS_DE_NOVA_VERSAO = [
    (TEDVersion.Tipo.ADITIVO.value, TEDVersion.Tipo.ADITIVO.label),
    (TEDVersion.Tipo.PRORROGACAO.value, TEDVersion.Tipo.PRORROGACAO.label),
]


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

class TEDVersaoRubricaEntradaSerializer(serializers.Serializer):
    rubrica = serializers.PrimaryKeyRelatedField(queryset=BudgetRubrica.objects.all())
    valor_aprovado = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class TEDVersaoOriginalEntradaSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=False, allow_blank=True, default="")
    vigencia_inicio = serializers.DateField()
    vigencia_fim = serializers.DateField()
    valor_global = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    rubricas = TEDVersaoRubricaEntradaSerializer(many=True, allow_empty=False)
    documento_key = serializers.CharField(
        help_text="Chave devolvida por `POST /sgp/ted/documentos/upload-url/` depois do envio do PDF.",
    )

    def validate_rubricas(self, value):
        ids = [item["rubrica"].pk for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Cada rubrica aparece uma vez só.")
        return value

    def validate(self, attrs):
        if attrs["vigencia_fim"] <= attrs["vigencia_inicio"]:
            raise serializers.ValidationError({"vigencia_fim": "O fim da vigência precisa ser depois do início."})
        return attrs


class TEDVersaoNovaEntradaSerializer(TEDVersaoOriginalEntradaSerializer):
    tipo = serializers.ChoiceField(choices=TIPOS_DE_NOVA_VERSAO)
    motivo = serializers.CharField()


class TEDCreateSerializer(serializers.Serializer):
    numero = serializers.CharField(max_length=100)
    participes = serializers.ListField(
        child=serializers.CharField(max_length=255), allow_empty=False,
    )
    objeto = serializers.CharField(required=False, allow_blank=True, default="")
    versao = TEDVersaoOriginalEntradaSerializer(help_text="Versão original do TED.")


CAMPOS_DA_VERSAO = ("valor_global", "vigencia_inicio", "vigencia_fim", "versao_vigente")


class TEDUpdateSerializer(serializers.Serializer):
    """Só a identificação. Valor global e vigência vêm da versão vigente: mandá-los
    aqui é recusado, para o cliente não achar que mudou o que não mudou."""

    numero = serializers.CharField(max_length=100, required=False)
    participes = serializers.ListField(
        child=serializers.CharField(max_length=255), allow_empty=False, required=False,
    )
    objeto = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        enviados = [campo for campo in CAMPOS_DA_VERSAO if campo in self.initial_data]
        if enviados:
            raise serializers.ValidationError({
                campo: "Muda só com o registro de uma nova versão do TED." for campo in enviados
            })
        return attrs


class TEDDocumentoUploadURLSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        erro = erro_no_documento(attrs["content_type"], attrs["size"])
        if erro:
            campo, mensagem = erro
            raise serializers.ValidationError({campo: mensagem})
        return attrs


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

class TEDVersaoRubricaSerializer(serializers.ModelSerializer):
    rubrica = BudgetRubricaNestedSerializer(read_only=True)

    class Meta:
        model = TEDVersionRubrica
        fields = ["rubrica", "valor_aprovado"]
        read_only_fields = fields


class TEDVersaoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    registrado_por = UsuarioRefSerializer(read_only=True, allow_null=True)
    rubricas = TEDVersaoRubricaSerializer(many=True, read_only=True)

    class Meta:
        model = TEDVersion
        fields = [
            "id", "numero_versao", "tipo", "tipo_display", "motivo",
            "vigencia_inicio", "vigencia_fim", "valor_global", "rubricas",
            "registrado_por", "registrado_em",
        ]
        read_only_fields = fields


class TEDVersaoDetalheSerializer(TEDVersaoSerializer):
    documento_url = serializers.SerializerMethodField()

    class Meta(TEDVersaoSerializer.Meta):
        fields = TEDVersaoSerializer.Meta.fields + ["plano_snapshot", "documento_url"]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_documento_url(self, obj):
        url = get_storage().generate_presigned_get(obj.documento_key, VALIDADE_DO_LINK_DO_DOCUMENTO)
        request = self.context.get("request")
        if url.startswith("/") and request is not None:
            url = request.build_absolute_uri(url)
        return url


class TEDSerializer(serializers.ModelSerializer):
    versao_vigente = TEDVersaoSerializer(read_only=True, allow_null=True)

    class Meta:
        model = TED
        fields = [
            "id", "numero", "participes", "objeto", "valor_global",
            "vigencia_inicio", "vigencia_fim", "versao_vigente", "criado_em",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Monitoramento: aderência, custo por entrega, rastreabilidade e comparativo
# ---------------------------------------------------------------------------

class ErroDoRelatorioSerializer(serializers.Serializer):
    code = serializers.CharField(help_text="Ex.: `ted_nao_cadastrado`, `versao_invalida`, `sem_versao_na_data`.")
    message = serializers.CharField()


ERRO_DO_RELATORIO = OpenApiResponse(
    response=ErroDoRelatorioSerializer,
    description="Parâmetro inválido (`{campo: [mensagem]}`) ou erro com código (`{code, message}`).",
)

FORMATOS_DE_EXPORTACAO = [("csv", "CSV"), ("xlsx", "XLSX")]


class _RecorteQuerySerializer(serializers.Serializer):
    territorio_id = serializers.IntegerField(min_value=1, required=False)
    periodo_inicio = serializers.DateField(required=False, help_text="Pela data de término da Atividade.")
    periodo_fim = serializers.DateField(required=False)

    def validate(self, attrs):
        inicio, fim = attrs.get("periodo_inicio"), attrs.get("periodo_fim")
        if inicio and fim and inicio > fim:
            raise serializers.ValidationError({"periodo_inicio": "Não pode ser depois de periodo_fim."})
        return attrs


class _VersaoQuerySerializer(_RecorteQuerySerializer):
    versao = serializers.IntegerField(
        min_value=1, required=False, help_text="Id da versão do TED. Sem ela, vale a vigente.",
    )
    data = serializers.DateField(required=False, help_text="Usa a versão vigente nessa data.")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("versao") and attrs.get("data"):
            raise serializers.ValidationError({"data": "Informe a versão ou a data, não as duas."})
        return attrs


class AderenciaQuerySerializer(_VersaoQuerySerializer):
    escopo = serializers.ChoiceField(choices=AdherenceIndex.Escopo.choices)


class AderenciaExportacaoQuerySerializer(AderenciaQuerySerializer):
    formato = serializers.ChoiceField(choices=FORMATOS_DE_EXPORTACAO, default="csv")


class AderenciaHistoricoQuerySerializer(serializers.Serializer):
    escopo = serializers.ChoiceField(choices=AdherenceIndex.Escopo.choices)
    referencia_id = serializers.IntegerField(min_value=1, required=False)
    periodo_inicio = serializers.DateField(required=False, help_text="Mês inicial (qualquer dia do mês).")
    periodo_fim = serializers.DateField(required=False, help_text="Mês final (qualquer dia do mês).")

    def validate(self, attrs):
        inicio, fim = attrs.get("periodo_inicio"), attrs.get("periodo_fim")
        if inicio and fim and inicio > fim:
            raise serializers.ValidationError({"periodo_inicio": "Não pode ser depois de periodo_fim."})
        return attrs


class CustoPorEntregaQuerySerializer(_VersaoQuerySerializer):
    agrupar = serializers.ChoiceField(choices=[(a, a) for a in AGRUPAMENTOS_DE_CUSTO], default="acao")
    indicador_id = serializers.IntegerField(min_value=1, required=False)


class CustoPorEntregaExportacaoQuerySerializer(CustoPorEntregaQuerySerializer):
    formato = serializers.ChoiceField(choices=FORMATOS_DE_EXPORTACAO, default="csv")


class ComposicaoQuerySerializer(serializers.Serializer):
    acao_id = serializers.IntegerField(min_value=1, required=False)
    indicador_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if bool(attrs.get("acao_id")) == bool(attrs.get("indicador_id")):
            raise serializers.ValidationError("Informe acao_id ou indicador_id.")
        return attrs


class RastreabilidadeQuerySerializer(_RecorteQuerySerializer):
    rubrica = serializers.SlugRelatedField(slug_field="slug", queryset=BudgetRubrica.objects.all())
    acao_id = serializers.IntegerField(min_value=1, required=False)


class ComparativoQuerySerializer(serializers.Serializer):
    de = serializers.IntegerField(min_value=1, help_text="Id da versão de origem.")
    para = serializers.IntegerField(min_value=1, help_text="Id da versão de destino.")


class VersaoDoRelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = TEDVersion
        fields = ["id", "numero_versao", "tipo", "registrado_em"]
        read_only_fields = fields


class _PaginadoSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)


class _CabecalhoDoRelatorioSerializer(_PaginadoSerializer):
    versao = VersaoDoRelatorioSerializer()
    acoes_fora_da_versao = serializers.IntegerField(
        help_text="Ações do plano atual que não estão no snapshot da versão e ficaram de fora.",
    )
    acoes_da_versao_fora_do_plano = serializers.IntegerField(
        help_text="Ações do snapshot que não existem mais no plano atual: entram com o planejado e sem execução.",
    )
    acoes_manuais_fora_do_recorte = serializers.IntegerField(
        help_text="Ações de Indicador com lançamento manual, que não tem território nem período: "
                  "ficam de fora quando há recorte ou quebra por território.",
    )


class AderenciaLinhaSerializer(serializers.Serializer):
    referencia_id = serializers.IntegerField(allow_null=True)
    nome = serializers.CharField()
    quantidade_planejada = serializers.DecimalField(max_digits=20, decimal_places=2)
    quantidade_realizada = serializers.DecimalField(max_digits=20, decimal_places=2)
    valor_planejado = serializers.DecimalField(max_digits=20, decimal_places=2)
    valor_executado = serializers.DecimalField(max_digits=20, decimal_places=2)
    perc_fisico = serializers.DecimalField(max_digits=24, decimal_places=2)
    perc_financeiro = serializers.DecimalField(max_digits=24, decimal_places=2)
    indice = serializers.DecimalField(max_digits=24, decimal_places=2, allow_null=True)
    faixa = serializers.ChoiceField(choices=AdherenceIndex.Faixa.choices, allow_null=True)


class AderenciaRespostaSerializer(_CabecalhoDoRelatorioSerializer):
    escopo = serializers.ChoiceField(choices=AdherenceIndex.Escopo.choices)
    results = AderenciaLinhaSerializer(many=True)


class AdherenceIndexSerializer(serializers.ModelSerializer):
    ted_versao = VersaoDoRelatorioSerializer(read_only=True)

    class Meta:
        model = AdherenceIndex
        fields = [
            "escopo", "referencia_id", "periodo_ref", "ted_versao", "perc_fisico", "perc_financeiro",
            "indice", "faixa", "calculado_em",
        ]
        read_only_fields = fields


class CustoPorEntregaLinhaSerializer(serializers.Serializer):
    referencia_id = serializers.IntegerField(allow_null=True)
    nome = serializers.CharField()
    territorio_id = serializers.IntegerField(allow_null=True)
    territorio_nome = serializers.CharField(allow_null=True)
    quantidade_realizada = serializers.DecimalField(max_digits=20, decimal_places=2)
    valor_executado = serializers.DecimalField(max_digits=20, decimal_places=2)
    custo_unitario_previsto = serializers.DecimalField(max_digits=24, decimal_places=2, allow_null=True)
    custo_unitario_realizado = serializers.DecimalField(max_digits=24, decimal_places=2, allow_null=True)
    desvio_percentual = serializers.DecimalField(max_digits=24, decimal_places=2, allow_null=True)
    faixa = serializers.ChoiceField(choices=FaixaDeCusto.CHOICES, allow_null=True)


class CustoPorEntregaRespostaSerializer(_CabecalhoDoRelatorioSerializer):
    agrupamento = serializers.ChoiceField(choices=[(a, a) for a in AGRUPAMENTOS_DE_CUSTO])
    limiar_desvio_percentual = serializers.DecimalField(max_digits=24, decimal_places=2)
    results = CustoPorEntregaLinhaSerializer(many=True)


class _RubricaRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    slug = serializers.CharField()


class ComposicaoPorRubricaSerializer(serializers.Serializer):
    rubrica = _RubricaRefSerializer()
    valor_executado = serializers.DecimalField(max_digits=20, decimal_places=2)
    participacao_percentual = serializers.DecimalField(max_digits=7, decimal_places=2)


class ComposicaoRespostaSerializer(_PaginadoSerializer):
    results = ComposicaoPorRubricaSerializer(many=True)


class RastreabilidadeSerializer(serializers.Serializer):
    """Uma solicitação paga, da rubrica até a evidência de campo da Atividade."""

    solicitacao_id = serializers.IntegerField(source="pk")
    valor_autorizado = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    valor_pago = serializers.DecimalField(max_digits=14, decimal_places=2)
    demanda = serializers.SerializerMethodField()
    atividade = serializers.SerializerMethodField()
    plano_trabalho = serializers.SerializerMethodField()
    evidencias = serializers.SerializerMethodField()

    @extend_schema_field(inline_serializer("DemandaRastreada", {
        "id": serializers.IntegerField(), "titulo": serializers.CharField(), "status": serializers.CharField(),
    }))
    def get_demanda(self, obj):
        return {"id": obj.demanda.pk, "titulo": obj.demanda.titulo, "status": obj.demanda.status}

    @extend_schema_field(inline_serializer("AtividadeRastreada", {
        "id": serializers.IntegerField(), "titulo": serializers.CharField(), "status": serializers.CharField(),
        "data_inicio": serializers.DateTimeField(), "data_fim": serializers.DateTimeField(),
        "municipio": serializers.CharField(), "territorio": serializers.CharField(allow_null=True),
    }))
    def get_atividade(self, obj):
        atividade = obj.demanda.activity
        territorio = atividade.municipio.territory
        return {
            "id": atividade.pk, "titulo": atividade.titulo, "status": atividade.status,
            "data_inicio": atividade.data_inicio, "data_fim": atividade.data_fim,
            "municipio": atividade.municipio.nome, "territorio": territorio.nome if territorio else None,
        }

    @extend_schema_field(PlanoTrabalhoSerializer(allow_null=True))
    def get_plano_trabalho(self, obj):
        return plano_trabalho_da_acao(obj.demanda.activity.acao)

    @extend_schema_field(inline_serializer("EvidenciasDaAtividade", {
        "fotos": serializers.IntegerField(), "documentos": serializers.IntegerField(),
        "listas_presenca": serializers.IntegerField(), "ufpas": serializers.IntegerField(),
        "membros": serializers.IntegerField(),
    }))
    def get_evidencias(self, obj):
        return {
            "fotos": obj.evidencia_fotos, "documentos": obj.evidencia_documentos,
            "listas_presenca": obj.evidencia_listas_presenca,
            "ufpas": obj.evidencia_ufpas, "membros": obj.evidencia_membros,
        }


class _ConsolidadoDaVersaoSerializer(serializers.Serializer):
    quantidade_planejada = serializers.DecimalField(max_digits=20, decimal_places=2)
    valor_planejado = serializers.DecimalField(max_digits=20, decimal_places=2)
    data_inicio = serializers.DateField(allow_null=True)
    data_fim = serializers.DateField(allow_null=True)


ELEMENTOS_DO_COMPARATIVO = [("meta", "Meta"), ("submeta", "Submeta"), ("acao", "Ação")]
SITUACOES_DO_COMPARATIVO = [("incluida", "Incluída"), ("removida", "Removida"), ("alterada", "Alterada")]


class DiferencaEntreVersoesSerializer(serializers.Serializer):
    elemento = serializers.ChoiceField(choices=ELEMENTOS_DO_COMPARATIVO)
    chave = serializers.CharField(help_text="Número da Meta, da Submeta ou da Ação.")
    nome = serializers.CharField()
    situacao = serializers.ChoiceField(choices=SITUACOES_DO_COMPARATIVO)
    campos_alterados = serializers.ListField(child=serializers.CharField())
    antes = _ConsolidadoDaVersaoSerializer(allow_null=True)
    depois = _ConsolidadoDaVersaoSerializer(allow_null=True)


class ComparativoRespostaSerializer(serializers.Serializer):
    de = VersaoDoRelatorioSerializer()
    para = VersaoDoRelatorioSerializer()
    diferencas = DiferencaEntreVersoesSerializer(many=True)
