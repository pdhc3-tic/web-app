# Orçamento — contrato de integração para o SGD

Este documento descreve o contrato que o SGP expõe ao SGD (Sistema de Gestão de Demandas) — o motor de saldo e os endpoints HTTP — e a ordem de lock que os dois seguem.

## Modelos

- `BudgetRubrica`: catálogo das 6 rubricas (§5.3.1).
- `BudgetAllocation`: a distribuição por Meta/Rubrica/Nível (`nacional`/`estadual`/`territorial`), com `valor_alocado`, `valor_comprometido` e `valor_executado`.
- `BudgetTransaction`: trilha de auditoria imutável de cada movimento (`reserva`/`execucao`/`liberacao`/`remanejamento`).

## O motor (`apps.sgp.services.budget`)

Seis funções públicas, chamadas em resposta ao ciclo de vida de uma demanda no SGD:

```python
def verificar_saldo(*, meta, rubrica, nivel, territorio=None, estado=None, valor) -> SaldoCheck
def saldo_para_consulta(*, meta_id, rubrica_slug, nivel, estado_sigla, territorio, valor) -> SaldoCheck
def reservar(*, allocation, valor, demanda_id, usuario, justificativa="") -> BudgetTransaction
def ajustar_reserva(*, demanda_id, novo_valor, usuario, justificativa="") -> BudgetTransaction
def executar(*, demanda_id, usuario, valor_executado=None) -> BudgetTransaction
def liberar(*, demanda_id, usuario, motivo) -> BudgetTransaction
```

`saldo_para_consulta` é a variante que resolve tudo a partir de ids/slugs crus
(usada pelo `SaldoConsultaView` e pela porta de orçamento do SGD,
`apps.sgd.services.orcamento`) — `verificar_saldo` espera instâncias já
resolvidas. No SGD, só a porta importa o motor; ela resolve a Meta pela
atividade da demanda e devolve os erros do motor como exceções de domínio
(`apps.sgd.exceptions`). `ajustar_reserva` e o parâmetro `valor_executado` de `executar`
foram adicionados para o SGD (`Pré-autorizada → Autorizada com valor
ajustado` e conclusão com valor efetivamente pago menor que o autorizado,
§4.2 do documento do SGD) — aditivos: nenhum código que só chama
`reservar`/`executar()`/`liberar` sem passar por `ajustar_reserva` muda de
comportamento.

### Estado da demanda → chamada esperada

| Estado da demanda no SGD | Chamada |
|---|---|
| Formulário sendo preenchido (antes de criar) | `GET /api/v1/sgp/orcamento/saldo/` (ou `saldo_para_consulta`/`verificar_saldo` direto, se a chamada for interna) |
| Demanda criada, saldo reservado | `reservar(allocation=..., valor=..., demanda_id=<id da demanda>, usuario=...)` |
| Decisão final com valor diferente do estimado | `ajustar_reserva(demanda_id=..., novo_valor=..., usuario=...)` |
| Demanda concluída pela FGD (consumo definitivo, valor efetivamente pago) | `executar(demanda_id=..., usuario=..., valor_executado=<valor pago>)` |
| Demanda recusada ou cancelada | `liberar(demanda_id=..., usuario=..., motivo=...)` |

### Invariantes

- Todas as operações rodam dentro de `transaction.atomic()` com `select_for_update()` na alocação.
- **Idempotentes por `demanda_id`**: chamar `reservar`/`executar`/`liberar` duas vezes para o mesmo `demanda_id` não duplica o efeito — a segunda chamada devolve a `BudgetTransaction` já existente, sem alterar nada de novo.
- `executar`/`liberar` recebem só `demanda_id` (não a alocação nem o valor) — eles localizam a `BudgetTransaction` de tipo `reserva` original para saber qual alocação e quanto mexer. Por isso `reservar` **precisa** ter sido chamado antes com o mesmo `demanda_id`.
- `liberar` devolve o saldo à mesma alocação onde a reserva foi feita (o nível do solicitante) — nunca ao nível pai.
- `reservar` levanta `SaldoInsuficienteError` (exceção Python simples, não amarrada a DRF) se o valor pedido exceder o saldo disponível.
- Nenhuma função do motor importa `apps.sgd` — o motor não conhece quem o chama.

