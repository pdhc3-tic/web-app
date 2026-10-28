# Pendências de backend — sprint 11

*Compilado em 25/10/2026, na branch `frontend/sprint-11a`. Os itens também estão na issue de backend #373, que reúne as pendências abertas do frontend.*

*Os documentos das sprints anteriores (`pendencias-backend-sprint-9.md` e `pendencias-backend-sprint-10.md`) continuam valendo para o que está lá.*

---

## 1. Não há rota que liste as rubricas do orçamento (#319)

> **Ainda aberto em 27/10/2026.** A #373 foi fechada pelo PR #376 sem este item (o 14 de lá): `GET /api/v1/sgp/rubricas/` continua respondendo 404.

*Compilado em 25/10/2026, ao planejar a issue #319 (configuração do mapeamento tipo de solicitação → rubrica).*

A tela da #319 consome o CRUD da BE-8 (`/api/v1/sgd/config/tipo-rubrica/`). Para criar ou alterar um mapeamento, o Super Admin escolhe a rubrica, e o `POST`/`PATCH` espera o `id` dela (`rubrica`).

Nenhuma rota do backend lista as rubricas (`BudgetRubrica`) com o `id`. Conferido em 25/10/2026 contra a `main`, pelo `schema.yml` e pela API:
- o `GET /api/v1/choices/` não traz rubricas;
- a lista do próprio mapeamento só mostra as rubricas que já estão mapeadas (`rubrica`, `rubrica_nome`);
- `GET /api/v1/sgp/metas/{id}/orcamento/` traz as rubricas de uma meta, dentro do orçamento dela, e serve à distribuição, não a um cadastro geral;
- `GET /api/v1/sgd/painel/rubricas/` é o painel de execução, recortado pelos filtros de demanda.

Montar a lista no front a partir de uma dessas rotas seria contornar a falta da rota certa.

**Pedido:** uma rota de leitura do catálogo de rubricas, sem paginação, com este contrato:

```
GET /api/v1/sgp/rubricas/?ativo=true
```

```json
[
  { "id": 4, "slug": "alimentacao-refeicoes", "nome": "Alimentação/Refeições", "ativo": true }
]
```

- ordenada por `nome`;
- `?ativo=true` devolve só as ativas. Sem o parâmetro, devolve todas, para a tela mostrar o nome de uma rubrica inativa que ainda esteja num mapeamento antigo;
- leitura para qualquer usuário autenticado. É um catálogo, sem valores de orçamento, e outras telas também podem usá-la.

*Estado atual no frontend:* a tela de Tipos e Rubricas (`/admin/configuracoes/sgd/tipos-rubricas`) chama só essa rota para montar o campo "Rubrica". Enquanto ela não existe, o campo mostra o erro do componente, e não dá para criar um mapeamento nem trocar a rubrica de um existente. Listar, desativar, reativar e remover funcionam. No E2E, que roda só contra o backend real, os testes de criar e de trocar a rubrica ficam escritos e marcados como `fixme` até a rota existir.

---

## 2. Mapeamento Arlo ↔ SGD: a #320 entregue sem o catálogo nem o preview

> **Resolvido no backend em 26/10/2026 pelo PR #376** (item 7 da #373). A tela usa `campos/` e `preview/`; o `CAMPOS_FALLBACK` e o aviso de pendência saíram do front.

*Compilado em 26/10/2026, ao implementar a issue #320 (configuração do mapeamento Arlo ↔ SGD).*

Os dois endpoints pedidos no item 18 do `pendencias-backend-sprint-10.md` continuam abertos: `GET /api/v1/sgd/config/arlo-mapping/campos/` e `GET /api/v1/sgd/config/arlo-mapping/preview/?direcao=exportacao`. A tela #320 foi entregue mesmo assim, pelo mesmo critério das outras pendências desta sprint: implementar reativamente, para quando o backend responder, o front já funcionar.

*Estado atual no frontend:*

