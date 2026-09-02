"""
Criptografia de campos em repouso (AES-256-GCM).

Usada pelos campos definidos em `apps/core/fields.py` para persistir dados
sensíveis (ex.: saúde e cor/raça de `MembroFamilia`) de forma que o valor
não seja legível em texto claro na camada de persistência — nem por acesso
direto ao banco (psql, dump, backup).

Formato do token armazenado (string, base64 urlsafe):
    base64( nonce[12 bytes] || ciphertext || tag[16 bytes] )

A chave é lida uma única vez de `settings.FIELD_ENCRYPTION_KEY` (base64 de
32 bytes) e cacheada em memória do processo.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.core.exceptions import ImproperlyConfigured

_NONCE_SIZE = 12  # 96 bits, recomendado para AES-GCM

_cached_key: bytes | None = None


def _load_key() -> bytes:
    global _cached_key
    if _cached_key is not None:
        return _cached_key

    from django.conf import settings

    raw = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not raw:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY não configurada. Gere uma chave com "
            "`python -c \"import os,base64;print(base64.b64encode(os.urandom(32)).decode())\"` "
            "e defina em backend/.env."
        )

    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY inválida: deve ser uma string base64."
        ) from exc

    if len(key) != 32:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY inválida: deve decodificar para exatamente "
            f"32 bytes (AES-256). Tamanho atual: {len(key)} bytes."
        )

    _cached_key = key
    return key


def encrypt_to_text(plaintext: str) -> str:
    """Criptografa `plaintext` (str) e retorna um token opaco em base64."""
    key = _load_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_to_text(token: str) -> str:
    """Reverte `encrypt_to_text`. Levanta `ValueError` se o token for inválido."""
    key = _load_key()
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except (InvalidTag, ValueError, TypeError) as exc:
        raise ValueError("Token criptografado inválido ou corrompido.") from exc
    return plaintext.decode("utf-8")
