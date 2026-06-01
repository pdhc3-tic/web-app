from typing import Any

from apps.core.models.audit_log import AuditLog
from apps.core.utils import get_client_ip


def log_audit(
    *,
    user,
    acao: str,
    modulo: str,
    entidade: str,
    entidade_id: str | int,
    valores_anteriores: dict[str, Any] | None = None,
    valores_novos: dict[str, Any] | None = None,
    request=None,
    ip: str | None = None,
    user_agent: str = "",
) -> AuditLog:
    if request is not None:
        ip = get_client_ip(request) or None
        user_agent = request.META.get("HTTP_USER_AGENT", "")

    return AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        acao=acao,
        modulo=modulo,
        entidade=entidade,
        entidade_id=str(entidade_id),
        valores_anteriores=valores_anteriores or {},
        valores_novos=valores_novos or {},
        ip=ip or None,
        user_agent=user_agent,
    )
