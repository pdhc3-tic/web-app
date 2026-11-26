# Pendências de backend — sprint 12h

*Compilado em 26/11/2026, na branch `frontend/sprint-12h`.*

*Os itens viram uma issue de backend no fim da sprint, junto do PR da `frontend/sprint-12h`. Os documentos das sprints anteriores continuam valendo para o que está lá.*

| Item | Pedido | Issue de front que espera |
|---|---|---|
| 1 | Filtros `meta`, `submeta` e `indicador` no calendário de atividades | #464 |

---

## 1. Filtros do Plano de Trabalho no calendário de atividades (#464)

A #464 pede os filtros de Meta, Submeta e Indicador na lista de Atividades e no Calendário. Na lista, o `ActivityFilter` já aceita `meta`, `submeta` e `indicador`, e o front passou a usá-los.

O Calendário usa outra rota, `GET /api/v1/sgp/atividades/calendario/?inicio=&fim=`, e ela não passa pelo `ActivityFilter`. O `calendario` de `apps/sgp/views/activity.py` aplica os filtros à mão e só conhece `tecnico_id`, `projeto`, `acao`, `tipo_atividade` e `status`. Um `?meta=` é ignorado em silêncio e a resposta traz as atividades de todas as Metas. Se o front mandasse o filtro, o Calendário mostraria atividades fora dele sem nenhum aviso.

**Pedido:** a rota do calendário aceitar `meta`, `submeta` e `indicador`, com o mesmo significado da listagem (`acao__meta_id`, `acao__submeta_id`, `acao__indicador_id`). Uma forma que evita a divergência nos próximos filtros é aplicar o próprio `ActivityFilter` ao queryset do calendário, mantendo a validação de `inicio` e `fim` e o limite de 90 dias.

*Estado atual no frontend:* a lista de Atividades filtra por Meta, Submeta e Indicador. O Calendário continua só com os filtros que a rota aceita, e a #464 fica aberta por este ponto. Quando a rota aceitar os três parâmetros, o Calendário ganha os mesmos selects da lista (as opções já saem de `opcoesDoPlano`, em `app/(protected)/sgp/atividades/_components/`).
