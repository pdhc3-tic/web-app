from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from apps.core.services.permissions import user_has_role
from apps.sgd.models.demand import STATUS_EDITAVEIS

# Comprovante é enviado pela FGD durante/após o atendimento — os demais tipos
# (suporte, ata, cotação) são do solicitante, só enquanto a demanda é editável.
TIPOS_FGD = {"comprovante"}
STATUS_ENVIO_FGD = {"em_atendimento", "concluida"}


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
