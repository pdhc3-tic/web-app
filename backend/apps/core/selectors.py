"""
Selectors — queries reutilizáveis que encapsulam filtragem de negócio.

Filosofia: views não constroem querysets — delegam para selectors.
"""

from apps.core.models import Organization
from apps.core.services.permissions import user_has_role, user_territories


def organization_list(user, *, action: str = "list"):
    """
    Retorna o queryset de Organization adequado ao perfil do usuário e à ação.

    - articulador-estadual: vê apenas organizações nos seus territórios (sempre ativas).
    - list: qualquer outro perfil vê apenas ativas.
    - retrieve/outros: sem filtro de ativa (permite busca de inativas pelo admin).
    """
    qs = Organization.objects.select_related(
        "municipio", "municipio__state"
    ).prefetch_related("territorios")

    if user_has_role(user, "articulador-estadual"):
        territories = user_territories(user)
        return qs.filter(territorios__in=territories, ativa=True).distinct()

    if action == "list":
        return qs.filter(ativa=True)

    return qs
