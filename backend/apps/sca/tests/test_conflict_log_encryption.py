"""
Correção de auditoria dos critérios de aceitação das Issues #186/#187:
`ConflictLog.valor_local`/`valor_servidor`/`valor_final` não podem ficar em
texto claro no banco quando o conflito envolve um campo sensível (saúde,
cor/raça) — mesmo padrão de criptografia em repouso (AES-256-GCM) já usado
em `MembroFamilia.saude`/`cor_raca`.
"""
from uuid import uuid4

import pytest
from django.db import connection

from apps.sca.models import ConflictLog
from apps.sca.tests.factories import ConflictLogFactory

pytestmark = pytest.mark.django_db


class TestCriptografiaEmRepouso:
    def test_valor_bruto_no_banco_nao_e_legivel_em_texto_claro(self, upf_existente, territory):
        conflito = ConflictLogFactory(
            entidade="member",
            uuid_local=uuid4(),
            campo="saude",
            valor_local=["diabetes", "gestante"],
            valor_servidor=["hipertensao"],
            valor_final=None,
            campo_sensivel=True,
            status=ConflictLog.Status.PENDENTE,
            territorio=territory,
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT valor_local, valor_servidor FROM sca_conflictlog WHERE id = %s",
                [conflito.pk],
            )
            raw_local, raw_servidor = cursor.fetchone()

        assert "diabetes" not in raw_local
        assert "gestante" not in raw_local
        assert "hipertensao" not in raw_servidor

        conflito.refresh_from_db()
        assert conflito.valor_local == ["diabetes", "gestante"]
        assert conflito.valor_servidor == ["hipertensao"]

    def test_valor_final_nulo_antes_da_resolucao_e_preservado(self, upf_existente, territory):
        """`valor_final` é nulo até a resolução manual — cobre o bugfix de
        `EncryptedFieldMixin.from_db_value` para campo nulável (antes,
        devolvia a classe `list`, não `None`, quando a coluna era NULL)."""
        conflito = ConflictLogFactory(
            entidade="member",
            uuid_local=uuid4(),
            campo="cor_raca",
            valor_local=2,
            valor_servidor=3,
            valor_final=None,
            campo_sensivel=True,
            status=ConflictLog.Status.PENDENTE,
            territorio=territory,
        )
        conflito.refresh_from_db()
        assert conflito.valor_final is None

    def test_tokens_criptografados_sao_diferentes_para_o_mesmo_valor(self, upf_existente, territory):
        c1 = ConflictLogFactory(
            uuid_local=uuid4(), campo="cor_raca", valor_local=2, valor_servidor=2, territorio=territory,
        )
        c2 = ConflictLogFactory(
            uuid_local=uuid4(), campo="cor_raca", valor_local=2, valor_servidor=2, territorio=territory,
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT valor_local FROM sca_conflictlog WHERE id IN (%s, %s)",
                [c1.pk, c2.pk],
            )
            valores = {row[0] for row in cursor.fetchall()}

        assert len(valores) == 2

    def test_resolucao_aplica_valor_criptografado_normalmente(
        self, auth_client_super_admin, super_admin_user, upf_existente, territory
    ):
        """Regressão: a mudança de tipo do campo não pode quebrar o fluxo de
        resolução (decisão local/servidor/manual) já coberto em
        test_sca_admin_endpoints.py."""
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
        conflito.refresh_from_db()
        assert conflito.valor_final == "9999"


@pytest.fixture
def upf_existente(db, municipio, projeto):
    from apps.sgp.tests.factories import UPFFactory

    upf = UPFFactory(municipio=municipio, projeto=projeto, titular_cpf="86288366757")
    upf.uuid_local = uuid4()
    upf.save(update_fields=["uuid_local"])
    return upf
