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
- **Virada do período:** com `budget_limit_carry_over`, a linha nova soma o saldo positivo da linha que termina na véspera, mesmo sem padrão no perfil, e esse saldo é debitado da linha antiga no ledger. O que for liberado depois na linha antiga fica nela e expira. Quem não teve linha no período anterior não acumula.
- **Reserva presa à linha:** ajuste, liberação e execução usam a linha em que a reserva foi feita, encontrada pelo ledger, mesmo depois da virada. Uma reserva nova usa o período novo.
- **Alteração do padrão:** se já estiver em uso, vale a partir do período seguinte; sem uso, ou com período `vigencia`, o próprio registro é corrigido. Com um valor já agendado, a alteração vale sobre ele. Padrão encerrado não pode ser alterado, e um padrão novo não pode se sobrepor a um agendado.
- **Redução:** não invalida o que já foi autorizado. O comprometido fica como está, e o novo teto vale para as próximas reservas, mesmo com saldo negativo.
- **Sobrealocação:** com `budget_overallocation_allowed` desligado, um aumento de limite (cadastro, Django Admin ou recurso extra) é recusado se a soma do território passar do pool. Na rota de limites, o erro traz `soma_limites` e `valor_pool`. O pool fica travado até o commit, para dois aumentos simultâneos não passarem. Reduzir nunca é recusado. A soma conta só quem reserva no pool do território: o Articulador reserva no estadual e fica de fora. Território sem pool também fica de fora.
- **Sobreposição:** duas linhas individuais do mesmo usuário e rubrica não podem cobrir o mesmo dia. A linha herdada do mesmo período vira sobrescrita, mesmo com o valor igual, e a linha gerada do padrão é encurtada para não cobrir uma sobrescrita de datas próprias.
- **Sobrescrita com acúmulo ligado:** vale exatamente o valor informado, sem somar o saldo anterior.
- **Leitura e reserva:** a FGD lê o orçamento nacional, mas o perfil de leitura não decide de onde sai a reserva. Quem é FGD e ADT reserva no pool do território.
- **Ledger da linha:** a linha criada do padrão abre o ledger com um `aumento_limite` do valor dela, que já inclui o saldo acumulado.
- **Recurso extra aprovado:** eleva a linha do período vigente na data da decisão, que vira sobrescrita. `periodo_aplicacao` é texto livre e não define o período.
- **Django Admin:** altera só linhas individuais, e `herdado` e `territorio` são somente leitura. Mudar o valor exige justificativa, e a linha herdada vira sobrescrita. O padrão por perfil é cadastrado pela rota de limites.

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
| UGP, Super Admin, FGD | Todos | Todos |
| Articulador Estadual | Nacional, e estaduais e territoriais do próprio estado | Do próprio estado |
| ADT/ACR e demais | Territorial do próprio território | O próprio |

- Todo usuário lê os padrões por perfil.
- `sgp_budgettransaction` segue o pool ou o limite referenciado.
- A FGD entra entre os perfis globais porque conclui as demandas.
- O Articulador vê o nacional porque o painel o mostra a ele.

**O RLS protege o que as views leem. A autorização das operações fica nos serviços.** O motor age em nome de outra pessoa, e por isso `apps.sgp.budget.rls.visao_total` define o papel `super-admin` durante a operação e o restaura no fim. Usam a visão total as operações de saldo de `apps.sgd.services.balance`, a prévia da decisão, `verificar_saldos` e a task `check_budget_thresholds`. Fora de uma requisição, sem isso, as tabelas aparecem vazias e sem erro nenhum.

Os agregados também usam visão total: o `valor_distribuido` do nacional e o aprovado da rota da Meta são os mesmos para todo perfil, e o recorte de quais linhas cada um vê fica nos serviços. A rota de pools busca o pool com visão total antes de autorizar, para o pool de outro estado dar `403`, e não `404`.

## Ordem de lock

Toda transação que trava mais de uma destas linhas segue esta ordem:

1. Linha do `User` solicitante, em `FOR NO KEY UPDATE`: a submissão e a desativação a travam antes de tudo, e assim uma não passa pela outra. A edição do cadastro também a trava, mas não toca em saldo depois. Esse modo não barra a checagem de FK de outras transações.
2. `BudgetIncreaseRequest` (pedido de recurso extra).
3. Saldo, rubrica por rubrica em ordem de `rubrica_id`: **primeiro todas as linhas de `SpendingLimit` da rubrica** e depois os `BudgetPool` da rubrica, cada grupo em ordem crescente de pk.
4. `Demand`.
5. `DemandRequest`.

Dentro de uma rubrica, nenhuma transação trava um limite depois de um pool. Depois da virada do período, uma demanda pode ter reservas em duas linhas de limite: travá-las uma a uma, intercaladas com o pool, abriria um ciclo com o cancelamento em lote. Por isso `balance.na_ordem_de_lock` trava, ao entrar em cada rubrica, as linhas das reservas e as do período vigente de todos os solicitantes envolvidos. Na autorização e na conclusão, trava em seguida, em ordem de pk, os pools das reservas e a origem do excedente, antes de mover qualquer solicitação.

