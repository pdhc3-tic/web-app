# Documentacao de Throttling do Backend PDHC

## Objetivo

Esta documentacao descreve como o backend do PDHC aplica limites de requisicao (throttling) nos endpoints de autenticacao e como configurar novos throttles para endpoints futuros.

O objetivo principal da refatoracao do PR2 foi separar os contadores de login, refresh e redefinicao de senha. Assim, uma sequencia de tentativas em um fluxo nao bloqueia outro fluxo legitimo.

## Arquivos Envolvidos

- `apps/core/throttling.py`: define as classes de throttle usadas pela API.
- `setup/settings.py`: define os limites de requisicao em `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`.
- `setup/views.py`: aplica os throttles nas views de autenticacao.
- `apps/core/tests/test_throttling.py`: testa limites, isolamento entre escopos e normalizacao de chaves.

## Configuracao Atual

Os limites atuais ficam em `setup/settings.py`:

```python
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/min",
        "user": "1000/min",
        "auth_login": "5/5min",
        "auth_refresh": "10/5min",
        "auth_password_reset_confirm": "3/5min",
        "auth_password_reset_email": "3/5min",
        "auth_password_reset_ip": "5/5min",
        "notification_unread_count": "60/min",
    },
}
```

### Significado Dos Rates

- `5/5min`: permite 5 requisicoes em uma janela de 5 minutos.
- `10/5min`: permite 10 requisicoes em uma janela de 5 minutos.
- `3/5min`: permite 3 requisicoes em uma janela de 5 minutos.
- `100/min`: permite 100 requisicoes por minuto.

O DRF suporta unidades simples como `min`, mas nao interpreta naturalmente expressoes como `5min`. Por isso o projeto usa `CustomWindowRateThrottle`, que converte `5/5min` em uma janela real de 300 segundos.

## Classes De Throttle

As classes estao em `apps/core/throttling.py`.

### CustomWindowRateThrottle

Classe base para throttles que precisam de janelas customizadas como `5/5min`.

Responsabilidades:

- Parsear rates como `5/5min`, `10/5min` e `3/5min`.
- Gerar cache key padrao por escopo e IP.
- Servir como base para throttles de autenticacao.

Formato da chave padrao:

```python
throttle_<scope>_<ip>
```

Exemplo:

```python
throttle_auth_login_127.0.0.1
```

### LoginRateThrottle

Usado apenas no login.

```python
class LoginRateThrottle(CustomWindowRateThrottle):
    scope = "auth_login"
```

Rate atual:

```python
"auth_login": "5/5min"
```

### RefreshRateThrottle

Usado apenas no refresh de token.

```python
class RefreshRateThrottle(CustomWindowRateThrottle):
    scope = "auth_refresh"
```

Rate atual:

```python
"auth_refresh": "10/5min"
```

### PasswordResetByIPThrottle

Usado no endpoint de solicitacao de reset de senha. Limita por IP.

```python
class PasswordResetByIPThrottle(CustomWindowRateThrottle):
    scope = "auth_password_reset_ip"
```

Rate atual:

```python
"auth_password_reset_ip": "5/5min"
```

### PasswordResetByEmailThrottle

Usado no endpoint de solicitacao de reset de senha. Limita por e-mail informado no payload.

```python
class PasswordResetByEmailThrottle(CustomWindowRateThrottle):
    scope = "auth_password_reset_email"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "").strip().lower()
        if not email:
            return None
        return f"throttle_{self.scope}_{email}"
```

Rate atual:

```python
"auth_password_reset_email": "3/5min"
```

A normalizacao com `strip().lower()` evita contadores diferentes para entradas como:

- `usuario@example.com`
- ` Usuario@Example.COM `
- `USUARIO@example.com`

### PasswordResetConfirmThrottle

Usado apenas na confirmacao da redefinicao de senha.

```python
class PasswordResetConfirmThrottle(CustomWindowRateThrottle):
    scope = "auth_password_reset_confirm"
```

Rate atual:

```python
"auth_password_reset_confirm": "3/5min"
```

## Aplicacao Nos Endpoints Atuais

Em `setup/views.py`:

```python
class LoginView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]


class RefreshView(TokenRefreshView):
    throttle_classes = [RefreshRateThrottle]


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetByIPThrottle, PasswordResetByEmailThrottle])
def password_reset_request(request):
    ...


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetConfirmThrottle])
def password_reset_confirm(request):
    ...
```

## Por Que Separar Escopos

Antes da refatoracao, login, refresh e reset de senha compartilhavam o mesmo throttle de login. Isso gerava riscos como:

- Tentativas invalidas de login bloqueando reset de senha legitimo.
- Tentativas invalidas de refresh bloqueando login legitimo.
- Dificuldade de monitorar qual fluxo estava sofrendo abuso.

Com escopos separados, cada fluxo tem contador proprio:

- `auth_login`
- `auth_refresh`
- `auth_password_reset_ip`
- `auth_password_reset_email`
- `auth_password_reset_confirm`

## Como Configurar Throttling Em Novos Endpoints

### 1. Criar Um Scope No Settings

