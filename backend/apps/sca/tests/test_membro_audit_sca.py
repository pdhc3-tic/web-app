"""
Correção de auditoria dos critérios de aceitação das Issues #186/#187:
criações/edições de membro (titular ou não) feitas pelo sincronizador SCA —
push e resolução de conflito — passam a gerar `AuditLog` (entidade
"MembroFamilia"), centralizado em `apps.core.services.membro_audit`, no
mesmo formato usado pelo SGP: `campos_alterados` com os NOMES dos campos
sensíveis que mudaram, nunca o valor.

Cobre também a correção do vazamento de `valor_final` no `AuditLog` de
`sca.conflict_resolved` quando o conflito resolvido é sensível.
"""
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.core.models import AuditLog
from apps.sca.models import ConflictLog
from apps.sca.tests.factories import ConflictLogFactory
from apps.sca.tests.test_sync_push import build_item, post_batch
from apps.sgp.models import MembroFamilia
from apps.sgp.tests.factories import MembroFactory, UPFFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def upf_existente(db, municipio, projeto):
    upf = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")
    upf.uuid_local = uuid4()
    upf.save(update_fields=["uuid_local"])
    return upf


# ──────────────────────────────────────────────────────────────
# Push cria/edita membro → AuditLog entidade MembroFamilia
# ──────────────────────────────────────────────────────────────

class TestAuditLogPushCriaEEditaMembro:
    def test_criacao_de_membro_via_push_gera_auditlog_sem_expor_valor(
        self, auth_client, upf_existente
    ):
        item = build_item(
            entidade="member",
            payload={
                "upf": upf_existente.pk,
                "nome_completo": "Filho via SCA",
                "grau_parentesco": "filho",
                "cor_raca": 2,
                "saude": ["diabetes"],
            },
        )
        response = post_batch(auth_client, [item])
        assert response.data["resultados"][0]["status"] == "ok"

        criado = MembroFamilia.objects.get(nome_completo="Filho via SCA")
        log = AuditLog.objects.filter(
            acao="MEMBRO.create", entidade="MembroFamilia", entidade_id=str(criado.pk)
        ).latest("timestamp")

        assert log.valores_novos["origem"] == "sca"
        assert set(log.valores_novos["campos_alterados"]) == {"saude", "cor_raca"}
        assert "diabetes" not in str(log.valores_novos)
        assert "saude" not in log.valores_novos
        assert "cor_raca" not in log.valores_novos

    def test_criacao_sem_campos_sensiveis_registra_campos_alterados_vazio(
        self, auth_client, upf_existente
    ):
        item = build_item(
            entidade="member",
            payload={
                "upf": upf_existente.pk,
                "nome_completo": "Filho Sem Sensivel SCA",
                "grau_parentesco": "filho",
            },
        )
        response = post_batch(auth_client, [item])
        assert response.data["resultados"][0]["status"] == "ok"

        criado = MembroFamilia.objects.get(nome_completo="Filho Sem Sensivel SCA")
        log = AuditLog.objects.filter(
            acao="MEMBRO.create", entidade="MembroFamilia", entidade_id=str(criado.pk)
        ).latest("timestamp")
        assert log.valores_novos["campos_alterados"] == []

    def test_edicao_de_saude_via_push_gera_auditlog_com_campo_alterado_sem_valor(
        self, auth_client, upf_existente
    ):
        membro = MembroFactory(
            upf=upf_existente, grau_parentesco="filho", saude=[], uuid_local=uuid4(),
        )
        base = {
            "upf": upf_existente.pk,
            "nome_completo": membro.nome_completo,
            "grau_parentesco": "filho",
            "saude": [],
        }
        payload = dict(base, saude=["hipertensao"])
        item = build_item(
            entidade="member",
            operacao="update",
            uuid_local=membro.uuid_local,
            payload=payload,
            base=base,
            updated_at=timezone.now(),
        )
        response = post_batch(auth_client, [item])
        assert response.data["resultados"][0]["status"] == "ok"

        log = AuditLog.objects.filter(
            acao="MEMBRO.update", entidade="MembroFamilia", entidade_id=str(membro.pk)
        ).latest("timestamp")
        assert log.valores_novos["campos_alterados"] == ["saude"]
        assert log.valores_novos["origem"] == "sca"
        assert "hipertensao" not in str(log.valores_novos)
        assert "hipertensao" not in str(log.valores_anteriores)

    def test_criacao_de_upf_via_push_audita_titular_como_membrofamilia(
        self, auth_client, municipio, projeto
    ):
        from apps.sca.tests.conftest import payload_upf

        payload = payload_upf(projeto, municipio)
        payload["titular"] = dict(payload["titular"], cor_raca=1)
        item = build_item(entidade="upf", payload=payload)

        response = post_batch(auth_client, [item])
        assert response.data["resultados"][0]["status"] == "ok"

        from apps.sgp.models import UPF

        upf = UPF.objects.get(pk=response.data["resultados"][0]["id_servidor"])
        log = AuditLog.objects.filter(
            acao="MEMBRO.create", entidade="MembroFamilia", entidade_id=str(upf.titular_id)
        ).latest("timestamp")
        assert log.valores_novos["campos_alterados"] == ["cor_raca"]
        assert "cor_raca" not in log.valores_novos  # não é chave própria com o valor 1


