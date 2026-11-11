from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.core.services.audit import log_audit
from apps.core.services.permissions import user_has_role
from apps.core.signals.audit import get_audit_context
from apps.sgd.models.demand import STATUS_EDITAVEIS, Demand
from apps.sgd.models.demand_document import DemandDocument

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


def travar_para_gerenciar_documento(demand, usuario, tipo: str) -> None:
    """Trava a `Demand` e confere a permissão com o status relido: sem o lock, um
    documento removido durante a submissão sairia de uma demanda já submetida."""
    demand.status = Demand.objects.select_for_update().values_list("status", flat=True).get(pk=demand.pk)
    exigir_pode_gerenciar_documento(demand, usuario, tipo)


def documentos_no_limite(demand) -> int:
    """Documentos que contam no limite por demanda. O anexo já informado num campo do
    formulário fica de fora: quem limita quantos ele pode ter é o schema do tipo."""
    return DemandDocument.objects.filter(demanda=demand, ativo=True).exclude(
        tipo="anexo", solicitacao__isnull=False,
    ).count()


def snapshot(documento) -> dict:
    return {
        "doc_id": documento.pk, "demanda_id": documento.demanda_id, "tipo": documento.tipo,
        "nome_original": documento.nome_original, "arquivo_key": documento.arquivo_key,
        "tamanho_bytes": documento.tamanho_bytes, "ativo": documento.ativo,
    }


def remover(documento, *, usuario=None) -> None:
    """Remoção lógica, com o mesmo registro de auditoria da aba de documentos."""
    anterior = snapshot(documento)
    documento.ativo = False
    documento.save(update_fields=["ativo"])
    contexto = get_audit_context()
    log_audit(
        user=usuario or contexto["user"], acao="demand_document.deleted", modulo="sgd",
        entidade=ENTIDADE_DOCUMENTO, entidade_id=documento.demanda_id, valores_anteriores=anterior,
        _ip=contexto["ip"], _user_agent=contexto["user_agent"],
    )
