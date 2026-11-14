from apps.core.middleware import ROTAS_DEPRECIADAS


def sem_rotas_depreciadas(endpoints: list[tuple], **kwargs) -> list[tuple]:
    """O schema descreve só a rota canônica; o alias existe para quem ainda não migrou."""
    return [endpoint for endpoint in endpoints if not endpoint[0].startswith(tuple(ROTAS_DEPRECIADAS))]
