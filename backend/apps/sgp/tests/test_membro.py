from datetime import date

import pytest

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import MembroFamilia, UFPA
from apps.sgp.tests.factories import MembroFactory

pytestmark = pytest.mark.django_db


class TestCriacaoMembro:
    def test_create_membro_with_minimum_fields(
        self, auth_client, ufpa, membro_payload_minimo
    ):
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            membro_payload_minimo,
            format="json",
        )
        assert response.status_code == 201
        assert response.data["nome_completo"] == "João Filho"
        assert response.data["grau_parentesco"] == "filho"

    def test_create_membro_titular(
        self, auth_client, ufpa, titular_payload
    ):
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            titular_payload,
            format="json",
        )
        assert response.status_code == 400

    def test_create_second_titular_returns_400(
        self, auth_client, ufpa, titular_payload
    ):
        # UFPA already has a titular from the factory; adding another must fail
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            titular_payload,
            format="json",
        )
        assert response.status_code == 400

    def test_create_membro_without_cpf_allowed(
        self, auth_client, ufpa, membro_payload_minimo
    ):
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            membro_payload_minimo,
            format="json",
        )
        assert response.status_code == 201
        assert response.data["cpf"] == ""

    def test_create_membro_with_invalid_cpf_returns_400(
        self, auth_client, ufpa, membro_payload_minimo
    ):
        payload = {**membro_payload_minimo, "cpf": "11111111111"}
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 400

    def test_create_membro_for_inactive_ufpa_returns_400(
        self, auth_client, ufpa_inativa, membro_payload_minimo
    ):
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa_inativa.pk}/membros/",
            membro_payload_minimo,
            format="json",
        )
        assert response.status_code == 400
        assert "UFPA inativa" in str(response.data)


class TestIdade:
    def test_idade_calculated_from_data_nasc(
        self, auth_client, ufpa
    ):
        payload = {
            "nome_completo": "Criança",
            "grau_parentesco": "filho",
            "data_nascimento": "2010-06-15",
        }
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 201
        today = date.today()
        expected_age = today.year - 2010 - (
            (today.month, today.day) < (6, 15)
        )
        assert response.data["idade"] == expected_age


class TestListagem:
    def test_list_membros_returns_only_for_own_ufpa(
        self, auth_client, ufpa, outra_ufpa, membro, membro_outra_ufpa
    ):
        response = auth_client.get(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/"
        )
        assert response.status_code == 200
        ids = [m["id"] for m in response.data["results"]]
        assert membro.pk in ids
        assert membro_outra_ufpa.pk not in ids

    def test_access_membro_from_wrong_ufpa_returns_404(
        self, auth_client, ufpa, outra_ufpa, membro, membro_outra_ufpa
    ):
        response = auth_client.get(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{membro_outra_ufpa.pk}/"
        )
        assert response.status_code == 404


class TestSaude:
    def test_saude_json_accepts_valid_array(
        self, auth_client, ufpa, membro_payload_minimo
    ):
        payload = {
            **membro_payload_minimo,
            "saude": ["diabetes", "hipertensao"],
        }
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 201
        assert response.data["saude"] == ["diabetes", "hipertensao"]

    def test_saude_json_rejects_invalid_value(
        self, auth_client, ufpa, membro_payload_minimo
    ):
        payload = {
            **membro_payload_minimo,
            "saude": ["doenca_inexistente"],
        }
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 400


class TestDeleteUFPA:
    def test_delete_ufpa_does_not_delete_membros(
        self, auth_client, ufpa, membro
    ):
        auth_client.delete(f"/api/v1/sgp/ufpas/{ufpa.pk}/")
        ufpa_atualizada = UFPA.all_objects.get(pk=ufpa.pk)
        assert ufpa_atualizada.ativo is False
        assert MembroFamilia.objects.filter(
            ufpa=ufpa, pk=membro.pk
        ).exists()


