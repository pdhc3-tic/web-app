from django.db.models import QuerySet

from apps.core.models.territory import Territory
from apps.core.models.user_profile import UserProfile


def user_has_role(user, slug: str) -> bool:
    return UserProfile.objects.filter(user=user, perfil__slug=slug).exists()


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
