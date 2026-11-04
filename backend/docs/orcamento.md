# Orçamento — modelo, motor de saldo e contrato com o SGD

Este documento descreve o controle financeiro do SGP: os modelos, o motor de saldo, os limites de gasto, o ledger, a ordem de lock e os endpoints. O código fica em `apps/sgp/budget/`, ainda no app `sgp`.

## Modelos

- `BudgetRubrica`: catálogo das rubricas.
- `BudgetPool`: saldo autônomo de uma rubrica num nível (`nacional`, `estadual` ou `territorial`), com `valor_alocado`, `valor_comprometido` e `valor_executado`. Há um pool por rubrica, nível, estado e território. A Meta não faz parte do saldo.
- `SpendingLimit`: limite de gasto por rubrica e período, que pode ser o padrão de um perfil ou a linha individual de um usuário.
- `BudgetTransaction`: ledger único de pools e limites, só por INSERT.
- `BudgetTransfer`: remanejamento entre pools da mesma rubrica, só por INSERT.
- `BudgetIncreaseRequest`: pedido de recurso extra.

## As duas travas

Uma demanda só reserva se passar nas duas travas: primeiro o limite individual do solicitante, depois o pool territorial. O pool é localizado pelo nível do solicitante e pela rubrica.

## Limites de gasto

| Tipo de registro | Campos | Observação |
|---|---|---|
| Padrão por perfil | `perfil`, `rubrica`, `valor_limite` | Vale até ser alterado (`periodo_fim` em aberto) |
| Linha individual herdada | `user`, `rubrica`, `herdado=true` | Nasce do padrão na primeira reserva do período |
| Sobrescrita individual | `user`, `rubrica`, `justificativa` | Justificativa obrigatória |

- **Limite efetivo:** a linha individual vigente; sem ela, o que o padrão do perfil geraria. A consulta não grava nada.
- **Mais de um perfil:** vale o maior padrão.
- **Sem limite nem padrão:** a demanda é bloqueada, com orientação para pedir recurso extra.
- **Período:** vem de `budget_limit_period` (`mensal`, `trimestral`, `semestral` ou `vigencia`). A linha existente não muda se o parâmetro for alterado no meio do período.
- **Virada do período:** com `budget_limit_carry_over`, a linha nova soma o saldo positivo da anterior.
- **Reserva presa à linha:** ajuste, liberação e execução usam a linha em que a reserva foi feita, encontrada pelo ledger, mesmo depois da virada. Uma reserva nova usa o período novo.
- **Alteração do padrão:** se já estiver em uso, vale a partir do período seguinte; sem uso, o próprio registro é corrigido.
- **Redução:** nunca abaixo do já comprometido e executado.
- **Sobrealocação:** com `budget_overallocation_allowed` desligado, criar ou alterar um limite é recusado se a soma do território passar do pool. O erro traz `soma_limites` e `valor_pool`.
- **Recurso extra aprovado:** eleva a linha do período vigente na data da decisão, que vira sobrescrita. `periodo_aplicacao` é texto livre e não define o período.

## Ledger

`BudgetTransaction` aponta para um pool ou para um limite, nunca para os dois.

| Campo | Conteúdo |
|---|---|
| `tipo` | `reserva`, `ajuste`, `execucao`, `liberacao`, `remanejamento` ou `aumento_limite` |
| `valor` | Com sinal em `ajuste`, `remanejamento` e `aumento_limite` |
| `saldo_anterior`, `saldo_posterior` | Saldo disponível (alocado ou limite, menos comprometido e executado) antes e depois |
| `demand_request_id` | Solicitação: é a chave de idempotência da reserva |
| `demanda_id` | Demanda |
| `activity` | Liga o executado à Meta, pela cadeia Atividade → Ação → Meta |
| `ip` | IP da requisição, quando houver |

Um trigger recusa `UPDATE` e `DELETE` em `sgp_budgettransaction` e `sgp_budgettransfer`: correção é sempre um novo lançamento. Por isso `seed_demo --reset` esvazia as duas tabelas com `TRUNCATE`, que exige `DB_USER=postgres`.

## O motor (`apps.sgp.budget.services`)

```python
def verificar_saldo(*, rubrica, nivel, territorio=None, estado=None, valor) -> SaldoCheck
def saldo_para_consulta(*, rubrica_slug, nivel, estado_sigla, territorio, valor, consumo_previo=0) -> SaldoCheck
def reservar(*, pool, valor, demand_request_id, usuario, justificativa="", demanda_id=None, activity_id=None) -> BudgetTransaction
def ajustar_reserva(*, demand_request_id, novo_valor, usuario, justificativa="") -> BudgetTransaction
def executar(*, demand_request_id, usuario, valor_executado=None) -> BudgetTransaction
def liberar(*, demand_request_id, usuario, motivo) -> BudgetTransaction
def remanejar(*, origem, destino, valor, usuario, justificativa) -> tuple[BudgetTransaction, BudgetTransaction]
```

