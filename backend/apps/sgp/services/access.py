"""Única fonte da regra de escopo territorial do SGP.

super-admin/ugp veem tudo; articulador-estadual vê seus estados; adt-acr vê
seus territórios; qualquer outro papel não tem escopo.
"""

from rest_framework.exceptions import PermissionDenied

from apps.core.models.user_profile import UserProfile
from apps.core.services.permissions import user_has_role, user_role_slugs, user_states
from apps.sgp.models import UPF, Tecnico

ROLES_COM_ESCOPO = ("super-admin", "ugp", "articulador-estadual", "adt-acr")


def is_global_user(user) -> bool:
    """super-admin/ugp — sem escopo territorial nenhum, vê tudo.

    Não é sobre território: usado também por decisões binárias de
    visibilidade não-territoriais (ex.: quem pode listar registros
    inativos com `?ativo=false`)."""
    return user_has_role(user, "super-admin") or user_has_role(user, "ugp")


def _territorios_do_papel(user, role_slug):
    """Territórios do usuário para um papel específico.

    Diferente de `user_territories()`: um perfil com `territorio=None`
    não conta como acesso global aqui — só é ignorado. Isso importa para
    `adt-acr`, onde `territorio=None` é lacuna de cadastro, não uma
    concessão deliberada de acesso global (que só faz sentido para papéis
    como super-admin/ugp, que não passam por esta função).
    """
    return list(
        UserProfile.objects.filter(
            user=user, perfil__slug=role_slug, territorio__isnull=False,
        ).values_list("territorio_id", flat=True)
    )


def resolver_escopo(user, *, role_slugs=None):
    """Resolve o escopo territorial do usuário.

    Retorna uma tupla `(tipo, valor)`:
    - `("global", None)` — sem filtro, vê tudo.
    - `("estados", {siglas})` — restrito às siglas de estado.
    - `("territorios", [ids])` — restrito aos ids de território.
    - `("vazio", None)` — tem um papel com escopo territorial, mas o
      escopo em si está vazio (ex.: adt-acr sem território atribuído).
      Diferente de "negado": aqui a resposta é sempre lista vazia, nunca
      403 — o usuário tem o papel, só não tem nada visível ainda.
    - `("negado", None)` — nenhum papel com escopo territorial.

    `role_slugs` pode vir pré-computado (ex.: `user_role_slugs(user, ...)`
    já chamado por quem invoca) para evitar refazer a query.
    """
    if role_slugs is None:
        role_slugs = user_role_slugs(user, ROLES_COM_ESCOPO)

    if "super-admin" in role_slugs or "ugp" in role_slugs:
        return "global", None

    if "articulador-estadual" in role_slugs:
        states = user_states(user)
        return ("estados", states) if states else ("vazio", None)

    if "adt-acr" in role_slugs:
        territory_ids = _territorios_do_papel(user, "adt-acr")
        return ("territorios", territory_ids) if territory_ids else ("vazio", None)

    return "negado", None


def scope_queryset(
    qs,
    user,
    *,
    state_lookup,
    territory_lookup,
    role_slugs=None,
    deny_message="Você não tem acesso ao módulo SGP.",
    raise_on_no_role=True,
):
    """Filtra `qs` pelo escopo territorial do usuário.

    `state_lookup`/`territory_lookup` são expressões de lookup Django
    completas, sufixo incluído (ex.: `"municipio__state__sigla__in"`,
    `"territorio__estados__overlap"`, `"territorio__in"`).

    `raise_on_no_role=False` faz retornar `qs.none()` em vez de levantar
    `PermissionDenied` quando o usuário não tem nenhum papel com escopo —
    necessário para funções cujo contrato público já é "queryset vazio,
    nunca exceção" (`upfs_acessiveis_ao_usuario`, `tecnicos_acessiveis_ao_usuario`).
    Um papel reconhecido com escopo vazio (`"vazio"`) sempre devolve
    `qs.none()`, nunca levanta — só a ausência de papel (`"negado"`) é
    afetada por `raise_on_no_role`.
    """
    tipo, valor = resolver_escopo(user, role_slugs=role_slugs)

    if tipo == "global":
        return qs
    if tipo == "estados":
        return qs.filter(**{state_lookup: list(valor)})
    if tipo == "territorios":
        return qs.filter(**{territory_lookup: valor})
    if tipo == "vazio":
        return qs.none()

    if raise_on_no_role:
        raise PermissionDenied(deny_message)
    return qs.none()


def upfs_acessiveis_ao_usuario(user, role_slugs=None, *, raise_on_no_role=False):
    """Retorna queryset de UPFs acessíveis ao usuário conforme regras territoriais.

    `role_slugs` pode ser passado já computado (ver `UPFViewSet.get_queryset`)
    para evitar refazer a checagem de roles do usuário em outra query.

    Usa `all_objects`: RLS territorial e soft-delete são preocupações
    independentes — o padrão de só ativas fica em
    `apps.sgp.filters.somente_ativas_sem_filtro_ativo` (listagem e exportação),
    e quem precisa de uma UPF ativa específica checa `upf.ativo` por conta própria.
    """
    return scope_queryset(
        UPF.all_objects.all(),
        user,
        state_lookup="municipio__state__sigla__in",
        territory_lookup="territorio__in",
        role_slugs=role_slugs,
        raise_on_no_role=raise_on_no_role,
    )


def tecnicos_acessiveis_ao_usuario(user, role_slugs=None):
    """Retorna queryset de Tecnicos acessíveis ao usuário conforme regras territoriais.

    `Territory.estados` é `ArrayField` — `territorio__estados__overlap` é o
    lookup Postgres equivalente ao antigo loop Python que cruzava
    `Territory.objects.all()` contra os estados do usuário. `role_slugs`
    pode vir pré-computado (ver `TecnicoViewSet.get_queryset`) para evitar
    refazer a checagem de roles do usuário em outra query.
    """
    return scope_queryset(
        Tecnico.objects.all(),
        user,
        state_lookup="territorio__estados__overlap",
        territory_lookup="territorio__in",
        role_slugs=role_slugs,
        raise_on_no_role=False,
    )
