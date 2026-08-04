import pytest

from apps.core.models.audit_log import AuditLog

from ..models import Comunidade

pytestmark = pytest.mark.django_db

LIST_URL_TPL = '/api/v1/municipios/{}/comunidades/'
DETAIL_URL_TPL = '/api/v1/comunidades/{}/'


# ──────────────────────────────────────────────────────────────
# CREATE
# ──────────────────────────────────────────────────────────────


class TestCreateComunidade:
    def test_create_comunidade_as_adt_returns_201(self, adt_client, municipio):
        url = LIST_URL_TPL.format(municipio.pk)
        payload = {'nome': 'Cacimba Nova'}
        response = adt_client.post(url, payload, format='json')
        assert response.status_code == 201
        assert response.data['nome'] == 'Cacimba Nova'
        assert response.data['municipio'] == municipio.pk
        assert response.data['ativa'] is True
        assert 'criada_por' in response.data
        assert Comunidade.objects.filter(nome='Cacimba Nova', municipio=municipio).exists()

    def test_create_comunidade_unauthenticated_returns_401(self, api_client, municipio):
        url = LIST_URL_TPL.format(municipio.pk)
        payload = {'nome': 'Comunidade Secreta'}
        response = api_client.post(url, payload, format='json')
        assert response.status_code == 401

    def test_create_comunidade_duplicate_in_same_municipio_returns_400(
        self, adt_client, municipio
    ):
        url = LIST_URL_TPL.format(municipio.pk)
        payload = {'nome': 'Cacimba Nova'}
        response1 = adt_client.post(url, payload, format='json')
        assert response1.status_code == 201

        response2 = adt_client.post(url, payload, format='json')
        assert response2.status_code == 400
        assert 'Já existe uma comunidade ativa com este nome neste município' in str(
            response2.data
        )

    def test_create_comunidade_same_name_different_municipios_allowed(
        self, adt_client, municipio, outro_municipio
    ):
        url1 = LIST_URL_TPL.format(municipio.pk)
        payload = {'nome': 'Cacimba Nova'}
        response1 = adt_client.post(url1, payload, format='json')
        assert response1.status_code == 201

        url2 = LIST_URL_TPL.format(outro_municipio.pk)
        response2 = adt_client.post(url2, payload, format='json')
        assert response2.status_code == 201
        assert response2.data['municipio'] == outro_municipio.pk


# ──────────────────────────────────────────────────────────────
# LIST
# ──────────────────────────────────────────────────────────────


class TestListComunidades:
    def test_list_comunidades_filtered_by_municipio(
        self, adt_client, municipio, outro_municipio
    ):
        c1 = Comunidade.objects.create(
            nome='Comunidade A', municipio=municipio, criada_por=adt_client.handler._force_user,
        )
        Comunidade.objects.create(
            nome='Comunidade B', municipio=outro_municipio, criada_por=adt_client.handler._force_user,
        )

        url = LIST_URL_TPL.format(municipio.pk)
        response = adt_client.get(url)
        assert response.status_code == 200
        results = response.data['results']
        nomes = [r['nome'] for r in results]
        assert 'Comunidade A' in nomes
        assert 'Comunidade B' not in nomes

    def test_list_comunidades_search_by_q(self, adt_client, municipio):
        Comunidade.objects.create(
            nome='Cacimba do Sítio', municipio=municipio, criada_por=adt_client.handler._force_user,
        )
        Comunidade.objects.create(
            nome='Saco do Ferreiro', municipio=municipio, criada_por=adt_client.handler._force_user,
        )

        url = LIST_URL_TPL.format(municipio.pk) + '?q=cacimba'
        response = adt_client.get(url)
        assert response.status_code == 200
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['nome'] == 'Cacimba do Sítio'

    def test_list_default_excludes_inactive(self, adt_client, municipio):
        ativa = Comunidade.objects.create(
            nome='Ativa', municipio=municipio, ativa=True, criada_por=adt_client.handler._force_user,
        )
        Comunidade.objects.create(
            nome='Inativa', municipio=municipio, ativa=False, criada_por=adt_client.handler._force_user,
        )

        url = LIST_URL_TPL.format(municipio.pk)
        response = adt_client.get(url)
        assert response.status_code == 200
        results = response.data['results']
        nomes = [r['nome'] for r in results]
        assert 'Ativa' in nomes
        assert 'Inativa' not in nomes

    def test_list_inactive_with_ativa_param_by_admin(self, super_admin_client, municipio):
        Comunidade.objects.create(
            nome='Inativa', municipio=municipio, ativa=False, criada_por=super_admin_client.handler._force_user,
        )
        url = LIST_URL_TPL.format(municipio.pk) + '?ativa=false'
        response = super_admin_client.get(url)
        assert response.status_code == 200
        nomes = [r['nome'] for r in response.data['results']]
        assert 'Inativa' in nomes


