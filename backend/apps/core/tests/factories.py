import factory
from apps.core.models import User
from apps.core.models.role import Role
from apps.core.models.territory import Territory
from apps.core.models.user_profile import UserProfile
from apps.core.models.audit_log import AuditLog
from apps.core.models.notifications import Notification, NotificationPreference, TipoNotificacao, StatusNotificacao


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


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user_{n}@example.com")
    nome = factory.Sequence(lambda n: f"User {n}")
    senha = factory.PostGenerationMethodCall("set_password", "senha123")
    ativo = True

    @factory.post_generation
    def senha(obj, create, extracted, **kwargs):
        password = extracted or "senha123"
        obj.set_password(password)
        if create:
            obj.save(update_fields=["password"])


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

class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    tipo = TipoNotificacao.EMAIL
    titulo = factory.Sequence(lambda n: f"Notificação {n}")
    mensagem = factory.Sequence(lambda n: f"Mensagem de teste {n}")
    link = "https://ufersa.edu.br"
    status = StatusNotificacao.PENDENTE
    tentativas = 0


class NotificationPreferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationPreference

    user = factory.SubFactory(UserFactory)
    tipo_evento = "nova_visita"
    canal = TipoNotificacao.EMAIL
    ativo = True

class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "core.Organization"

    nome = factory.Sequence(lambda n: f"Organização {n}")
    cnpj = factory.Sequence(lambda n: f"{n:014d}")
    tipo = "associacao"
    ativa = True
