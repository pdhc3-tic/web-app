# Plano de Trabalho: Meta → Submeta → Ação → Indicador

Referência: SGP v1.3 §5.1–5.6 (RF07, RF15, RF18–RF26), SGD v1.1 SGD-RF02 e
matriz de permissões do Core §2.1.

## Hierarquia

| Nível | Model | Numeração | Regras |
| :--- | :--- | :--- | :--- |
| Meta | `WorkPlanMeta` | `X` (1 a 7) | Não muda de número depois de ter Submetas (a numeração delas começa com `X`). O período precisa conter o de todas as Submetas. Com Submetas, a API não a exclui (400). |
| Submeta | `WorkPlanSubmeta` | `X.Y`, com `X` da Meta | Período obrigatório, contido no da Meta. Responsável opcional, só usuário UGP. Sem orçamento próprio: só consolida as Ações. |
| Ação | `WorkPlanAcao` | `X.Y.Z`, com `X.Y` da Submeta | Submeta, Indicador e período obrigatórios; período contido no da Submeta. `meta` é derivada da Submeta no `save()` e só leitura na API. |
| Indicador | `Indicator` | código curto (`IND-OFI`) | Catálogo institucional, compartilhado entre Ações de Metas diferentes. |

A Ação continua gravando `meta` porque o orçamento (`BudgetAllocation.meta`),
o SGD e os filtros por Meta leem dela. Mudar o número ou a Meta de uma Submeta
renumera as Ações dela e atualiza a Meta delas.

As regras da tabela ficam nos models: `clean()` valida (prefixo, períodos,
filhos que ficariam fora do novo período, responsável da UGP, Indicador
inativo) e o `save()` da Submeta renumera as Ações. A API chama o `clean()`
pelos serializers, então as regras valem igual na API e no admin do Django.
No admin, a forma de apuração de um Indicador em uso é só leitura, porque a
troca exige a confirmação e a auditoria da API; o número e a Meta de uma
Submeta com Ações também, porque as Ações do inline seriam validadas e
gravadas com o número antigo.

### Migração dos dados (0033–0035)

A 0034 converte o modelo antigo:
- cada valor de `tipo_unidade` vira um Indicador do catálogo inicial (IND-SEM, IND-OFI, IND-CUR, IND-PLA, IND-REL, IND-INT, IND-AUD, IND-VIS, IND-ENC, IND-UNI, IND-FAM, IND-OUT);
- cada Meta com Ações ganha a Submeta `X.1`, e as Ações passam de `X.Y` para `X.1.Y`;
- Ação sem período herda o da Submeta.

As três migrations são reversíveis. Depois de migrar um banco que já tinha
dados, rode `manage.py verificar_progresso_acoes`: a migration não recalcula
nada, então a quantidade realizada das Ações que passaram para uma forma de
apuração diferente da contagem de atividades (ex.: IND-FAM, soma de UFPAs) e o
valor executado só ficam corretos depois do comando.

## Indicador

| Campo | Valores |
| :--- | :--- |
| `unidade_medida` | unidade, familia, pessoa, evento, plano, relatorio, hectare, outro |
| `forma_apuracao` | contagem_atividades, soma_ufpas, soma_participantes, manual |
| `categoria` | formacao, assistencia_tecnica, estruturacao_produtiva, gestao, outro (opcional) |
| `ods_ids` | lista de 1 a 17 |
| `desagregacoes` | lista de genero, geracao, pct, territorio |

- Indicador com Ações não pode ser excluído (`409 indicador_em_uso`); o caminho é inativar.
- Indicador inativo não pode ser vinculado a Ação nova nem entrar numa troca de Indicador. Ação que já o usa continua válida.
- Trocar a forma de apuração de um Indicador com Ações exige `confirmar_recalculo=true` (sem isso, `409 confirmacao_necessaria`). Com a confirmação, as quantidades das Ações são recalculadas e a troca fica no AuditLog como `Indicator.forma_apuracao_alterada`.

## Quantidade realizada (RF21)

