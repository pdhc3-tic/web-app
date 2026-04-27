from rest_framework.permissions import DjangoModelPermissions


class FullDjangoModelPermissions(DjangoModelPermissions):
    def __init__(self):
        # Adicionamos o 'GET' à lista de métodos que exigem permissão
        self.perms_map["GET"] = ["%(app_label)s.view_%(model_name)s"]
