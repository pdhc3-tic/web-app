import factory
from apps.core.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user_{n}@example.com")
    nome = factory.Sequence(lambda n: f"User {n}")
    perfil = User.PerfilChoices.TECNICO_CAMPO_ADT_ACR
    senha = factory.PostGenerationMethodCall("set_password", "senha123")
    ativo = True