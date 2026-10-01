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
`NAO_ENCONTRADO`, `FORA_TERRITORIO`, `ERRO_INTERNO`, `EXCLUIDO_NO_SERVIDOR`,
`CAMPO_SENSIVEL_NAO_AUTORIZADO`, e os códigos de regra de negócio (ver seção
abaixo): `TRANSICAO_INVALIDA`, `EVIDENCIA_OBRIGATORIA`,
`JUSTIFICATIVA_OBRIGATORIA`, `NOVA_DATA_OBRIGATORIA`, `DATA_FIM_INVALIDA`,
`MEMBRO_FORA_UPF`, `CPF_INVALIDO`, `CPF_DUPLICADO`, `TITULAR_DUPLICADO`,
`DATA_NASCIMENTO_INVALIDA`, `SAUDE_INVALIDA`, `SEGURIDADE_SOCIAL_INVALIDA`.

## Conflitos de regra de negócio (`estrategia=regra_negocio_rejeitada`)

UPF, Membro e Atividade são gravados tanto pela API web quanto pelo sync do
SCA — as duas portas de entrada aplicam exatamente as mesmas regras de
negócio, consumindo os mesmos serviços de domínio do app `sgp`:

- `apps.sgp.services.activity_status` — transição de status, evidência
  obrigatória para concluir, justificativa obrigatória, nova data obrigatória
  ao reagendar, `data_fim` não anterior a `data_inicio`, membros
  participantes pertencentes às UPFs participantes selecionadas (Activity).
  A validação de status/justificativa/`data_fim` roda em toda atualização,
  mesmo quando o campo em questão não vem no payload — com fallback pro
  valor atual da atividade, igual à API web (senão um update que só toca
  outro campo escaparia da regra).
- `apps.sgp.services.membro_rules` — CPF normalizado (só dígitos) e validado
  (dígito verificador, mesma checagem de `apps.sgp.validators.validate_cpf`)
  antes de checar unicidade global; titular único por UPF; data de
  nascimento não pode ser futura; saúde e seguridade social restritas ao
  catálogo, sem duplicidade e sem combinar "nenhuma(m)" com outras opções
  (Membro, e titular da UPF).

Quando um item do push viola uma dessas regras, o sync **nunca grava
silenciosamente em estado inválido**: o item é rejeitado normalmente (erro
por item em `erros_detalhes`, códigos acima) **e**, adicionalmente, é
registrada uma entrada em `ConflictLog` com
`estrategia=regra_negocio_rejeitada` e `status=pendente`, visível em
`GET /api/v1/sca/conflicts/` para acompanhamento administrativo (UGP/
Articulador). Isso cobre, por exemplo, uma atividade marcada como
"concluída" offline sem evidência ainda confirmada no servidor — a regra
rejeita a transição e o caso fica registrado para follow-up manual; não há
fila de reprocessamento automático (o app mobile decide se reenvia depois).

**Corrida entre pushes concorrentes.** A checagem de CPF único/titular único
é feita em memória antes de gravar; se dois pushes concorrentes passarem
juntos por ela (nenhum viu o outro ainda commitado), só a `UniqueConstraint`
do banco barra o segundo. Esse caso também vira `CPF_DUPLICADO`/
`TITULAR_DUPLICADO` com entrada em `conflict_log` — nunca um `ERRO_INTERNO`
genérico — porque `PushProcessor._process_item` reconhece a
`IntegrityError` pelo nome da constraint (`unique_cpf_global`/
`unique_titular_por_upf`) e a reclassifica antes de responder ao item; o log
é gravado fora da transação que sofreu rollback, senão seria descartado
junto.

**CPF duplicado: create vs. update.** No **create**, um CPF já cadastrado no
servidor é pego antes mesmo de chamar `entity.create()`, pela busca por
identificador natural (Estratégia 1) — vira `DUPLICATA` com
`estrategia=duplicate_rejeitado`, `status=resolvido_auto` (não chega a ser
`regra_negocio_rejeitada`). Isso vale igual para CPF com ou sem máscara: a
busca por identificador natural normaliza o CPF antes de comparar, senão um
CPF formatado diferente do já cadastrado escaparia da Estratégia 1 e só
seria pego mais adiante (mesmo resultado final, estratégia errada no log).
Só no **update** — trocar o CPF de um registro já existente para um CPF
usado por outro — é que a checagem nova desta issue entra em ação, com
`estrategia=regra_negocio_rejeitada`, `status=pendente`.

**Mudança de comportamento na API web:** a unicidade de CPF no cadastro de
UPF (`POST/PATCH /api/v1/upfs/`) passou a ser **global**, no mesmo escopo da
constraint do banco — antes era só "por projeto" (`upf__projeto_id`), o que
deixava passar um CPF já usado por um membro não-titular ou por titular de
UPF em outro projeto, e que acabava batendo na constraint do banco como
`IntegrityError` não tratado. A mensagem de erro também mudou (não cita mais
"neste projeto"). Times de frontend que dependem dessa mensagem devem
revisar.

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
