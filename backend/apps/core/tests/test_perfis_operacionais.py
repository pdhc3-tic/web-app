"""Perfis operacionais: categoria, abrangência por objeto e o que eles não podem ampliar."""
import importlib
from io import StringIO
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.core.models.role import Role
from apps.core.models.territory import Territory
from apps.core.models.user_profile import ObjetoTipo, UserProfile
from apps.core.permissions import IsEventCoordinator, IsSelectionEvaluator
from apps.core.services.permissions import user_states, user_territories
from apps.core.tests.factories import RoleFactory, TerritoryFactory, UserFactory

pytestmark = pytest.mark.django_db

migration = importlib.import_module("apps.core.migrations.0024_perfis_operacionais")

USERS_URL = "/api/v1/users/"
OPERACIONAIS = {"coordenador-evento", "credenciador", "avaliador-selecao", "gestor-edital"}
PRINCIPAIS = {"agricultor", "adt-acr", "articulador-estadual", "ugp", "fgd", "super-admin"}


def _operacional(slug="coordenador-evento"):
    # Sem depender da migration: os testes com `transaction=True` esvaziam a tabela.
    return Role.objects.update_or_create(
        slug=slug, defaults={"nome": slug, "categoria": Role.Categoria.OPERACIONAL},
    )[0]


def _principal(slug="adt-acr"):
    return RoleFactory(slug=slug)


def _payload(*perfis, email="novo@test.com"):
    return {
        "email": email, "nome_completo": "Novo", "password": "SenhaForte1",
        "perfis_input": list(perfis),
    }


def _designar(user, slug, *, objeto_tipo=ObjetoTipo.EVENTO, objeto_id=10):
    return UserProfile.objects.create(user=user, perfil=_operacional(slug), objeto_tipo=objeto_tipo, objeto_id=objeto_id)


@pytest.fixture
def cliente(api_client, super_admin_user):
    api_client.force_authenticate(user=super_admin_user)
    return api_client


class TestCatalogo:
    def test_migration_semeia_os_quatro_como_operacionais_e_pode_rodar_de_novo(self):
        Role.objects.filter(slug__in=OPERACIONAIS).delete()

        migration.semear_perfis_operacionais(apps, None)
        migration.semear_perfis_operacionais(apps, None)

        assert set(Role.objects.filter(categoria=Role.Categoria.OPERACIONAL).values_list("slug", flat=True)) == OPERACIONAIS

    def test_seed_core_cria_as_duas_categorias(self):
        Role.objects.filter(slug__in=OPERACIONAIS | PRINCIPAIS).delete()

        call_command("seed_core", stdout=StringIO())

        categorias = dict(Role.objects.values_list("slug", "categoria"))
        assert {slug for slug in OPERACIONAIS if categorias[slug] == Role.Categoria.OPERACIONAL} == OPERACIONAIS
        assert {slug for slug in PRINCIPAIS if categorias[slug] == Role.Categoria.PRINCIPAL} == PRINCIPAIS

    def test_perfil_novo_e_principal_por_padrao(self):
        assert RoleFactory(slug="ugp").categoria == Role.Categoria.PRINCIPAL

    @pytest.mark.parametrize("rota", ["/api/v1/core/roles/", "/api/v1/roles/"])
    def test_filtra_por_categoria(self, cliente, rota):
        operacional = _operacional()
        principal = _principal()

        resposta = cliente.get(rota, {"categoria": "operacional", "limit": 100})

        ids = {item["id"] for item in resposta.data["results"]}
        assert operacional.pk in ids and principal.pk not in ids
        assert all(item["categoria"] == "operacional" for item in resposta.data["results"])

    def test_rota_do_core_e_so_de_leitura(self, cliente):
        assert cliente.post("/api/v1/core/roles/", {}, format="json").status_code == 405

    def test_categoria_nao_e_gravavel_pela_api(self, cliente):
        perfil = _principal()

        resposta = cliente.patch(f"/api/v1/roles/{perfil.pk}/", {"categoria": "operacional"}, format="json")

        assert resposta.status_code == 200
        perfil.refresh_from_db()
        assert perfil.categoria == Role.Categoria.PRINCIPAL


