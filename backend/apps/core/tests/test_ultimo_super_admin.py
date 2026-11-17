"""Ninguém desativa a própria conta, e o sistema não fica sem Super Admin ativo."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.contrib.admin.sites import site
from django.db import connection, transaction
from django.forms.models import inlineformset_factory
from django.test import RequestFactory
from rest_framework.exceptions import ValidationError

from apps.core.models import User, UserProfile
from apps.core.services.usuarios import desativar
from apps.core.tests.factories import RoleFactory, UserFactory

USERS_URL = "/api/v1/users/"


@pytest.fixture
def perfil_super_admin(db):
    return RoleFactory(slug="super-admin", nome="Super Admin")


@pytest.fixture
def outro_super_admin(perfil_super_admin):
    return UserFactory(nome="Outro Super Admin", profiles=[(perfil_super_admin, None)])


@pytest.fixture
def cliente(api_client, super_admin_user):
    api_client.force_authenticate(user=super_admin_user)
    return api_client


@pytest.mark.django_db
class TestPropriaConta:
    def test_delete_da_propria_conta_e_400(self, cliente, super_admin_user, outro_super_admin):
        resposta = cliente.delete(f"{USERS_URL}{super_admin_user.pk}/")

        assert resposta.status_code == 400
        assert "própria conta" in str(resposta.data["ativo"])
        super_admin_user.refresh_from_db()
        assert super_admin_user.ativo is True

    def test_patch_ativo_false_na_propria_conta_e_400(self, cliente, super_admin_user, outro_super_admin):
        resposta = cliente.patch(f"{USERS_URL}{super_admin_user.pk}/", {"ativo": False}, format="json")

        assert resposta.status_code == 400
        super_admin_user.refresh_from_db()
        assert super_admin_user.ativo is True

    def test_desativar_outro_usuario_continua_valendo(self, cliente, outro_super_admin):
        assert cliente.delete(f"{USERS_URL}{outro_super_admin.pk}/").status_code == 204
        outro_super_admin.refresh_from_db()
        assert outro_super_admin.ativo is False


@pytest.mark.django_db
class TestUltimoSuperAdmin:
    def test_servico_recusa_desativar_o_ultimo_super_admin_ativo(self, perfil_super_admin):
        unico = UserFactory(profiles=[(perfil_super_admin, None)])
        UserFactory(ativo=False, profiles=[(perfil_super_admin, None)])

        with pytest.raises(ValidationError) as erro:
            desativar(unico, por=None)

        assert "último Super Admin ativo" in str(erro.value.detail["ativo"])
        unico.refresh_from_db()
        assert unico.ativo is True

    def test_com_outro_super_admin_ativo_desativa(self, perfil_super_admin, outro_super_admin):
        alvo = UserFactory(profiles=[(perfil_super_admin, None)])

        desativar(alvo, por=None)

        alvo.refresh_from_db()
        assert alvo.ativo is False

    def test_quem_nao_e_super_admin_nao_depende_de_outro(self):
        alvo = UserFactory()

        desativar(alvo, por=None)

        alvo.refresh_from_db()
        assert alvo.ativo is False

    def test_patch_que_tira_o_perfil_do_ultimo_super_admin_e_400(self, cliente, super_admin_user):
        ugp = RoleFactory(slug="ugp")

        resposta = cliente.patch(
            f"{USERS_URL}{super_admin_user.pk}/", {"perfis_input": [{"perfil_id": ugp.pk}]}, format="json",
        )

        assert resposta.status_code == 400
        assert super_admin_user.profiles.filter(perfil__slug="super-admin").exists()

    def test_patch_que_tira_o_perfil_com_outro_super_admin_ativo_passa(self, cliente, outro_super_admin):
        ugp = RoleFactory(slug="ugp")

        resposta = cliente.patch(
            f"{USERS_URL}{outro_super_admin.pk}/", {"perfis_input": [{"perfil_id": ugp.pk}]}, format="json",
        )

        assert resposta.status_code == 200, resposta.data
        assert not outro_super_admin.profiles.filter(perfil__slug="super-admin").exists()

    def test_patch_que_mantem_o_perfil_do_ultimo_super_admin_passa(self, cliente, super_admin_user, perfil_super_admin):
        ugp = RoleFactory(slug="ugp")

        resposta = cliente.patch(f"{USERS_URL}{super_admin_user.pk}/", {"perfis_input": [
            {"perfil_id": perfil_super_admin.pk}, {"perfil_id": ugp.pk},
        ]}, format="json")

        assert resposta.status_code == 200, resposta.data


@pytest.mark.django_db
class TestAdmin:
    def _salvar_perfis_pelo_admin(self, usuario, ator, monkeypatch):
        """O inline com o único vínculo do usuário marcado para excluir."""
        vinculo = usuario.profiles.get()
        FormSet = inlineformset_factory(
            User, UserProfile, fields=("perfil", "territorio", "objeto_tipo", "objeto_id"), extra=0, can_delete=True,
        )
        formset = FormSet({
            "profiles-TOTAL_FORMS": "1", "profiles-INITIAL_FORMS": "1",
            "profiles-0-id": str(vinculo.pk), "profiles-0-perfil": str(vinculo.perfil_id), "profiles-0-DELETE": "on",
        }, instance=usuario, prefix="profiles")
        assert formset.is_valid(), formset.errors
        model_admin = site._registry[User]
        mensagem = Mock()
        monkeypatch.setattr(model_admin, "message_user", mensagem)
        request = RequestFactory().post("/")
        request.user = ator
        model_admin.save_related(request, SimpleNamespace(instance=usuario, save_m2m=Mock()), [formset], True)
        return mensagem

    def test_inline_nao_tira_o_perfil_do_ultimo_super_admin(self, super_admin_user, monkeypatch):
        mensagem = self._salvar_perfis_pelo_admin(super_admin_user, super_admin_user, monkeypatch)

        assert "último Super Admin ativo" in mensagem.call_args.args[1]
        assert super_admin_user.profiles.filter(perfil__slug="super-admin").exists()

    def test_inline_tira_o_perfil_com_outro_super_admin_ativo(self, super_admin_user, outro_super_admin, monkeypatch):
        mensagem = self._salvar_perfis_pelo_admin(outro_super_admin, super_admin_user, monkeypatch)

        mensagem.assert_not_called()
        assert not outro_super_admin.profiles.exists()


def _esperar_alguem_bloqueado(timeout=10):
    prazo = time.monotonic() + timeout
    while time.monotonic() < prazo:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
            )
            if cursor.fetchone()[0]:
                return
        time.sleep(0.02)
    raise AssertionError("Nenhuma conexão ficou esperando lock.")


@pytest.mark.django_db(transaction=True)
def test_dois_super_admins_desativando_um_ao_outro_ao_mesmo_tempo(perfil_super_admin):
    """Cada um é o outro Super Admin ativo do pedido do colega: sem a trava, os dois passariam."""
    ana = UserFactory(profiles=[(perfil_super_admin, None)])
    bia = UserFactory(profiles=[(perfil_super_admin, None)])
    desativou, pode_commitar = threading.Event(), threading.Event()
    erros = {}

    def ana_desativa_bia():
        try:
            with transaction.atomic():
                desativar(User.objects.get(pk=bia.pk), por=ana)
                desativou.set()
                pode_commitar.wait(timeout=10)
        except Exception as exc:
            erros["ana"] = exc
        finally:
            desativou.set()
            connection.close()

    def bia_desativa_ana():
        try:
            desativar(User.objects.get(pk=ana.pk), por=bia)
        except Exception as exc:
            erros["bia"] = exc
        finally:
            connection.close()

    primeira = threading.Thread(target=ana_desativa_bia)
    primeira.start()
    assert desativou.wait(timeout=10)
    segunda = threading.Thread(target=bia_desativa_ana)
    segunda.start()
    try:
        _esperar_alguem_bloqueado()
    finally:
        pode_commitar.set()
        primeira.join(timeout=15)
        segunda.join(timeout=15)

    assert not primeira.is_alive() and not segunda.is_alive()
    assert set(erros) == {"bia"} and isinstance(erros["bia"], ValidationError)
    assert set(User.objects.filter(pk__in=[ana.pk, bia.pk], ativo=True).values_list("pk", flat=True)) == {ana.pk}
