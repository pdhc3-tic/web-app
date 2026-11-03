# Pendências de backend — sprint 12

*Compilado em 01/11/2026, na branch `frontend/sprint-12`. Revisto em 03/11/2026, depois da abertura da série AJ (#384 a #407).*

*Os itens deste documento vão para uma issue de backend nova, aberta no fim da sprint 12.*

*Os documentos das sprints anteriores continuam valendo para o que está lá.*

---

## 1. Risco de glosa fora do detalhe da demanda (#360) → complemento da #391

A #360 pede que a linha do tempo da demanda mostre o registro de glosa. `registrar_pagamento` (`apps/sgd/services/workflow.py`) grava um `GlosaRisk` quando o pago passa do autorizado, mas nenhuma rota de demanda o devolve: não está em `etapas`, que só traz `ApprovalStep`, nem no `DemandSerializer`.

**Relação com a #391 (AJ-BE-08):** ela generaliza o `GlosaRisk` (`tipo`, `severidade`, `valor_exposto`, `activity_id`) e cria `GET /sgp/glosa-riscos/?activity=&tipo=&severidade=`, só leitura. A rota cobre a ficha da atividade (#404), mas não filtra por demanda, então a #360 continua sem fonte. O pedido entra como complemento da #391, já no formato novo do registro.

**Pedido:** na rota da #391, aceitar também `?demanda=<id>`, com os riscos da demanda em ordem cronológica e lista vazia quando não houver. Cada item precisa trazer, além dos campos da #391, a solicitação e os valores que geraram o risco de pago acima do autorizado:

```json
{
  "id": 7,
  "tipo": "pago_acima_autorizado",
  "severidade": "media",
  "valor_exposto": "200.00",
  "activity_id": 31,
  "demanda_id": 70800,
  "demand_request_id": 42,
  "valor_autorizado": "1200.00",
  "valor_pago": "1400.00",
  "criado_em": "2026-11-01T10:30:00-03:00"
}
```

Alternativa equivalente para o front: o `DemandSerializer` devolver esses itens num campo `glosas`. `demanda_id` e `demand_request_id` são texto no `GlosaRisk` atual, então a consulta compara com o id como string e a resposta devolve inteiros.

*Estado atual no frontend:* o aviso da conclusão funciona. A `LinhaDoTempo` do `DemandaPainel` já lê `glosas` (`GlosaDemanda` em `app/lib/demandas.ts`) e mostra o excedente, a solicitação, os valores e a data. Quando a #391 entrar com o filtro por demanda, o front passa a buscar por ela e troca `excedente` por `valor_exposto`; com o campo no `DemandSerializer`, só o nome do valor muda.

---

## 2. Pools nacionais fora das opções de origem (#363) → complemento da #384

A #363 pede que a UGP escolha a origem do excedente entre pools estaduais e nacionais, e o backend aceita os dois em `origem_allocation`. O front, porém, só tem de onde listar as estaduais: o `detalhamento` de `GET /api/v1/sgp/metas/{id}/orcamento/` nunca traz a linha nacional, por causa do `orcamento_detalhamento_scope`, e nenhuma outra rota devolve o id dela.

**Relação com a #384 (AJ-BE-01):** ela troca `BudgetAllocation` por `BudgetPool(rubrica, nivel, estado, territorio, …)`, tira a Meta do controle de saldo e faz o painel devolver a matriz **Rubrica × Nível**. Com isso a rota citada acima perde o sentido, e o pedido antigo (incluir a linha nacional no `detalhamento` da meta) deixa de valer. A issue não diz se a matriz traz o id de cada pool, que é o que a origem do excedente e a do recurso extra enviam.

**Pedido:** na matriz Rubrica × Nível da #384, cada célula traz o `id` do `BudgetPool`, o `nivel`, o `estado` (`null` no nacional), o `territorio` e o saldo disponível. Para os perfis globais (UGP e Super Admin), o nível nacional aparece. O campo da origem nas decisões (`origem_allocation` hoje) passa a aceitar esse id; se mudar de nome, informar o novo.

Alternativa: uma rota própria das origens possíveis para uma rubrica, combinada com o front.

*Estado atual no frontend:* a seleção de origem do excedente e a do recurso extra usam `useAlocacoesDeOrigem` (`app/lib/hooks/useAlocacoesDeOrigem.ts`), que já aceita qualquer alocação acima do território e rotula a sem estado como "Nacional". Ele lê a rota da meta, que a #384 vai depreciar. A troca para a matriz nova fica com a #399 (AJ-FE-03, adaptação às rotas depreciadas), e então as linhas nacionais aparecem sem outra mudança de tela.