class TestAtribuicaoPelaApi:
    def test_operacional_com_objeto_junto_de_um_principal(self, cliente):
        principal, operacional = _principal(), _operacional()

        resposta = cliente.post(USERS_URL, _payload(
            {"perfil_id": principal.pk},
            {"perfil_id": operacional.pk, "objeto_tipo": "evento", "objeto_id": 10},
        ), format="json")

        assert resposta.status_code == 201, resposta.data
        vinculo = next(p for p in resposta.data["perfis"] if p["id"] == operacional.pk)
        assert (vinculo["objeto_tipo"], vinculo["objeto_id"], vinculo["territorio_id"]) == ("evento", 10, None)
        outro = next(p for p in resposta.data["perfis"] if p["id"] == principal.pk)
        assert (outro["objeto_tipo"], outro["objeto_id"]) == (None, None)

    def test_principal_com_objeto_e_400(self, cliente):
        resposta = cliente.post(USERS_URL, _payload(
            {"perfil_id": _principal().pk, "objeto_tipo": "evento", "objeto_id": 10},
        ), format="json")

        assert resposta.status_code == 400
        assert "perfis_input" in resposta.data

    @pytest.mark.parametrize("objeto", [
        {}, {"objeto_tipo": "evento"}, {"objeto_id": 10},
    ])
    def test_operacional_sem_objeto_completo_e_400(self, cliente, objeto):
        resposta = cliente.post(USERS_URL, _payload(
            {"perfil_id": _principal().pk}, {"perfil_id": _operacional().pk, **objeto},
        ), format="json")

        assert resposta.status_code == 400

    def test_operacional_com_territorio_e_400(self, cliente):
        resposta = cliente.post(USERS_URL, _payload(
            {"perfil_id": _principal().pk},
            {
                "perfil_id": _operacional().pk, "objeto_tipo": "evento", "objeto_id": 10,
                "territorio_id": TerritoryFactory().pk,
            },
        ), format="json")

        assert resposta.status_code == 400

    @pytest.mark.parametrize("slug,tipo", [
        ("coordenador-evento", "edital"),
        ("credenciador", "candidatura"),
        ("avaliador-selecao", "evento"),
        ("gestor-edital", "evento"),
    ])
    def test_tipo_do_objeto_incoerente_com_o_perfil_e_400(self, cliente, slug, tipo):
        resposta = cliente.post(USERS_URL, _payload(
            {"perfil_id": _principal().pk},
            {"perfil_id": _operacional(slug).pk, "objeto_tipo": tipo, "objeto_id": 10},
        ), format="json")

        assert resposta.status_code == 400

    def test_operacional_sozinho_e_400(self, cliente):
        resposta = cliente.post(USERS_URL, _payload(
            {"perfil_id": _operacional().pk, "objeto_tipo": "evento", "objeto_id": 10},
        ), format="json")

        assert resposta.status_code == 400

    def test_perfil_inexistente_e_400(self, cliente):
        assert cliente.post(USERS_URL, _payload({"perfil_id": 999999}), format="json").status_code == 400

    def test_patch_valida_e_grava_o_objeto(self, cliente):
        usuario = UserFactory()
        principal, operacional = _principal(), _operacional()

        resposta = cliente.patch(f"{USERS_URL}{usuario.pk}/", {"perfis_input": [
            {"perfil_id": principal.pk},
            {"perfil_id": operacional.pk, "objeto_tipo": "evento", "objeto_id": 10},
        ]}, format="json")

        assert resposta.status_code == 200, resposta.data
        vinculo = usuario.profiles.get(perfil=operacional)
        assert (vinculo.objeto_tipo, vinculo.objeto_id) == ("evento", 10)

    def test_patch_de_principal_sem_os_campos_opcionais_continua_valido(self, cliente):
        usuario = UserFactory()

        resposta = cliente.patch(
            f"{USERS_URL}{usuario.pk}/", {"perfis_input": [{"perfil_id": _principal().pk}]}, format="json",
        )

        assert resposta.status_code == 200, resposta.data


