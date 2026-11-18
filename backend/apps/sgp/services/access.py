"""Única fonte da regra de escopo territorial do SGP.

super-admin/ugp veem tudo; articulador-estadual vê os estados dos territórios
do próprio perfil; adt-acr vê os territórios do próprio perfil; qualquer outro
papel não tem escopo. Quem acumula Articulador e ADT/ACR recebe a união dos
dois escopos. Vínculo ausente nunca vira acesso global.

A política RLS de `sgp_ufpa` (apps/sgp/migrations/0022_rls_ufpa.py) aplica a
mesma regra no banco.
"""

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.core.models.municipality import Municipality
from apps.core.models.territory import Territory
from apps.core.models.user_profile import UserProfile
from apps.core.services.permissions import user_has_role, user_role_slugs
from apps.sgp.models import UFPA, Activity, Tecnico

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


def _estados_do_papel(user, role_slug) -> set[str]:
    """Siglas dos estados dos territórios do usuário para um papel.

    Diferente de `user_states()`, que soma os territórios de todos os perfis e
    trata "sem território" como todos os estados: aqui só contam os
    territórios do próprio perfil, e sem nenhum o resultado é vazio."""
    estados: set[str] = set()
    ids = _territorios_do_papel(user, role_slug)
    if not ids:
        return estados
    for lista in Territory.objects.filter(pk__in=ids).values_list("estados", flat=True):
        estados.update(lista or [])
    return estados


def estados_do_articulador(user) -> set[str]:
    """Estados do Articulador pela regra do SGP e da RLS de sgp_ufpa: só os
    territórios do próprio perfil, e sem vínculo nenhum estado."""
    return _estados_do_papel(user, "articulador-estadual")


def resolver_escopo(user, *, role_slugs=None):
    """Resolve o escopo territorial do usuário.

    Retorna uma tupla `(tipo, valor)`:
    - `("global", None)` — sem filtro, vê tudo.
    - `("estados", {siglas})` — restrito às siglas de estado.
    - `("territorios", [ids])` — restrito aos ids de território.
    - `("combinado", ({siglas}, [ids]))` — Articulador e ADT/ACR ao mesmo
      tempo: a união dos estados de um com os territórios do outro.
    - `("vazio", None)` — tem um papel com escopo territorial, mas o
      escopo em si está vazio (ex.: adt-acr ou articulador sem território
      atribuído). Diferente de "negado": aqui a resposta é sempre lista
      vazia, nunca 403 — o usuário tem o papel, só não tem nada visível ainda.
    - `("negado", None)` — nenhum papel com escopo territorial.

    `role_slugs` pode vir pré-computado (ex.: `user_role_slugs(user, ...)`
    já chamado por quem invoca) para evitar refazer a query.
    """
    if role_slugs is None:
        role_slugs = user_role_slugs(user, ROLES_COM_ESCOPO)

    if "super-admin" in role_slugs or "ugp" in role_slugs:
        return "global", None

    estados = _estados_do_papel(user, "articulador-estadual") if "articulador-estadual" in role_slugs else set()
    territorios = _territorios_do_papel(user, "adt-acr") if "adt-acr" in role_slugs else []

    if estados and territorios:
        return "combinado", (estados, territorios)
    if estados:
        return "estados", estados
    if territorios:
        return "territorios", territorios
    if "articulador-estadual" in role_slugs or "adt-acr" in role_slugs:
        return "vazio", None
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
    nunca exceção" (`ufpas_acessiveis_ao_usuario`, `tecnicos_acessiveis_ao_usuario`).
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
    if tipo == "combinado":
        estados, territorios = valor
        return qs.filter(Q(**{state_lookup: list(estados)}) | Q(**{territory_lookup: territorios}))
    if tipo == "vazio":
        return qs.none()

    if raise_on_no_role:
        raise PermissionDenied(deny_message)
    return qs.none()


def atividades_acessiveis_ao_usuario(
    user, qs=None, *, raise_on_no_role=False, deny_message="Você não tem acesso ao módulo SGP.",
):
    """Atividades dentro do escopo territorial do usuário.

    `qs` permite partir de um queryset já com select/prefetch (ver
    `ActivityViewSet.get_queryset`).
    """
    return scope_queryset(
        Activity.objects.all() if qs is None else qs,
        user,
        state_lookup="municipio__state__sigla__in",
        territory_lookup="municipio__territory__in",
        deny_message=deny_message,
        raise_on_no_role=raise_on_no_role,
    )


def municipios_acessiveis_ao_usuario(user):
    """Municípios dentro do escopo territorial do usuário."""
    return scope_queryset(
        Municipality.objects.all(),
        user,
        state_lookup="state__sigla__in",
        territory_lookup="territory__in",
        raise_on_no_role=False,
    )


def ufpas_acessiveis_ao_usuario(user, role_slugs=None, *, raise_on_no_role=False):
    """Retorna queryset de UFPAs acessíveis ao usuário conforme regras territoriais.

    `role_slugs` pode ser passado já computado (ver `UFPAViewSet.get_queryset`)
    para evitar refazer a checagem de roles do usuário em outra query.

    Usa `all_objects`: RLS territorial e soft-delete são preocupações
    independentes — o padrão de só ativas fica em
    `apps.sgp.filters.somente_ativas_sem_filtro_ativo` (listagem e exportação),
    e quem precisa de uma UFPA ativa específica checa `ufpa.ativo` por conta própria.
    """
    return scope_queryset(
        UFPA.all_objects.all(),
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


ROLES_ESCRITA_UFPA = ("super-admin", "adt-acr")


def pode_escrever_ufpa(user, role_slugs=None) -> bool:
    """Matriz do Core: só Super Admin (Total) e ADT/ACR (CRUD territorial)
    escrevem UFPAs. UGP e Articulador só leem."""
    if role_slugs is None:
        role_slugs = user_role_slugs(user, ROLES_ESCRITA_UFPA)
    return bool(set(role_slugs) & set(ROLES_ESCRITA_UFPA))


def pode_escrever_ufpa_no_territorio(user, territorio_id) -> bool:
    """Escrita no território de destino: o mesmo critério de escrita da RLS de
    `sgp_ufpa`. Super Admin escreve em qualquer um; ADT/ACR, só nos
    territórios do próprio perfil. Território indefinido só para Super Admin."""
    role_slugs = user_role_slugs(user, ROLES_ESCRITA_UFPA)
    if "super-admin" in role_slugs:
        return True
    if "adt-acr" not in role_slugs or territorio_id is None:
        return False
    return territorio_id in _territorios_do_papel(user, "adt-acr")
