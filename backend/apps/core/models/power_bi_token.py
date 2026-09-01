import hashlib
import secrets

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils import timezone


class PowerBIToken(models.Model):
    """Token administrável usado pelo conector Power BI (Issue 143).

    Mesmo padrão de `PasswordResetToken`: só o hash SHA-256 é persistido: o
    texto puro é gerado em memória e devolvido uma única vez, na resposta da
    regeneração — nunca fica recuperável a partir do banco.
    """

    token_hash = models.CharField(max_length=64, unique=True)
    token_mascarado = models.CharField(max_length=16)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="power_bi_tokens",
    )
    revogado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Token de administração do Power BI"
        verbose_name_plural = "Tokens de administração do Power BI"
        ordering = ["-criado_em"]
        constraints = [
            # Trava a nível de banco a invariante "no máximo um token ativo":
            # gerar() já desativa o anterior antes de criar o novo, mas só a
            # constraint garante a invariante sob regenerações concorrentes
            # (duas chamadas simultâneas não podem deixar dois ativos).
            models.UniqueConstraint(
                fields=["ativo"],
                condition=models.Q(ativo=True),
                name="uniq_power_bi_token_ativo",
            ),
        ]

    def __str__(self):
        return f"PowerBIToken({self.token_mascarado}, ativo={self.ativo})"

    @staticmethod
    def _hash(token_raw: str) -> str:
        return hashlib.sha256(token_raw.encode()).hexdigest()

    @staticmethod
    def _mask(token_raw: str) -> str:
        return f"••••{token_raw[-4:]}"

    @classmethod
    def gerar(cls, *, criado_por, _tentativas=3) -> tuple["PowerBIToken", str]:
        """Cria um novo token ativo e desativa o anterior, em transação.

        Sob duas regenerações concorrentes, a constraint `uniq_power_bi_token_ativo`
        rejeita a segunda `create()` antes de deixar dois tokens ativos; a
        exceção é tratada aqui com uma nova tentativa (a segunda chamada só
        precisa repetir o `update()`, que já vai encontrar o token da primeira
        como o ativo a desativar).

        Retorna (instância, token_em_claro) — o texto puro só existe aqui.
        """
        ultima_excecao = None
        for _ in range(_tentativas):
            token_raw = secrets.token_urlsafe(32)
            try:
                with transaction.atomic():
                    cls.objects.filter(ativo=True).update(
                        ativo=False, revogado_em=timezone.now()
                    )
                    instancia = cls.objects.create(
                        token_hash=cls._hash(token_raw),
                        token_mascarado=cls._mask(token_raw),
                        criado_por=criado_por,
                    )
                return instancia, token_raw
            except IntegrityError as exc:
                ultima_excecao = exc
        raise ultima_excecao

    @classmethod
    def validar(cls, token_raw: str) -> bool:
        if not token_raw:
            return False
        return cls.objects.filter(
            token_hash=cls._hash(token_raw), ativo=True
        ).exists()

    @classmethod
    def ativo_atual(cls):
        return cls.objects.filter(ativo=True).first()
