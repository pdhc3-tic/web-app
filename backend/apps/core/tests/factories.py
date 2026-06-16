import factory
from apps.core.models import User, Organization, Municipality, State
from apps.core.models.role import Role
from apps.core.models.territory import Territory
from apps.core.models.user_profile import UserProfile
from apps.core.models.audit_log import AuditLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gerar_cnpj(n: int) -> str:
    """Gera um CNPJ válido (sem pontuação) a partir de um número de sequência."""
    base = f"{n:08d}0001"

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def _digito(parcial, pesos):
        resto = sum(int(d) * p for d, p in zip(parcial, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    d1 = _digito(base, pesos1)
    d2 = _digito(base + str(d1), pesos2)
    return base + str(d1) + str(d2)


# ---------------------------------------------------------------------------
# Core factories
# ---------------------------------------------------------------------------

class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Role
        django_get_or_create = ("slug",)

    nome = factory.Sequence(lambda n: f"Role {n}")
    slug = factory.Sequence(lambda n: f"role-{n}")
    ativo = True


class TerritoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Territory

    nome = factory.Sequence(lambda n: f"Território {n}")
    estados = ["RN"]
    ativo = True


class StateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = State
        django_get_or_create = ("sigla",)

    sigla = factory.Sequence(lambda n: f"S{n:1d}")
    nome = factory.Sequence(lambda n: f"Estado {n}")


class MunicipalityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Municipality
        django_get_or_create = ("codigo_ibge",)

    nome = factory.Sequence(lambda n: f"Município {n}")
    state = factory.SubFactory(StateFactory)
    codigo_ibge = factory.Sequence(lambda n: f"{2400000 + n:07d}")


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    nome = factory.Sequence(lambda n: f"OSC {n}")
    cnpj = factory.Sequence(_gerar_cnpj)
    tipo = "ASSOCIACAO"
    municipio = factory.SubFactory(MunicipalityFactory)
    ativa = True


# ---------------------------------------------------------------------------
# User factories
# ---------------------------------------------------------------------------

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user_{n}@example.com")
    nome = factory.Sequence(lambda n: f"User {n}")
    senha = factory.PostGenerationMethodCall("set_password", "senha123")
    ativo = True


class UserProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    perfil = factory.SubFactory(RoleFactory)
    territorio = None


class AuditLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditLog

    user = factory.SubFactory(UserFactory)
    acao = "CREATE"
    modulo = "core"
    entidade = "User"
    entidade_id = factory.Sequence(lambda n: str(n))
    valores_anteriores = {}
    valores_novos = {"nome": "Teste"}
    ip = "127.0.0.1"
    user_agent = "Mozilla/5.0"
