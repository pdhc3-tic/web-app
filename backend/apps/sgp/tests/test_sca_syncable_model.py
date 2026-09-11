from uuid import UUID

from django.apps import apps
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

from apps.sgp.models import Activity, MembroFamilia, UPF
from apps.sgp.models.mixins import ScaSyncableModel

SYNCABLE_MODELS = [Activity, UPF, MembroFamilia]


def test_syncable_models_herdam_o_mixin():
    for model in SYNCABLE_MODELS:
        assert issubclass(model, ScaSyncableModel)


def test_campos_preservados():
    """Os 4 campos de sync mantêm os mesmos atributos nos 3 models."""
    for model in SYNCABLE_MODELS:
        device_id = model._meta.get_field("device_id")
        assert device_id.max_length == 100
        assert device_id.blank is True
        assert device_id.default == ""

        uuid_local = model._meta.get_field("uuid_local")
        assert uuid_local.null is True
        assert uuid_local.blank is True
        assert uuid_local.unique is True

        ultima_origem = model._meta.get_field("ultima_origem")
        assert ultima_origem.max_length == 10
        assert ultima_origem.default == "web"
        assert dict(ultima_origem.choices) == {"sca": "SCA", "web": "Web"}

        ultimo_sync_em = model._meta.get_field("ultimo_sync_em")
        assert ultimo_sync_em.null is True
        assert ultimo_sync_em.blank is True


def test_uuid_local_aceita_atribuicao_por_model():
    """Cada model mantém sua própria coluna — não é um campo compartilhado."""
    for model in SYNCABLE_MODELS:
        instance = model()
        instance.uuid_local = UUID("12345678-1234-5678-1234-567812345678")
        assert instance.uuid_local == UUID("12345678-1234-5678-1234-567812345678")


def test_migration_e_noop():
    """Mover os campos pro mixin não deixa nenhuma alteração de schema pendente pro app sgp."""
    loader = MigrationLoader(None, ignore_no_migrations=True)
    autodetector = MigrationAutodetector(
        loader.project_state(),
        ProjectState.from_apps(apps),
    )
    changes = autodetector.changes(
        graph=loader.graph, trim_to_apps={"sgp"}, convert_apps={"sgp"},
    )
    assert changes == {}, f"Há alteração de schema pendente em sgp: {changes}"
