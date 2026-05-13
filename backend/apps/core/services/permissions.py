from django.db.models import QuerySet

from apps.core.models.territory import Territory


def user_has_role(user, slug: str) -> bool:
    role = getattr(user, "role", None)
    if role is None:
        return False
    return role.slug == slug


def user_territories(user) -> QuerySet[Territory]:
    """Sem territórios vinculados → acesso global (Territory.objects.all())."""
    qs = user.territorios.all()
    if qs.exists():
        return qs
    return Territory.objects.all()


def user_states(user) -> set[str]:
    """Siglas de estado acessíveis. Sem territórios → todos os estados."""
    qs = user.territorios.all()
    if not qs.exists():
        qs = Territory.objects.all()

    states: set[str] = set()
    for estados_list in qs.values_list("estados", flat=True):
        if estados_list:
            states.update(estados_list)
    return states
