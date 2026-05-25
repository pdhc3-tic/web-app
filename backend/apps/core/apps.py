from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from apps.core.models.user import User
        from apps.core.models.user_profile import UserProfile
        from apps.core.models.role import Role
        from apps.core.models.territory import Territory
        from apps.core.models.organization import Organization
        from apps.core.signals.audit import _register_audited_model
        _register_audited_model(User, modulo="core")
        _register_audited_model(UserProfile, modulo="core")
        _register_audited_model(Role, modulo="core")
        _register_audited_model(Territory, modulo="core")
        _register_audited_model(Organization, modulo="core")
        # SystemConfig será adicionado aqui quando vier do main
        #_register_audited_model(SystemConfig, modulo="core")
