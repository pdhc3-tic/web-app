from django.contrib.contenttypes.models import ContentType
from django.db import models


class SeedImportRecord(models.Model):
    source_file = models.CharField(max_length=255)
    source_sheet = models.CharField(max_length=255)
    source_id = models.CharField(max_length=255)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_file", "source_sheet", "source_id"],
                name="unique_seed_import_source",
            ),
        ]
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="idx_seed_import_object",
            ),
        ]