O `FOR UPDATE` trava só a linha da tabela da ordem: com JOIN na query (`select_related` ou um `ordering` por FK), usar `select_for_update(of=("self",))`. Sem isso, a linha do usuário fica travada junto, e o commit de outra transação que gravou uma notificação, auditoria ou etapa para ele espera esse lock na checagem da FK, fechando um ciclo com a `Demand`.

As transições de status passam por `apps.sgd.services.workflow.executar_transicao` (o cancelamento automático, pela variante em lote `cancelar_pelo_sistema`): primeiro o efeito no saldo, depois a `Demand` travada com o status relido (e as solicitações conferidas, quando o saldo partiu delas) e, por último, a gravação das `DemandRequest`. Se a demanda mudou nesse meio, a transição é recusada com `INVALID_TRANSITION`.

| Caminho | O que trava |
|---|---|
| Submissão | Linha do solicitante, recusando se ele estiver inativo → por rubrica: linhas de limite (a do período é criada aqui, se faltar) → pool → `Demand` → `DemandRequest` |
| Autorização, recusa, cancelamento pelo solicitante ou pela UGP/Super Admin, conclusão pela FGD | Por rubrica: linhas de limite → pools das reservas, em ordem de pk → `Demand` → `DemandRequest` (estado da reserva, `valor_autorizado` e `valor_pago`, em ordem de pk). Na conclusão, só as solicitações ainda sem pagamento |
| Autorização com excedente (remanejamento emergencial) | Por rubrica: linhas de limite → pools (origem e os das reservas, em ordem de pk) → depois segue como a autorização |
| Pré-autorização, devolução, início do atendimento | Só a `Demand` |
| Importação do Arlo, por linha | Limite → pool da solicitação paga → `Demand` (status relido) → `DemandRequest`. Cada linha numa transação própria. A última linha conclui a demanda sem travar mais saldo, porque já está tudo pago |
| Cancelamento automático por atividade (`tasks.py`) | `liberar_duas_travas_em_lote`: por rubrica, todas as linhas de limite e depois todos os pools; só então as `Demand`, em ordem de pk, e por fim as `DemandRequest`. Se uma demanda mudou, a transação volta e a task é repetida (até 3 vezes) |
| Desativação de usuário (`core.services.usuarios.desativar`) | Grava `ativo` na linha do usuário, sem conflito com a checagem de FK, e segue como o cancelamento em lote, só para demandas não autorizadas. Os outros campos do usuário são gravados por último: trocar o e-mail, coluna única, conflita com essa checagem. Se uma demanda mudou para fora desses status, a transação inteira volta com `INVALID_TRANSITION`, sem repetição automática |
| Edição do cadastro do usuário (`PATCH /users/{id}/`) | Só a linha do usuário. Trocar o e-mail sobe esse lock para `FOR UPDATE`, sem esperar nenhuma linha de saldo depois |
| Edição da demanda; inclusão de solicitação | Só a `Demand` |
| Edição e remoção de solicitação | Limite → pool (se há reserva) → `Demand` → `DemandRequest`; a edição relê a reserva já com o limite travado |
| Decisão de recurso extra | Pedido → linha de limite do período → pools (territorial e origem, em ordem de pk) → `Demand` → todas as `DemandRequest` da demanda. Com a sobrealocação desligada, relê o pool territorial, já travado |
| Parecer, devolução, submissão e edição do pedido | Só o pedido |
| Criação do pedido | A `Demand`, e depois o pedido novo, que nenhuma outra transação enxerga antes do commit |
| Cadastro de limite (`/sgp/orcamento/limites/`, alias e Django Admin) | O limite. Com a sobrealocação desligada, depois os pools territoriais envolvidos, em ordem de pk |
| `remanejar`, `atualizar_valor_alocado` | Pools em ordem crescente de pk |
| Avaliação de alerta (`alertas.py`) | Um alvo por transação, pool ou limite, e depois a linha do alerta. Quem move saldo grava o alerta com o alvo já travado, depois do saldo |

## Reconciliação

```
python manage.py verificar_saldos
```

Para cada `BudgetPool` e cada linha individual de `SpendingLimit`, confere:

- `valor_comprometido` contra `reserva + ajuste − execucao − liberacao` do ledger;
- `valor_executado` contra a soma de `execucao`;
- o saldo disponível contra o `saldo_posterior` da última transação.

No SGD, confere também o comprometido dos limites contra as reservas ativas das solicitações, por solicitante e rubrica, e os totais de cada demanda contra a soma das solicitações. Sai com código diferente de 0 (via `CommandError`) e lista as divergências encontradas.

A tarefa `reconcile_budget_balances` roda a mesma checagem toda noite e notifica o Super Admin quando há divergência.

## Alertas

