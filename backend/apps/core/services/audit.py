"""
Service de auditoria centralizado.

Regra de uso:
  - Views com request → log_audit(..., request=request)  → popula ip + user_agent
  - Signals sem request → log_audit(..., request=None)   → ip=None, user_agent=None

Nunca chamar AuditLog.objects.create() fora deste módulo.
"""

from apps.core.utils import get_client_ip


def log_audit(
    *,
    user,
    acao: str,
    modulo: str,
    entidade: str,
    entidade_id,
    valores_anteriores=None,
    valores_novos=None,
    request=None,
    _ip=None,
    _user_agent=None,
):
    """
    Cria um registro de AuditLog de forma padronizada.

    Args:
        user: instância do usuário responsável pela ação (pode ser None/anônimo).
        acao: string snake_case descrevendo a ação (ex: ``organization_created``).
        modulo: app/módulo de origem (ex: ``core``).
        entidade: nome da classe do modelo afetado (ex: ``Organization``).
        entidade_id: pk da instância afetada (convertido para str automaticamente).
        valores_anteriores: dict com estado anterior do objeto (opcional).
        valores_novos: dict com estado posterior do objeto (opcional).
        request: objeto HttpRequest; quando fornecido, extrai IP e User-Agent.
        _ip: IP de override para contextos sem request (ex.: signals com thread-local).
        _user_agent: User-Agent de override para contextos sem request.
    """
    # Import lazy para evitar import circular (models → services → models)
    from apps.core.models.audit_log import AuditLog

    ip = None
    user_agent = None
    if request is not None:
        ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "") or None
    else:
        ip = _ip or None
        user_agent = _user_agent or None

    authenticated_user = user if (user is not None and getattr(user, "is_authenticated", False)) else None

    return AuditLog.objects.create(
        user=authenticated_user,
        acao=acao,
        modulo=modulo,
        entidade=entidade,
        entidade_id=str(entidade_id),
        valores_anteriores=valores_anteriores or {},
        valores_novos=valores_novos or {},
        ip=ip,
        user_agent=user_agent,
    )
