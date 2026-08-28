# SCA — Sync offline e administração

Módulo de sincronização offline do app SCA e endpoints administrativos de
acompanhamento (issues #156–#160). API sob `/api/v1/sca/` com JWT.

## Endpoints de sincronização (app mobile)

| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/api/v1/sca/sync/push/` | Envia criações/alterações offline em lote |
| GET | `/api/v1/sca/sync/pull/` | Baixa registros alterados desde o último pull |
| GET | `/api/v1/sca/sync/forms/` | Formulários dinâmicos para preenchimento offline |
| GET | `/api/v1/sca/sync/status/` | Estado da sessão de sync do dispositivo |
| POST | `/api/v1/sca/auth/refresh/` | Renovação de token com vínculo de dispositivo |

## Endpoints administrativos (Super Admin / UGP; conflitos também Articulador Estadual)

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/api/v1/sca/devices/` | Dispositivos com último sync, territórios e `limiar_alerta_dias` |
| GET | `/api/v1/sca/sync-events/` | Auditoria de eventos push/pull (+ detail com `erros_detalhes`) |
| GET | `/api/v1/sca/conflicts/` | Fila de conflitos (+ detail com snapshot do registro) |
| POST | `/api/v1/sca/conflicts/{id}/resolver/` | Resolução manual: `local`, `servidor` ou `manual` |

## Formato dos erros por item (`SyncEvent.erros_detalhes`)

Cada item rejeitado no push gera um objeto:

```json
{"uuid_local": "...", "entidade": "upf", "codigo": "PAYLOAD_INVALIDO", "mensagem": "..."}
```

Códigos possíveis: `PAYLOAD_INVALIDO`, `ENTIDADE_NAO_SUPORTADA`, `DUPLICATA`,
`NAO_ENCONTRADO`, `FORA_TERRITORIO`, `ERRO_INTERNO`.

## Decisões de contrato V1

Registro formal de decisões levantadas nas pendências do frontend, para evitar
reabertura do tema (#196).

### 1. `status_conexao` é derivado no frontend

`status_conexao` **não é um campo do backend**. O frontend calcula a faixa
(verde/laranja/vermelho) no cliente a partir de:

- `ultimo_sync_servidor` — exposto por `GET /api/v1/sca/devices/`
  (maior entre `ultimo_push_em` e `ultimo_pull_em`; `null` quando o
  dispositivo nunca sincronizou);
- `limiar_alerta_dias` — devolvido no payload da mesma listagem
  (`SystemConfig.sca_sync_alerta_dias`, seed/migração = 7).

Nenhuma migração ou campo adicional é necessário.

### 2. `tipo_conexao` aceita `null` na V1

`SyncEvent.tipo_conexao` é populado a partir do header `X-Connection-Type`
do push/pull. Enquanto o cliente do app SCA não enviar essa informação,
o backend **aceita o valor `null` sem rejeitar o evento** — eventos de
sincronização sem header continuam sendo gravados e auditados normalmente.
O preenchimento completo fica condicionado a atualização futura do cliente
SCA, fora do escopo atual.
