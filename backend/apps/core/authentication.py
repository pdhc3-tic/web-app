from __future__ import annotations

import secrets

from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


class PowerBIServicePrincipal:
    """Identidade mínima para um consumidor máquina-a-máquina, sem usuário Django."""

    is_active = True
    is_anonymous = False
    is_authenticated = True
    pk = "power-bi-service"

    def __str__(self) -> str:
        return "power-bi-service"


class PowerBIServiceTokenAuthentication(BaseAuthentication):
    """Autentica exclusivamente o token dedicado ao conector Power BI."""

    keyword = b"token"

    def authenticate(self, request):
        authorization = get_authorization_header(request).split()
        if not authorization:
            return None
        if len(authorization) != 2 or authorization[0].lower() != self.keyword:
            raise AuthenticationFailed("Token de serviço inválido.")

        try:
            supplied_token = authorization[1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed("Token de serviço inválido.") from exc

        if self._matches_persisted_token(supplied_token):
            return PowerBIServicePrincipal(), "power-bi-service"

        # Canal secundário (infra/emergência) — o token administrável pela
        # tela (Issue 143) é o caminho principal e não depende deste.
        configured_token = settings.POWER_BI_SERVICE_TOKEN
        if configured_token and secrets.compare_digest(
            supplied_token, configured_token
        ):
            return PowerBIServicePrincipal(), "power-bi-service"

        raise AuthenticationFailed("Token de serviço inválido.")

    @staticmethod
    def _matches_persisted_token(supplied_token: str) -> bool:
        from apps.core.models.power_bi_token import PowerBIToken

        return PowerBIToken.validar(supplied_token)

    def authenticate_header(self, request):
        return "Token"
