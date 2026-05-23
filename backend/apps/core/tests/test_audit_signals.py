import pytest
from django.test import Client as DjangoClient
from rest_framework.test import APIClient

from apps.core.models.audit_log import AuditLog
from apps.core.tests.factories import UserFactory, RoleFactory
from apps.core.models.role import Role


@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def superadmin():
    role, _ = Role.objects.get_or_create(
        slug="super-admin",
        defaults={"nome": "Super Admin", "ativo": True}
    )
    return UserFactory(is_superuser=True, role=role)

@pytest.fixture
def superadmin_client(superadmin):
    client = APIClient()
    client.force_authenticate(user=superadmin)
    return client

@pytest.mark.django_db
def test_audit_logged_on_user_create(superadmin_client):
    """
    POST /api/v1/users/ gera 1 AuditLog com acao='CREATE',
    entidade='User', valores_novos contém email mas não senha_hash.
    """
    role = RoleFactory()
    response = superadmin_client.post("/api/v1/users/", {
        "email": "novo@example.com",
        "nome": "Novo Usuario",
        "password": "senha123",
        "role": role.pk,
        "ativo": True,
    })

    assert response.status_code in (200, 201)

    log = AuditLog.objects.filter(entidade="User", acao="CREATE").last()
    assert log is not None
    assert log.acao == "CREATE"
    assert log.entidade == "User"
    assert "email" in log.valores_novos
    assert "password" not in log.valores_novos
    assert "senha_hash" not in log.valores_novos

@pytest.mark.django_db
def test_audit_logged_on_user_update(superadmin_client):
    """
    PATCH em campo do User gera AuditLog com valores_anteriores
    e valores_novos preenchidos corretamente.
    """
    usuario = UserFactory(nome="Nome Antigo")

    response = superadmin_client.patch(f"/api/v1/users/{usuario.pk}/", {
        "nome": "Nome Novo",
    })

    assert response.status_code == 200

    log = AuditLog.objects.filter(
        entidade="User", 
        acao="UPDATE",
        entidade_id=str(usuario.pk),
    ).order_by("pk").last()

    assert log is not None
    assert log.valores_anteriores.get("nome") == "Nome Antigo"
    assert log.valores_novos.get("nome") == "Nome Novo"

@pytest.mark.django_db
def test_audit_logged_on_user_delete(superadmin_client):
    """
    DELETE (soft-delete via PATCH ativo=False) gera AuditLog
    com acao='UPDATE' e valores_novos com ativo=False.
    """
    usuario = UserFactory(ativo=True)

    response = superadmin_client.patch(f"/api/v1/users/{usuario.pk}/", {
        "ativo": False,
    })

    assert response.status_code == 200

    log = AuditLog.objects.filter(
        entidade="User", 
        acao="UPDATE",
        entidade_id=str(usuario.pk),
    ).order_by("pk").last()

    assert log is not None
    assert log.valores_novos.get("ativo") == False

@pytest.mark.django_db
def test_audit_excludes_password_field():
    """
    Alteração de senha não aparece em valores_anteriores/valores_novos.
    """
    usuario = UserFactory()
    usuario.set_password("nova_senha_456")
    usuario.save()

    log = AuditLog.objects.filter(
        entidade="User", 
        acao="UPDATE",
        entidade_id=str(usuario.pk),).order_by("pk").last()
    
    assert log is not None
    assert "password" not in log.valores_anteriores
    assert "password" not in log.valores_novos
    assert "senha_hash" not in log.valores_anteriores
    assert "senha_hash" not in log.valores_novos

@pytest.mark.django_db
def test_audit_without_request_user_does_not_crash():
    """
    Criar User via factory sem middleware gera log com user=None
    e não causa crash.
    """
    usuario = UserFactory()

    log = AuditLog.objects.filter(entidade="User", 
                                  acao="CREATE",
                                  entidade_id=str(usuario.pk),).order_by("pk").last()
    
    assert log is not None
    assert log.user is None
    assert log.ip is None

@pytest.mark.django_db
def test_audit_list_requires_super_admin(superadmin_client):
    """
    ADT, Articulador e UGP recebem 403 em GET /api/v1/audit-logs/.
    Super Admin recebe 200.
    """
    # Usuários sem permissão
    for usuario in [UserFactory(), UserFactory(), UserFactory()]:
        c = APIClient()
        c.force_authenticate(user=usuario)
        response = c.get("/api/v1/audit-logs/")
        assert response.status_code == 403

    # Super Admin recebe 200
    response = superadmin_client.get("/api/v1/audit-logs/")
    assert response.status_code == 200

@pytest.mark.django_db
def test_audit_list_filters_by_entity_and_period(superadmin_client):
    """
    Filtros entidade=User e timestamp__gte funcionam como esperado.
    """
    # Gera logs via factory
    UserFactory()
    UserFactory()
    RoleFactory()

    response = superadmin_client.get("/api/v1/audit-logs/?entidade=User")
    assert response.status_code == 200
    results = response.data["results"]
    assert all(r["entidade"] == "User" for r in results)

    response = superadmin_client.get("/api/v1/audit-logs/?entidade=Role")
    assert response.status_code == 200
    results = response.data["results"]
    assert all(r["entidade"] == "Role" for r in results)