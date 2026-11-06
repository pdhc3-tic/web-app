"""Criação de atividade por outro módulo, com as regras do cadastro, e custo da atividade."""
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce, Least

from apps.sgp.budget.rls import com_visao_total
from apps.sgp.models.activity import Activity
from apps.sgp.services.activity_status import ActivityRuleError, validar_datas, validar_transicao

STATUS_PLANEJADO = "planejado"
DEMANDA_CONCLUIDA = "concluida"
DEMANDA_SEM_CUSTO_PREVISTO = (DEMANDA_CONCLUIDA, "cancelada", "recusada")


@com_visao_total
def custos_da_atividade(activity) -> dict:
    """Custo previsto e realizado. Sem visão total, o RLS das demandas faria cada pessoa ver um
    total diferente da mesma atividade. O realizado é o executado: pago acima do autorizado fica
    no risco de glosa, não no custo."""
    return activity.demandas.aggregate(
        previsto=Sum("solicitacoes__valor_estimado", filter=~Q(status__in=DEMANDA_SEM_CUSTO_PREVISTO)),
        realizado=Sum(
            Least(
                "solicitacoes__valor_pago",
                Coalesce("solicitacoes__valor_autorizado", "solicitacoes__valor_estimado"),
            ),
            filter=Q(status=DEMANDA_CONCLUIDA, solicitacoes__valor_pago__isnull=False),
        ),
    )


class CadastroInvalidoError(ActivityRuleError):
    sync_code = "CADASTRO_INVALIDO"

    def __init__(self, message, *, field):
        super().__init__(message)
        self.field = field


@transaction.atomic
def criar_planejada(*, titulo, tipo_atividade, acao, municipio, data_prevista, usuario) -> Activity:
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
