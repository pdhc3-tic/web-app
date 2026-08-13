from django.contrib import admin

from apps.sca.models import ConflictLog, SyncDevice, SyncEvent


@admin.register(SyncDevice)
class SyncDeviceAdmin(admin.ModelAdmin):
    list_display = ("device_id", "user", "ativo", "ultimo_sync_em", "criado_em")
    list_filter = ("ativo", "user")
    search_fields = ("device_id", "user__email", "user__nome")


@admin.register(SyncEvent)
class SyncEventAdmin(admin.ModelAdmin):
    list_display = ("tipo", "user", "device", "contagem", "recebido_em")
    list_filter = ("tipo", "user")
    search_fields = ("user__email", "device__device_id")
    date_hierarchy = "recebido_em"


@admin.register(ConflictLog)
class ConflictLogAdmin(admin.ModelAdmin):
    list_display = ("entidade", "campo", "user", "estrategia", "campo_sensivel", "criado_em")
    list_filter = ("estrategia", "campo_sensivel", "entidade")
    search_fields = ("user__email", "uuid_local", "campo")
    date_hierarchy = "criado_em"
