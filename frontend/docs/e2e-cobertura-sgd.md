# Cobertura E2E dos fluxos críticos do SGD

Mapa dos critérios da issue #317 (SGD-FE-6) para os testes Playwright que os cobrem. Os testes rodam contra o backend real, sobre os dados do `seed_demo`. Cada spec monta e remove os próprios dados com uma fixture (`frontend/e2e/helpers/`), e por isso não depende do que uma execução anterior deixou.

## Ciclo de vida da demanda — `e2e/ciclo-demanda.spec.ts`

Cada teste é uma jornada inteira feita pela tela. O ADT cria a demanda pela ficha da atividade, monta a solicitação e submete. Cada perfil age na própria sessão. A fixture (`cicloDemandaFixture.ts`, prefixo `E2E-317`) só cria as atividades e uma verba de alimentação. Nenhuma demanda nasce pronta.

| Critério da #317 | Teste | O que confere |
|---|---|---|
| Caminho feliz completo | `caminho feliz: criada, submetida, pré-autorizada, autorizada, atendida e concluída com valor pago` | Saldo das duas travas antes de salvar a solicitação. Fila de cada perfil. Preview do impacto antes de autorizar. Valor pago na conclusão. Linha do tempo vista pelo solicitante. |
| Devolução e ressubmissão | `devolução: o Articulador devolve com justificativa e o solicitante corrige e submete de novo` | Motivo obrigatório. Motivo visível ao solicitante. "Corrigir e submeter de novo". Edição da solicitação. Volta à fila do Articulador. |
| Recusa pela UGP | `recusa: a UGP só recusa com justificativa, e o solicitante vê o motivo` | Justificativa obrigatória no drawer. Status Recusada. Sem opção de editar. Justificativa na linha do tempo. |
| Cancelamento automático | `cancelamento automático: cancelada a atividade, a demanda é cancelada e o saldo volta` | Atividade cancelada pela ficha. Demanda Cancelada (a task do Celery é esperada com `toPass`, sem espera fixa). O valor reservado volta ao limite individual e à verba do território. |

## Bloqueio de saldo — `e2e/montar-demanda.spec.ts` (#295)

Já coberto pela tela de montagem e submissão. Não é repetido na spec do ciclo.

| Critério da #317 | Teste | O que confere |
|---|---|---|
| Bloqueio pela trava individual | `submissão barrada pelo limite individual: mensagem e atalho; a outra solicitação segue no rascunho` | "Limite individual insuficiente." na solicitação barrada. Atalho para o recurso extra. A outra solicitação continua no rascunho. |
| Bloqueio pela trava territorial | `submissão barrada pela verba do território orienta acionar o Articulador Estadual` | "Verba do território insuficiente." com a orientação de acionar o Articulador Estadual, sem atalho de recurso extra. |
| Desbloqueio pelo recurso extra | `o atalho pede o recurso extra; aprovado o pedido, a demanda é submetida` e `recusado o pedido, a submissão continua barrada com a mensagem original` | Fluxo do recurso extra (#321) a partir do bloqueio. |

## Decisões isoladas por perfil — `e2e/painel-demandas.spec.ts` (#296, #322)

Cobre cada decisão com as demandas já no status certo, incluindo os casos que as jornadas não exercitam:
- autorização com valor ajustado e mudança de faixa no preview;
- bloqueio da confirmação enquanto o impacto não é validado;
- cancelamento manual de uma demanda autorizada pela UGP;
- visibilidade por estado do Articulador;
- auditoria restrita ao Super Admin.

## Como rodar

Com a stack de pé (`docker compose up -d backend db redis celery_worker celery_beat`) e o front em `:3000`:

```bash
cd frontend
npx playwright test e2e/ciclo-demanda.spec.ts --project=chromium --no-deps
```

O cancelamento automático depende do `celery_worker`. Sem ele, a demanda não muda de status e o teste falha por tempo.

## Validação contra o backend da sprint 12 (#362)

Em 01/11/2026, as 11 specs do SGD e a `orcamento-saldo` rodaram juntas contra a `main` com os PRs #378, #379 e #382: 100 testes passando em 4,9 minutos, sem `fixme` nem simulação de resposta. O `page.route` dessas specs só atrasa ou derruba requisições.

## Orçamento por pool (#399)

Depois da #384 a #386, o saldo fica no `BudgetPool` (um por rubrica e local), o limite no `SpendingLimit` (por pessoa, rubrica e período) e cada movimento no ledger, imutável por trigger. As fixtures do SGD usam o prelúdio de `e2e/helpers/orcamentoE2E.ts`:

- `fotografar(chave)` no setup guarda pools, limites e o último id do ledger, das transferências e dos alertas num arquivo do container;
- `definir_pool` e `definir_limite` ajustam o que o teste precisa;
- `restaurar(chave)` no teardown, antes de apagar demandas e atividades (o ledger referencia a atividade), apaga só o que o teste lançou, com `session_replication_role = replica` na sessão do `postgres`, e devolve os valores da foto.

Os specs rodam em série num único worker, então uma restauração nunca apaga lançamento de outro spec. Não rodar E2E com teste manual em andamento.

Em 08/11/2026, contra a `main` com os PRs #410 a #415: 95 testes do SGD passando. Ficam para a issue de cada tela:
- `tipos-rubricas`: a tela da #319 virou alias do catálogo de tipos (#357). Refeita na #365 sobre o catálogo: o Super Admin cria um tipo e o ADT o solicita, 8 testes;
- `orcamento`, `orcamento-saldo` e `orcamento-distribuicao`: a matriz do SGP era Meta × Rubrica. Refeitas na #398 sobre os pools (matriz Rubrica × Nível, saldo do ADT sem Meta, distribuição por pool), com as fixtures `orcamentoFixture` e `distribuicaoFixture` no mesmo prelúdio de fotografia.

## Situação do CI

O workflow `Playwright E2E` (`.github/workflows/playwright.yml`) roda a suíte completa em cada PR para a `main`. Hoje ele não chega ao fim:
- o job tem `timeout-minutes: 20`;
- a suíte tem mais de 300 testes, com `workers: 1`, e o setup espera a janela do limite de logins;
- as execuções são canceladas por tempo antes de terminar, e várias specs de fora do SGD também falhavam na última execução.

Isso fica fora do escopo da #317 e precisa de tratamento à parte. A spec do ciclo não depende do ambiente local. Ela usa só os perfis do `auth.setup.ts`, o `seed_demo` e a própria fixture.
