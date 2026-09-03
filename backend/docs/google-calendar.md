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

## Modelo De Autenticação Suportado

A integração atual usa uma Service Account para criar eventos em nome de um
usuário Google Workspace. Como as atividades sempre incluem o técnico
responsável e a equipe adicional como participantes e enviam notificações,
`GOOGLE_CALENDAR_DELEGATED_USER` e a Domain-Wide Delegation são obrigatórios
em produção.

Uma Service Account compartilhada diretamente em uma agenda de conta Google
pessoal pode criar eventos sem participantes, mas não pode convidar técnicos
ou equipe. Portanto, esse modelo não é compatível com o comportamento atual
da aplicação sem alteração de código.

## Pré-Requisitos Google Cloud E Workspace

1. Crie a Service Account no projeto Google Cloud.
2. Ative a Google Calendar API no mesmo projeto.
3. Gere uma chave JSON da Service Account.
4. Habilite Domain-Wide Delegation na Service Account e copie seu Client ID
   numérico.
5. No Google Admin Console, acesse **Security > Access and data control > API
   controls > Manage Domain Wide Delegation**.
6. Adicione o Client ID numérico da Service Account e autorize o escopo:

   ```text
   https://www.googleapis.com/auth/calendar
   ```

7. Escolha um usuário Google Workspace com Calendar ativo para ser
   impersonado, por exemplo `agenda@dominio.org.br`.

O Client ID numérico da Service Account não é o OAuth Client ID de uma
aplicação Web. OAuth Client ID não é usado pelo fluxo atual.

## Credenciais Sensíveis

A chave JSON da Service Account não fica no banco, endpoint ou repositório.
Ela deve ser fornecida por variável de ambiente ou secret montado no runtime.

A implementação suporta duas formas, nesta ordem de prioridade:

1. `GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO`: JSON completo da conta de serviço.
2. `GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE`: caminho para arquivo JSON montado no ambiente.

`GOOGLE_CALENDAR_DELEGATED_USER` define o usuário Workspace impersonado pela
Service Account. Ele é obrigatório para produção com participantes.

### Opção 1: JSON Em Variável

```env
GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO={"type":"service_account","project_id":"..."}
GOOGLE_CALENDAR_DELEGATED_USER=agenda@dominio.org.br
```

Use esta opção em ambientes que gerenciam secrets diretamente como variáveis, como Railway, Render, Heroku ou Kubernetes Secrets injetados como env.

### Opção 2: Arquivo JSON Montado

```env
GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE=/run/secrets/google-calendar-service-account.json
GOOGLE_CALENDAR_DELEGATED_USER=agenda@dominio.org.br
```

Use esta opção quando a infraestrutura monta secrets como arquivos no container.

`GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO` recebe o JSON completo, nunca um
caminho de arquivo. `GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE` recebe o caminho
dentro do container.

## Docker Em Produção

O arquivo de credenciais deve existir apenas no host ou no gerenciador de
secrets e ser montado como somente leitura nos serviços `backend` e
`celery_worker`:

```yaml
services:
  backend:
    volumes:
      - /caminho-seguro-no-host/google-calendar-service-account.json:/run/secrets/google-calendar-service-account.json:ro

  celery_worker:
    volumes:
      - /caminho-seguro-no-host/google-calendar-service-account.json:/run/secrets/google-calendar-service-account.json:ro
```

Adapte o caminho do host ao servidor de produção. Não armazene o JSON no
repositório, em imagens Docker ou em diretórios públicos.

## Variáveis De Ambiente

```env
GOOGLE_CALENDAR_SERVICE_ACCOUNT_INFO=
GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE=
GOOGLE_CALENDAR_DELEGATED_USER=
SENTRY_DSN=
```

`SENTRY_DSN` é opcional. Quando configurado, exceções da sincronização são enviadas ao Sentry.

## Configuração Pelo Sistema

Como Super Admin, configure o calendário de destino no endpoint:

```http
PATCH /api/v1/core/config/google-calendar/
```

```json
{
  "calendario_destino_id": "agenda@dominio.org.br",
  "lembretes": [1440, 60],
  "integracao_ativa": true
}
```

