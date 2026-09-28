from rest_framework import serializers


class NestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)


class EstadoNestedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    sigla = serializers.CharField(read_only=True)
    nome = serializers.CharField(read_only=True)


class MunicipioNestedSerializer(serializers.Serializer):
    """Município com o estado embutido — NestedSerializer genérico não dava
    conta disso e a UI ficava sem Estado (issue #226)."""
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)
    estado = EstadoNestedSerializer(source="state", read_only=True)


def plano_trabalho_da_acao(acao) -> dict | None:
    """Cadeia Meta → Submeta → Ação → Indicador de uma Atividade, derivada da
    Ação e só para leitura (SGP-RF07). Espera `acao__meta`, `acao__submeta` e
    `acao__indicador` já carregados via select_related."""
    if acao is None:
        return None
    return {
        "meta": {"id": acao.meta_id, "numero": acao.meta.numero, "titulo": acao.meta.titulo},
        "submeta": {
            "id": acao.submeta_id,
            "numero": acao.submeta.numero,
            "titulo": acao.submeta.titulo,
        },
        "acao": {"id": acao.pk, "numero": acao.numero, "descricao": acao.descricao},
        "indicador": {
            "id": acao.indicador_id,
            "codigo": acao.indicador.codigo,
            "nome": acao.indicador.nome,
            "unidade_medida": acao.indicador.unidade_medida,
        },
    }