No SGD, só a porta `apps.sgd.services.orcamento` importa o motor e `apps.sgp.budget.limites`. Ela devolve os erros do motor como exceções de domínio (`apps.sgd.exceptions`).

### Estado da demanda → chamada esperada

| Estado da demanda no SGD | Chamada |
|---|---|
| Formulário sendo preenchido (antes de criar) | `GET /api/v1/sgd/saldo/` ou `GET /api/v1/sgp/orcamento/saldo/` |
| Submissão | `reservar(pool=..., valor=..., demand_request_id=..., demanda_id=..., activity_id=..., usuario=...)` |
| Decisão final com valor diferente do estimado | `ajustar_reserva(demand_request_id=..., novo_valor=..., usuario=...)` |
| Concluída pela FGD ou pelo retorno do Arlo | `executar(demand_request_id=..., usuario=..., valor_executado=<menor entre o pago e o autorizado>)`; o que for pago acima do autorizado vira `GlosaRisk` (`apps.sgd.services.workflow.registrar_pagamento`) |
| Recusada ou cancelada | `liberar(demand_request_id=..., usuario=..., motivo=...)` |

### Invariantes

- Todas as operações rodam em `transaction.atomic()`, com `select_for_update()` no pool.
- **Idempotentes por `demand_request_id`:** chamar `reservar`, `executar` ou `liberar` duas vezes não duplica o efeito.
- `executar` e `liberar` localizam o pool e o valor pela reserva original, que precisa existir.
- `liberar` devolve o saldo ao mesmo pool da reserva, nunca ao nível acima.
- `reservar` levanta `SaldoInsuficienteError`, uma exceção Python simples, se o valor passar do saldo.
- O motor não importa `apps.sgd`.

## RLS

`sgp_budgetpool`, `sgp_spendinglimit` e `sgp_budgettransaction` têm RLS. O usuário de runtime (`app_user`) não é dono das tabelas, e o papel vem das variáveis de sessão definidas por `SessionContextMiddleware`.

| Perfil | Pools | Limites |
|---|---|---|
| UGP, FGD, Super Admin | Todos | Todos |
| Articulador Estadual | Nacional, e estaduais e territoriais do próprio estado | Do próprio estado |
| ADT/ACR e demais | Territorial do próprio território | O próprio |

- Todo usuário lê os padrões por perfil.
- `sgp_budgettransaction` segue o pool ou o limite referenciado.
- A FGD entra entre os perfis globais porque conclui as demandas.
- O Articulador vê o nacional porque o painel o mostra a ele.

**O RLS protege o que as views leem. A autorização das operações fica nos serviços.** O motor age em nome de outra pessoa, e por isso `apps.sgp.budget.rls.visao_total` define o papel `super-admin` durante a operação e o restaura no fim. Usam a visão total as operações de saldo de `apps.sgd.services.balance`, a prévia da decisão, `verificar_saldos` e a task `check_budget_threshold_alert`. Fora de uma requisição, sem isso, as tabelas aparecem vazias e sem erro nenhum.

## Ordem de lock

Toda transação que trava mais de uma destas linhas segue esta ordem:

1. `BudgetIncreaseRequest` (pedido de recurso extra).
2. Saldo, rubrica por rubrica em ordem de `rubrica_id`: **primeiro todas as linhas de `SpendingLimit` da rubrica** e depois os `BudgetPool` da rubrica, cada grupo em ordem crescente de pk.
3. `Demand`.
4. `DemandRequest`.

Dentro de uma rubrica, nenhuma transação trava um limite depois de um pool. Depois da virada do período, uma demanda pode ter reservas em duas linhas de limite: travá-las uma a uma, intercaladas com o pool, abriria um ciclo com o cancelamento em lote. Por isso `balance.na_ordem_de_lock` trava, ao entrar em cada rubrica, as linhas das reservas e as do período vigente de todos os solicitantes envolvidos.

O `FOR UPDATE` trava só a linha da tabela da ordem: com JOIN na query (`select_related` ou um `ordering` por FK), usar `select_for_update(of=("self",))`. Sem isso, a linha do usuário fica travada junto, e o commit de outra transação que gravou uma notificação, auditoria ou etapa para ele espera esse lock na checagem da FK, fechando um ciclo com a `Demand`.

As transições de status passam por `apps.sgd.services.workflow.executar_transicao` (o cancelamento automático, pela variante em lote `cancelar_pelo_sistema`): primeiro o efeito no saldo, depois a `Demand` travada com o status relido (e as solicitações conferidas, quando o saldo partiu delas) e, por último, a gravação das `DemandRequest`. Se a demanda mudou nesse meio, a transição é recusada com `INVALID_TRANSITION`.

