from django.apps import AppConfig


class SgdConfig(AppConfig):
    name = "apps.sgd"

    def ready(self):
        import apps.sgd.signals.activity  # noqa
