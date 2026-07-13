from django.conf import settings

from .r2 import LocalStorage, R2Storage


def get_storage():
    if settings.STORAGE_BACKEND == "r2":
        return R2Storage()
    return LocalStorage()