Fonte única: `apps/sgp/services/apuracao.py`.

| Forma | Conta |
| :--- | :--- |
| `contagem_atividades` | Atividades concluídas e ativas da Ação |
| `soma_ufpas` | UFPAs **distintas** vinculadas às Atividades concluídas da Ação |
| `soma_participantes` | Membros **distintos** vinculados às Atividades concluídas da Ação |
| `manual` | Valor lançado pela UGP no `PATCH /api/v1/acoes/{id}/` (`quantidade_realizada`); nas outras formas esse campo dá 400 |

- `WorkPlanAcao.quantidade_realizada` é materializado e recalculado:
  - pelos signals de `apps/sgp/signals/workplan.py`: ao salvar uma Atividade (inclusive trocando de Ação ou sendo desativada), ao alterar UFPAs e membros participantes pelos dois lados da relação e ao excluir de fato uma UFPA ou um membro;
  - ao trocar o Indicador de uma Ação (signal do `WorkPlanAcao`, vale também no admin) ou a forma de apuração de um Indicador.
- O painel, a exportação e a visão por Indicador apuram de novo, com a mesma regra, só sobre as Atividades do escopo do usuário (e do território e período pedidos). Na forma manual vale o número lançado, que não tem recorte territorial; na visão por Indicador com `territorio_id` ou período, o realizado de um Indicador manual vem `null`.

## Valor executado

Soma do `valor_pago` das demandas `concluida` das Atividades ativas da Ação
(SGP §5.5). Fica materializado em `WorkPlanAcao.valor_executado` e é
recalculado:
- quando o SGD conclui uma demanda (`apps/sgd/services/approval.concluir`);
- quando uma Atividade muda de Ação ou é desativada.

É o valor da Ação inteira, igual para todo perfil. `sgd_demand` tem RLS pelo
papel da sessão; o recálculo lê as demandas com visão total só durante a
consulta e restaura o papel anterior logo em seguida
(`apuracao._leitura_total_do_sgd`). Sem isso, um recálculo disparado por um
ADT, por uma task ou por um comando veria só parte das demandas.

`manage.py verificar_progresso_acoes` reconcilia a quantidade (exceto na forma
manual) e o valor executado; `--check-only` só detecta.

## Consolidados

- **Ação:** valor total (quantidade × valor unitário), percentual realizado, custo unitário realizado (executado ÷ realizado) e status (`no_prazo`, `em_atraso`, `concluida`).
- **Submeta:** soma das Ações (quantidades, valor total, valor executado). Fica `concluida` quando todas as Ações estão.
- **Meta:** soma das Submetas. O status passa a derivar das Submetas.

## Endpoints

| Método | Rota | Permissão |
| :--- | :--- | :--- |
| CRUD | `/api/v1/sgp/indicadores/` | Escrita: Super Admin/UGP. Leitura: autenticado (catálogo, sem escopo territorial) |
| CRUD | `/api/v1/sgp/submetas/` | Escrita: Super Admin/UGP. Leitura: escopo territorial, como as Metas |
| CRUD | `/api/v1/acoes/` | Escrita: Super Admin/UGP. Excluir Ação com Atividades: `400 acao_com_atividades` |
| GET | `/api/v1/sgp/plano-trabalho/painel/` | Escopo territorial |
| GET | `/api/v1/sgp/plano-trabalho/indicadores/` | Escopo territorial |
| GET | `/api/v1/sgp/plano-trabalho/exportar/` | Escopo territorial |

**Filtros**
- `/sgp/indicadores/`: `?ativo=`, `?categoria=`, `?forma_apuracao=`, `?unidade_medida=`, `?q=` (código ou nome).
- `/sgp/submetas/`: `?meta=`.
- `/acoes/`: `?meta=`, `?submeta=`, `?indicador=`.
- `/sgp/atividades/`: `?meta=`, `?submeta=`, `?indicador=` (RF15).

