from django.db.models import QuerySet

from apps.core.models.territory import Territory
from apps.core.models.user_profile import UserProfile


def user_has_role(user, slug: str) -> bool:
    if not user.is_authenticated:
        return False
    return UserProfile.objects.filter(user=user, perfil__slug=slug).exists()


def user_role_slugs(user, slugs=None) -> set[str]:
    """Slugs de perfil do usuário em uma única query.

    Se `slugs` for informado, restringe a busca a esses slugs — mais barato
    quando só interessam algumas roles (ex.: guard de acesso a um módulo).
    """
    if not user.is_authenticated:
        return set()
    qs = UserProfile.objects.filter(user=user)
    if slugs is not None:
        qs = qs.filter(perfil__slug__in=slugs)
    return set(qs.values_list("perfil__slug", flat=True))


def user_territories(user) -> QuerySet[Territory]:
    """Sem territórios vinculados → acesso global (Territory.objects.all())."""
    profile_territory_ids = list(
        UserProfile.objects.filter(
            user=user, territorio__isnull=False
        ).values_list("territorio_id", flat=True)
    )
    if not profile_territory_ids:
        has_global = UserProfile.objects.filter(
            user=user, territorio__isnull=True
        ).exists()
        if has_global:
            return Territory.objects.all()
        return Territory.objects.none()
    return Territory.objects.filter(pk__in=profile_territory_ids)


def user_states(user) -> set[str]:
    """Siglas de estado acessíveis. Sem territórios → todos os estados."""
    qs = user_territories(user)
    if not qs.exists():
        qs = Territory.objects.all()

    states: set[str] = set()
    for estados_list in qs.values_list("estados", flat=True):
        if estados_list:
            states.update(estados_list)
    return states