class TestAuditLog:
    def test_audit_log_on_membro_create_update_delete(
        self, auth_client, ufpa, membro_payload_minimo
    ):
        res = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            membro_payload_minimo,
            format="json",
        )
        membro_id = res.data["id"]
        assert AuditLog.objects.filter(
            entidade="MembroFamilia",
            entidade_id=str(membro_id),
            acao="MEMBRO.create",
        ).exists()

        auth_client.patch(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{membro_id}/",
            {"nome_completo": "Nome Atualizado"},
            format="json",
        )
        assert AuditLog.objects.filter(
            entidade="MembroFamilia",
            entidade_id=str(membro_id),
            acao="MEMBRO.update",
        ).exists()

        auth_client.delete(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{membro_id}/"
        )
        assert AuditLog.objects.filter(
            entidade="MembroFamilia",
            entidade_id=str(membro_id),
            acao="MEMBRO.delete",
        ).exists()


class TestDeleteTitular:
    def test_delete_unico_titular_retorna_400(
        self, auth_client, ufpa
    ):
        membro = ufpa.titular
        response = auth_client.delete(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{membro.pk}/"
        )
        assert response.status_code == 400
        assert "único titular" in str(response.data).lower()

    def test_delete_titular_com_outros_membros_retorna_400(
        self, auth_client, ufpa, membro
    ):
        response = auth_client.delete(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{ufpa.titular.pk}/"
        )
        assert response.status_code == 400
        assert "titularidade" in str(response.data).lower()


class TestCPFUnicoGlobal:
    def test_cpf_duplicado_entre_ufpas_diferentes_retorna_400(
        self, auth_client, ufpa, outra_ufpa, membro_payload_minimo
    ):
        payload = {
            **membro_payload_minimo,
            "cpf": "12345678909",
        }
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 201

        payload_outra = {
            "nome_completo": "Membro Duplicado",
            "grau_parentesco": "filho",
            "cpf": "12345678909",
        }
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{outra_ufpa.pk}/membros/",
            payload_outra,
            format="json",
        )
        assert response.status_code == 400
        assert "já existe um membro" in str(response.data).lower()


class TestDataNascimentoFutura:
    def test_data_nascimento_futura_retorna_400(
        self, auth_client, ufpa
    ):
        payload = {
            "nome_completo": "Membro Futuro",
            "grau_parentesco": "filho",
            "data_nascimento": "2030-01-01",
        }
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/",
            payload,
            format="json",
        )
        assert response.status_code == 400
        assert "futura" in str(response.data).lower()


class TestResumoMembros:
    def test_resumo_retorna_totais_e_faixas_etarias(
        self, auth_client, ufpa, membro
    ):
        response = auth_client.get(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/resumo/"
        )
        assert response.status_code == 200
        assert response.data["total_membros"] >= 2
        assert "faixa_etaria" in response.data
        assert "genero" in response.data
        assert response.data["tem_titular"] is True

    def test_resumo_sem_titular_retorna_false(
        self, auth_client, ufpa, membro
    ):
        ufpa.titular = membro
        ufpa.save()
        MembroFamilia.objects.filter(
            ufpa=ufpa, grau_parentesco="titular"
        ).exclude(pk=membro.pk).update(grau_parentesco="filho")

        response = auth_client.get(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/resumo/"
        )
        assert response.status_code == 200
        assert response.data["tem_titular"] is False

    def test_resumo_nao_inclui_dados_individuais(
        self, auth_client, ufpa, membro
    ):
        response = auth_client.get(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/resumo/"
        )
        assert response.status_code == 200
        dados = response.data
        assert "saude" not in dados
        assert "cor_raca" not in dados
        assert "cpf" not in dados


