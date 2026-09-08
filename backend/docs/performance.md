# Performance do Painel do PT e da Listagem de UPFs

## Objetivo

Documenta a denormalização de `WorkPlanAcao.quantidade_realizada` (issue #229) e comprova, com números medidos, que os RNFs de latência do SGP são atendidos:

- Painel do PT atualizado em **< 500ms** após a conclusão de uma atividade.
- Listagem de **5.000 UPFs em < 3s**, com filtros e paginação de 50.

Antes desta issue, `WorkPlanAcao.quantidade_realizada` era uma `@property` que executava um `COUNT` por Ação a cada acesso, e `WorkPlanMeta.status_calculado` disparava essa property uma vez por Ação da Meta — um N+1 sem medição registrada.

## Arquivos Envolvidos

- `apps/sgp/models/workplan.py` — `WorkPlanAcao.quantidade_realizada` materializado; `status_execucao` deixou de rodar `COUNT`.
- `apps/sgp/signals/workplan.py` — mantém o campo em sincronia com `Activity` (`post_save`/`pre_save`).
- `apps/sgp/apps.py` — registra o novo módulo de signals.
- `apps/sgp/migrations/0026_workplanacao_quantidade_realizada.py` e `0027_popula_quantidade_realizada.py` — schema e backfill.
- `apps/sgp/management/commands/verificar_progresso_acoes.py` — reconciliação sob demanda.
- `apps/sgp/tests/test_workplan_performance.py` — os 7 testes desta issue, incluindo os dois testes de carga citados abaixo.

## Método de Medição

- **Ferramenta de tempo**: `time.monotonic()` ao redor da chamada HTTP feita pelo `APIClient` de teste (sem rede real, mede o custo de view + ORM + serialização).
- **Ferramenta de contagem de queries**: `django.test.utils.CaptureQueriesContext`, comparando o total de queries entre um cenário com 5 Ações e outro com 30 Ações na mesma Meta — a contagem deve ser idêntica.
- **Ambiente**: banco Postgres do `docker-compose.yml` do projeto (container `db`), aplicação rodando via `docker compose exec backend pytest`.
- **Datasets de carga**:
  - Painel do PT: 7 Metas × 30 Ações × 500 Atividades concluídas (105.000 Atividades), populadas via `bulk_create` para não pagar o custo de criação no cronômetro do teste.
  - Listagem de UPFs: 5.000 UPFs (com seus 5.000 titulares) populados via `bulk_create`, consultados com filtro por `municipio` (indexado) e paginação padrão (`page_size=50`).
- **Como reproduzir**:
  ```bash
  docker compose exec backend pytest apps/sgp/tests/test_workplan_performance.py -v -s
  ```
  O `-s` é necessário: os testes de carga e o de contagem de queries imprimem
  o valor medido (`[RNF] ...`) no output — é dali que vêm os números da
  tabela abaixo.

## Resultados

| Cenário | RNF | Medido | Método |
| --- | --- | --- | --- |
| Painel do PT (105.000 Atividades, 210 Ações, 7 Metas) | < 500ms | **0.155s** | `time.monotonic()` |
| Listagem de 5.000 UPFs, paginação de 50 | < 3s | **0.076s** | `time.monotonic()` |
| Queries de `GET /api/v1/sgp/plano-trabalho/painel/` (5 vs. 30 Ações na mesma Meta) | constante | **5 queries em ambos os casos** | `CaptureQueriesContext` |

> Medido via `docker compose exec backend pytest apps/sgp/tests/test_workplan_performance.py -v -s` (suíte completa, incluindo `test_workplan.py`, passando 100%). Todos os RNFs foram atendidos com folga considerável em relação ao limite.

## Decisões Derivadas da Medição

- Nenhum índice novo foi adicionado a `UPF` (além dos já existentes em `municipio`, `territorio`, `projeto`, `comunidade`). Caso `test_listagem_5000_upfs_sob_3s` não atinja o RNF neste ambiente, avaliar um índice em `criado_em` (usado no `ordering` padrão) ou um índice composto alinhado ao filtro exercitado no teste.
- `services/workplan_dashboard.py` (painel do PT) e `services/workplan_export.py` continuam calculando o progresso via `Count(...)` anotado por requisição, em vez de ler `quantidade_realizada` diretamente — esses endpoints filtram o progresso por escopo territorial do usuário, algo que o campo materializado (global, sem escopo) não captura. O campo `quantidade_realizada` resolve o N+1 dos consumidores "crus" da Ação (serializer padrão, admin, `WorkPlanMetaViewSet.list()` via `status_calculado`).
- `manage.py verificar_progresso_acoes` reconcilia (corrige) as divergências por padrão; use `--check-only` para apenas detectá-las sem alterar o banco (útil em CI/monitoramento).
