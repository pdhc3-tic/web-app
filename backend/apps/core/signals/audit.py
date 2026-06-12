import threading
from django.forms.models import model_to_dict
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from apps.core.services.audit import log_audit

# ---------------------------------------------------------------------------
# Contexto de thread — preenchido pelo AuditContextMiddleware
# ---------------------------------------------------------------------------

_audit_context = threading.local()


def get_audit_context():
    """Retorna o contexto de auditoria da thread atual."""
    return {
        "user": getattr(_audit_context, "user", None),
        "ip": getattr(_audit_context, "ip", None),
        "user_agent": getattr(_audit_context, "user_agent", ""),
    }


def set_audit_context(user, ip, user_agent):
    """Chamado pelo middleware para injetar o contexto na thread."""
    _audit_context.user = user
    _audit_context.ip = ip
    _audit_context.user_agent = user_agent


def clear_audit_context():
    """Limpa o contexto ao final do request."""
    _audit_context.user = None
    _audit_context.ip = None
    _audit_context.user_agent = ""


# ---------------------------------------------------------------------------
# Campos que NUNCA devem aparecer no log
# ---------------------------------------------------------------------------

AUDIT_EXCLUDED_FIELDS = {
    "password",
    "senha_hash",
    "token",
    "refresh_token",
    "token_hash",
    "last_login",
    "ultimo_login",
}


def _serialize(instance):
    """
    Serializa o model para dict excluindo campos não-auditáveis.
    Ignora campos que causam erro na serialização.
    """
    fields = [
        f.name for f in instance._meta.fields
        if f.name not in AUDIT_EXCLUDED_FIELDS
    ]

    data = {}
    for field_name in fields:
        try:
            value = getattr(instance, field_name)
            # Garante que o valor é serializável como JSON
            if isinstance(value, (str, int, float, bool, type(None), dict, list)):
                data[field_name] = value
            else:
                data[field_name] = str(value)
        except Exception:
            pass

    return data


# ---------------------------------------------------------------------------
# Models auditados
# ---------------------------------------------------------------------------

AUDITED_MODELS = {}


def _register_audited_model(model_class, modulo="core"):
    """Registra um model para auditoria automática."""
    AUDITED_MODELS[model_class] = modulo


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _get_model_name(instance):
    return instance.__class__.__name__


def _get_modulo(instance):
    return AUDITED_MODELS.get(instance.__class__, "core")


@receiver(pre_save)
def handle_pre_save(sender, instance, **kwargs):
    """
    Captura o estado anterior do registro antes de salvar.
    Armazena em _audit_valores_anteriores na própria instância
    para que o post_save possa acessar.
    """
    if sender not in AUDITED_MODELS:
        return

    if sender is AuditLog:
        return

    if instance.pk:
        try:
            anterior = sender.objects.get(pk=instance.pk)
            instance._audit_valores_anteriores = _serialize(anterior)
        except sender.DoesNotExist:
            instance._audit_valores_anteriores = {}
    else:
        instance._audit_valores_anteriores = {}

@receiver(post_save)
def handle_post_save(sender, instance, created, **kwargs):
    if sender not in AUDITED_MODELS:
        return

    # Evita loop infinito — AuditLog não audita a si mesmo
    from apps.core.models.audit_log import AuditLog
    if sender is AuditLog:
        return

    ctx = get_audit_context()

    valores_anteriores = getattr(instance, "_audit_valores_anteriores", {})
    valores_novos = _serialize(instance)

    log_audit(
        user=ctx["user"],
        acao="CREATE" if created else "UPDATE",
        modulo=_get_modulo(instance),
        entidade=_get_model_name(instance),
        entidade_id=instance.pk,
        valores_anteriores={} if created else valores_anteriores,
        valores_novos=valores_novos,
        _ip=ctx["ip"],
        _user_agent=ctx["user_agent"],
    )


@receiver(post_delete)
def handle_post_delete(sender, instance, **kwargs):
    if sender not in AUDITED_MODELS:
        return

    from apps.core.models.audit_log import AuditLog
    if sender is AuditLog:
        return

    ctx = get_audit_context()

    log_audit(
        user=ctx["user"],
        acao="DELETE",
        modulo=_get_modulo(instance),
        entidade=_get_model_name(instance),
        entidade_id=instance.pk,
        valores_anteriores=_serialize(instance),
        valores_novos={},
        _ip=ctx["ip"],
        _user_agent=ctx["user_agent"],
    )