import factory

from apps.sca.models import ConflictLog, SyncDevice, SyncEvent


class SyncDeviceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SyncDevice
        django_get_or_create = ("user", "device_id")

    user = factory.SubFactory("apps.core.tests.factories.UserFactory")
    device_id = factory.Sequence(lambda n: f"dev-{n}")
    ativo = True


class SyncEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SyncEvent

    user = factory.SubFactory("apps.core.tests.factories.UserFactory")
    device = factory.SubFactory(SyncDeviceFactory)
    tipo = SyncEvent.Tipo.PUSH
    contagem = 0


class ConflictLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConflictLog

    user = factory.SubFactory("apps.core.tests.factories.UserFactory")
    device = factory.SubFactory(SyncDeviceFactory)
    entidade = "upf"
    uuid_local = factory.Faker("uuid4")
    campo = "whatsapp"
    valor_local = {}
    valor_servidor = {}
    estrategia = ConflictLog.Estrategia.LAST_WRITE_WINS