# ──────────────────────────────────────────────────────────────
# Resolução de conflito sensível — AuditLog sem vazar valor_final
# ──────────────────────────────────────────────────────────────

class TestAuditLogResolucaoDeConflito:
    def _conflito_sensivel_pendente(self, membro, territorio, valor_local, valor_servidor):
        return ConflictLogFactory(
            entidade="member",
            uuid_local=str(membro.uuid_local),
            campo="cor_raca",
            valor_local=valor_local,
            valor_servidor=valor_servidor,
            estrategia=ConflictLog.Estrategia.LAST_WRITE_WINS,
            campo_sensivel=True,
            status=ConflictLog.Status.PENDENTE,
            territorio=territorio,
        )

    def test_resolucao_de_conflito_sensivel_nao_grava_valor_final_no_auditlog(
        self, auth_client_super_admin, super_admin_user, upf_existente, territory
    ):
        membro = MembroFactory(
            upf=upf_existente, grau_parentesco="filho", cor_raca=3, uuid_local=uuid4(),
        )
        conflito = self._conflito_sensivel_pendente(membro, territory, valor_local=1, valor_servidor=3)

        response = auth_client_super_admin.post(
            f"/api/v1/sca/conflicts/{conflito.pk}/resolver/",
            data={"decisao": "local"},
            format="json",
        )
        assert response.status_code == 200

        log_conflito = AuditLog.objects.filter(
            acao="sca.conflict_resolved", entidade="ConflictLog", entidade_id=str(conflito.pk)
        ).latest("timestamp")
        assert "valor_final" not in log_conflito.valores_novos
        assert log_conflito.valores_novos["campo"] == "cor_raca"
        assert "1" not in str(log_conflito.valores_novos)

    def test_resolucao_de_conflito_sensivel_audita_membrofamilia_sem_valor(
        self, auth_client_super_admin, super_admin_user, upf_existente, territory
    ):
        membro = MembroFactory(
            upf=upf_existente, grau_parentesco="filho", cor_raca=3, uuid_local=uuid4(),
        )
        conflito = self._conflito_sensivel_pendente(membro, territory, valor_local=1, valor_servidor=3)

        response = auth_client_super_admin.post(
            f"/api/v1/sca/conflicts/{conflito.pk}/resolver/",
            data={"decisao": "local"},
            format="json",
        )
        assert response.status_code == 200
        membro.refresh_from_db()
        assert membro.cor_raca == 1  # decisão "local" aplicada normalmente

        log_membro = AuditLog.objects.filter(
            acao="MEMBRO.update", entidade="MembroFamilia", entidade_id=str(membro.pk)
        ).latest("timestamp")
        assert log_membro.valores_novos["campos_alterados"] == ["cor_raca"]
        assert log_membro.valores_novos["origem"] == "sca_conflict_resolution"
        assert "cor_raca" not in log_membro.valores_novos
        assert log_membro.valores_anteriores == {}

    def test_resolucao_de_conflito_nao_sensivel_continua_gravando_valor_final(
        self, auth_client_super_admin, super_admin_user, upf_existente, territory
    ):
        """Regressão: a omissão é só para campo sensível — conflitos comuns
        (ex.: whatsapp) continuam com o valor final no log, como antes."""
        conflito = ConflictLogFactory(
            entidade="upf",
            uuid_local=str(upf_existente.uuid_local),
            campo="whatsapp",
            valor_local="9999",
            valor_servidor="1111",
            campo_sensivel=False,
            status=ConflictLog.Status.PENDENTE,
            territorio=territory,
        )

        response = auth_client_super_admin.post(
            f"/api/v1/sca/conflicts/{conflito.pk}/resolver/",
            data={"decisao": "local"},
            format="json",
        )
        assert response.status_code == 200

        log = AuditLog.objects.filter(
            acao="sca.conflict_resolved", entidade="ConflictLog", entidade_id=str(conflito.pk)
        ).latest("timestamp")
        assert log.valores_novos["valor_final"] == "9999"
