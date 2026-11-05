"""Criação de atividade por outro módulo, com as regras do cadastro."""
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import transaction

from apps.sgp.models.activity import Activity
from apps.sgp.services.activity_status import ActivityRuleError, validar_datas, validar_transicao

STATUS_PLANEJADO = "planejado"


class CadastroInvalidoError(ActivityRuleError):
    sync_code = "CADASTRO_INVALIDO"

    def __init__(self, message, *, field):
        super().__init__(message)
        self.field = field


@transaction.atomic
def criar_planejada(*, titulo, tipo_atividade, acao, municipio, data_prevista, usuario) -> Activity:
    """Só os campos que o SGD §2.2 exige. Os demais, obrigatórios no cadastro, recebem
    um valor padrão editável depois, e quem cria fica como técnico responsável."""
    atividade = Activity(
        titulo=titulo, tipo_atividade=tipo_atividade, acao=acao, municipio=municipio,
        forma_atuacao="realizacao", ambito="municipal", tecnico_responsavel=usuario,
        data_inicio=data_prevista, data_fim=data_prevista,
        descricao_narrativa=f"Atividade criada a partir da demanda '{titulo}'.",
        status=STATUS_PLANEJADO, criado_por=usuario,
    )
    validar_transicao(None, STATUS_PLANEJADO)
    validar_datas(data_prevista, data_prevista)
    try:
        atividade.full_clean()
    except ValidationError as exc:
        campo, mensagens = next(iter(exc.message_dict.items()))
        raise CadastroInvalidoError(
            mensagens[0], field=None if campo == NON_FIELD_ERRORS else campo,
        ) from exc
    atividade.save()
    return atividade
