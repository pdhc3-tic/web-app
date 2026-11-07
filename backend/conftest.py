import os
from unittest.mock import patch

import pytest
from django.conf import settings


def pytest_configure(config):
    settings.DATABASES["default"]["USER"] = os.getenv("POSTGRES_USER")
    settings.DATABASES["default"]["PASSWORD"] = os.getenv("POSTGRES_PASSWORD")
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }


@pytest.fixture(autouse=True)
def sem_tarefa_de_alerta_no_broker():
    """Com `transaction=True` o `on_commit` roda de verdade, e um worker de desenvolvimento
    consumiria ids do banco de teste."""
    with patch("apps.sgp.tasks.check_budget_thresholds.delay"):
        yield


def pytest_collection_modifyitems(config, items):
    # Pula em vez de desselecionar: no `-v` cada teste aparece como SKIPPED
    # com o motivo, então fica visível no log do CI que eles não rodaram.
    if os.getenv("SKIP_PERFORMANCE_TESTS", "").strip().lower() not in ("1", "true"):
        return
    pular = pytest.mark.skip(reason="SKIP_PERFORMANCE_TESTS ativo")
    for item in items:
        if item.get_closest_marker("performance"):
            item.add_marker(pular)
