from django.apps import AppConfig


class SgpConfig(AppConfig):
    name = "apps.sgp"

    def ready(self):
        from apps.sgp.models import Comunidade
        from apps.core.signals.audit import _register_audited_model
        _register_audited_model(Comunidade, modulo="sgp")
