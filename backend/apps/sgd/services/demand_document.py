from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.core.services.permissions import user_has_role
from apps.sgd.models.demand import STATUS_EDITAVEIS
from apps.sgd.models.demand_document import TIPO_ANEXO, DemandDocument
from apps.sgd.services import auditoria as auditoria_service
from apps.sgd.services.workflow import travar_e_ler_status

# Comprovante é enviado pela FGD durante/após o atendimento — os demais tipos
# (suporte, ata, cotação) são do solicitante, só enquanto a demanda é editável.
TIPOS_FGD = {"comprovante"}
STATUS_ENVIO_FGD = {"em_atendimento", "concluida"}

ENTIDADE_DOCUMENTO = "DemandDocument"


def exigir_pode_gerenciar_documento(demand, usuario, tipo: str) -> None:
    if tipo in TIPOS_FGD:
        if user_has_role(usuario, "fgd") and demand.status in STATUS_ENVIO_FGD:
            return
        raise PermissionDenied(
            "Só a FGD pode enviar ou remover comprovantes, com a demanda em atendimento ou concluída."
        )
    if demand.solicitante_id == usuario.pk and demand.status in STATUS_EDITAVEIS:
        return
    raise PermissionDenied(
        "Só o solicitante pode enviar ou remover este documento, com a demanda em Rascunho ou Devolvida."
    )


def travar_demanda(demand) -> None:
    """Trava a `Demand` e relê o status. Quem grava documento trava antes: sem isso, um
    documento removido durante a submissão sairia de uma demanda já submetida."""
    demand.status = travar_e_ler_status(demand)


def documentos_no_limite(demand, tipo: str) -> int:
    """Quantos documentos contam no limite de quem envia um do `tipo`. Os da aba contam
    entre si; os anexos, só enquanto não foram informados num campo do formulário, porque
    depois quem limita quantos a solicitação tem é o schema do tipo."""
    ativos = DemandDocument.objects.filter(demanda=demand, ativo=True)
    if tipo == TIPO_ANEXO:
        return ativos.filter(tipo=TIPO_ANEXO, solicitacao__isnull=True).count()
    return ativos.exclude(tipo=TIPO_ANEXO).count()


def snapshot(documento) -> dict:
    return {
        "doc_id": documento.pk, "demanda_id": documento.demanda_id, "tipo": documento.tipo,
        "nome_original": documento.nome_original, "arquivo_key": documento.arquivo_key,
        "tamanho_bytes": documento.tamanho_bytes, "ativo": documento.ativo,
        "solicitacao_id": documento.solicitacao_id, "campo": documento.campo,
    }


def auditar(acao: str, demand, *, usuario=None, anteriores=None, novos=None) -> None:
    auditoria_service.registrar_evento(
        acao=acao, entidade=ENTIDADE_DOCUMENTO, entidade_id=demand.pk, usuario=usuario,
        anteriores=anteriores, novos=novos,
    )


def remover(documento, *, usuario=None) -> None:
    """Remoção lógica, com o mesmo registro de auditoria da aba de documentos."""
    anterior = snapshot(documento)
    documento.ativo = False
    documento.save(update_fields=["ativo"])
    auditoria_service.registrar_evento(
        acao="demand_document.deleted", entidade=ENTIDADE_DOCUMENTO, entidade_id=documento.demanda_id,
        usuario=usuario, anteriores=anterior,
    )
