import factory
from apps.core.models import User
from apps.core.models.role import Role
from apps.core.models.territory import Territory


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user_{n}@example.com")
    nome = factory.Sequence(lambda n: f"User {n}")
    senha = factory.PostGenerationMethodCall("set_password", "senha123")
    ativo = True

class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Role

    nome = factory.Sequence(lambda n: f"Role {n}")
    slug = factory.Iterator(['agricultor', 'adt-acr', 'articulador-estadual', 'ugp', 'fgd', 'super-admin'])
    ativo = True

class TerritoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Territory

    nome = factory.Sequence(lambda n: f"Território {n}")
    estados = ["RN"]
    ativo = True

