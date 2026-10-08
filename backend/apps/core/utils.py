import ipaddress
import json

from django.conf import settings


def get_client_ip(request) -> str | None:
    """IP do cliente atrás de `settings.TRUSTED_PROXY_COUNT` proxies confiáveis.

    Cada proxy acrescenta ao fim do `X-Forwarded-For` o IP que ele viu, então o
    cliente real é o N-ésimo da direita. O que vem antes disso é escrito pelo
    próprio cliente e pode ser forjado, por isso nunca é usado. Valor inválido
    ou cadeia curta demais caem no `REMOTE_ADDR`.
    """
    remote_addr = _ip_valido(request.META.get("REMOTE_ADDR"))
    proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 1)
    cadeia = [
        ip.strip() for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if ip.strip()
    ]
    if proxies < 1 or len(cadeia) < proxies:
        return remote_addr
    return _ip_valido(cadeia[-proxies]) or remote_addr


def _ip_valido(valor) -> str | None:
    try:
        return str(ipaddress.ip_address(valor))
    except ValueError:
        return None


from django.core.cache import cache

from apps.core.models.system_config import SystemConfig, TipoConfiguracao


def get_config(chave, default=None):
    cache_key = f"system_config:{chave}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        obj = SystemConfig.objects.get(chave=chave)
    except SystemConfig.DoesNotExist:
        return default

    valor = obj.valor

    if obj.tipo == TipoConfiguracao.INTEGER:
        result = int(valor)
    elif obj.tipo == TipoConfiguracao.BOOLEAN:
        result = valor == "True"
    elif obj.tipo == TipoConfiguracao.JSON:
        result = json.loads(valor)
    else:
        result = valor

    cache.set(cache_key, result, timeout=300)
    return result