### Ordem de lock no SGD

Toda transação que trava mais de uma destas linhas segue esta ordem, para que duas transações nunca esperem uma pela outra:

1. `BudgetIncreaseRequest` (pedido de recurso extra).
2. Saldo, rubrica por rubrica em ordem de `rubrica_id`: os `DemandIndividualLimit` da rubrica e depois as `BudgetAllocation` da rubrica, cada grupo em ordem crescente de pk.
3. `Demand`.
4. `DemandRequest`.

As transições de status passam por `apps.sgd.services.workflow.executar_transicao` (o cancelamento automático, pela variante em lote `cancelar_pelo_sistema`): primeiro o efeito no saldo, depois a `Demand` travada com o status relido (e as solicitações conferidas, quando o saldo partiu delas) e, por último, a gravação das `DemandRequest`. Se a demanda mudou nesse meio, a transição é recusada com `INVALID_TRANSITION`.

| Caminho | O que trava |
|---|---|
| Submissão; autorização; recusa; conclusão pela FGD; cancelamento pelo solicitante ou, de demanda autorizada, pela UGP/Super Admin | limite → alocação, rubrica a rubrica → `Demand` → `DemandRequest` (estado da reserva, `valor_autorizado` e `valor_pago`, em ordem de pk) |
| Pré-autorização, devolução, início do atendimento | só a `Demand` |
| Importação do Arlo, por linha | limite → alocação da solicitação paga → `Demand` (status relido) → `DemandRequest`. Cada linha numa transação própria: com o arquivo numa só, os locks de uma linha ficariam presos enquanto a seguinte trava o limite de outro solicitante |
| Cancelamento automático por atividade (`tasks.py`) | `liberar_duas_travas_em_lote`: por rubrica, todos os limites e depois todas as alocações; só então as `Demand`, em ordem de pk, e por fim as `DemandRequest`. Se uma demanda deixou de ser cancelável ou ganhou, perdeu ou trocou a rubrica de uma solicitação, a transação volta e a task é repetida (até 3 vezes) |
| Edição da demanda; inclusão de solicitação | só a `Demand` |
| Edição e remoção de solicitação | limite → alocação (se há reserva) → `Demand` → `DemandRequest`; a edição relê a reserva já com o limite travado |
| Decisão de recurso extra | pedido → limite → alocações (territorial e origem) → `Demand` → todas as `DemandRequest` da demanda |
| Parecer, devolução, submissão e edição do pedido | só o pedido |
| Criação do pedido | a `Demand`, e depois o pedido novo, que nenhuma outra transação enxerga antes do commit |
| Edição do limite individual (`PATCH /sgd/limites-individuais/{id}/` ou Django Admin); exclusão pelo Django Admin, só sem saldo | só o limite |
| `remanejar`, `atualizar_valor_alocado` | alocações em ordem crescente de pk |

### Reconciliação

```
python manage.py verificar_saldos
```

Confere, para cada `BudgetAllocation`, se `valor_comprometido`/`valor_executado` batem com a soma das suas `BudgetTransaction` por tipo (`reserva`/`execucao`/`liberacao`). No SGD, confere também se o `valor_comprometido` de cada limite individual bate com a soma do `valor_reservado` das solicitações com reserva ativa (`valor_reservado > 0` e `valor_executado` nulo) do mesmo solicitante e rubrica; essa parte lê `sgd_demand` com visão total, já que o comando não passa pelo middleware que define o papel da sessão para o RLS. Sai com código de saída ≠ 0 (via `CommandError`) e lista as divergências encontradas, se houver.

## Endpoints HTTP

### `GET /api/v1/sgp/orcamento/saldo/?meta={id}&rubrica={slug}&valor={decimal}`

O endpoint que o formulário de demanda do SGD chama no `onChange` do campo de valor, antes de criar a demanda. Resolve o nível automaticamente pelo perfil do usuário autenticado — UGP/Super Admin → nacional, Articulador Estadual → seu estado, ADT/ACR → seu território.

