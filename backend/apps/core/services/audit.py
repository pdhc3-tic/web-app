SENSITIVE_AUDIT_KEYS = {
    "password",
    "senha",
    "senha_hash",
    "nova_senha",
    "access",
    "access_token",
    "refresh",
    "refresh_token",
    "authorization",
    "cookie",
    "cookies",
    "token",
    "token_hash",
    "reset_token",
    "payload",
}


def get_client_ip(request):
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def sanitize_audit_values(values):
    if not values:
        return {}
    sanitized = {}
    for key, value in values.items():
        if key.lower() in SENSITIVE_AUDIT_KEYS:
            continue
        sanitized[key] = value
    return sanitized


def create_audit_log(
    *,
    user,
    acao,
    modulo="core",
    entidade="",
    entidade_id="",
    valores_anteriores=None,
    valores_novos=None,
    request=None,
    ip=None,
    user_agent=None,
):
    from apps.core.models.audit_log import AuditLog

    if ip is None:
        ip = get_client_ip(request)
    if user_agent is None:
        user_agent = request.META.get("HTTP_USER_AGENT", "") if request is not None else ""

    return AuditLog.objects.create(
        user=user,
        acao=acao,
        modulo=modulo,
        entidade=entidade,
        entidade_id=str(entidade_id or ""),
        valores_anteriores=sanitize_audit_values(valores_anteriores),
        valores_novos=sanitize_audit_values(valores_novos),
        ip=ip or None,
        user_agent=user_agent or "",
    )
