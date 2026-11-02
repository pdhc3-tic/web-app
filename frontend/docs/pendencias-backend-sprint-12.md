# Pendências de backend — sprint 12

*Compilado em 01/11/2026, na branch `frontend/sprint-12`.*

*Os itens deste documento vão para uma issue de backend nova, aberta no fim da sprint 12.*

*Os documentos das sprints anteriores continuam valendo para o que está lá.*

---

## 1. Risco de glosa fora do detalhe da demanda (#360)

A #360 pede que a linha do tempo da demanda mostre o registro de glosa. `registrar_pagamento` (`apps/sgd/services/workflow.py`) grava um `GlosaRisk` quando o pago passa do autorizado, mas nenhuma rota de demanda o devolve: não está em `etapas`, que só traz `ApprovalStep`, nem no `DemandSerializer`.

**Pedido:** incluir no `DemandSerializer` o campo `glosas`, em ordem cronológica e vazio quando não houver:

```json
"glosas": [
  {
    "id": 7,
    "demand_request_id": 42,
    "valor_autorizado": "1200.00",
    "valor_pago": "1400.00",
    "excedente": "200.00",
    "criado_em": "2026-11-01T10:30:00-03:00"
  }
]
```

`demanda_id` e `demand_request_id` são texto no `GlosaRisk`, então a consulta compara com o id como string, e `demand_request_id` sai como inteiro.

*Estado atual no frontend:* o aviso da conclusão funciona. A `LinhaDoTempo` do `DemandaPainel` já lê `glosas` e mostra o excedente, a solicitação, os valores e a data. Quando o campo entrar, aparece sem mudança no front.

---

## 2. Alocações nacionais fora das opções de origem (#363)

A #363 pede que a UGP escolha a origem do excedente entre pools estaduais e nacionais, e o backend aceita os dois em `origem_allocation`. O front, porém, só tem de onde listar as estaduais: o `detalhamento` de `GET /api/v1/sgp/metas/{id}/orcamento/` nunca traz a linha nacional, por causa do `orcamento_detalhamento_scope`, e nenhuma outra rota devolve o id dela.

**Pedido:** incluir as alocações nacionais no `detalhamento` para os perfis globais (UGP e Super Admin), no mesmo formato de `BudgetAllocationSerializer`, com `nivel: "nacional"` e `estado: null`. Alternativa: uma rota própria das origens possíveis, combinada com o front.

*Estado atual no frontend:* a seleção de origem do excedente e a do recurso extra usam `useAlocacoesDeOrigem`, que já aceita qualquer alocação acima do território e rotula a sem estado como "Nacional". Quando as linhas nacionais entrarem no `detalhamento`, aparecem sem mudança no front. Conferir antes as telas que leem o `detalhamento`, porque hoje elas não esperam essa linha.