- Tela em `/admin/configuracoes/sgd/integracao-arlo`, só Super Admin, com as duas direções em abas.
- CRUD completo contra `ArloFieldMappingViewSet` (BE-9): listar, criar, editar coluna/formato/ativo, remover, reordenar por drag-and-drop e por botões ↑/↓.
- **Catálogo:** o front chama `fetchCamposArloMapping()` e cai no `CAMPOS_FALLBACK` (`app/lib/arloMapping.ts`), espelho fiel de `apps/sgd/services/arlo_mapping.py` (campos, obrigatoriedade e formatos permitidos por direção). Em `404` o fallback entra sem erro. Quando o endpoint `.../campos/` existir, o front passa a usar o catálogo do backend sem mudar nenhum componente — o rótulo de cada campo e a tag "Obrigatório" vêm do catálogo.
- **Preview:** o front chama `fetchPreviewArloMapping("exportacao")` e, em `404`, mostra o aviso "Preview aguardando o backend" na própria tela, apontando este doc e a #373. A reordenação já invalida a query do preview para quando a rota responder.

Rodar a #320 contra a `main` hoje mostra o CRUD funcionando (o `seed_demo` traz o mapeamento padrão da migration `sgd.0007`), a tag "Obrigatório" nos campos conforme o backend, e o aviso de pendência onde entraria o preview.

---

## 3. Itens em aberto da #302 Parte A — o que ficou de fora da sprint

*Compilado em 26/10/2026 ao revisar o que a #302 Parte A ainda pede, com o estado real da `main` depois do PR #342.*

Os itens abaixo não cabiam nesta entrega sem backend novo. Ficam listados para o #373 e para o planejamento da próxima sprint:

### 3.1 A3 #238 — contrato real de `/sgp/producao/` e `/sgp/producao/indicadores/`

> **Resolvido em 27/10/2026.** O `/indicadores/` já aplica o `ProducaoConsolidadaFilter` (`filter_queryset`); o front passou a mandar tipo, cultura e espécie também aos indicadores, e o E2E da produção roda contra o seed.

A tela e os tipos (`ProducaoConsolidadaItem`, `IndicadoresProducao` em `app/lib/producao.ts`) foram escritos contra o contrato combinado, mas a conferência contra a resposta real do backend ainda não aconteceu — ela depende de rodar com o seed completo e um usuário com escopo nos três filtros (tipo, cultura, espécie).

Também segue aberto o pedido do critério: **repassar os filtros de tipo, cultura e espécie aos indicadores**, se o backend os suportar. O endpoint `/indicadores/` hoje aceita só o escopo territorial e o período; para o painel reproduzir os mesmos recortes da listagem, o backend precisa aceitar os três filtros no `/indicadores/` também.

**Pedido** — alinhar `IndicadoresProducaoView` para aceitar `?tipo=`, `?cultura=` e `?especie=` como `ProducaoConsolidadaFilter` já faz; e documentar o contrato de `/sgp/producao/` no `schema.yml`.

### 3.2 A4 #239 e A5 #240 — fluxo assíncrono dos relatórios

> **Resolvido em 27/10/2026.** O backend já gera o Plano de Trabalho e as Atividades pelo `POST /sgp/exportacoes/` (tipos `plano_trabalho` e `atividades`); Relatórios, o Exportar do painel e as UPFs usam o mesmo fluxo (`app/lib/exportacoes.ts` e `useExportacao`).