Adicione um novo scope em `setup/settings.py`:

```python
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "reports_export": "2/5min",
    },
}
```

O nome do scope deve ser descritivo e indicar o dominio ou fluxo protegido.

Bons exemplos:

- `reports_export`
- `organization_import`
- `notification_send`
- `auth_mfa_confirm`

Evite nomes genericos como:

- `limited`
- `custom`
- `endpoint`

### 2. Criar A Classe De Throttle

Para limite por IP:

```python
from apps.core.throttling import CustomWindowRateThrottle


class ReportsExportThrottle(CustomWindowRateThrottle):
    scope = "reports_export"
```

Essa classe usara automaticamente a chave:

```python
throttle_reports_export_<ip>
```

### 3. Aplicar Em Class-Based Views

```python
class ReportsExportView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReportsExportThrottle]

    def post(self, request):
        ...
```

### 4. Aplicar Em Function-Based Views

```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ReportsExportThrottle])
def export_reports(request):
    ...
```

## Throttle Por Campo Do Payload

Use esse padrao quando o limite precisa ser por um campo da requisicao, nao apenas por IP.

Exemplo: limitar convite por e-mail.

### 1. Settings

```python
"invite_by_email": "5/5min"
```

### 2. Classe

```python
class InviteByEmailThrottle(CustomWindowRateThrottle):
    scope = "invite_by_email"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "").strip().lower()
        if not email:
            return None
        return f"throttle_{self.scope}_{email}"
```

### 3. View

```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([InviteByEmailThrottle])
def invite_user(request):
    ...
```

## Usando Multiplos Throttles No Mesmo Endpoint

Um endpoint pode usar mais de um throttle.

Exemplo: limitar por IP e por e-mail ao mesmo tempo.

```python
@throttle_classes([PasswordResetByIPThrottle, PasswordResetByEmailThrottle])
def password_reset_request(request):
    ...
```

Nesse caso, a requisicao sera bloqueada se qualquer um dos limites for atingido.

## Boas Praticas

- Use um scope por fluxo de negocio.
- Nao reutilize throttle de login em outros fluxos.
- Prefira limites por IP para endpoints anonimos.
- Combine limite por IP e por campo em fluxos sensiveis, como reset de senha.
- Normalize campos usados na chave: `strip().lower()` para e-mail.
- Mantenha os rates em `settings.py`, nao hardcoded na classe.
- Nomeie scopes de forma clara e pesquisavel.
- Adicione testes para cada novo throttle.

## Testes Recomendados

Para cada novo throttle, adicione testes cobrindo:

- Bloqueio apos o limite configurado.
- Resposta HTTP `429` quando o limite e atingido.
- Isolamento entre escopos diferentes.
- Normalizacao da chave quando o throttle usa campo do payload.
- Limpeza de cache entre testes.

Exemplo de teste unitario para parser:

```python
def test_custom_window_rate_throttle_parseia_janela_de_5_minutos():
    throttle = PasswordResetByEmailThrottle()

    assert throttle.parse_rate("5/5min") == (5, 300)
    assert throttle.parse_rate("10/5min") == (10, 300)
    assert throttle.parse_rate("3/5min") == (3, 300)
```

Exemplo de teste de normalizacao:

```python
def test_password_reset_email_throttle_normaliza_email():
    request = type("Request", (), {"data": {"email": " Usuario@Example.COM "}})()

    cache_key = PasswordResetByEmailThrottle().get_cache_key(request, None)

    assert cache_key == "throttle_auth_password_reset_email_usuario@example.com"
```

## Checklist Para Novos Endpoints

- Definir o risco do endpoint.
- Criar um scope claro em `DEFAULT_THROTTLE_RATES`.
- Criar uma classe de throttle em `apps/core/throttling.py`.
- Aplicar a classe na view.
- Adicionar teste de limite.
- Adicionar teste de isolamento, quando houver escopos relacionados.
- Confirmar que `pytest` passa.

## Troubleshooting

### Erro: `.get_cache_key() must be overridden`

Esse erro acontece quando uma classe herda de `SimpleRateThrottle` sem implementar `get_cache_key`.

No PDHC, novos throttles devem herdar de `CustomWindowRateThrottle`, que ja implementa a chave padrao por IP.

### Endpoint Retorna 429 Em Testes Isolados

O cache de throttling pode estar contaminado por testes anteriores. Use limpeza de cache:

```python
@pytest.fixture(autouse=True)
def limpa_cache():
    cache.clear()
    yield
    cache.clear()
```

### Limite Nao Esta Sendo Aplicado

Verifique:

- Se o scope da classe existe em `DEFAULT_THROTTLE_RATES`.
- Se a view tem `throttle_classes` configurado.
- Se a classe herda de `CustomWindowRateThrottle`.
- Se o endpoint passa pelos decorators na ordem correta.

## Resumo

O throttling atual separa os fluxos criticos de autenticacao em escopos independentes. Isso evita bloqueios cruzados entre login, refresh e redefinicao de senha, mantendo os limites configuraveis em `settings.py` e as regras centralizadas em `apps/core/throttling.py`.
