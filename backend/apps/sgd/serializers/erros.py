"""Corpo dos erros de domínio do SGD no schema OpenAPI. Só documentação: quem
monta o corpo é `ErroDeDominio.como_dict` (`apps/sgd/exceptions.py`)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse
from rest_framework import serializers

from apps.sgd.exceptions import ACAO_SUGERIDA, TRAVA_INDIVIDUAL, TRAVA_TERRITORIAL

_VALOR = {"help_text": "Valor com duas casas decimais, como texto."}


class BloqueioDeSaldoSerializer(serializers.Serializer):
    code = serializers.CharField(default="INSUFFICIENT_BALANCE")
    trava = serializers.ChoiceField(choices=[TRAVA_INDIVIDUAL, TRAVA_TERRITORIAL])
    rubrica = serializers.CharField(help_text="Slug da rubrica.")
    disponivel = serializers.CharField(**_VALOR)
    solicitado = serializers.CharField(**_VALOR)
    acao_sugerida = serializers.ChoiceField(choices=sorted(ACAO_SUGERIDA.values()))
    valor_faltante = serializers.CharField(
        allow_null=True,
        help_text=(
            "Só na trava individual da submissão: o que falta na rubrica inteira, o mesmo valor que "
            "o pedido de recurso extra registraria sem `valor_solicitado`. Nos outros casos, `null`."
        ),
    )
    detail = serializers.CharField()


class SaldoInsuficienteSerializer(BloqueioDeSaldoSerializer):
    """`INSUFFICIENT_BALANCE`. Na submissão, o primeiro bloqueio vai no topo e
    todos aparecem em `solicitacoes_bloqueadas`, chaveados pelo id da solicitação."""

    solicitacao_id = serializers.IntegerField(required=False)
    solicitacoes_bloqueadas = serializers.DictField(child=BloqueioDeSaldoSerializer(), required=False)


ERRO_DE_DOMINIO = OpenApiResponse(
    response=OpenApiTypes.OBJECT,
    description=(
        "Erro de validação ou de domínio (`BUSINESS_RULE`, `INVALID_TRANSITION`, `JUSTIFICATION_REQUIRED`), "
        "no formato `{campo: [mensagem], code}` ou `{code, detail}`."
    ),
)

SALDO_INSUFICIENTE = OpenApiResponse(
    response=SaldoInsuficienteSerializer,
    description=(
        "`INSUFFICIENT_BALANCE`, no corpo descrito. Os outros erros de domínio "
        "(`BUSINESS_RULE`, `INVALID_TRANSITION`, `JUSTIFICATION_REQUIRED`) usam o mesmo status, "
        "no formato `{campo: [mensagem], code}` ou `{code, detail}`."
    ),
)