O fluxo assíncrono entregue para a listagem de UPFs (PR #306, `/sgp/exportacoes/{id}/`) **não foi estendido** à exportação do Plano de Trabalho (`/sgp/plano-trabalho/exportar/`) nem à de Atividades (`/sgp/atividades/exportar/`). As duas continuam síncronas, com o `ExportTimeoutError` do cliente (60s) como única defesa.

A migração dos dois fluxos é uma issue inteira — reaproveitar o `app/lib/exportacoes.ts` combinado com a #240 — e depende de o backend oferecer o endpoint assíncrono equivalente para cada uma. Enquanto não oferece, a exportação segue síncrona.

**Pedido** — `apps/sgp/services/workplan_export.py` e `activity_export.py` ganharem o fluxo `202 → GET/download/repetir` do padrão `UPF_EXPORT`, com Celery. A tabela de contrato está no PR #306.

### 3.3 A6 #241 — pendência do `FIELD_ENCRYPTION_KEY` no CI

> **Parte do backend resolvida:** o `playwright.yml` já injeta a `FIELD_ENCRYPTION_KEY`. Fica com o front rodar o workflow a frio e registrar a duração na #241 (o job ainda é cortado pelo `timeout-minutes: 20`).

O workflow do Playwright do SGP foi escrito para rodar contra o seed real; falta ao backend injetar a chave `FIELD_ENCRYPTION_KEY` no job de CI para os campos criptografados saírem corretos. Enquanto não entra, o workflow pula os specs que dependem dos campos sensíveis.

**Pedido** — adicionar `FIELD_ENCRYPTION_KEY` ao job de CI (segredos do repositório) e rodar o workflow a frio para registrar na #241 a duração da suíte, como o workflow já imprime em "Duração da suíte".

### 3.4 Pagina a listagem de demandas (NFR da #323)

> **Resolvido em 27/10/2026.** `DemandViewSet` pagina com `DemandPagination` (`limit`/`offset`); o painel de demandas navega página a página e o E2E da #323 cria 10.000 demandas pela fixture `volumeDemandasFixture.ts`, sem precisar de um seed de volume.

O NFR "paginação/scroll com volume alto, equivalente aos 10.000 registros" não cabe em E2E hoje:

- `seed_demo` tem dezenas de demandas, não milhares;
- `GET /api/v1/sgd/demandas/` **não pagina** (`DemandViewSet` não declara `pagination_class`), então mesmo com 10k registros o front receberia tudo numa só resposta — o que o próprio pedido 13 do `pendencias-backend-sprint-10.md` registra como pendência de backend.

*Estado atual no frontend:* a listagem está pronta para paginar: a `useQuery` já aceita `placeholderData: keepPreviousData` e o skeleton foi dimensionado por página. Quando o backend paginar, só a função `listDemandas` passa a aceitar `limit`/`offset`.

**Pedido** — paginação em `DemandViewSet.list` (`LimitOffsetPagination`), e um comando `seed_demo_volume --demandas=10000` em `apps/sgd/management/commands/` para o teste manual do NFR em homologação. O NFR fica fora do E2E até esse seed existir.

---

## 4. Busca do mapa de UPFs ignorada pelo cache (B6 da #302) — aberta na #377

*Compilado em 27/10/2026, ao trocar as simulações da `mapa.spec` pelo backend real.*

`GET /api/v1/upfs/mapa/` guarda a resposta por 60 s (`UPF_MAP_CACHE_TIMEOUT`), e `build_upf_map_cache_key` (`apps/sgp/cache.py`) só considera `bbox`, `municipio`, `territorio`, `projeto` e `ativo`. O `q` da busca por texto fica fora da chave. Conferido pela API em 27/10/2026: depois de `GET /upfs/mapa/` (37 UPFs), `GET /upfs/mapa/?q=texto-que-nao-existe` devolve as mesmas 37, e na ordem inversa a primeira resposta (0) volta para quem pede sem filtro.

Além do `q`, também ficam fora da chave `comunidade`, `cadastrado_de` e `cadastrado_ate`, todos aceitos pelo `UPFFilter` que o endpoint aplica.

**Pedido (#377):** montar a chave com todos os parâmetros do `UPFFilter`, mais o `bbox`.

*Estado atual no frontend:* a tela manda `?q=` corretamente. No E2E, o teste da busca sem resultado está escrito e marcado como `fixme` até a correção.

---

## 5. Limiares do semáforo do orçamento fora do alcance da tela — na #373 (item 15)

*Compilado em 28/10/2026, ao corrigir a `orcamento.spec` (o vermelho passou de 80% para `budget_alert_red_pct`, 90% por padrão, na migração `core/0021`).*

O semáforo de `GET /api/v1/sgp/orcamento/painel/` segue `budget_alert_yellow_pct` e `budget_alert_red_pct` do `SystemConfig`. A tela escreve esses números nos rótulos ("Comprometido ≥ 90%") e no banner de alerta, mas não tem como lê-los: `/system-config/` é só de Super Admin e UGP (`IsSuperAdminOrUGPReadOnly`), e o painel também é visto por Articulador e ADT. Se a configuração mudar, a cor continua certa (vem do backend) e o número escrito fica errado.

**Pedido:** devolver em cada linha do painel os limiares em vigor, como inteiros:

```json
"limiares_semaforo": { "amarelo": 70, "vermelho": 90 }
```

*Estado atual no frontend:* `PainelOrcamentoLinhaApi.limiares_semaforo` já é lido por `limiaresDaLinha` (`app/lib/orcamento.ts`). Enquanto o campo não vem, os rótulos usam os padrões do backend (70 e 90). Nada muda no front quando o campo entrar.
