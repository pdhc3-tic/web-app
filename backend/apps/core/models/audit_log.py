from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Registro imutável de auditoria de ações realizadas no sistema.

    IMUTABILIDADE GARANTIDA EM DOIS NÍVEIS:
    1. Django: o método save() bloqueia qualquer tentativa de UPDATE
        (registros com pk já existente não podem ser salvos novamente).
    2. Banco de dados: um trigger PostgreSQL (core_auditlog_immutable)
        rejeita operações UPDATE e DELETE diretamente na tabela,
        inclusive via psql, migrations ou qualquer acesso direto ao banco.
        Nem o superusuário do Django pode contornar essa restrição.

    Campos estruturados para rastreabilidade completa:
    - user:               quem realizou a ação (NULL se sistema/anônimo)
    - acao:               verbo da ação (CREATE, UPDATE, DELETE, LOGIN…)
    - modulo:             app Django responsável (ex: "sgp", "core")
    - entidade:           nome do model afetado (ex: "Projeto", "User")
    - entidade_id:        PK do registro afetado (texto para suportar UUIDs)
    - valores_anteriores: snapshot do estado antes da alteração (vazio em CREATE)
    - valores_novos:      snapshot do estado após a alteração (vazio em DELETE)
    - ip:                 endereço IP do cliente
    - user_agent:         identificação do navegador/cliente HTTP
    - timestamp:          momento exato do evento (gerado automaticamente)
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Usuário",
        db_index=False,  # índice composto definido em Meta.indexes
    )

    acao = models.CharField(
        max_length=50,
        verbose_name="Ação",
        help_text="Verbo da operação: CREATE, UPDATE, DELETE, LOGIN, LOGOUT…",
    )

    modulo = models.CharField(
        max_length=100,
        verbose_name="Módulo",
        help_text="App Django responsável pela ação (ex: 'sgp', 'core').",
    )

    entidade = models.CharField(
        max_length=100,
        verbose_name="Entidade",
        help_text="Nome do model afetado (ex: 'Projeto', 'User').",
        db_index=False,  # índice composto definido em Meta.indexes
    )

    entidade_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="ID da Entidade",
        help_text="PK do registro afetado. Texto para suportar UUIDs e inteiros.",
    )

    valores_anteriores = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Valores Anteriores",
        help_text="Snapshot do estado antes da alteração. Vazio em CREATE.",
    )

    valores_novos = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Valores Novos",
        help_text="Snapshot do estado após a alteração. Vazio em DELETE.",
    )

    user_agent = models.TextField(
        blank=True,
        default="",
        verbose_name="User-Agent",
        help_text="Identificação do navegador ou cliente HTTP.",
    )
    
    ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        verbose_name="Endereço IP",
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Timestamp",
        db_index=False,  # índice composto definido em Meta.indexes
    )

    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(
                fields=["user", "-timestamp"],
                name="idx_auditlog_user_timestamp",
            ),
            models.Index(
                fields=["entidade", "entidade_id", "-timestamp"],
                name="idx_auditlog_entidade_ts",
            ),
        ]

    def save(self, *args, **kwargs):
        """Bloqueia UPDATE no nível da aplicação Django."""
        if self.pk:
            raise ValueError(
                "AuditLog é imutável: registros existentes não podem ser alterados."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Bloqueia DELETE no nível da aplicação Django."""
        raise ValueError(
            "AuditLog é imutável: registros não podem ser removidos."
        )

    def __str__(self) -> str:
        return f"[{self.acao}] {self.entidade}#{self.entidade_id} — {self.user} — {self.timestamp}"