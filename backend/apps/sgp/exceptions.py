from rest_framework import status
from rest_framework.exceptions import APIException


class ErroComCodigo(APIException):
    """Erro com `code` estável no corpo, para o front distinguir os casos sem
    depender do texto da mensagem. O corpo sai como `{"code": ..., "message": ...}`,
    sem as listas que o DRF aplica aos erros de serializer — por isso, quando
    levantado dentro de `validate()`, não passa pelo tratamento de ValidationError."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code, message, status_code=None, **extra):
        super().__init__({"code": code, "message": message, **extra})
        if status_code is not None:
            self.status_code = status_code


def recusar_parametros_desconhecidos(recebidos, aceitos) -> None:
    """400 com a lista dos parâmetros fora de `aceitos`. Usado onde um filtro
    ignorado em silêncio geraria um arquivo com a base inteira."""
    desconhecidos = sorted(set(recebidos) - set(aceitos))
    if desconhecidos:
        raise ErroComCodigo(
            "parametro_desconhecido",
            "Parâmetro(s) não aceito(s) na exportação: " + ", ".join(desconhecidos) + ".",
            parametros=desconhecidos,
        )
