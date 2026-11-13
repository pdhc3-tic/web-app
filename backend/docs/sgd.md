# SGD — Sistema de Gestão de Demandas

Este documento descreve o backend do SGD: as camadas, a máquina de estados, o contrato de erro, a porta de orçamento, a ordem de lock, a abrangência territorial e o mapa dos requisitos (SGD-RF01…RF32 do `SGD_Requisitos_v1_1.docx`) para o código e os testes. O código fica em `apps/sgd/`.

O saldo não é do SGD. Modelos, motor, limites de gasto, ledger e a tabela completa de locks estão em [`orcamento.md`](orcamento.md).

## Camadas

```
views/ (DRF) → services/ → services/orcamento.py (porta) → apps/sgp/budget (motor)
```

- **Views** (`views/`): autenticação, serialização e o perfil de quem pode chamar a rota. Não decidem regra de negócio.
- **Serviços** (`services/`): toda a regra de negócio. Não importam DRF e levantam só exceções de domínio (`apps/sgd/exceptions.py`) ou `PermissionDenied`.
- **Porta** (`services/orcamento.py`): o único módulo do SGD que importa o motor de saldo.
- **Contexto** (`services/contexto.py`): o único módulo que conhece o caminho até estado, território, cadeia do Plano de Trabalho e rubricas previstas no SGP.

`tests/test_arquitetura_sgd.py` lê os imports com AST e quebra se:
- algum arquivo do SGD fora da porta (tirando testes e migrations) importar `apps.sgp.budget.{services,models,limites}`;
- `services/` importar DRF;
- `balance.py` ler o saldo do `AuditLog` (ele só escreve nele).

## Máquina de estados

| Status | Grupo |
|---|---|
| `rascunho`, `devolvida` | Editáveis (`STATUS_EDITAVEIS`) |
| `submetida`, `pre_autorizada`, `autorizada`, `em_atendimento` | Em andamento |
| `concluida`, `recusada`, `cancelada` | Terminais (`STATUS_TERMINAIS`) |

As transições ficam na tabela `TRANSICOES` (`services/workflow.py`). `executar_transicao` é o único lugar que aplica uma linha dela.

| De | Para | Rota (`/api/v1/sgd/demandas/{id}/…`) | Quem | Origem | Efeito no saldo | Justificativa |
|---|---|---|---|---|---|---|
| `rascunho`, `devolvida` | `submetida` | `submeter/` | Solicitante (dono) | usuário | **Reservar** | — |
| `submetida` | `pre_autorizada` | `pre-autorizar/` | `articulador-estadual` do estado da demanda | usuário | Manter | — |
| `submetida` | `devolvida` | `devolver/` | `articulador-estadual` do estado da demanda | usuário | Manter (a reserva fica) | Obrigatória |
| `pre_autorizada` | `autorizada` | `autorizar/` | `ugp` | usuário | **Ajustar** ao valor autorizado; excedente opcional (RF16) | — |
| `pre_autorizada` | `recusada` | `recusar/` | `ugp` | usuário | **Liberar** | Obrigatória |
| `autorizada` | `em_atendimento` | `atender/` | `fgd` | usuário | Manter | — |
| `autorizada` | `em_atendimento` | importação do Arlo | — | arlo | Manter | — |
| `em_atendimento` | `concluida` | `concluir/` | `fgd` | usuário | **Executar** pelo valor pago | — |
| `em_atendimento` | `concluida` | importação do Arlo (última linha paga) | — | arlo | **Executar** | — |
| `rascunho`, `submetida`, `devolvida`, `pre_autorizada` | `cancelada` | `cancelar/` | Solicitante (dono) | usuário | **Liberar** | — |
| `autorizada` | `cancelada` | `cancelar/` | `super-admin`, `ugp` | usuário | **Liberar** | Obrigatória |
| As quatro acima e `autorizada` | `cancelada` | `cancelar_pelo_sistema` | — | sistema | **Liberar**, em lote | — |

### Efeito de cada transição no saldo

As funções ficam em `services/balance.py`, que só chega ao motor pela porta.