# ──────────────────────────────────────────────────────────────
# PATCH
# ──────────────────────────────────────────────────────────────


class TestPatchComunidade:
    def test_patch_comunidade_as_adt_returns_403(self, adt_client, municipio):
        comunidade = Comunidade.objects.create(
            nome='Antigo', municipio=municipio, criada_por=adt_client.handler._force_user,
        )
        url = DETAIL_URL_TPL.format(comunidade.pk)
        response = adt_client.patch(url, {'nome': 'Novo'}, format='json')
        assert response.status_code == 403

    def test_patch_comunidade_as_super_admin_returns_200(
        self, super_admin_client, municipio
    ):
        comunidade = Comunidade.objects.create(
            nome='Antigo', municipio=municipio, criada_por=super_admin_client.handler._force_user,
        )
        url = DETAIL_URL_TPL.format(comunidade.pk)
        response = super_admin_client.patch(url, {'nome': 'Novo Nome'}, format='json')
        assert response.status_code == 200
        assert response.data['nome'] == 'Novo Nome'

    def test_patch_comunidade_as_ugp_returns_200(self, ugp_client, municipio):
        comunidade = Comunidade.objects.create(
            nome='Antigo', municipio=municipio, criada_por=ugp_client.handler._force_user,
        )
        url = DETAIL_URL_TPL.format(comunidade.pk)
        response = ugp_client.patch(url, {'nome': 'UGP Editou'}, format='json')
        assert response.status_code == 200
        assert response.data['nome'] == 'UGP Editou'


# ──────────────────────────────────────────────────────────────
# DELETE (soft-delete)
# ──────────────────────────────────────────────────────────────


class TestDeleteComunidade:
    def test_delete_comunidade_is_soft_delete(self, super_admin_client, municipio):
        comunidade = Comunidade.objects.create(
            nome='Sera Removida',
            municipio=municipio,
            ativa=True,
            criada_por=super_admin_client.handler._force_user,
        )
        pk = comunidade.pk
        url = DETAIL_URL_TPL.format(pk)
        response = super_admin_client.delete(url)
        assert response.status_code == 204

        comunidade.refresh_from_db()
        assert comunidade.ativa is False

        assert Comunidade.objects.filter(pk=pk).exists()

    def test_delete_comunidade_as_adt_returns_403(self, adt_client, municipio):
        comunidade = Comunidade.objects.create(
            nome='Nao Pode Apagar',
            municipio=municipio,
            criada_por=adt_client.handler._force_user,
        )
        url = DETAIL_URL_TPL.format(comunidade.pk)
        response = adt_client.delete(url)
        assert response.status_code == 403


# ──────────────────────────────────────────────────────────────
# AUDIT LOG
# ──────────────────────────────────────────────────────────────


class TestAuditLogOnComunidade:
    def test_audit_log_entry_on_create(self, adt_client, municipio):
        url = LIST_URL_TPL.format(municipio.pk)
        payload = {'nome': 'Auditavel'}
        response = adt_client.post(url, payload, format='json')
        assert response.status_code == 201

        log = AuditLog.objects.filter(
            entidade='Comunidade',
            acao='comunidade.create',
        ).last()
        assert log is not None
        assert log.entidade_id == str(response.data['id'])
        assert log.modulo == 'sgp'
        assert log.valores_novos['nome'] == 'Auditavel'

    def test_audit_log_entry_on_update(self, super_admin_client, municipio):
        comunidade = Comunidade.objects.create(
            nome='Original',
            municipio=municipio,
            criada_por=super_admin_client.handler._force_user,
        )
        url = DETAIL_URL_TPL.format(comunidade.pk)
        super_admin_client.patch(url, {'nome': 'Alterado'}, format='json')

        log = AuditLog.objects.filter(
            entidade='Comunidade',
            acao='UPDATE',
        ).last()
        assert log is not None
        assert log.valores_anteriores['nome'] == 'Original'
        assert log.valores_novos['nome'] == 'Alterado'

    def test_audit_log_entry_on_soft_delete(self, super_admin_client, municipio):
        comunidade = Comunidade.objects.create(
            nome='Sera Deletada',
            municipio=municipio,
            criada_por=super_admin_client.handler._force_user,
        )
        url = DETAIL_URL_TPL.format(comunidade.pk)
        super_admin_client.delete(url)

        log = AuditLog.objects.filter(
            entidade='Comunidade',
            acao='comunidade.soft_delete',
        ).last()
        assert log is not None
        assert log.valores_novos['ativa'] is False
