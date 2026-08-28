"""
Model Activity — SGP Requisitos seção 3.1
Motor de status: seção 3.2 (8 estados)
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------

TIPO_ATIVIDADE_CHOICES = [
    ("visita_tecnica", "Visita técnica"),
    ("reuniao_comunitaria", "Reunião comunitária"),
    ("oficina", "Oficina"),
    ("intercambio", "Intercâmbio"),
    ("curso_capacitacao", "Curso/Capacitação"),
    ("dia_de_campo", "Dia de campo"),
    ("seminario", "Seminário"),
    ("encontro", "Encontro"),
    ("dia_de_partilha", "Dia de partilha"),
    ("atividade_interna", "Atividade interna"),
    ("pesquisa_de_campo", "Pesquisa de campo"),
    ("ater", "Assistência técnica/ATER"),
    ("outro", "Outro"),
]

FORMA_ATUACAO_CHOICES = [
    ("realizacao", "Realização"),
    ("participacao", "Participação"),
    ("apoio", "Apoio"),
    ("articulacao", "Articulação"),
]

AMBITO_CHOICES = [
    ("municipal", "Municipal"),
    ("microrregional", "Microrregional"),
    ("estadual", "Estadual"),
    ("supraestadual", "Supraestadual"),
]

STATUS_CHOICES = [
    ("planejado", "Planejado"),
    ("agendado", "Agendado"),
    ("em_andamento", "Em andamento"),
    ("concluido", "Concluído"),
    ("concluido_sem_evidencia", "Concluído sem evidência"),
    ("adiada", "Adiada"),
    ("nao_realizada", "Não realizada"),
    ("cancelada", "Cancelada"),
]

# Estados terminais — não permitem mais transições
STATUS_TERMINAIS = {"concluido", "concluido_sem_evidencia", "nao_realizada", "cancelada"}

# Tabela de transições permitidas: status_atual → {próximos válidos}
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "planejado": {"agendado", "cancelada"},
    "agendado": {"em_andamento", "adiada", "cancelada"},
    "em_andamento": {"concluido", "concluido_sem_evidencia", "nao_realizada", "cancelada"},
    "adiada": {"agendado", "cancelada"},
    # terminais não permitem saída
    "concluido": set(),
    "concluido_sem_evidencia": set(),
    "nao_realizada": set(),
    "cancelada": set(),
}

GOOGLE_CALENDAR_SYNC_STATUS_CHOICES = [
    ("pendente", "Pendente"),
    ("ok", "OK"),
    ("erro", "Erro"),
]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Activity(models.Model):
    # ── Identificação ────────────────────────────────────────────────────────
    titulo = models.CharField(max_length=255, verbose_name="Título")

    tipo_atividade = models.CharField(
        max_length=30,
        choices=TIPO_ATIVIDADE_CHOICES,
        verbose_name="Tipo de Atividade",
    )

    # ── Vínculos com PT ──────────────────────────────────────────────────────
    acao = models.ForeignKey(
        "sgp.WorkPlanAcao",
        on_delete=models.PROTECT,
        related_name="atividades",
        verbose_name="Ação do PT",
    )

    # ── Atuação ──────────────────────────────────────────────────────────────
    forma_atuacao = models.CharField(
        max_length=20,
        choices=FORMA_ATUACAO_CHOICES,
        verbose_name="Forma de Atuação",
    )

    # ── Equipe ───────────────────────────────────────────────────────────────
    tecnico_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="atividades_responsavel",
        verbose_name="Técnico Responsável",
    )
    equipe_adicional = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="atividades_equipe",
        blank=True,
        verbose_name="Equipe Adicional",
    )

    # ── Localização ──────────────────────────────────────────────────────────
    municipio = models.ForeignKey(
        "core.Municipality",
        on_delete=models.PROTECT,
        related_name="atividades",
        verbose_name="Município",
    )
    comunidade = models.ForeignKey(
        "sgp.Comunidade",
        on_delete=models.SET_NULL,
        related_name="atividades",
        null=True,
        blank=True,
        verbose_name="Comunidade",
    )
    ambito = models.CharField(
        max_length=20,
        choices=AMBITO_CHOICES,
        verbose_name="Âmbito",
    )
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True, verbose_name="Latitude",
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True, verbose_name="Longitude",
    )

    # ── Datas ────────────────────────────────────────────────────────────────
    data_inicio = models.DateTimeField(verbose_name="Data de Início")
    data_fim = models.DateTimeField(verbose_name="Data de Fim")

    # ── Participantes ────────────────────────────────────────────────────────
    upfs_participantes = models.ManyToManyField(
        "sgp.UPF",
        related_name="atividades",
        blank=True,
        verbose_name="UPFs Participantes",
    )
    membros_participantes = models.ManyToManyField(
        "sgp.MembroFamilia",
        related_name="atividades",
        blank=True,
        verbose_name="Membros Participantes",
    )

    # ── Parceiros (texto livre — BE-2 pode adicionar M2M Organization depois) ─
    parceiros = models.TextField(
        blank=True,
        default="",
        verbose_name="Parceiros",
        help_text="Lista de parceiros em texto livre. Futura versão integrará com Organizations.",
    )

    # ── Narrativa ────────────────────────────────────────────────────────────
    descricao_narrativa = models.TextField(verbose_name="Descrição Narrativa")
    resultados_alcancados = models.TextField(
        blank=True, default="", verbose_name="Resultados Alcançados",
    )

    # ── Status e motor de estado ──────────────────────────────────────────────
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="planejado",
        verbose_name="Status",
        db_index=True,
    )
    justificativa = models.TextField(
        blank=True,
        default="",
        verbose_name="Justificativa",
        help_text="Obrigatório quando status = Não realizada ou Cancelada.",
    )

    # ── Soft-delete ───────────────────────────────────────────────────────────
    ativo = models.BooleanField(default=True, verbose_name="Ativo", db_index=True)

    # ── Auditoria ────────────────────────────────────────────────────────────
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="atividades_criadas",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # ── Sync SCA (compatibilidade com dispositivos offline) ──────────────────
    device_id = models.CharField(
        max_length=100,
        blank=True, default="",
        verbose_name="Device ID",
        help_text="Identificador do dispositivo de origem (sync SCA).",
    )
    uuid_local = models.UUIDField(
        null=True, blank=True,
        unique=True,
        verbose_name="UUID Local",
        help_text="UUID gerado pelo dispositivo para idempotência no sync SCA.",
    )
    ultima_origem = models.CharField(
        max_length=10,
        choices=[("sca", "SCA"), ("web", "Web")],
        default="web",
        verbose_name="Última Origem",
        help_text="Indica se a última alteração partiu do app SCA ou da plataforma Web.",
    )
    ultimo_sync_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Último Sync SCA",
        help_text="Timestamp da última sincronização bem-sucedida via SCA.",
    )

    # ── Integração Google Calendar ────────────────────────────────────────────
    google_calendar_event_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="ID do Evento Google Calendar",
    )
    google_calendar_sync_status = models.CharField(
        max_length=20,
        choices=GOOGLE_CALENDAR_SYNC_STATUS_CHOICES,
        default="ok",
        verbose_name="Status de Sync Google Calendar",
    )

    # ── Campo calculado território (derivado do município) ────────────────────
    @property
    def territorio(self):
        return self.municipio.territory if self.municipio_id else None

    @property
    def territorio_id(self):
        return self.municipio.territory_id if self.municipio_id else None

    # ── Lógica de evidências (BE-2 stub) ──────────────────────────────────────
    def has_evidencias(self) -> bool:
        """
        Retorna True se a atividade possui ao menos 1 foto ativa
        ou 1 documento ativo vinculado.
        """
        return (
            self.fotos.filter(ativa=True).exists()
            or self.documentos.filter(ativo=True).exists()
        )

    # ── Utilitário de status ───────────────────────────────────────────────────
    def get_transicoes_permitidas(self) -> set[str]:
        return STATUS_TRANSITIONS.get(self.status, set())

    class Meta:
        verbose_name = "Atividade"
        verbose_name_plural = "Atividades"
        ordering = ["-data_inicio", "-criado_em"]
        indexes = [
            models.Index(fields=["status"], name="idx_activity_status"),
            models.Index(fields=["municipio"], name="idx_activity_municipio"),
            models.Index(fields=["acao"], name="idx_activity_acao"),
            models.Index(fields=["tecnico_responsavel"], name="idx_activity_tecnico"),
            models.Index(fields=["data_inicio", "data_fim"], name="idx_activity_datas"),
            models.Index(fields=["ativo"], name="idx_activity_ativo"),
        ]

    def __str__(self):
        return f"{self.titulo} [{self.get_status_display()}]"