**Painel (RF23)**
Cada Meta mantém `meta`, `resumo` e `acoes` como antes e ganha:
- `consolidado`;
- `submetas`: lista com `submeta`, `consolidado` e os `id` das `acoes`.

O `consolidado` traz quantidades, percentual realizado, progresso esperado,
semáforo físico, status, valor total, valor executado, percentual financeiro
e semáforo financeiro.
- O semáforo físico é o de antes (realizado × progresso esperado).
- O financeiro usa os limiares 70/90 do Core (`budget_alert_yellow_pct` e `budget_alert_red_pct`, SGP §6.8) sobre executado ÷ planejado.
- Cada Ação ganha `submeta`, `indicador`, `valor_total`, `valor_executado`, `percentual_financeiro` e `semaforo_financeiro`.

**Visão por Indicador (RF22)**
- `GET /sgp/plano-trabalho/indicadores/?territorio_id=&meta_id=&indicador_id=&periodo_inicio=&periodo_fim=`.
- Soma planejado e realizado de todas as Ações que usam cada Indicador.
- Quebras: `por_meta`, `por_submeta` e `por_territorio`. A quebra territorial traz só o realizado, porque o planejado não é territorial, e não inclui Ações de apuração manual.
- O período filtra pela data de término das Atividades.

**Atividades (RF07)**
Listagem, detalhe e calendário trazem `plano_trabalho` com Meta, Submeta,
Ação e Indicador, derivados da Ação e só leitura.

**SGD (SGD-RF02)**
O `contexto` da demanda ganha `submeta_numero`, `submeta_titulo`,
`indicador_codigo`, `indicador_nome` e `indicador_unidade_medida`.

## Débito técnico

### Alias `tipo_unidade_display` e chave `tipo_unidade` do Power BI

**O que é:**
- `WorkPlanAcaoSerializer.tipo_unidade_display` (em `apps/sgp/serializers_workplan.py`) devolve o **nome do Indicador** da Ação;
- a chave `tipo_unidade` das linhas de `workplan_export_rows` (em `apps/sgp/services/workplan_export.py`) também. Ela só existe no dataset do Power BI; o CSV e o XLSX não a trazem.

**Por que existe:** o Indicador substituiu o campo `tipo_unidade` da Ação (SGP
§5.4) e o campo saiu do model na migration 0035. O front atual
(`frontend/app/lib/acoes.ts` e `painel.ts`) e o conector do Power BI ainda
leem `tipo_unidade_display` e `tipo_unidade`. O alias mantém a leitura
funcionando até esses consumidores passarem a usar `indicador_detalhe` e as
chaves `indicador`/`unidade_medida`.

**O que já não funciona, mesmo com o alias:**
- o valor numérico `tipo_unidade` (código de 1 a 12) não é mais devolvido;
- o front não consegue criar nem editar Ação enviando `tipo_unidade`. A criação passou a exigir `submeta` e `indicador`, e o número passou a `X.Y.Z`.

**Como remover** (quando o front e o Power BI tiverem migrado):
1. apagar o campo `tipo_unidade_display` e o comentário que o acompanha em `WorkPlanAcaoSerializer`;
2. apagar a chave `"tipo_unidade"` e o comentário em `_serialize_action` de `apps/sgp/services/workplan_export.py`;
3. apagar os testes `test_alias_tipo_unidade_display_traz_nome_do_indicador` (`apps/sgp/tests/test_workplan_submeta.py`) e `test_power_bi_mantem_alias_tipo_unidade` (`apps/sgp/tests/test_workplan_hierarquia.py`);
4. tirar esta seção e o parágrafo sobre o alias em `backend/docs/export.md`.

## Fora do escopo

- Monitoramento do TED: índice de aderência (RF49), custo por território (RF53), curva S e fechamento mensal.
- Árvore do PT offline no SCA.
- Filtros do SGD por Submeta (SGD-RF26) e colunas do Arlo.
- FGD não lê Metas nem Submetas: o escopo territorial nega a quem não tem papel com escopo. É um gap que já existia; a Submeta segue o padrão da Meta.
