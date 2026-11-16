import hashlib

from django.core.cache import cache

from apps.sgp.filters import UFPAFilter


UFPA_MAP_CACHE_TIMEOUT = 60
UFPA_MAP_CACHE_VERSION_KEY = "sgp:ufpas:mapa:version"
POWER_BI_SNAPSHOT_CACHE_KEY = "sgp:workplan:power-bi:snapshot"


def get_ufpa_map_cache_version():
    version = cache.get(UFPA_MAP_CACHE_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(UFPA_MAP_CACHE_VERSION_KEY, version, None)
    return version


def build_ufpa_map_cache_key(user_id, query_params):
    # Derivada do FilterSet que o mapa aplica: um filtro novo no UFPAFilter
    # entra na chave sem precisar lembrar daqui.
    params_da_chave = {"bbox", *UFPAFilter.base_filters}
    version = get_ufpa_map_cache_version()
    normalized_params = sorted(
        (key, tuple(query_params.getlist(key)))
        for key in query_params.keys()
        if key in params_da_chave
    )
    # Hash em vez dos valores: o `q` traz nome ou CPF do titular, e a chave
    # aparece no log quando o Django avisa de caractere inválido ou tamanho.
    params_hash = hashlib.sha256(repr(normalized_params).encode()).hexdigest()
    return f"sgp:ufpas:mapa:v{version}:user:{user_id}:params:{params_hash}"


def invalidate_ufpa_map_cache():
    version = get_ufpa_map_cache_version()
    cache.set(UFPA_MAP_CACHE_VERSION_KEY, version + 1, None)


def get_power_bi_snapshot():
    return cache.get(POWER_BI_SNAPSHOT_CACHE_KEY)


def set_power_bi_snapshot(snapshot):
    # O próximo Beat substitui o snapshot; ele não deve expirar antes disso.
    cache.set(POWER_BI_SNAPSHOT_CACHE_KEY, snapshot, timeout=None)
