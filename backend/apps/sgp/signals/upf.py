from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from apps.sgp.cache import invalidate_upf_map_cache
from apps.sgp.models.upf import UPF


@receiver(pre_save, sender=UPF)
def auto_preencher_territorio(sender, instance, **kwargs):
    if instance.municipio_id:
        try:
            territory = instance.municipio.territory
            if territory:
                instance.territorio = territory
        except Exception:
            pass


@receiver(pre_save, sender=UPF)
@receiver(pre_delete, sender=UPF)
def invalidate_mapa_cache(sender, instance, **kwargs):
    invalidate_upf_map_cache()