- **Reservar** (`reservar_duas_travas`): passa cada solicitação pelas duas travas (`verificar_duas_travas`), somando o consumo anterior da mesma rubrica. A submissão é tudo ou nada (RF13): se uma solicitação for barrada, nada é reservado, e o erro é `SaldoInsuficiente.para_submissao`. A reserva roda num savepoint e confere antes se o solicitante continua ativo.
- **Ajustar** (`ajustar_duas_travas`): leva a reserva ao valor autorizado. Dentro de cada rubrica, as reduções vêm antes dos aumentos. Com `excedente_autorizado`, `remanejamento.cobrir_excedente` cobre o que passa do limite com saldo estadual ou nacional (`origem_allocation`), sem elevar o limite individual.
- **Liberar** (`liberar_duas_travas_em_lote`): devolve a reserva ao limite e ao pool. O excedente que veio de remanejamento não volta para o limite individual.
- **Executar** (`workflow.registrar_pagamento` → `executar_duas_travas`): converte a reserva em executado por `min(pago, autorizado)` e devolve a diferença ao limite e ao pool. É a mesma política na conclusão pela FGD e na importação do Arlo:
  - pago acima do autorizado gera um `GlosaRisk` `PAGO_ACIMA_AUTORIZADO`, com o excedente como `valor_exposto`;
  - solicitação já paga é recusada com `BUSINESS_RULE`;
  - se a atividade já foi concluída sem evidência, a conclusão da demanda gera um `GlosaRisk` `DEMANDA_SEM_EVIDENCIA`. O caso inverso, a atividade fechando depois, é tratado em `registrar_riscos_da_atividade_sem_evidencia`.
- **Manter**: não toca no saldo e trava só a `Demand`.

### `executar_transicao`, passo a passo

1. Encontra a linha de `TRANSICOES` para o status atual e o destino. Sem linha, `INVALID_TRANSITION`.
2. Confere o perfil (`_exigir_perfil`) e a regra extra da linha, como `exigir_pode_decidir_articulador`.
3. Exige a justificativa quando a linha pede. Sem ela, `JUSTIFICATION_REQUIRED`.
4. Aplica o efeito no saldo. Essa etapa trava limites e pools.
5. Trava a `Demand` e relê o status e as solicitações. Se algo mudou, recusa com `INVALID_TRANSITION`.
6. Roda `conferir_sob_lock(demand)`, quando quem chama passou essa função: a regra que depende de dados que outra requisição pode mudar até ali. A submissão passa `demand_request.exigir_regras_de_submissao`, que também roda antes do saldo, para o erro comum sair sem travar nada, e de novo aqui, porque um anexo pode ser removido enquanto a submissão espera o lock.
7. Grava a demanda, a auditoria, as `DemandRequest`, a etapa (`ApprovalStep`) e a notificação.

### Cancelamento pelo sistema

`cancelar_pelo_sistema` libera em lote o saldo de todas as demandas e só então trava cada `Demand`, em ordem de pk. Ele tem dois chamadores:

- **Atividade cancelada ou não realizada** (`signals/activity.py` → `tasks.cancelar_demandas_da_atividade`): cancela as demandas não atendidas (RF10). `em_atendimento` fica de fora, porque a FGD já está atendendo. Se uma demanda mudar no meio, a task é repetida até 3 vezes. A partir daí, a atividade também não aceita demanda nova (`ACTIVITY_STATUS_BLOQUEIAM_NOVA_DEMANDA`).
- **Desativação de usuário** (`services/desativacao.py`): cancela só as demandas que o solicitante ainda poderia cancelar, sem as autorizadas.

## Contrato de erro

Os serviços não conhecem HTTP. `setup/exceptions.custom_exception_handler` devolve todo `ErroDeDominio` como **400**, com `exc.como_dict()`, e desfaz a transação (`set_rollback`).

| Classe | `code` | Campo padrão |
|---|---|---|
| `RegraDeNegocio` | `BUSINESS_RULE` | — |
| `TransicaoInvalida` | `INVALID_TRANSITION` | `status` |
| `JustificativaObrigatoria` | `JUSTIFICATION_REQUIRED` | `justificativa` |
| `SaldoInsuficiente` | `INSUFFICIENT_BALANCE` | — |

O corpo de `como_dict` tem três formas. Em todas, `code` vem por último, para o front não ler o código como a primeira mensagem do campo:

```json
{"status": ["A demanda mudou de status."], "code": "INVALID_TRANSITION"}
{"campo_a": ["…"], "campo_b": ["…"], "code": "BUSINESS_RULE"}
{"code": "BUSINESS_RULE", "detail": "…"}
```