class TestNoBanco:
    def _inserir(self, perfil, **campos):
        with pytest.raises(IntegrityError), transaction.atomic():
            UserProfile.objects.create(user=UserFactory(), perfil=perfil, **campos)

    def test_principal_com_objeto_e_recusado(self):
        self._inserir(_principal(), objeto_tipo=ObjetoTipo.EVENTO, objeto_id=1)

    def test_operacional_sem_objeto_e_recusado(self):
        self._inserir(_operacional())

    def test_operacional_com_territorio_e_recusado(self):
        self._inserir(_operacional(), objeto_tipo=ObjetoTipo.EVENTO, objeto_id=1, territorio=TerritoryFactory())

    def test_tipo_sem_id_e_recusado(self):
        self._inserir(_operacional(), objeto_tipo=ObjetoTipo.EVENTO)

    def test_id_sem_tipo_e_recusado(self):
        self._inserir(_principal(), objeto_id=1)

    def test_vinculos_validos_sao_aceitos(self):
        usuario = UserFactory()

        UserProfile.objects.create(user=usuario, perfil=_principal(), territorio=TerritoryFactory())
        _designar(usuario, "coordenador-evento")

        assert usuario.profiles.count() == 2

    def test_clean_mostra_o_erro_antes_do_banco(self):
        vinculo = UserProfile(user=UserFactory(), perfil=_principal(), objeto_tipo=ObjetoTipo.EVENTO, objeto_id=1)

        with pytest.raises(ValidationError):
            vinculo.clean()


class TestPermissoes:
    @pytest.mark.parametrize("classe,slug,tipo", [
        (IsEventCoordinator, "coordenador-evento", ObjetoTipo.EVENTO),
        (IsSelectionEvaluator, "avaliador-selecao", ObjetoTipo.CANDIDATURA),
    ])
    def test_perfil_e_objeto(self, classe, slug, tipo):
        usuario = UserFactory()
        _designar(usuario, slug, objeto_tipo=tipo, objeto_id=10)
        request = SimpleNamespace(user=usuario)
        permissao = classe()

        assert permissao.has_permission(request, None) is True
        assert permissao.has_object_permission(request, None, SimpleNamespace(pk=10)) is True
        assert permissao.has_object_permission(request, None, SimpleNamespace(pk=11)) is False

    @pytest.mark.parametrize("classe", [IsEventCoordinator, IsSelectionEvaluator])
    def test_sem_o_perfil_nega(self, classe):
        request = SimpleNamespace(user=UserFactory())
        permissao = classe()

        assert permissao.has_permission(request, None) is False
        assert permissao.has_object_permission(request, None, SimpleNamespace(pk=10)) is False

    def test_mesmo_id_em_outro_tipo_de_objeto_nao_vale(self):
        usuario = UserFactory()
        _designar(usuario, "avaliador-selecao", objeto_tipo=ObjetoTipo.CANDIDATURA, objeto_id=10)

        permitido = IsEventCoordinator().has_object_permission(
            SimpleNamespace(user=usuario), None, SimpleNamespace(pk=10),
        )

        assert permitido is False

    def test_outro_perfil_operacional_no_mesmo_objeto_nao_vale(self):
        usuario = UserFactory()
        _designar(usuario, "credenciador", objeto_tipo=ObjetoTipo.EVENTO, objeto_id=10)

        permitido = IsEventCoordinator().has_object_permission(
            SimpleNamespace(user=usuario), None, SimpleNamespace(pk=10),
        )

        assert permitido is False


class TestNaoAmpliaOAcesso:
    def test_adt_que_vira_credenciador_mantem_so_o_proprio_territorio(self):
        territorio = TerritoryFactory(estados=["RN"])
        TerritoryFactory(estados=["CE"])
        usuario = UserFactory(profiles=[(_principal(), territorio)])

        _designar(usuario, "credenciador")

        assert list(user_territories(usuario)) == [territorio]
        assert user_states(usuario) == {"RN"}

    def test_so_o_operacional_nao_e_acesso_global(self):
        TerritoryFactory()
        usuario = UserFactory()
        _designar(usuario, "credenciador")

        assert not user_territories(usuario).exists()

    def test_perfil_principal_sem_territorio_continua_global(self):
        TerritoryFactory()
        usuario = UserFactory(profiles=[(_principal("ugp"), None)])

        assert user_territories(usuario).count() == Territory.objects.count()
