# Pendências de backend — sprint 12h

*Compilado em 26/11/2026, na branch `frontend/sprint-12h`.*

*Os itens viram uma issue de backend no fim da sprint, junto do PR da `frontend/sprint-12h`. Os documentos das sprints anteriores continuam valendo para o que está lá.*

| Item | Pedido | Issue de front que espera |
|---|---|---|
| 1 | Filtros `meta`, `submeta` e `indicador` no calendário de atividades | #464 |
| 2 | Histórico de remanejamentos: filtros de território, período e responsável, documento de respaldo e exportação CSV | #466 |
| 3 | Painel do SGD: dizer se há orçamento lançado no escopo, para separar "sem orçamento" de "nenhuma rubrica em alerta" | #467 |
| 4 | Rótulos de status da atividade no feminino (Planejada, Agendada, Concluída…) | #467 |

---

## 1. Filtros do Plano de Trabalho no calendário de atividades (#464)

A #464 pede os filtros de Meta, Submeta e Indicador na lista de Atividades e no Calendário. Na lista, o `ActivityFilter` já aceita `meta`, `submeta` e `indicador`, e o front passou a usá-los.

O Calendário usa outra rota, `GET /api/v1/sgp/atividades/calendario/?inicio=&fim=`, e ela não passa pelo `ActivityFilter`. O `calendario` de `apps/sgp/views/activity.py` aplica os filtros à mão e só conhece `tecnico_id`, `projeto`, `acao`, `tipo_atividade` e `status`. Um `?meta=` é ignorado em silêncio e a resposta traz as atividades de todas as Metas. Se o front mandasse o filtro, o Calendário mostraria atividades fora dele sem nenhum aviso.

**Pedido:** a rota do calendário aceitar `meta`, `submeta` e `indicador`, com o mesmo significado da listagem (`acao__meta_id`, `acao__submeta_id`, `acao__indicador_id`). Uma forma que evita a divergência nos próximos filtros é aplicar o próprio `ActivityFilter` ao queryset do calendário, mantendo a validação de `inicio` e `fim` e o limite de 90 dias.

*Estado atual no frontend:* a lista de Atividades filtra por Meta, Submeta e Indicador. O Calendário continua só com os filtros que a rota aceita, e a #464 fica aberta por este ponto. Quando a rota aceitar os três parâmetros, o Calendário ganha os mesmos selects da lista (as opções já saem de `opcoesDoPlano`, em `app/(protected)/sgp/atividades/_components/`).

---

## 2. Histórico de remanejamentos: filtros, documento e CSV (#466)

A #466 pede a tela de histórico de remanejamentos com filtro por rubrica, território, período e responsável, o saldo antes e depois de origem e destino, o documento de respaldo e a exportação CSV (SGP-RF41).

A issue cita `GET /api/v1/sgp/orcamento/remanejamentos/`, mas essa rota só aceita `POST` (`RemanejamentoView`). A listagem que existe é `GET /api/v1/sgd/remanejamentos/transferencias/` (`RemanejamentoViewSet.transferencias`, para UGP, Super Admin e FGD), sobre o `BudgetTransfer`. Ela já traz origem, destino, valor, motivo, os quatro saldos, o aprovador e a data, e filtra só por `demanda`, `escopo` e `rubrica`. O front passou a usá-la em `/sgp/orcamento/remanejamentos`.

**Pedido:**

1. **Filtros na `transferencias/`**, com os nomes que o `DemandFilter` já usa:
   - `territorio` (id): o território da origem **ou** do destino (`pool_origem__territorio_id` ou `pool_destino__territorio_id`);
   - `periodo_inicio` e `periodo_fim` (`AAAA-MM-DD`): `criado_em` dentro do intervalo, com os dois extremos inclusos;
   - `aprovado_por` (id do usuário).
2. **Opções do filtro de responsável**: uma lista de quem já aprovou remanejamentos (`id` e `nome`), por exemplo `GET /api/v1/sgd/opcoes/usuarios/?papel=aprovador_remanejamento`, no padrão do `papel=solicitante` e do `papel=responsavel`.
3. **Documento de respaldo**: o `BudgetTransfer.documento_url` existe, mas não sai no `BudgetTransferSerializer`, e o `POST /api/v1/sgp/orcamento/remanejamentos/` não o recebe, então hoje nenhum remanejamento tem documento. É preciso expor o campo na listagem e aceitá-lo na confirmação do remanejamento, como URL ou como upload (no padrão do `upload-url` das evidências).
4. **Exportação CSV**: `GET /api/v1/sgd/remanejamentos/transferencias/exportar/?formato=csv`, com os mesmos filtros da listagem e as colunas da tela (data, rubrica, tipo, origem, destino, valor, saldos antes e depois, aprovado por, motivo, documento), no padrão do `/sgd/demandas/exportar/`.

*Estado atual no frontend:* a tela lista os remanejamentos com saldos antes e depois, aprovador, motivo, a origem (direto da UGP, excedente da demanda ou recurso extra, com link) e paginação, com filtro só por rubrica. Os filtros de território, período e responsável, a coluna do documento e o botão Exportar CSV entram quando o backend entregar estes pontos; a #466 fica aberta por eles.

---

## 3. Painel do SGD: orçamento lançado no escopo (#467)

O painel do SGD (`GET /api/v1/sgd/dashboard/`, `DashboardSerializer`) devolve em `alertas_saldo` só as rubricas em faixa amarela ou vermelha. Quando a lista vem vazia, o front não sabe se é porque tudo está abaixo da faixa amarela ou porque não há orçamento lançado no escopo do usuário. A tela dizia "As rubricas do seu escopo estão abaixo da faixa amarela" mesmo sem orçamento nenhum, o que o teste de 23/11 apontou.

**Pedido:** um campo no painel que diga quantas linhas de orçamento existem no escopo, por exemplo `rubricas_com_orcamento` (inteiro), contando as linhas de `_linhas_orcamento_do_escopo(user)` com `valor_aprovado` maior que zero. Zero significa "sem orçamento lançado".

*Estado atual no frontend:* o aviso vazio passou a um texto neutro ("Nenhuma rubrica do seu escopo está na faixa amarela ou vermelha"). Com o campo, a tela mostra "Ainda não há orçamento lançado no seu escopo" quando ele vier zero. A #467 fica aberta por este ponto.

---

## 4. Rótulos de status da atividade no feminino (#467)

Os rótulos de `STATUS_CHOICES` (`apps/sgp/models/activity.py`) misturam os gêneros: "Planejado", "Agendado", "Concluído" e "Concluído sem evidência" no masculino, e "Adiada", "Não realizada" e "Cancelada" no feminino. Na tela, a mesma atividade aparece como "Planejado" ao lado de "Atrasada", e a legenda do calendário põe "Cancelada" junto de "Agendado".

**Pedido:** rótulos no feminino, concordando com "atividade": Planejada, Agendada, Em andamento, Concluída, Concluída sem evidência, Adiada, Não realizada e Cancelada. Só os rótulos mudam; as chaves (`planejado`, `agendado`, `concluido`…) ficam. Eles chegam ao front por `status_display` e por `/choices/` (`status_atividade`).

*Estado atual no frontend:* os rótulos vêm do backend; mudar só no front deixaria a mesma tela com os dois gêneros. Quando o backend mudar, o front acerta os rótulos locais que repetem os do backend (padrões do `Badge` e legenda do calendário). A #467 fica aberta por este ponto.
