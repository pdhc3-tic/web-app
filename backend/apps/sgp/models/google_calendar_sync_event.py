"""
Log append-only de tentativas de sincronização com o Google Calendar (uma
linha por sucesso OU falha), usado para alimentar o endpoint agregado
GET /api/v1/core/config/google-calendar/status/.

Um único campo por Activity sobrescreveria falhas repetidas da mesma
atividade dentro da janela de "falhas recentes", subcontando — por isso o
histórico vive num log próprio em vez de campos adicionais em Activity.
"""
from django.db import models


class GoogleCalendarSyncEvent(models.Model):
    activity = models.ForeignKey(
        "sgp.Activity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="google_calendar_sync_events",
        verbose_name="Atividade",
    )
    sucesso = models.BooleanField(verbose_name="Sucesso")
    mensagem_erro = models.TextField(blank=True, default="", verbose_name="Mensagem de erro")
    ocorrido_em = models.DateTimeField(auto_now_add=True, verbose_name="Ocorrido em")

    class Meta:
        verbose_name = "Evento de Sincronização Google Calendar"
        verbose_name_plural = "Eventos de Sincronização Google Calendar"
        ordering = ["-ocorrido_em"]
        indexes = [
            models.Index(fields=["sucesso", "ocorrido_em"], name="idx_gcalsync_sucesso_ocorrido"),
        ]

    def __str__(self):
        estado = "sucesso" if self.sucesso else "falha"
        return f"GoogleCalendarSyncEvent #{self.pk} — {estado} ({self.ocorrido_em})"