`BudgetAlert` segue o modelo de dados do SGP (`escopo`, `referencia_id`, `rubrica`, `faixa`, `percentual_atingido`, `alertado_em`, `usuarios_alertados_ids`), mais `tipo` e `resolvido_em`. Cada alvo tem no máximo um alerta aberto por tipo. Os alertas por rubrica, de subexecução e de remanejamento excessivo, usam o pool nacional dela como alvo.

## Endpoints HTTP

### `GET /api/v1/sgp/orcamento/saldo/?rubrica={slug}&valor={decimal}`

Resolve o nível pelo perfil do usuário: UGP/Super Admin/FGD → nacional, Articulador Estadual → seu estado, ADT/ACR → seu território. `meta` é ignorado, com aviso no log.

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

Distribuição do orçamento, a única forma de alterar um pool: no Django Admin ele é só consulta. Só o nível nacional não tem pai. Estadual e territorial são limitados pelo saldo do nível acima, e uma `reserva_ugp` não recebe filhos. Pool repetido retorna `400`. UGP e Super Admin alteram qualquer nível; o Articulador, só os territórios do próprio estado.

As rotas antigas seguem como alias enquanto o front migra:

| Alias | Rota nova |
|---|---|
| `POST /sgp/metas/{id}/orcamento/alocacoes/` | `POST /sgp/orcamento/pools/` (a Meta só é conferida, `404` se não existir) |
| `PATCH`/`DELETE /sgp/orcamento/alocacoes/{id}/` | `PATCH`/`DELETE /sgp/orcamento/pools/{id}/` |
| `GET /sgp/orcamento/alocacoes/{id}/transacoes/` | `GET /sgp/orcamento/pools/{id}/transacoes/` |
| `GET /sgp/metas/{id}/orcamento/` | Sem substituta direta: a resposta é a mesma para qualquer Meta. Use o painel |

### `POST /api/v1/sgp/orcamento/remanejamentos/`

Além dos lançamentos no ledger, grava um `BudgetTransfer`, com motivo, saldos, aprovador e IP, e sem `escopo`.

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
  "valor_faltante": "2900.00",
  "acao_sugerida": "informar_outra_origem",
  "detail": "Saldo insuficiente na origem: R$ 100.00 disponível."
}
```

`trava: "origem"` é um valor a mais em relação às duas travas da submissão: aqui o saldo em questão é o do pool de origem.

### `GET`/`POST /api/v1/sgp/orcamento/limites/` e `PATCH .../limites/{id}/`

Só Super Admin e UGP. O padrão por perfil aceita só os perfis operacionais (ADT/ACR e Articulador Estadual). A lista traz os limites vigentes em `?data=` (hoje, se omitido), com os filtros `?escopo=`, `?rubrica=` (slug), `?user=` e `?perfil=` (slug).

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
| `super-admin`, `ugp`, `fgd` | Todos os pools | Qualquer estado ou território |
| `articulador-estadual` | Nacional e os do próprio estado | Só o próprio estado (`403` fora dele) |
| `adt-acr` | Os do próprio território | Só o próprio território; `estado=` retorna `403` |

- O pool territorial não grava estado: na matriz, `estado` vem do território (o primeiro, se ele cobrir dois), e `territorio.estados` traz todos. Só o nacional tem `estado` nulo.
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
- `sgp.tasks.check_budget_thresholds` grava em `BudgetAlert` a faixa de pools e limites vigentes e notifica a cada nova entrada numa faixa. Roda depois de cada movimentação, só para o alvo movido, e uma vez por dia para todos. O amarelo avisa o responsável só no app; o vermelho avisa também o nível superior e vai por e-mail.
- `sgp.tasks.check_budget_underexecution`, semanal, e `sgp.tasks.reconcile_budget_balances`, às 2h30.

### Meu saldo, simulador e alertas

| Rota | Quem | O que faz |
|---|---|---|
| `GET /api/v1/sgp/orcamento/meu-saldo/` | Autenticado | Limite, comprometido, executado, disponível e semáforo por rubrica, com o período e o saldo do pool do território |
| `GET /api/v1/sgp/orcamento/meu-saldo/{rubrica}/extrato/` | Autenticado | Linhas do ledger do próprio usuário no período vigente, com `efeito` no saldo; `?historico=true` traz os encerrados; paginado |
| `POST /api/v1/sgp/orcamento/remanejamentos/simular/` | UGP e Super Admin | Saldo, percentuais de comprometimento e de execução e faixa antes e depois, sem gravar nada |
| `GET /api/v1/sgp/orcamento/alertas/` | Perfis do orçamento, no próprio escopo | Filtros `?tipo=`, `?faixa=` e `?abertos=`; paginado |

## Painel por rubrica do SGD

`GET /api/v1/sgd/painel/rubricas/` traz por rubrica o solicitado e o autorizado das demandas filtradas e os totais do orçamento no nível do usuário. Traz também os limites de gasto agregados no período vigente (`limite_total`, `limite_comprometido`, `limite_executado` e `limite_disponivel`). Esses totais somam só as linhas individuais já criadas: quem ainda não reservou no período não entra, mesmo tendo limite herdado do perfil.
