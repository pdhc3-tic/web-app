import json

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
