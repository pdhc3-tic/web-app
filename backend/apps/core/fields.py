"""
Model fields que criptografam o valor em repouso (AES-256-GCM, ver `apps.core.crypto`).

A coluna no banco vira `text` (armazena o token opaco), mas o valor em
Python continua se comportando como o tipo original — `choices`,
`get_FOO_display()` e validação de formulário/serializer não mudam.

Uso:
    cor_raca = EncryptedIntChoiceField(choices=COR_RACA_CHOICES, null=True, blank=True)
    saude = EncryptedJSONField(default=list, blank=True)
"""

from __future__ import annotations

import json

from django.db import models

from apps.core.crypto import decrypt_to_text, encrypt_to_text


class EncryptedFieldMixin:
    """
    Base comum: delega a serialização Python<->str para as subclasses via
    `value_to_plaintext`/`plaintext_to_value`, e cuida só da criptografia.

    Importante: NÃO sobrescrevemos `get_internal_type()` — ele continua
    reportando o tipo original (ex.: "PositiveSmallIntegerField",
    "JSONField"), pois classes-base do Django (ex.: `IntegerField.validators`)
    dependem dele para calcular validação de range sobre o valor Python já
    decriptado, que continua sendo um int/lista normal. Só a coluna real no
    banco muda, via `db_type()`.
    """

    def db_type(self, connection):
        return "text"

    def get_prep_value(self, value):
        if value is None:
            return None
        return encrypt_to_text(self.value_to_plaintext(value))

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            # Campo nulável: None é o valor correto, não `self.empty_value`
            # (reservado a campo NOT NULL sem valor persistido ainda).
            if self.null:
                return None
            empty = self.empty_value
            return empty() if callable(empty) else empty
        return self.plaintext_to_value(decrypt_to_text(value))

    def value_to_plaintext(self, value) -> str:
        raise NotImplementedError

    def plaintext_to_value(self, text: str):
        raise NotImplementedError


class EncryptedIntChoiceField(EncryptedFieldMixin, models.IntegerField):
    """
    Inteiro (tipicamente `choices`) armazenado criptografado como texto.

    Base `IntegerField`, não `PositiveSmallIntegerField`: as variantes
    "Positive*" fazem o Postgres backend adicionar automaticamente um CHECK
    constraint `"coluna" >= 0` baseado em `get_internal_type()` — que
    quebraria contra a coluna `text` real. A validação de intervalo/choices
    continua garantida em Python via `full_clean()`/DRF `ChoiceField`.
    """

    empty_value = None

    def value_to_plaintext(self, value) -> str:
        return str(int(value))

    def plaintext_to_value(self, text: str):
        return int(text)


class EncryptedJSONField(EncryptedFieldMixin, models.JSONField):
    """Estrutura JSON (ex.: lista de strings) armazenada criptografada como texto."""

    empty_value = list

    def value_to_plaintext(self, value) -> str:
        return json.dumps(value)

    def plaintext_to_value(self, text: str):
        return json.loads(text)

    def get_prep_value(self, value):
        # Evita a serialização JSON nativa do JSONField (que geraria jsonb);
        # controlamos a serialização nós mesmos via value_to_plaintext.
        if value is None:
            return None
        return encrypt_to_text(self.value_to_plaintext(value))