| Caminho | O que trava |
|---|---|
| Submissão | Por rubrica: linhas de limite (a do período é criada aqui, se faltar) → pool → `Demand` → `DemandRequest` |
| Autorização, recusa, cancelamento pelo solicitante ou pela UGP/Super Admin, conclusão pela FGD | Por rubrica: linhas de limite → pool → `Demand` → `DemandRequest` (estado da reserva, `valor_autorizado` e `valor_pago`, em ordem de pk) |
| Autorização com excedente (remanejamento emergencial) | Por rubrica: linhas de limite → pools (origem e o da reserva, em ordem de pk) → depois segue como a autorização |
| Pré-autorização, devolução, início do atendimento | Só a `Demand` |
| Importação do Arlo, por linha | Limite → pool da solicitação paga → `Demand` (status relido) → `DemandRequest`. Cada linha numa transação própria |
| Cancelamento automático por atividade (`tasks.py`) | `liberar_duas_travas_em_lote`: por rubrica, todas as linhas de limite e depois todos os pools; só então as `Demand`, em ordem de pk, e por fim as `DemandRequest`. Se uma demanda mudou, a transação volta e a task é repetida (até 3 vezes) |
| Edição da demanda; inclusão de solicitação | Só a `Demand` |
| Edição e remoção de solicitação | Limite → pool (se há reserva) → `Demand` → `DemandRequest`; a edição relê a reserva já com o limite travado |
| Decisão de recurso extra | Pedido → linha de limite do período → pools (territorial e origem, em ordem de pk) → `Demand` → todas as `DemandRequest` da demanda |
| Parecer, devolução, submissão e edição do pedido | Só o pedido |
| Criação do pedido | A `Demand`, e depois o pedido novo, que nenhuma outra transação enxerga antes do commit |
| Cadastro de limite (`/sgp/orcamento/limites/`, alias e Django Admin) | Só o limite |
| `remanejar`, `atualizar_valor_alocado` | Pools em ordem crescente de pk |

## Reconciliação

```
python manage.py verificar_saldos
```

Para cada `BudgetPool` e cada linha individual de `SpendingLimit`, confere:

- `valor_comprometido` contra `reserva + ajuste − execucao − liberacao` do ledger;
- `valor_executado` contra a soma de `execucao`;
- o saldo disponível contra o `saldo_posterior` da última transação.

No SGD, confere também o comprometido dos limites contra as reservas ativas das solicitações, por solicitante e rubrica, e os totais de cada demanda contra a soma das solicitações. Sai com código diferente de 0 (via `CommandError`) e lista as divergências encontradas.

## Endpoints HTTP

### `GET /api/v1/sgp/orcamento/saldo/?rubrica={slug}&valor={decimal}`

Resolve o nível pelo perfil do usuário: UGP/Super Admin → nacional, Articulador Estadual → seu estado, ADT/ACR → seu território. `meta` é ignorado, com aviso no log.

```json
{
  "disponivel": true,
  "saldo": "12500.00",
  "nivel": "territorial",
  "estado": null,
  "territorio": {"id": 7, "nome": "Território Central"},
  "pool_id": 42,
  "allocation_id": 42,
  "motivo_bloqueio": null
}
```

`allocation_id` repete `pool_id` enquanto o front migra. Rubrica inexistente ou inativa retorna `400`. Saldo zero ou insuficiente retorna `disponivel: false`: o bloqueio é de quem chama.

### `POST /api/v1/sgp/orcamento/pools/`, `PATCH`/`DELETE .../pools/{id}/` e `GET .../pools/{id}/transacoes/`

Distribuição do orçamento. Só o nível nacional não tem pai. Estadual e territorial são limitados pelo saldo do nível acima, e uma `reserva_ugp` não recebe filhos. Pool repetido retorna `400`. UGP e Super Admin alteram qualquer nível; o Articulador, só os territórios do próprio estado.

As rotas antigas seguem como alias enquanto o front migra:

| Alias | Rota nova |
|---|---|
| `POST /sgp/metas/{id}/orcamento/alocacoes/` | `POST /sgp/orcamento/pools/` (a Meta só é conferida, `404` se não existir) |
| `PATCH`/`DELETE /sgp/orcamento/alocacoes/{id}/` | `PATCH`/`DELETE /sgp/orcamento/pools/{id}/` |
| `GET /sgp/orcamento/alocacoes/{id}/transacoes/` | `GET /sgp/orcamento/pools/{id}/transacoes/` |
| `GET /sgp/metas/{id}/orcamento/` | Sem substituta direta: a resposta é a mesma para qualquer Meta. Use o painel |

