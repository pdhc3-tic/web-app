from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgd.constants import (
    Classe,
    MeioTransporte,
    TipoMaterial,
    TipoRefeicao,
    TipoVeiculo,
    Urgencia,
    Vinculo,
)
from apps.sgd.models.demand import STATUS_CHOICES as DEMANDA_STATUS_CHOICES
from apps.sgd.models.demand_document import TIPO_CHOICES as DEMANDA_DOCUMENTO_TIPO_CHOICES
from apps.sgd.models.demand_request import TIPO_CHOICES as SOLICITACAO_TIPO_CHOICES
from apps.sgp.constants import (
    AGUA_CHOICES,
    COR_RACA_CHOICES,
    DISPOSITIVO_CHOICES,
    ENERGIA_CHOICES,
    ESCOLARIDADE_CHOICES,
    GENERO_CHOICES,
    MATERIAL_CONSTRUCAO_CHOICES,
    ODS_CHOICES,
    PARENTESCO_CHOICES,
    PCT_CHOICES,
    POSSE_TERRA_CHOICES,
    SAUDE_CHOICES,
    SEGURIDADE_SOCIAL_CHOICES,
    SITUACAO_MORADIA_CHOICES,
    STATUS_WORKPLAN,
    TIPO_MORADIA_CHOICES,
)
from apps.sgp.models import ActivityDocument, Cultura, EspecieAnimal, Production, UPFDocument
from apps.sgp.models.activity import (
    AMBITO_CHOICES,
    FORMA_ATUACAO_CHOICES,
    STATUS_CHOICES,
    TIPO_ATIVIDADE_CHOICES,
)

# Única lista do que o endpoint publica. Os testes de contrato conferem que
# toda constante de choices do SGP e do SGD está aqui.
CHOICES_PUBLICADOS = {
    "genero": GENERO_CHOICES,
    "cor_raca": COR_RACA_CHOICES,
    "escolaridade": ESCOLARIDADE_CHOICES,
    "dispositivo": DISPOSITIVO_CHOICES,
    "pct": PCT_CHOICES,
    "posse_terra": POSSE_TERRA_CHOICES,
    "situacao_moradia": SITUACAO_MORADIA_CHOICES,
    "tipo_moradia": TIPO_MORADIA_CHOICES,
    "material_construcao": MATERIAL_CONSTRUCAO_CHOICES,
    "energia": ENERGIA_CHOICES,
    "agua": AGUA_CHOICES,
    "grau_parentesco": PARENTESCO_CHOICES,
    "saude": SAUDE_CHOICES,
    "seguridade_social": SEGURIDADE_SOCIAL_CHOICES,
    "ods": ODS_CHOICES,
    "status_plano_trabalho": STATUS_WORKPLAN,
    "tipo_atividade": TIPO_ATIVIDADE_CHOICES,
    "forma_atuacao": FORMA_ATUACAO_CHOICES,
    "ambito": AMBITO_CHOICES,
    "status_atividade": STATUS_CHOICES,
    "producao_tipo": Production.TIPO_CHOICES,
    "producao_sistema_criacao": Production.SISTEMA_CRIACAO_CHOICES,
    "producao_tipo_outra": Production.TIPO_OUTRA_CHOICES,
    "cultura_categoria": Cultura.CATEGORIA_CHOICES,
    "especie_categoria": EspecieAnimal.CATEGORIA_CHOICES,
    "upf_documento_tipo": UPFDocument.TIPO_CHOICES,
    "atividade_documento_tipo": ActivityDocument.TIPO_CHOICES,
    "solicitacao_tipo": SOLICITACAO_TIPO_CHOICES,
    "demanda_status": DEMANDA_STATUS_CHOICES,
    "demanda_documento_tipo": DEMANDA_DOCUMENTO_TIPO_CHOICES,
    "beneficiario_vinculo": Vinculo.choices,
    "meio_transporte": MeioTransporte.choices,
    "classe": Classe.choices,
    "urgencia": Urgencia.choices,
    "tipo_veiculo": TipoVeiculo.choices,
    "tipo_material": TipoMaterial.choices,
    "tipo_refeicao": TipoRefeicao.choices,
}


class OpcaoTextoSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class OpcaoNumeroSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    label = serializers.CharField()


def _opcoes_serializer(opcoes):
    serializer = OpcaoNumeroSerializer if isinstance(opcoes[0][0], int) else OpcaoTextoSerializer
    return serializer(many=True)


class SGPChoicesView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        responses=inline_serializer(
            "ChoicesResposta",
            fields={chave: _opcoes_serializer(opcoes) for chave, opcoes in CHOICES_PUBLICADOS.items()},
        ),
    )
    def get(self, request):
        return Response({
            chave: [{"value": valor, "label": rotulo} for valor, rotulo in opcoes]
            for chave, opcoes in CHOICES_PUBLICADOS.items()
        })
