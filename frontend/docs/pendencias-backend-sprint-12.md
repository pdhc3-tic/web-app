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
