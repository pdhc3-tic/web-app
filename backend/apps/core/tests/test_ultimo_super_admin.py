"""Ninguém desativa a própria conta, e o sistema não fica sem Super Admin ativo."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.contrib.admin.sites import site
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from django.forms.models import inlineformset_factory
from django.test import RequestFactory
from rest_framework.exceptions import ValidationError

from apps.core.models import User, UserProfile
from apps.core.services.usuarios import desativar, exigir_super_admin_restante
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
        assert "último Super Admin ativo" in str(resposta.data["perfis_input"])
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
class TestAcessoRevogado:
    def test_super_admin_revogado_nao_conta_como_outro(self, perfil_super_admin):
        unico_que_entra = UserFactory(profiles=[(perfil_super_admin, None)])
        UserFactory(acesso_revogado=True, profiles=[(perfil_super_admin, None)])

        with pytest.raises(ValidationError):
            desativar(unico_que_entra, por=None)

    def test_revogar_o_proprio_acesso_e_400(self, cliente, super_admin_user, outro_super_admin):
        resposta = cliente.patch(f"{USERS_URL}{super_admin_user.pk}/revogar-acesso/")

        assert resposta.status_code == 400
        assert "próprio acesso" in str(resposta.data["acesso_revogado"])
        super_admin_user.refresh_from_db()
        assert super_admin_user.acesso_revogado is False

    def test_revogar_outro_super_admin_com_quem_reative_passa(self, cliente, outro_super_admin):
        assert cliente.patch(f"{USERS_URL}{outro_super_admin.pk}/revogar-acesso/").status_code == 200
        outro_super_admin.refresh_from_db()
        assert outro_super_admin.acesso_revogado is True


def _formset_do_inline(usuario, *, excluir):
    UserProfileInline = next(inline for inline in site._registry[User].inlines if inline.model is UserProfile)
    FormSet = inlineformset_factory(
        User, UserProfile, formset=UserProfileInline.formset,
        fields=("perfil", "territorio", "objeto_tipo", "objeto_id"), extra=0, can_delete=True,
    )
    vinculo = usuario.profiles.get()
    dados = {
        "profiles-TOTAL_FORMS": "1", "profiles-INITIAL_FORMS": "1",
        "profiles-0-id": str(vinculo.pk), "profiles-0-perfil": str(vinculo.perfil_id),
    }
    if excluir:
        dados["profiles-0-DELETE"] = "on"
    return FormSet(dados, instance=usuario, prefix="profiles")


def _request(usuario):
    request = RequestFactory().post("/")
    request.user = usuario
    return request


@pytest.mark.django_db
class TestAdmin:
    def test_inline_nao_tira_o_perfil_do_ultimo_super_admin(self, super_admin_user):
        formset = _formset_do_inline(super_admin_user, excluir=True)

        assert not formset.is_valid()
        assert "último Super Admin ativo" in str(formset.non_form_errors())

    def test_inline_tira_o_perfil_com_outro_super_admin_ativo(self, super_admin_user, outro_super_admin):
        formset = _formset_do_inline(outro_super_admin, excluir=True)

        assert formset.is_valid(), formset.non_form_errors()
        formset.save()
        assert not outro_super_admin.profiles.exists()

    def test_inline_sem_mudar_o_perfil_do_ultimo_super_admin_passa(self, super_admin_user):
        assert _formset_do_inline(super_admin_user, excluir=False).is_valid()

    def test_admin_nao_desativa_o_ultimo_super_admin_ativo(self, super_admin_user, monkeypatch):
        """Pelo Admin entra quem é superusuário do Django, mesmo sem o perfil Super Admin."""
        model_admin = site._registry[User]
        mensagem = Mock()
        monkeypatch.setattr(model_admin, "message_user", mensagem)
        super_admin_user.ativo = False

        model_admin.save_model(
            _request(UserFactory(is_superuser=True)), super_admin_user, SimpleNamespace(changed_data=["ativo"]), True,
        )

        assert "último Super Admin ativo" in mensagem.call_args.args[1]
        super_admin_user.refresh_from_db()
        assert super_admin_user.ativo is True

    def test_admin_nao_exclui_o_ultimo_super_admin(self, super_admin_user):
        model_admin = site._registry[User]
        request = _request(UserFactory(is_superuser=True))

        assert not model_admin.has_delete_permission(request, super_admin_user)
        with pytest.raises(PermissionDenied):
            model_admin.delete_queryset(request, User.objects.filter(pk=super_admin_user.pk))
        assert User.objects.filter(pk=super_admin_user.pk).exists()

    def test_admin_exclui_super_admin_com_outro_ativo(self, super_admin_user, outro_super_admin):
        model_admin = site._registry[User]
        request = _request(UserFactory(is_superuser=True))

        assert model_admin.has_delete_permission(request, outro_super_admin)
        model_admin.delete_model(request, outro_super_admin)
        assert not User.objects.filter(pk=outro_super_admin.pk).exists()


@pytest.mark.django_db
class TestAdminDePerfis:
    def _formulario(self, vinculo, perfil):
        model_admin = site._registry[UserProfile]
        Formulario = model_admin.get_form(_request(UserFactory(is_superuser=True)), vinculo)
        return Formulario(data={"user": vinculo.user_id, "perfil": perfil.pk}, instance=vinculo)

    def test_nao_troca_o_perfil_do_ultimo_super_admin(self, super_admin_user):
        vinculo = super_admin_user.profiles.get()

        formulario = self._formulario(vinculo, RoleFactory(slug="ugp"))

        assert not formulario.is_valid()
        assert "último Super Admin ativo" in str(formulario.non_field_errors())

    def test_troca_o_perfil_com_outro_super_admin_ativo(self, super_admin_user, outro_super_admin):
        formulario = self._formulario(outro_super_admin.profiles.get(), RoleFactory(slug="ugp"))

        assert formulario.is_valid(), formulario.errors

    def test_nao_exclui_o_vinculo_do_ultimo_super_admin(self, super_admin_user):
        model_admin = site._registry[UserProfile]
        request = _request(UserFactory(is_superuser=True))
        vinculo = super_admin_user.profiles.get()

        assert not model_admin.has_delete_permission(request, vinculo)
        with pytest.raises(PermissionDenied):
            model_admin.delete_model(request, vinculo)
        with pytest.raises(PermissionDenied):
            model_admin.delete_queryset(request, UserProfile.objects.filter(pk=vinculo.pk))
        assert UserProfile.objects.filter(pk=vinculo.pk).exists()

    def test_exclui_o_vinculo_com_outro_super_admin_ativo(self, super_admin_user, outro_super_admin):
        model_admin = site._registry[UserProfile]
        vinculo = outro_super_admin.profiles.get()

        assert model_admin.has_delete_permission(_request(UserFactory(is_superuser=True)), vinculo)


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


@pytest.mark.django_db(transaction=True)
def test_desativar_enquanto_outro_pedido_tira_o_perfil_do_colega(perfil_super_admin):
    """O pedido que esperou a trava confere de novo e vê o vínculo apagado pelo outro."""
    ana = UserFactory(profiles=[(perfil_super_admin, None)])
    bia = UserFactory(profiles=[(perfil_super_admin, None)])
    tirou, pode_commitar = threading.Event(), threading.Event()
    erros = {}

    def tirar_o_perfil_de_bia():
        try:
            with transaction.atomic():
                exigir_super_admin_restante(sem_usuarios=[bia.pk], campo="perfis_input")
                UserProfile.objects.filter(user_id=bia.pk, perfil__slug="super-admin").delete()
                tirou.set()
                pode_commitar.wait(timeout=10)
        except Exception as exc:
            erros["perfil"] = exc
        finally:
            tirou.set()
            connection.close()

    def desativar_ana():
        try:
            desativar(User.objects.get(pk=ana.pk), por=None)
        except Exception as exc:
            erros["desativar"] = exc
        finally:
            connection.close()

    primeira = threading.Thread(target=tirar_o_perfil_de_bia)
    primeira.start()
    assert tirou.wait(timeout=10)
    segunda = threading.Thread(target=desativar_ana)
    segunda.start()
    try:
        _esperar_alguem_bloqueado()
    finally:
        pode_commitar.set()
        primeira.join(timeout=15)
        segunda.join(timeout=15)

    assert not primeira.is_alive() and not segunda.is_alive()
    assert set(erros) == {"desativar"} and isinstance(erros["desativar"], ValidationError)
    assert User.objects.get(pk=ana.pk).ativo is True


@pytest.mark.django_db
class TestCamposDaRevogacao:
    def test_patch_nao_grava_acesso_revogado(self, cliente, super_admin_user):
        resposta = cliente.patch(
            f"{USERS_URL}{super_admin_user.pk}/", {"acesso_revogado": True, "acesso_revogado_em": None}, format="json",
        )

        assert resposta.status_code == 200, resposta.data
        super_admin_user.refresh_from_db()
        assert super_admin_user.acesso_revogado is False

    def test_revogacao_volta_inteira_se_a_auditoria_falhar(self, cliente, outro_super_admin, monkeypatch):
        def falhar(**_):
            raise RuntimeError("auditoria fora do ar")

        monkeypatch.setattr("apps.core.views.users.log_audit", falhar)

        with pytest.raises(RuntimeError):
            cliente.patch(f"{USERS_URL}{outro_super_admin.pk}/revogar-acesso/")

        outro_super_admin.refresh_from_db()
        assert outro_super_admin.acesso_revogado is False

    def test_conferencia_fora_de_transacao_e_recusada(self, monkeypatch):
        conexao = SimpleNamespace(in_atomic_block=False)
        monkeypatch.setattr("apps.core.services.usuarios.transaction.get_connection", lambda: conexao)

        with pytest.raises(TransactionManagementError):
            exigir_super_admin_restante(sem_usuarios=[1])


@pytest.mark.django_db(transaction=True)
class TestExclusaoEmLotePeloAdmin:
    """A ação "Excluir selecionados" roda sem a transação que o Admin abre na edição."""

    @pytest.fixture
    def admin_logado(self, client):
        client.force_login(UserFactory(is_superuser=True))
        return client

    def _excluir(self, cliente, modelo, pks):
        return cliente.post(f"/admin/core/{modelo}/", {
            "action": "delete_selected", "_selected_action": [str(pk) for pk in pks], "post": "yes",
        })

    def test_exclui_vinculo_que_nao_e_super_admin(self, admin_logado, perfil_super_admin):
        UserFactory(profiles=[(perfil_super_admin, None)])
        vinculo = UserFactory(profiles=[(RoleFactory(slug="ugp"), None)]).profiles.get()

        resposta = self._excluir(admin_logado, "userprofile", [vinculo.pk])

        assert resposta.status_code == 302
        assert not UserProfile.objects.filter(pk=vinculo.pk).exists()

    def test_nao_exclui_o_vinculo_do_ultimo_super_admin(self, admin_logado, perfil_super_admin):
        vinculo = UserFactory(profiles=[(perfil_super_admin, None)]).profiles.get()

        resposta = self._excluir(admin_logado, "userprofile", [vinculo.pk])

        assert resposta.status_code == 403
        assert UserProfile.objects.filter(pk=vinculo.pk).exists()

    def test_nao_exclui_os_dois_ultimos_super_admins_juntos(self, admin_logado, perfil_super_admin):
        ana = UserFactory(profiles=[(perfil_super_admin, None)])
        bia = UserFactory(profiles=[(perfil_super_admin, None)])

        resposta = self._excluir(admin_logado, "user", [ana.pk, bia.pk])

        assert resposta.status_code == 403
        assert User.objects.filter(pk__in=[ana.pk, bia.pk]).count() == 2
