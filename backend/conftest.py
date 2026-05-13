import os
from django.conf import settings


def pytest_configure(config):
    settings.DATABASES["default"]["USER"] = os.getenv("POSTGRES_USER")
    settings.DATABASES["default"]["PASSWORD"] = os.getenv("POSTGRES_PASSWORD")
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }