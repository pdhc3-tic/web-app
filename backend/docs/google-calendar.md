# Integração Google Calendar

## Visão Geral

A integração sincroniza o ciclo de vida das atividades do SGP com o Google Calendar por meio de uma task Celery chamada `sync_activity_to_google_calendar(activity_id)`.

O fluxo HTTP de criação/edição da atividade não chama a API do Google diretamente. A API apenas decide se deve enfileirar a task e marca a atividade como `google_calendar_sync_status="pendente"`. A execução assíncrona faz a chamada ao Google Calendar e atualiza a atividade com `ok` ou `erro`.

## Configuração Não Sensível

As configurações editáveis ficam no endpoint singleton restrito a Super Admin:

```http
GET /api/v1/core/config/google-calendar/
PATCH /api/v1/core/config/google-calendar/
```

Campos:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `calendario_destino_id` | string | ID do calendário de destino no Google Calendar |
| `lembretes` | lista de inteiros | Minutos antes do evento. Padrão: `[1440, 60]` |
| `integracao_ativa` | boolean | Quando `false`, novas sincronizações não são enfileiradas |

Exemplo:

```json
{
  "calendario_destino_id": "agenda@pdhc.org.br",
  "lembretes": [1440, 60],
  "integracao_ativa": true
}
```

## Credenciais Sensíveis

As credenciais OAuth2 da conta de serviço não ficam no banco, endpoint ou repositório. Elas devem ser fornecidas por variável de ambiente.

A implementação suporta duas formas, nesta ordem de prioridade:

1. `GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO`: JSON completo da conta de serviço.
2. `GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE`: caminho para arquivo JSON montado no ambiente.

Opcionalmente, use `GOOGLE_CALENDAR_DELEGATED_USER` para domain-wide delegation em Google Workspace.

### Opção 1: JSON Em Variável

```env
GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO={"type":"service_account","project_id":"..."}
GOOGLE_CALENDAR_DELEGATED_USER=agenda@pdhc.org.br
```

Use esta opção em ambientes que gerenciam secrets diretamente como variáveis, como Railway, Render, Heroku ou Kubernetes Secrets injetados como env.

### Opção 2: Arquivo JSON Montado

```env
GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE=/run/secrets/google-calendar-service-account.json
GOOGLE_CALENDAR_DELEGATED_USER=agenda@pdhc.org.br
```

Use esta opção quando a infraestrutura monta secrets como arquivos no container.

## Variáveis De Ambiente

```env
GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO=
GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE=
GOOGLE_CALENDAR_DELEGATED_USER=
SENTRY_DSN=
```

`SENTRY_DSN` é opcional. Quando configurado, exceções da sincronização são enviadas ao Sentry.

## Eventos Sincronizados

### Criação

Quando uma atividade muda para `agendado` e ainda não possui `google_calendar_event_id`, a task chama `events.insert`.

### Atualização

Quando uma atividade já `agendado` possui `google_calendar_event_id` e muda algum destes campos, a task chama `events.update`:

| Campo |
|-------|
| `data_inicio` |
| `data_fim` |
| `municipio` |
| `comunidade` |
| `equipe_adicional` |

### Remoção

Quando uma atividade muda para `cancelada` ou `nao_realizada`, a task chama `events.delete` se houver `google_calendar_event_id` salvo.

## Payload Enviado Ao Google Calendar

O evento é criado/atualizado com:

| Campo Google | Origem |
|--------------|--------|
| `summary` | `[Tipo] — [Título da atividade]` |
| `start.dateTime` | `Activity.data_inicio` |
| `end.dateTime` | `Activity.data_fim` |
| `location` | Município, comunidade e coordenadas GPS quando disponíveis |
| `description` | Tipo, Ação do PT, âmbito e link para a atividade |
| `attendees` | Técnico responsável e equipe adicional |
| `reminders` | Configuração `lembretes` do Core |

Exemplo de payload simplificado:

```json
{
  "summary": "[Oficina] — Manejo agroecológico",
  "start": {
    "dateTime": "2026-08-10T08:00:00-03:00",
    "timeZone": "America/Sao_Paulo"
  },
  "end": {
    "dateTime": "2026-08-10T12:00:00-03:00",
    "timeZone": "America/Sao_Paulo"
  },
  "location": "Mossoró - Sítio Boa Vista - GPS: -5.1870000, -37.3440000",
  "attendees": [
    {"email": "tecnico@example.com"},
    {"email": "equipe@example.com"}
  ],
  "reminders": {
    "useDefault": false,
    "overrides": [
      {"method": "popup", "minutes": 1440},
      {"method": "popup", "minutes": 60}
    ]
  }
}
```

## Campos Na Atividade

| Campo | Descrição |
|-------|-----------|
| `google_calendar_event_id` | ID do evento salvo para permitir update/delete subsequentes |
| `google_calendar_sync_status` | `ok`, `pendente` ou `erro`. O valor padrão é `ok`; quando uma sincronização é enfileirada, muda para `pendente` |

## Tratamento De Falhas

Se a API do Google falhar por erro de rede, token expirado, credencial inválida ou outro erro:

1. A exceção é registrada em log.
2. A exceção é enviada ao Sentry quando `SENTRY_DSN` está configurado.
3. A atividade é marcada com `google_calendar_sync_status="erro"`.
4. Um e-mail é enviado aos usuários com perfil `super-admin` via `send_email_notification`.
5. A exceção não é propagada para o fluxo HTTP da atividade.

## Execução Manual Da Task

Em shell Django:

```python
from apps.sgp.tasks import sync_activity_to_google_calendar

sync_activity_to_google_calendar.delay(activity_id)
```

Para execução síncrona em diagnóstico:

```python
sync_activity_to_google_calendar(activity_id)
```

## Testes

Testes automatizados específicos:

```bash
pytest apps/sgp/tests/test_google_calendar_sync.py
```

Testes relacionados ao calendário e atividades:

```bash
pytest apps/sgp/tests/test_activity.py apps/sgp/tests/test_activity_calendario.py apps/sgp/tests/test_google_calendar_sync.py
```
