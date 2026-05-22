import pytest
from django.db import connection, transaction
from django.db.utils import DatabaseError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models.audit_log import AuditLog
from apps.core.tests.factories import AuditLogFactory, UserFactory

@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def superadmin():
    return UserFactory(is_superuser=True)

#pytestmark = pytest.mark.django_db

class TestAuditLogModel:
    @pytest.mark.django_db
    def test_auditlog_create_persists_all_fields(self):
        """
        Cria um AuditLog com valores_anteriores e valores_novos como dicts
        aninhados e confirma que todos os campos persistiram sem perda de dados.
        """
        usuario = UserFactory()
        valores_anteriores = {"nome": "João", "endereco": {"cidade": "Mossoró", "uf": "RN"}}
        valores_novos = {"nome": "João Silva", "endereco": {"cidade": "Natal", "uf": "RN"}}

        log = AuditLog(
            user=usuario,
            acao="UPDATE",
            modulo="core",
            entidade="User",
            entidade_id=str(usuario.pk),
            valores_anteriores=valores_anteriores,
            valores_novos=valores_novos,
            ip="192.168.0.1",
            user_agent="Mozilla/5.0",
        )
        log.save()

        salvo = AuditLog.objects.get(pk=log.pk)
        assert salvo.user == usuario
        assert salvo.acao == "UPDATE"
        assert salvo.modulo == "core"
        assert salvo.entidade == "User"
        assert salvo.entidade_id == str(usuario.pk)
        assert salvo.valores_anteriores == valores_anteriores
        assert salvo.valores_novos == valores_novos
        assert salvo.valores_anteriores["endereco"]["cidade"] == "Mossoró"
        assert salvo.valores_novos["endereco"]["cidade"] == "Natal"
        assert salvo.ip == "192.168.0.1"
        assert salvo.user_agent == "Mozilla/5.0"
        assert salvo.timestamp is not None

    @pytest.mark.django_db
    def test_auditlog_update_raises(self):
        """
        Tentar UPDATE direto via SQL levanta DatabaseError com a mensagem do trigger PostgreSQL.
        """
        log = AuditLogFactory()

        with pytest.raises(DatabaseError, match="imutáveis"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE core_auditlog SET acao = %s WHERE id = %s",
                        ["ALTERADO", log.pk]
                    )

    @pytest.mark.django_db
    def test_auditlog_delete_raises(self):
        """
        Tentar DELETE direto via SQL levanta DatabaseError e o registro continua na tabela após a tentativa.
        """
        log = AuditLogFactory()
        log_id = log.pk

        with pytest.raises(DatabaseError, match="imutáveis"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM core_auditlog WHERE id = %s",
                        [log_id]
                    )

        # Confirma que o registro ainda existe no banco
        assert AuditLog.objects.filter(pk=log_id).exists()

    @pytest.mark.django_db
    def test_auditlog_superadmin_cannot_delete_via_admin(self, client, superadmin):
        """
        Super Admin autenticado recebe 403 ao tentar excluir um AuditLog via /admin/.
        """
        log = AuditLogFactory()
        client.force_login(superadmin)

        response = client.post(
            f"/admin/core/auditlog/{log.pk}/delete/",{"post": "yes"},
        )

        assert response.status_code == 403
        assert AuditLog.objects.filter(pk=log.pk).exists()

    @pytest.mark.django_db
    def test_auditlog_index_query_uses_index(self):
        """
        Smoke test: EXPLAIN da query por (entidade, entidade_id) ordenando por
        timestamp DESC confirma que o índice idx_auditlog_entidade_ts é utilizado.
        """
        AuditLogFactory(entidade="Projeto", entidade_id="1")
        AuditLogFactory(entidade="Projeto", entidade_id="1")
        
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN SELECT * FROM core_auditlog
                WHERE entidade = 'Projeto' AND entidade_id = '1'
                ORDER BY timestamp DESC
            """)
            explain = "\n".join(row[0] for row in cursor.fetchall())
        print(f"INDICE = {explain}")
        assert "idx_auditlog_entidade_ts" in explain