```json
{
  "disponivel": true,
  "saldo": "12500.00",
  "nivel": "territorial",
  "estado": null,
  "territorio": {"id": 7, "nome": "Território Central"},
  "allocation_id": 42,
  "motivo_bloqueio": null
}
```

`rubrica` é o **slug** (ex. `diarias`), não o id. Rubrica inexistente ou inativa retorna `400`. Saldo zero (ou insuficiente para o `valor` pedido) retorna `disponivel: false` com `motivo_bloqueio` preenchido — o bloqueio em si é responsabilidade de quem chama (o SGD), este endpoint só responde a pergunta.

### `POST /api/v1/sgp/orcamento/remanejamentos/`

Remanejamento emergencial — só UGP/Super Admin, com justificativa obrigatória. Move `valor_alocado` entre duas alocações da mesma Meta e Rubrica, gerando duas `BudgetTransaction` (`remanejamento`, débito na origem e crédito no destino).

```json
{"origem_allocation": 12, "destino_allocation": 45, "valor": "3000.00", "justificativa": "..."}
```

### `GET /api/v1/sgp/orcamento/alocacoes/{id}/transacoes/`

Histórico completo de `BudgetTransaction` de uma alocação, mais recente primeiro.

### `GET /api/v1/sgp/orcamento/painel/?meta=&rubrica=&estado=&territorio=`

Matriz Meta × Rubrica com semáforo (§5.3.3), pro painel executivo. Todos os parâmetros são
opcionais: `meta` (id), `rubrica` (slug), `estado` (sigla) e `territorio` (id).

O **nível exibido por linha é dinâmico**, resolvido pelo perfil do usuário autenticado — mesma
política de RBAC do endpoint acima: `super-admin`/`ugp` → nacional por padrão, drill-down
livre pra qualquer estado/território; `articulador-estadual` → **nacional agregado por
padrão** (nacional não é dado sensível por território), com `estado`/`territorio` descendo
só dentro do seu próprio estado; `adt-acr` → sempre o próprio território, sem acesso a
nacional/estadual (`estado=` devolve `403` pra esse perfil). Filtro fora do escopo do perfil
retorna `403`; qualquer um dos 4 filtros com id/slug/sigla inexistente retorna `400`
(todos validados contra a FK real). `estado`/`territorio` juntos: `territorio` vence pra
`super-admin`/`ugp`/`articulador-estadual` — `adt-acr` rejeita `estado=` com `403` mesmo
que o `territorio` enviado junto seja o seu próprio (esse perfil não tem nível estadual).

Sem filtro, 5 queries (4 pro ADT/ACR — nível padrão territorial, sem "distribuído"). Cada
filtro informado soma +1 query de validação — pior caso, 9 (Articulador Estadual com
`territorio`, que confirma posse com 1 query a mais; 8 pros demais perfis).

```json
[
  {
    "meta": {"id": 3, "numero": 3, "titulo": "Meta 3"},
    "rubrica": {"id": 1, "nome": "Diárias", "slug": "diarias"},
    "nivel": "nacional",
    "valor_aprovado": "10000.00",
    "valor_distribuido": "4000.00",
    "valor_comprometido": "6000.00",
    "valor_executado": "2000.00",
    "saldo_disponivel": "-2000.00",
    "semaforo": "vermelho",
    "alerta_80": true
  }
]
```

`semaforo` ∈ `verde` (< 60% comprometido sobre o alocado), `amarelo` (60–79%), `vermelho`
(≥ 80%) — `alerta_80` é `true` no mesmo limiar de `vermelho`. Alocação de valor 0 → `verde`,
sem divisão por zero. A task diária `sgp.tasks.check_budget_threshold_alert` notifica UGP e
Super Admin sobre toda `BudgetAllocation` em vermelho, em qualquer nível (nacional, estadual
ou territorial), espelhando `sgp.tasks.check_acao_progress_alert` (que faz o mesmo para Ações
do PT físico em vermelho).