### `POST /api/v1/sgp/orcamento/remanejamentos/`

Só UGP e Super Admin, com justificativa obrigatória. Move `valor_alocado` entre dois pools da mesma rubrica e gera duas transações `remanejamento`.

```json
{"origem_allocation": 12, "destino_allocation": 45, "valor": "3000.00", "justificativa": "..."}
```

Os campos mantêm o nome e recebem o id do pool. Sem saldo na origem, retorna `400` com o contrato `INSUFFICIENT_BALANCE`:

```json
{
  "valor": ["Saldo insuficiente na origem: R$ 100.00 disponível."],
  "code": "INSUFFICIENT_BALANCE",
  "trava": "origem",
  "rubrica": "diarias",
  "disponivel": "100.00",
  "solicitado": "3000.00",
  "detail": "Saldo insuficiente na origem: R$ 100.00 disponível."
}
```

### `GET`/`POST /api/v1/sgp/orcamento/limites/` e `PATCH .../limites/{id}/`

Só Super Admin e UGP. A lista traz os limites vigentes em `?data=` (hoje, se omitido), com os filtros `?escopo=`, `?rubrica=` (slug), `?user=` e `?perfil=` (slug).

```json
{"escopo": "perfil", "perfil": 2, "rubrica": 1, "valor_limite": "1000.00"}
{"escopo": "individual", "user": 9, "rubrica": 1, "valor_limite": "2500.00", "justificativa": "Mutirão."}
```

O `PATCH` recebe `valor_limite` e `justificativa`, obrigatória quando o valor muda. `/sgd/limites-individuais/` segue como alias, com o contrato antigo, para as linhas individuais do período vigente.

### `GET /api/v1/sgp/rubricas/?ativo=`

Catálogo de `BudgetRubrica`, sem paginação, ordenado por `nome`, para qualquer usuário autenticado. Sem o parâmetro, devolve também as inativas. Valor que não seja booleano retorna `400`.

### `GET /api/v1/sgp/orcamento/painel/?rubrica=&estado=&territorio=&nivel=&meta=`

Matriz Rubrica × Nível: uma linha por pool no escopo do perfil, com o `id` que a origem do excedente e a do recurso extra enviam.

| Perfil | Sem filtro | Drill-down |
|---|---|---|
| `super-admin`, `ugp` | Todos os pools | Qualquer estado ou território |
| `articulador-estadual` | Nacional e os do próprio estado | Só o próprio estado (`403` fora dele) |
| `adt-acr` | Os do próprio território | Só o próprio território; `estado=` retorna `403` |

- `estado` traz o estadual e os territoriais do estado. `territorio` traz o pool dele e vence `estado` se os dois vierem.
- `meta` não recorta o saldo: só acrescenta `valor_executado_meta`, calculado pela cadeia Atividade → Ação → Meta.
- Filtro com id, slug ou sigla inexistente retorna `400`.
- Perfil sem estado ou território vinculado recebe `403` com `code: "SEM_TERRITORIO"`.

```json
[
  {
    "id": 42,
    "rubrica": {"id": 1, "nome": "Diárias", "slug": "diarias"},
    "nivel": "nacional",
    "estado": null,
    "territorio": null,
    "reserva_ugp": false,
    "valor_aprovado": "10000.00",
    "valor_distribuido": "4000.00",
    "valor_comprometido": "1000.00",
    "valor_executado": "500.00",
    "saldo_disponivel": "4500.00",
    "saldo_pool": "8500.00",
    "semaforo": "verde",
    "alerta_80": false,
    "limiares_semaforo": {"amarelo": 70, "vermelho": 90}
  }
]
```

- `saldo_disponivel` é o aprovado menos distribuído, comprometido e executado.
- `saldo_pool` é o alocado menos comprometido e executado: o que o remanejamento aceita sair do pool.
- `semaforo` segue o percentual comprometido sobre o alocado e os limiares `budget_alert_yellow_pct` e `budget_alert_red_pct` do Core (70 e 90 por padrão). `alerta_80` mantém o nome, mas é `true` no mesmo limiar de `vermelho`.
- A task diária `sgp.tasks.check_budget_threshold_alert` notifica UGP e Super Admin sobre todo `BudgetPool` em vermelho, em qualquer nível.

## Painel por rubrica do SGD

`GET /api/v1/sgd/painel/rubricas/` traz por rubrica o solicitado e o autorizado das demandas filtradas e os totais do orçamento no nível do usuário. Traz também os limites de gasto agregados no período vigente (`limite_total`, `limite_comprometido`, `limite_executado` e `limite_disponivel`). Esses totais somam só as linhas individuais já criadas: quem ainda não reservou no período não entra, mesmo tendo limite herdado do perfil.
