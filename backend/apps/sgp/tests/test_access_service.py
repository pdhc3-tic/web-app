import pytest

from apps.core.tests.factories import RoleFactory, UserFactory
from apps.sgp.models import UPF
from apps.sgp.services.access import resolver_escopo, scope_queryset
from apps.sgp.tests.factories import UPFFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def role_super_admin():
    return RoleFactory(slug="super-admin", nome="Super Admin")


@pytest.fixture
def role_ugp():
    return RoleFactory(slug="ugp", nome="UGP")


@pytest.fixture
def role_articulador():
    return RoleFactory(slug="articulador-estadual", nome="Articulador Estadual")


@pytest.fixture
def role_adt():
    return RoleFactory(slug="adt-acr", nome="ADT/ACR")


@pytest.fixture
def role_sem_escopo():
    return RoleFactory(slug="agricultor", nome="Agricultor")


# ===========================================================================
# resolver_escopo()
# ===========================================================================

def test_super_admin_tem_escopo_global(role_super_admin):
    user = UserFactory(profiles=[(role_super_admin, None)])
    assert resolver_escopo(user) == ("global", None)


def test_ugp_tem_escopo_global(role_ugp):
    user = UserFactory(profiles=[(role_ugp, None)])
    assert resolver_escopo(user) == ("global", None)


def test_articulador_com_territorio_ve_seus_estados(role_articulador, territory_rn):
    user = UserFactory(profiles=[(role_articulador, territory_rn)])
    tipo, valor = resolver_escopo(user)
    assert tipo == "estados"
    assert valor == {"RN"}


def test_articulador_sem_territorio_cai_no_fallback_global(role_articulador, territory_rn, territory_ce):
    """territorio=None é concessão deliberada de acesso global — comportamento
    intencional herdado de user_states(), preservado sem alteração."""
    user = UserFactory(profiles=[(role_articulador, None)])
    tipo, valor = resolver_escopo(user)
    assert tipo == "estados"
    assert valor == {"RN", "CE"}


def test_adt_com_territorio_ve_seu_territorio(role_adt, territory_rn):
    user = UserFactory(profiles=[(role_adt, territory_rn)])
    tipo, valor = resolver_escopo(user)
    assert tipo == "territorios"
    assert valor == [territory_rn.pk]


def test_adt_sem_territorio_nao_recebe_acesso_global(role_adt, territory_rn, territory_ce):
    """O gap: territorio=None para adt-acr não pode virar acesso global —
    diferente de articulador-estadual, aqui é lacuna de cadastro, não concessão."""
    user = UserFactory(profiles=[(role_adt, None)])
    assert resolver_escopo(user) == ("negado", None)


def test_adt_com_multiplos_territorios_ignora_perfil_sem_territorio(role_adt, territory_rn, territory_ce):
    user = UserFactory(profiles=[(role_adt, territory_rn), (role_adt, None)])
    tipo, valor = resolver_escopo(user)
    assert tipo == "territorios"
    assert valor == [territory_rn.pk]


def test_sem_papel_com_escopo_e_negado(role_sem_escopo):
    user = UserFactory(profiles=[(role_sem_escopo, None)])
    assert resolver_escopo(user) == ("negado", None)


def test_usuario_sem_nenhum_perfil_e_negado():
    user = UserFactory()
    assert resolver_escopo(user) == ("negado", None)


def test_role_slugs_pre_computado_evita_query(role_super_admin, django_assert_num_queries):
    user = UserFactory(profiles=[(role_super_admin, None)])
    with django_assert_num_queries(0):
        assert resolver_escopo(user, role_slugs={"super-admin"}) == ("global", None)


# ===========================================================================
# scope_queryset()
# ===========================================================================

UPF_LOOKUPS = dict(
    state_lookup="municipio__state__sigla__in",
    territory_lookup="territorio__in",
)


def test_scope_queryset_global_retorna_tudo(role_super_admin, municipio_rn, projeto):
    user = UserFactory(profiles=[(role_super_admin, None)])
    upf = UPFFactory(municipio=municipio_rn, projeto=projeto)
    result = scope_queryset(UPF.objects.all(), user, **UPF_LOOKUPS)
    assert list(result) == [upf]


def test_scope_queryset_filtra_por_estado(role_articulador, territory_rn, municipio_rn, municipio_ce, projeto):
    user = UserFactory(profiles=[(role_articulador, territory_rn)])
    upf_rn = UPFFactory(municipio=municipio_rn, projeto=projeto)
    UPFFactory(municipio=municipio_ce, projeto=projeto)
    result = scope_queryset(UPF.objects.all(), user, **UPF_LOOKUPS)
    assert list(result) == [upf_rn]


def test_scope_queryset_filtra_por_territorio(role_adt, territory_rn, territory_ce, municipio_rn, municipio_ce, projeto):
    user = UserFactory(profiles=[(role_adt, territory_rn)])
    upf_rn = UPFFactory(municipio=municipio_rn, projeto=projeto)
    UPFFactory(municipio=municipio_ce, projeto=projeto)
    result = scope_queryset(UPF.objects.all(), user, **UPF_LOOKUPS)
    assert list(result) == [upf_rn]


def test_scope_queryset_sem_papel_levanta_permission_denied_por_padrao(role_sem_escopo):
    from rest_framework.exceptions import PermissionDenied

    user = UserFactory(profiles=[(role_sem_escopo, None)])
    with pytest.raises(PermissionDenied):
        scope_queryset(UPF.objects.all(), user, **UPF_LOOKUPS)


def test_scope_queryset_sem_papel_retorna_vazio_quando_raise_desligado(role_sem_escopo):
    user = UserFactory(profiles=[(role_sem_escopo, None)])
    result = scope_queryset(
        UPF.objects.all(), user, raise_on_no_role=False, **UPF_LOOKUPS,
    )
    assert list(result) == []


def test_scope_queryset_adt_sem_territorio_nao_vaza_via_queryset(role_adt, territory_rn, municipio_rn, projeto):
    user = UserFactory(profiles=[(role_adt, None)])
    UPFFactory(municipio=municipio_rn, projeto=projeto)
    result = scope_queryset(
        UPF.objects.all(), user, raise_on_no_role=False, **UPF_LOOKUPS,
    )
    assert list(result) == []
