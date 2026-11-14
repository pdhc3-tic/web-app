from django.apps import AppConfig


class SgpConfig(AppConfig):
    name = "apps.sgp"

    def ready(self):
        import apps.sgp.signals.budget  # noqa
        import apps.sgp.signals.ufpa  # noqa
        import apps.sgp.signals.workplan  # noqa
