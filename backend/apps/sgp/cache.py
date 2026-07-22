from django.core.cache import cache


UPF_MAP_CACHE_TIMEOUT = 60
UPF_MAP_CACHE_VERSION_KEY = "sgp:upfs:mapa:version"


def get_upf_map_cache_version():
    version = cache.get(UPF_MAP_CACHE_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(UPF_MAP_CACHE_VERSION_KEY, version, None)
    return version


def build_upf_map_cache_key(user_id, query_params):
    version = get_upf_map_cache_version()
    normalized_params = sorted(
        (key, tuple(query_params.getlist(key)))
        for key in query_params.keys()
        if key in {"bbox", "municipio", "territorio", "projeto", "ativa"}
    )
    return f"sgp:upfs:mapa:v{version}:user:{user_id}:params:{normalized_params}"


def invalidate_upf_map_cache():
    version = get_upf_map_cache_version()
    cache.set(UPF_MAP_CACHE_VERSION_KEY, version + 1, None)