A primeira é o erro de um campo, a segunda é a que usa `erros`, e a terceira não tem campo.

### `INSUFFICIENT_BALANCE`

```json
{
  "code": "INSUFFICIENT_BALANCE",
  "trava": "individual",
  "rubrica": "alimentacao",
  "disponivel": "500.00",
  "solicitado": "1500.00",
  "acao_sugerida": "solicitar_recurso_extra",
  "valor_faltante": "1000.00",
  "detail": "Limite individual insuficiente.",
  "solicitacao_id": 42,
  "solicitacoes_bloqueadas": {
    "42": {"code": "INSUFFICIENT_BALANCE", "trava": "individual", "...": "mesmos campos, sem solicitacao_id"}
  }
}
```

- `trava`: `individual` (limite de gasto do solicitante) ou `territorial` (pool).
- `acao_sugerida`: `solicitar_recurso_extra` na trava individual e `acionar_articulador` na territorial.
- `disponivel` e `solicitado`: valores da solicitação barrada, como texto com duas casas.
- `valor_faltante`: só na trava individual da submissão. É o que falta na rubrica inteira, o mesmo valor que o pedido de recurso extra registraria sem `valor_solicitado` (`recurso_extra.deficit_individual`). Nos outros casos, `null`.
- `solicitacao_id` e `solicitacoes_bloqueadas`: na submissão. O primeiro bloqueio vai no topo, e todos aparecem no mapa, chaveados pelo id da solicitação.

### Outros status

- **403:** `PermissionDenied` do Django, que os serviços levantam para perfil ou escopo errado.
- **`SEM_TERRITORIO`** do motor: a porta transforma em `PermissionDenied` em `resolver_nivel_do_usuario` e em `BUSINESS_RULE` quando a decisão é em nome do solicitante (`pelo_solicitante`).
- **429:** `THROTTLED` com `retry_after`.

Testes: `tests/test_exceptions_sgd.py`.

## Porta de orçamento (`services/orcamento.py`)

A porta localiza o pool pelo nível da demanda e pela rubrica, chama o motor e devolve os erros dele como exceções do SGD: `SaldoInsuficienteError` vira `SaldoInsuficiente`, e erros de validação do motor viram `RegraDeNegocio`. A Meta não entra no saldo.

| Grupo | Funções |
|---|---|
| Pool | `localizar_pool`, `consultar_pool`, `reservar_pool`, `ajustar_pool`, `liberar_pool`, `executar_pool`, `pool_da_reserva`, `saldo_do_pool`, `total_reservado`, `travar_pools`, `travar_pools_das_reservas`, `remanejar` |
| Limite individual | `limite_efetivo`, `saldo_do_limite`, `limite_da_solicitacao`, `travar_limite_da_reserva`, `travar_limites_do_lote`, `registrar_movimento_do_limite`, `exigir_limite_dentro_do_pool`, `elevar_limite` |
| Nível e mensagens | `resolver_nivel_do_usuario`, `pelo_solicitante`, `bloqueio_territorial`, `mensagem_territorial`, `painel_orcamento_para_usuario` |
| Semáforo (reexportado do motor) | `limiares_semaforo`, `faixa_semaforo`, `percentual_comprometido`, `LimiaresSemaforo` |

As operações de saldo rodam com visão total da RLS (`rls.com_visao_total`), porque o motor age em nome de outra pessoa. Testes: `tests/test_orcamento_porta.py`.

## Ordem canônica de lock

Toda transação que trava saldo segue a mesma ordem:

1. Linha do `User` solicitante (`FOR NO KEY UPDATE`), quando a operação depende de ele estar ativo.
2. `BudgetIncreaseRequest`, quando há pedido de recurso extra.
3. **Rubrica a rubrica, em `rubrica_id` crescente: primeiro o limite individual (`SpendingLimit`) e depois o pool (`BudgetPool`)**, cada grupo em pk crescente.
4. `Demand`.
5. `DemandRequest`.

Dentro de uma rubrica, nenhuma transação trava um limite depois de um pool. No código:

- `workflow._solicitacoes` ordena por `rubrica_id, pk`.
- `balance.na_ordem_de_lock` trava, ao entrar em cada rubrica, todas as linhas de limite dela e, quando pedido, os pools das reservas e a origem do excedente.
- `balance.liberar_duas_travas_em_lote` faz o mesmo no cancelamento em lote.
- Com JOIN na query, o lock usa `select_for_update(of=("self",))`, para não travar junto a linha do usuário.

