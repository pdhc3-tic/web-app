# Politica de Logging do Backend PDHC

## Objetivo

Esta politica define como o backend registra eventos operacionais sem substituir o `AuditLog` imutavel do banco.

Logs em arquivo sao usados para observabilidade, seguranca operacional e troubleshooting. Eventos formais de conformidade, LGPD e historico de alteracoes devem continuar sendo persistidos no `AuditLog`.

## Arquivos Gerados

Os arquivos sao criados no diretorio definido por `LOG_DIR`.

Padrao:

```text
backend/logs/
```

Arquivos:

```text
app.log
security.log
audit-events.log
celery.log
errors.log
```

## Finalidade De Cada Arquivo

### app.log

Eventos gerais da aplicacao e logs de modulos `apps` e `setup`.

Exemplos:

- Operacoes gerais do backend.
- Eventos informativos nao sensiveis.
- Logs de apoio para troubleshooting.

### security.log

Eventos sensiveis de seguranca operacional.

Exemplos:

- Login bem-sucedido.
- Falha de login.
- Rate limit e throttling.
- Refresh token invalido.
- Logout e logout global.
- Reset de senha solicitado/concluido.

### audit-events.log

Resumo operacional de eventos que tambem devem estar cobertos por auditoria formal.

Exemplos:

- Usuario criado, atualizado ou desativado.
- Organizacao criada, atualizada ou desativada.
- Configuracao do sistema alterada.
- Acesso ao painel de auditoria.

Este arquivo nao substitui `AuditLog`.

### celery.log

Eventos de tarefas assincronas.

Exemplos:

- Envio de e-mail.
- Falha SMTP.
- Retry de notificacao.
- Notificacao cancelada por preferencia do usuario.

### errors.log

Eventos `ERROR` e `CRITICAL` consolidados.

Este arquivo facilita triagem rapida de falhas inesperadas.

## Rotacao E Retencao

Os arquivos usam `TimedRotatingFileHandler` com rotacao diaria.

Variaveis de ambiente:

```text
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_BACKUP_COUNT=14
SECURITY_LOG_LEVEL=INFO
SECURITY_LOG_BACKUP_COUNT=90
AUDIT_EVENT_LOG_LEVEL=INFO
AUDIT_LOG_BACKUP_COUNT=90
ERROR_LOG_BACKUP_COUNT=30
```

Retencao padrao:

```text
app.log: 14 dias
security.log: 90 dias
audit-events.log: 90 dias
celery.log: 14 dias
errors.log: 30 dias
```

O `docker-compose.yml` tambem limita logs de container com:

```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "5"
```

## Dados Permitidos

Preferir identificadores e metadados operacionais:

```text
event
user_id
actor_user_id
entity_id
ip
method
path
status_code
reason
error_class
```

## Dados Proibidos

Nunca registrar:

```text
senha
password
nova_senha
access_token
refresh_token
Authorization
cookies
token de reset
token_hash
payload completo
valores sensiveis completos
```

## Relacao Entre Logging E AuditLog

Use log operacional para:

- Diagnosticar falhas.
- Monitorar eventos de seguranca.
- Investigar throttling, permissoes negadas e falhas tecnicas.

Use `AuditLog` para:

- Conformidade.
- LGPD.
- Historico imutavel.
- Alteracoes de dados pessoais.
- Alteracoes de configuracao global.
- Eventos formais de login/logout/reset quando exigidos por requisito.

## Boas Praticas

- Usar `logging.getLogger(__name__)` em modulos comuns.
- Usar `logging.getLogger("security")` para eventos de seguranca.
- Usar `logging.getLogger("audit_events")` para eventos operacionais correlatos a auditoria.
- Usar lazy formatting: `logger.info("user_id=%s", user_id)`.
- Nao usar f-strings em chamadas de logger.
- Nao logar payloads completos.
- Usar `logger.exception()` apenas quando o traceback for necessario.
- Evitar logs em endpoints de leitura muito frequentes.

## Eventos Ja Instrumentados

- `auth.login_success`
- `auth.login_failed`
- `auth.login_rate_limited`
- `auth.refresh_success`
- `auth.refresh_failed`
- `auth.logout_success`
- `auth.logout_failed`
- `auth.logout_all_success`
- `auth.password_reset_requested`
- `auth.password_reset_email_enqueued`
- `auth.password_reset_confirm_failed`
- `auth.password_reset_completed`
- `request.throttled`
- `user.created`
- `user.updated`
- `user.deactivated`
- `organization.created`
- `organization.updated`
- `organization.soft_deleted`
- `system_config.updated`
- `audit_log.accessed`
- `notifications.mark_all_read`
- `session_context.set_local_failed`

## Eventos Que Devem Ir Para AuditLog Em PR Futuro

- Login bem-sucedido.
- Logout.
- Logout global.
- Reset de senha concluido.
- Criacao/edicao/desativacao de usuario.
- Alteracao de perfil e territorio.
- Alteracao de configuracao global.
- Consulta IA futura com prompt, resposta, tokens e custo.