Use `primary` para a agenda principal do usuário delegado ou o ID exato de
uma agenda secundária. O ID pode ser consultado em Google Calendar >
Configurações > Integrar agenda.

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

## Status Agregado Da Sincronização

```http
GET /api/v1/core/config/google-calendar/status/
```

Mesmas permissões da view de config (`IsAuthenticatedActiveAccess` + `IsSuperAdmin`). Consumido por `frontend/app/lib/integracoes.ts :: fetchGoogleCalendarStatus`. Resposta:

```json
{
  "estado": "ok",
  "ultima_sincronizacao": "2026-08-28T12:00:00-03:00",
  "ultimo_erro": null,
  "falhas_recentes": 0
}
```

A persistência que alimenta este endpoint é o model append-only `GoogleCalendarSyncEvent` (`apps/sgp/models/google_calendar_sync_event.py`): uma linha por tentativa de sincronização (sucesso ou falha), gravada em `_set_sync_success()` e no bloco `except` de `sync_activity_to_google_calendar` (`apps/sgp/tasks.py`). Não usa `Activity.atualizado_em` como proxy de data de sincronização — esse campo muda em qualquer edição da atividade.

**Decisões (issue #210, Pendência 3):**

- `estado` espelha o vocabulário de `Activity.google_calendar_sync_status` (`ok`/`pendente`/`erro`) mais `nunca_executada`:
  - `pendente` se QUALQUER `Activity` estiver com `google_calendar_sync_status="pendente"` (sync enfileirada/em andamento);
  - `nunca_executada` se nenhum `GoogleCalendarSyncEvent` existe — o critério é "nenhuma tentativa de sincronização (sucesso ou falha) jamais registrada", não "integração nunca foi ativada" (essa segunda leitura ficaria errada se a integração for desligada depois de já ter sincronizado alguma vez);
  - senão `ok`/`erro` conforme o evento mais recente.
- `ultima_sincronizacao` (evento de sucesso mais recente) e `ultimo_erro` (evento de falha mais recente) são calculados de forma independente do `estado` atual — são histórico, não status "ao vivo". Ex.: em `estado="erro"`, `ultima_sincronizacao` continua mostrando o último sucesso anterior à falha.
- `falhas_recentes`: janela fixa de **24h**, rolling (`ocorrido_em` nas últimas 24h) — **não zera quando há um sucesso**, é contagem puramente temporal.

## Tratamento De Falhas

Se a API do Google falhar por erro de rede, token expirado, credencial inválida ou outro erro:

1. A exceção é registrada em log.
2. A exceção é enviada ao Sentry quando `SENTRY_DSN` está configurado.
3. A atividade é marcada com `google_calendar_sync_status="erro"`.
4. Um e-mail é enviado aos usuários com perfil `super-admin` via `send_email_notification`.
5. A exceção não é propagada para o fluxo HTTP da atividade.

A task não possui retry automático. Após corrigir a causa, reenfileire a task
manualmente ou salve uma alteração monitorada na atividade para disparar uma
nova sincronização.

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

## Validação De Go-Live

Antes de ativar a integração em produção:

1. Crie uma atividade com status `agendado` e confirme o evento, convidados e
   lembretes no Google Calendar.
2. Altere data, local e equipe e confirme a atualização do evento.
3. Altere o status para `cancelada` ou `nao_realizada` e confirme a remoção.
4. Consulte `GET /api/v1/core/config/google-calendar/status/` e confirme o
   estado `ok`.
5. Confirme que o `celery_worker` está ativo e sem erros nos logs.

## Segurança Operacional

- Nunca versione a chave JSON da Service Account, arquivos `.env` ou tokens.
- Rotacione imediatamente qualquer chave exposta.
- Restrinja o acesso de leitura ao arquivo JSON no host.
- Monitore as falhas recentes, os logs do worker e os alertas enviados a
  super-admins.

## Testes

Testes automatizados específicos:

```bash
pytest apps/sgp/tests/test_google_calendar_sync.py apps/core/tests/test_system_config.py
```

Testes relacionados ao calendário e atividades:

```bash
pytest apps/sgp/tests/test_activity.py apps/sgp/tests/test_activity_calendario.py apps/sgp/tests/test_google_calendar_sync.py
```