A tabela com o que cada caminho trava (submissão, decisões, Arlo, cancelamento em lote, desativação, recurso extra) está em [`orcamento.md` → Ordem de lock](orcamento.md#ordem-de-lock).

Testes:
- `tests/test_workflow_concorrencia.py`, que intercala transações reais;
- `tests/test_demand_balance_concurrency.py`;
- `tests/test_limite_por_periodo.py::test_na_ordem_de_lock_trava_rubrica_a_rubrica`;
- `tests/concorrencia.py`, que traz os helpers `intercalar` e `esperar_alguem_bloqueado`.

## Abrangência territorial

O estado e o território da demanda são os **do solicitante**, gravados na criação em `Demand.estado_sigla` e `Demand.territorio` e **congelados** (Issue #352). Se a lotação do usuário mudar depois, as demandas já criadas não se movem. O lugar da atividade não entra no critério.

| Nível do solicitante (`resolver_nivel_do_usuario`) | `estado_sigla` | `territorio` |
|---|---|---|
| Territorial | Estado-sede do território (`estados[0]`) | O território |
| Estadual | O estado | `null` |
| Nacional (ex.: Super Admin) | `null` | `null` |

- **Gravação:** `contexto.abrangencia_para_nova_demanda`, chamada por `services/demand.py` na criação.
- **Prévia:** `GET demandas/abrangencia/?activity_id=` devolve, pela mesma regra da criação, o estado, o território e os Articuladores que a demanda de quem chama vai receber, e se a atividade fica fora do estado.
- **Leitura:** fila do Articulador, visibilidade, RLS, notificações e pool leem a abrangência por `contexto`, com `estado_da_demanda` e `nivel_da_demanda`. O pool da reserva é o do nível da demanda.
- **RLS** (migration `0024_rls_demand_por_estado_sigla`): o Articulador vê as demandas cujo `estado_sigla` está entre os estados dos seus territórios. A demanda nacional não fica com nenhum Articulador.
- **Atividade fora do território:** quando a atividade acontece em outro estado, o serializer expõe `atividade_fora_do_territorio`. A busca `GET atividades-elegiveis/` oferece atividades de qualquer território para o vínculo.
- **Riscos de glosa:** o Articulador vê os riscos das demandas que ele vê e os das demandas do seu estado, pelo estado da demanda e não pelo da atividade (`approval.filtro_de_registro_da_demanda`, usado em `GET /sgp/glosa-riscos/`).
- **Migration 0023:** preencheu as demandas antigas pela lotação atual do solicitante.

Testes: `tests/test_abrangencia_territorial.py`, `tests/test_abrangencia_previa.py`, `tests/test_demand_rls.py`, `tests/test_demand_creation_scope.py` e `tests/test_atividades_elegiveis.py`.

## Diárias

A solicitação do tipo diária segue o serviço público federal (Lei 8.112/1990, art. 58; Decreto 5.992/2006), em `services/diarias.py` (Issue #358):
- **Faixa de destino:** `FaixaDestinoDiaria`, com o enquadramento dos municípios como dado. Município sem enquadramento cai em "demais capitais", se for capital, ou em "demais localidades".
- **Valor vigente:** `TabelaDiaria` por faixa, categoria e vigência. Editar um valor cria uma nova vigência, com `AuditLog`, e `origem` diz se o valor é o federal ou um valor próprio da FGD.
- **Contagem:** uma diária por pernoite, meia no dia do retorno, meia no deslocamento sem pernoite e meia por dia de hospedagem custeada por outro meio. Cada regra é um parâmetro do Core, assim como o adicional de embarque e desembarque.
- **Congelamento:** a validação grava em `campos_json` a faixa, o id da tabela, o valor por diária e a quantidade. Alterar a tabela não muda as solicitações já criadas.

Rotas: `config/diarias/simular/` (prévia do formulário), `config/diarias/tabela/`, `config/diarias/faixas/` e `config/diarias/parametros/`. Testes: `tests/test_simular_diarias.py` e `tests/test_tabela_diarias.py`.

## Semáforo

O semáforo do saldo usa os limiares `budget_alert_yellow_pct` (amarelo, 70 por padrão) e `budget_alert_red_pct` (vermelho, 90 por padrão) do `SystemConfig`. Eles são semeados pela migration `core/0021` e ajustáveis sem deploy.

O SGD os lê pela porta (`limiares_semaforo`, `faixa_semaforo`) na consulta de saldo (`semaforo_atual` e `semaforo_apos`), no painel e na prévia da decisão. O detalhe está em [`orcamento.md`](orcamento.md#alertas).

## Mapa RF → módulo → teste

Requisitos do `SGD_Requisitos_v1_1.docx`. Caminhos relativos a `apps/sgd/`. Todos os RFs têm parte no backend; a coluna "Issue" traz a issue de backend e, quando houver, a de tela.

| RF | Requisito | Módulo / rota | Testes (`tests/`) | Issue |
|---|---|---|---|---|
| RF01 | Demanda vinculada a uma Atividade de Campo | `services/demand.py`, `POST demandas/`, `GET atividades-elegiveis/` | `test_demand_creation.py`, `test_demand_creation_scope.py`, `test_atividades_elegiveis.py` | #289, #294, #419 |
| RF02 | Herança somente leitura da atividade e da cadeia Ação → Submeta → Meta → Indicador | `services/contexto.py`, `serializers/demand.py` | `test_contexto.py`, `test_demand_contexto_plano_trabalho.py` | #355, #294 |
| RF03 | Criar a atividade Planejada pelo formulário da demanda | `services/demand.py` (`apps.sgp.services.activity.criar_planejada`) | `test_demand_creation_scope.py` | #352, #361 |
| RF04 | Várias solicitações por demanda, com formulário por tipo | `models/tipo_solicitacao.py`, `services/demand_request.py`, `services/diarias.py`, `config/tipos-solicitacao/`, `config/diarias/` | `test_tipo_solicitacao.py`, `test_demand_campos_json_validation.py`, `test_simular_diarias.py`, `test_tabela_diarias.py` | #357, #358, #295, #365 |
| RF05 | Rubrica automática pelo tipo, por mapeamento configurável | `services/tipos_solicitacao.py`, `config/tipo-rubrica/` | `test_tipo_rubrica_mapping.py`, `test_tipo_solicitacao.py` | #312, #357 |
| RF06 | Salvar como rascunho | `services/demand.py` | `test_demand_creation.py` | #289 |
| RF07 | Editar em Rascunho ou Devolvida | `services/demand.py`, `services/demand_request.py` | `test_demand_balance_service.py`, `test_workflow_concorrencia.py` | #289, #296 |
| RF08 | Anexar documentos, inclusive nos campos de anexo do formulário | `views/demand_document.py`, `services/demand_document.py`, `services/anexos.py` | `test_demand_document_permissions.py`, `test_anexos_campos.py` | #289, #419 |
| RF09 | Cancelar a própria demanda antes de autorizada | `services/workflow.py` (`cancelar/`) | `test_demand_cancel.py`, `test_demand_cancelar_autorizada.py` | #291, #337 |
| RF10 | Bloquear e cancelar demandas de atividade cancelada ou não realizada | `signals/activity.py`, `tasks.py`, `workflow.cancelar_pelo_sistema` | `test_activity_cancel_signal.py`, `test_activity_adiada_signal.py` | #291 |
| RF11 | Duas travas por rubrica antes de aceitar a submissão, em transação atômica | `services/balance.py` (`verificar_duas_travas`) | `test_demand_balance_service.py`, `test_demand_balance_concurrency.py` | #290 |
| RF12 | Mensagem de bloqueio com a trava, o disponível e o solicitado | `exceptions.py` (`SaldoInsuficiente`) | `test_exceptions_sgd.py` | #349, #359 |
| RF13 | Reservar na submissão e ajustar quando o autorizado diverge | `balance.reservar_duas_travas`, `balance.ajustar_duas_travas` | `test_demand_balance_service.py`, `test_workflow_transicoes.py` | #290, #348 |
| RF14 | Liberar na recusa, no cancelamento e na não realização | `balance.liberar_duas_travas_em_lote` | `test_demand_cancel.py`, `test_activity_cancel_signal.py`, `test_desativacao_usuario.py` | #290, #350 |
| RF15 | Executar pelo valor pago, liberando a diferença | `workflow.registrar_pagamento`, `balance.executar_duas_travas` | `test_registro_pagamento.py`, `test_glosa_sem_evidencia.py` | #351, #360 |
| RF16 | UGP autoriza com excedente de saldo estadual ou nacional, com justificativa | `workflow._ajustar`, `services/remanejamento.py` (`cobrir_excedente`) | `test_excedente_pontual.py`, `test_approval_rbac.py` | #354, #363 |
| RF17 | Saldo disponível no formulário, antes da submissão | `GET saldo/` (`views/saldo.py`) | `test_saldo_view.py`, `test_saldo_performance.py` | #290, #295 |
| RF18 | Articulador vê as Submetidas do seu estado | `services/approval.py` (`demand_visibility_scope`), RLS 0004/0024 | `test_demand_rls.py`, `test_demand_aguardando_acao.py` | #291, #352 |
| RF19 | Articulador pré-autoriza ou devolve, com justificativa na devolução | `workflow.py` (`pre-autorizar/`, `devolver/`), `approval.exigir_pode_decidir_articulador` | `test_approval_rbac.py`, `test_workflow_transicoes.py` | #291, #296 |
| RF20 | UGP vê as Pré-autorizadas de todos os territórios | `services/approval.py` | `test_approval_rbac.py`, `test_demand_aguardando_acao.py` | #291, #296 |
| RF21 | UGP autoriza, ajusta o valor ou recusa com justificativa | `workflow.py` (`autorizar/`, `recusar/`) | `test_approval_rbac.py`, `test_workflow_transicoes.py` | #291, #296 |
| RF22 | Impacto da decisão no saldo, com a mudança de faixa do semáforo | `services/approval.py` (`preview-decisao/`) | `test_approval_rbac.py`, `test_excedente_pontual.py` | #291, #296 |
| RF23 | Alerta de rubrica fora das previstas da Ação | `approval.alerta_rubrica_fora_do_previsto`, `contexto.rubricas_previstas` | `test_contexto.py`, `test_demand_notifications.py` | #291 |
| RF24 | FGD registra o atendimento, o valor pago e os comprovantes do Arlo | `workflow.py` (`atender/`, `concluir/`), `services/arlo_import.py` | `test_registro_pagamento.py`, `test_arlo_integration.py` | #292, #360 |
| RF25 | Alerta de demanda parada há 5 dias úteis | `tasks.check_demand_inactivity_alert`, `services/business_days.py` | `test_demand_inactivity_task.py`, `test_alertas_sgd.py` | #291, #315 |
| RF26 | Filtros combináveis da listagem | `filters.py`, `services/consulta.py` | `test_demand_listagem_filtros.py`, `test_demand_listagem_performance.py` | #293, #296 |
| RF27 | Histórico com etapas, responsáveis, justificativas e horários | `historico/`, `auditoria/` (`services/auditoria.py`) | `test_historico_paginacao.py`, `test_demand_auditoria.py` | #293, #296 |
| RF28 | Painel de execução por rubrica | `GET painel/rubricas/` (`services/consulta.py`) | `test_demand_consulta.py`, `test_painel_rubricas_performance.py` | #293, #297 |
| RF29 | Custo por atividade e por entrega do Plano de Trabalho | `GET relatorios/custo-por-atividade/` | `test_demand_consulta.py` | #293, #297 |
| RF30 | Exportação CSV/Excel com os filtros aplicados | `demandas/exportar/` (`consulta.linhas_exportacao`) | `test_demand_consulta.py` | #293 |
| RF31 | Exportação das autorizadas no formato do Arlo | `services/arlo_export.py`, `services/arlo_mapping.py`, `arlo/exportar/` | `test_arlo_integration.py`, `test_arlo_field_mapping.py` | #292, #298 |
| RF32 | Importação do retorno do Arlo, com relatório de erros por linha | `services/arlo_import.py`, `tasks.process_arlo_import` | `test_arlo_integration.py`, `test_registro_pagamento.py`, `test_workflow_concorrencia.py` | #292, #298 |

## Pendências conhecidas

- **Pré-autorização de demanda nacional.** `exigir_pode_decidir_articulador` diz que só o Super Admin decide uma demanda nacional. Só que a linha da pré-autorização exige o perfil `articulador-estadual`, conferido antes (`workflow._exigir_perfil`), e o Super Admin sem esse perfil recebe 403. Hoje, nenhum perfil pré-autoriza ou devolve uma demanda nacional, e nenhum teste cobre o caso. Precisa de issue própria.
