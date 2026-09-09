from django.apps import AppConfig


class SgpConfig(AppConfig):
    name = "apps.sgp"

    def ready(self):
        import apps.sgp.signals.upf  # noqa
        import apps.sgp.signals.workplan  # noqa