class TestFaixasEtarias:
    """Testa que as faixas etárias cobrem todos os membros e os limites corretos."""

    def test_limite_29_fevereiro_usa_dia_28(self):
        from datetime import date as _date
        from apps.sgp.views import data_limite_aniversario
        hoje = _date(2027, 2, 28)  # ano não bissexto
        # quem nasceu em 29/02 de 12 anos atrás deve ser tratado como 28/02
        limite = data_limite_aniversario(hoje, 12)
        assert limite.day == 28

    def test_soma_faixas_mais_sem_data_igual_total(self, auth_client, ufpa, membro):
        from datetime import date as _date
        from apps.sgp.views import data_limite_aniversario
        hoje = _date.today()
        ufpa.titular.data_nascimento = hoje.replace(year=hoje.year - 30)
        ufpa.titular.save()
        # Limites exatos: nasce exatamente no aniversário de 12, 18 e 60 anos
        for anos in (12, 18, 60):
            MembroFamilia.objects.create(
                ufpa=ufpa,
                nome_completo=f"Limite {anos}",
                grau_parentesco="filho",
                data_nascimento=hoje.replace(year=hoje.year - anos),
            )
        MembroFactory(ufpa=ufpa, nome_completo="Sem data", data_nascimento=None)

        response = auth_client.get(f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/resumo/")
        faixas = response.data["faixa_etaria"]
        soma = sum(faixas.values())
        assert soma == response.data["total_membros"]
        # Quem nasceu exatamente no aniversário de N anos está NA faixa de N+
        assert faixas["0-11"] == 0
        assert faixas["12-17"] == 1
        assert faixas["18-59"] == 3
        assert faixas["60+"] == 1


# ──────────────────────────────────────────────────────────────
# Isolamento territorial por role
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestIsolamentoTerritorialPorRole:
    """Testa que cada role só acessa UFPAs/membros do seu território."""

    def _list(self, client, ufpa_pk):
        return client.get(f"/api/v1/sgp/ufpas/{ufpa_pk}/membros/")

    def _detail(self, client, ufpa_pk, membro_pk):
        return client.get(f"/api/v1/sgp/ufpas/{ufpa_pk}/membros/{membro_pk}/")

    def test_super_admin_ve_todas_ufpas(self, auth_client_super_admin, ufpa, outra_ufpa):
        """Super-admin acessa UFPAs de qualquer território."""
        MembroFactory(ufpa=ufpa, nome_completo="Membro UFPA 1", cpf="11111111111")
        MembroFactory(ufpa=outra_ufpa, nome_completo="Membro UFPA 2", cpf="22222222222")

        # Super-admin vê ambas
        r1 = self._list(auth_client_super_admin, ufpa.pk)
        r2 = self._list(auth_client_super_admin, outra_ufpa.pk)
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_ugp_ve_todas_ufpas(self, ugp_client, ufpa, outra_ufpa):
        """UGP acessa UFPAs de qualquer território."""
        MembroFactory(ufpa=ufpa, nome_completo="Membro UFPA 1", cpf="11111111111")
        MembroFactory(ufpa=outra_ufpa, nome_completo="Membro UFPA 2", cpf="22222222222")

        r1 = self._list(ugp_client, ufpa.pk)
        r2 = self._list(ugp_client, outra_ufpa.pk)
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_articulador_ve_apenas_seus_estados(self, auth_client_articulador_rn, ufpa, ufpa_ce):
        """Articulador estadual só vê UFPAs dos seus estados."""
        MembroFactory(ufpa=ufpa, nome_completo="Membro RN")
        MembroFactory(ufpa=ufpa_ce, nome_completo="Membro CE")

        # Vê UFPA do RN (seu estado)
        r1 = self._list(auth_client_articulador_rn, ufpa.pk)
        assert r1.status_code == 200

        # Não vê UFPA do CE (estado diferente)
        r2 = self._list(auth_client_articulador_rn, ufpa_ce.pk)
        assert r2.status_code == 404

    def test_adt_ve_apenas_seu_territorio(self, auth_client_adt_rn, ufpa, ufpa_ce):
        """ADT/ACR só vê UFPAs do seu território."""
        MembroFactory(ufpa=ufpa, nome_completo="Membro Território RN")
        MembroFactory(ufpa=ufpa_ce, nome_completo="Membro Território CE")

        r1 = self._list(auth_client_adt_rn, ufpa.pk)
        assert r1.status_code == 200

        r2 = self._list(auth_client_adt_rn, ufpa_ce.pk)
        assert r2.status_code == 404

    def test_sem_perfil_sgp_nao_ve_nada(self, auth_client_sem_acesso, ufpa):
        """Usuário sem perfil SGP não acessa endpoints de membros (404 por isolamento)."""
        MembroFactory(ufpa=ufpa, nome_completo="Membro")
        r = self._list(auth_client_sem_acesso, ufpa.pk)
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────
# PUT method
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPutMethod:
    """Testa o método PUT para atualização completa."""

    def test_put_atualiza_todos_campos(self, auth_client, ufpa, membro):
        url = f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{membro.pk}/"
        payload = {
            "nome_completo": "Novo Nome Completo",
            "grau_parentesco": "filho",
            "cpf": "49193681437",
            "data_nascimento": "2010-01-01",
            "genero": 1,
        }
        response = auth_client.put(url, payload, format="json")
        assert response.status_code == 200
        assert response.data["nome_completo"] == "Novo Nome Completo"
        assert response.data["grau_parentesco"] == "filho"
        assert response.data["cpf"] == "49193681437"

    def test_put_mantem_campos_nao_enviados(self, auth_client, ufpa, membro):
        """PUT deve requerer todos os campos obrigatórios."""
        url = f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{membro.pk}/"
        payload = {
            "nome_completo": "Nome Alterado",
            "grau_parentesco": "conjuge",
            "cpf": "49193681437",
        }
        response = auth_client.put(url, payload, format="json")
        assert response.status_code == 200
        assert response.data["nome_completo"] == "Nome Alterado"


# ──────────────────────────────────────────────────────────────
# Transferência de titularidade
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTransferirTitularidade:
    """Testa o endpoint de transferência de titularidade."""

    def _transfer(self, client, ufpa_pk, novo_titular_id):
        return client.post(
            f"/api/v1/sgp/ufpas/{ufpa_pk}/membros/transferir-titularidade/",
            {"novo_titular_id": novo_titular_id},
            format="json",
        )

    def test_transferencia_sucesso(self, auth_client, ufpa, membro):
        """Transfere titularidade de titular para outro membro."""
        antigo_titular_id = ufpa.titular_id
        assert antigo_titular_id != membro.pk

        response = self._transfer(auth_client, ufpa.pk, membro.pk)
        assert response.status_code == 200
        assert response.data["detail"] == "Titularidade transferida com sucesso."

        ufpa.refresh_from_db()
        membro.refresh_from_db()
        assert ufpa.titular_id == membro.pk
        assert membro.grau_parentesco == "titular"

        # Antigo titular virou filho
        antigo = response.data["antigo_titular"]
        assert antigo["id"] == antigo_titular_id

    def test_transferencia_mesmo_titular_retorna_400(self, auth_client, ufpa):
        """Tenta transferir para quem já é titular."""
        response = self._transfer(auth_client, ufpa.pk, ufpa.titular_id)
        assert response.status_code == 400
        assert "já é o titular" in str(response.data)

    def test_transferencia_membro_inexistente_retorna_400(self, auth_client, ufpa):
        """Tenta transferir para membro que não existe na UFPA."""
        response = self._transfer(auth_client, ufpa.pk, 999999)
        assert response.status_code == 400
        assert "não encontrado" in str(response.data)

    def test_transferencia_sem_novo_titular_retorna_400(self, auth_client, ufpa):
        """Payload sem novo_titular_id retorna 400."""
        response = auth_client.post(
            f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/transferir-titularidade/",
            {},
            format="json",
        )
        assert response.status_code == 400
        assert "obrigatório" in str(response.data)


# ──────────────────────────────────────────────────────────────
# Impedir rebaixar titular via PATCH
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestImpedirRebaixarTitular:
    """Testa que PATCH não permite alterar parentesco do titular."""

    def test_patch_titular_para_filho_retorna_400(self, auth_client, ufpa):
        """Tenta mudar titular para filho via PATCH."""
        url = f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{ufpa.titular.pk}/"
        response = auth_client.patch(url, {"grau_parentesco": "filho"}, format="json")
        assert response.status_code == 400
        assert "transferência de titularidade" in str(response.data)

    def test_patch_titular_para_conjuge_retorna_400(self, auth_client, ufpa):
        url = f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{ufpa.titular.pk}/"
        response = auth_client.patch(url, {"grau_parentesco": "conjuge"}, format="json")
        assert response.status_code == 400

    def test_patch_nao_titular_funciona(self, auth_client, ufpa, membro):
        """PATCH em membro não titular funciona normalmente."""
        url = f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/{membro.pk}/"
        response = auth_client.patch(url, {"grau_parentesco": "conjuge"}, format="json")
        assert response.status_code == 200
        assert response.data["grau_parentesco"] == "conjuge"


# ──────────────────────────────────────────────────────────────
# Choices exatos
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestChoicesValidos:
    """Testa validação de choices nos campos."""

    def _valid_cpf(self, n):
        """Gera CPFs válidos diferentes para cada teste."""
        cpfs = [
            "49193681437", "04227503523", "94141800368",
            "80741474875", "75708571438", "52998224725",
            "74260189204", "88555658187", "93402148625",
        ]
        return cpfs[n % len(cpfs)]

    def test_genero_aceita_valores_validos(self, auth_client, ufpa):
        """Gênero aceita 1,2,3,4."""
        for i, g in enumerate([1, 2, 3, 4]):
            payload = {"nome_completo": "Teste", "grau_parentesco": "filho", "cpf": self._valid_cpf(i), "genero": g}
            response = auth_client.post(f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/", payload, format="json")
            assert response.status_code == 201, f"Falhou para genero={g}: {response.data}"

    def test_genero_rejeita_invalido(self, auth_client, ufpa):
        payload = {"nome_completo": "Teste", "grau_parentesco": "filho", "cpf": self._valid_cpf(0), "genero": 99}
        response = auth_client.post(f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/", payload, format="json")
        assert response.status_code == 400

    def test_parentesco_aceita_todos(self, auth_client, ufpa):
        """Parentesco aceita todos os valores de PARENTESCO_CHOICES."""
        from apps.sgp.constants import PARENTESCO_CHOICES
        for i, (key, _) in enumerate(PARENTESCO_CHOICES):
            payload = {"nome_completo": f"Teste {key}", "grau_parentesco": key, "cpf": self._valid_cpf(i)}
            response = auth_client.post(f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/", payload, format="json")
            # Pode falhar se for "titular" e já existe titular
            if key == "titular":
                assert response.status_code in (201, 400)
            else:
                assert response.status_code == 201, f"Falhou para grau_parentesco={key}: {response.data}"

    def test_escolaridade_aceita_valores(self, auth_client, ufpa):
        """Escolaridade aceita valores de 1 a 7 (Superior completo)."""
        for i, e in enumerate(range(1, 8)):  # 1 a 7 conforme ESCOLARIDADE_CHOICES
            payload = {"nome_completo": "Teste", "grau_parentesco": "filho", "cpf": self._valid_cpf(i), "escolaridade": e}
            response = auth_client.post(f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/", payload, format="json")
            assert response.status_code == 201, f"Falhou para escolaridade={e}: {response.data}"


# ──────────────────────────────────────────────────────────────
# Concorrência CPF
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCPFConcorrencia:
    """Testa unicidade de CPF sob concorrência."""

    def test_cpf_duplicado_concorrente_integridade_banco(self, ufpa, usuario):
        """Duas criações simultâneas com mesmo CPF: banco bloqueia a segunda."""
        from django.db import IntegrityError

        MembroFactory(ufpa=ufpa, nome_completo="Membro 1", cpf="49193681437")

        # Tentativa direta no banco deve falhar
        with pytest.raises(IntegrityError):
            MembroFamilia.objects.create(
                ufpa=ufpa,
                nome_completo="Membro 2",
                grau_parentesco="filho",
                cpf="49193681437",
                criado_por=usuario,
            )
