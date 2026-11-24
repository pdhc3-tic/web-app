# Pendências de backend — sprint 12g

*Compilado em 23/11/2026, na branch `frontend/sprint-12g`.*

*Os documentos das sprints anteriores continuam valendo para o que está lá. O item 9 da 12b, o seletor de objeto de abrangência da #405, segue pendente.*

| Item | Issue do front | Depende de | Bloqueia critério de aceite? |
|---|---|---|---|
| 1 | #438 (dotação nacional) | #437 (entidade TED) | Não. A #438 fica aberta só por ele |
| 2 | #453 (catálogo de indicadores) | — | Não. Melhoria: a tela funciona com a cópia dos rótulos |
| 3 | #456 (Painel de Demandas) | — | Não. Melhoria: a coluna Atividade mostra Ação, município e data |
| 4 | #456 (Painel de Demandas) | — | Não. Melhoria: a ordenação por Valor estimado já funciona |

---

## 1. Dotação nacional ligada à versão vigente do TED (#438 ↔ #437)

*Não bloqueia os critérios da #438: a UGP já lança a dotação, distribui aos estados e territórios, e o SGD mostra saldo. O que falta é o teto do TED. A #438 fica aberta só por este item, por decisão do Andre.*

**O que existe hoje.** A tela `/sgp/orcamento/dotacao` lança e ajusta o pool nacional de cada rubrica com as rotas que já existem:
- `POST /api/v1/sgp/orcamento/pools/` com `nivel: "nacional"`;
- `PATCH /api/v1/sgp/orcamento/pools/{id}/`.

O backend não confere o valor contra nada, porque o pool nacional não tem pai (`criar_pool`, `apps/sgp/budget/services.py`). O único limite é o piso na redução: o que já desceu aos estados mais o comprometido e o executado. A tela espelha esse piso e mostra o erro do servidor no campo da rubrica.

**O que a #437 traz e o front precisa consumir.** A SGP-RF28 exige que a dotação respeite o valor aprovado no TED para cada rubrica. Para a tela mostrar e validar isso, o front precisa de:

1. **O valor aprovado por rubrica na versão vigente**, numa leitura que a UGP e o Super Admin acessem. Duas formas servem:
   - `GET /sgp/ted/vigente/`, devolvendo `{versao: {id, numero, tipo, vigencia_inicio, vigencia_fim}, rubricas: [{rubrica_id, valor_aprovado}]}`;
   - ou o painel (`/sgp/orcamento/painel/?nivel=nacional`) devolver, em cada linha nacional, `ted_versao_id` e `valor_aprovado_ted`.
2. **O erro de teto em `valor_alocado`**, no mesmo formato dos outros 400 de pool, por exemplo `{"valor_alocado": ["Acima do aprovado no TED vigente para esta rubrica (R$ 100.000,00)."]}`. A tela já ancora qualquer erro de `valor_alocado` no campo da rubrica, então isso funciona sem mudança no front.
3. **O que acontece com a dotação quando um aditivo reduz o valor aprovado** abaixo do que já foi lançado: se o pool é ajustado automaticamente, se fica acima até alguém ajustar, ou se o aditivo é recusado. O front precisa saber disso para mostrar o aviso certo.

*Estado atual no frontend:* `lancarDotacaoNacional` e `pisoDoPool` em `app/lib/orcamento.ts`. A página é `app/(protected)/sgp/orcamento/dotacao/page.tsx`. Quando a #437 entregar, a tela ganha uma coluna com o aprovado no TED, a versão vigente no topo e o bloqueio antes de enviar um valor acima do aprovado.

## 2. Rótulos do Indicador em `/api/v1/choices/` (#453)

*Melhoria, não bloqueia: a #453 fecha com a cópia dos rótulos no front.*

**Estado atual.** O Catálogo de Indicadores (`/sgp/indicadores`) mostra e edita unidade de medida, forma de apuração, categoria e desagregação. `/api/v1/choices/` não publica nenhuma dessas listas, e o schema só traz os códigos (`UnidadeMedidaEnum`, `FormaApuracaoEnum`, `IndicatorCategoriaEnum`; a desagregação é um `JSONField` sem forma). O front copiou os rótulos de `apps/sgp/models/indicator.py`. Se o backend mudar um rótulo, a tela fica com o antigo sem aviso. Um valor novo só aparece no `tsc`, quando os tipos forem regenerados.

**Pedido:** acrescentar a `CHOICES_PUBLICADOS` (`apps/sgp/views/choices.py`):

```python
from apps.sgp.models.indicator import (
    CATEGORIA_CHOICES as INDICADOR_CATEGORIA_CHOICES,
    DESAGREGACAO_CHOICES, FORMA_APURACAO_CHOICES, UNIDADE_MEDIDA_CHOICES,
)

    "indicador_unidade_medida": UNIDADE_MEDIDA_CHOICES,
    "indicador_forma_apuracao": FORMA_APURACAO_CHOICES,
    "indicador_categoria": INDICADOR_CATEGORIA_CHOICES,
    "indicador_desagregacao": DESAGREGACAO_CHOICES,
```

O comentário de `CHOICES_PUBLICADOS` diz que os testes de contrato conferem que toda constante de choices do SGP está lá. As do Indicador escaparam dessa conferência, então vale também acrescentá-las ao teste.

*Estado atual no frontend:* `UNIDADE_MEDIDA_LABEL`, `FORMA_APURACAO_LABEL`, `CATEGORIA_LABEL` e `DESAGREGACAO_LABEL` em `app/lib/indicadores.ts`. Quando as choices forem publicadas, a tela passa a lê-las de `useSgpChoices` e as cópias saem.

## 3. Título da atividade na listagem de demandas (#456)

*Melhoria, não bloqueia: a #456 fecha com a coluna provisória.*

**Estado atual.** O Painel de Demandas (`/sgd/demandas`) ganhou a coluna Atividade, com link para a ficha. `DemandSerializer` só traz o id (`activity`) e o contexto herdado, sem o título. A coluna mostra o que vem: "Ação 1.1.2 · Mossoró · 12/03/2026". Buscar o título linha a linha seriam até 50 chamadas por página, o que pesa justamente no que a #448 reclama.

**Pedido:** acrescentar ao `DemandSerializer` (`apps/sgd/serializers/demand.py`) o título da atividade, só leitura:

```python
activity_titulo = serializers.CharField(source="activity.titulo", read_only=True)
```

O `get_queryset` de `DemandViewSet` já faz `select_related` da atividade, então não há consulta a mais. O campo também serve à exportação (`COLUNAS_EXPORTACAO`), se fizer sentido lá.

*Estado atual no frontend:* `rotuloAtividade` em `app/(protected)/sgd/demandas/_components/DemandasTabela.tsx`. Quando o campo chegar, a coluna passa a mostrar o título.

## 4. Ordenação da listagem de demandas por outras colunas (#456)

*Melhoria, não bloqueia: a ordenação por Valor estimado já funciona.*

**Estado atual.** `DemandViewSet.list` só aceita `ordering` em `ORDENACOES_DA_LISTAGEM` (`valor_estimado_total` e o inverso) e responde 400 para qualquer outro valor. Sem o parâmetro, vêm as mais recentes primeiro. A #456 pede ordenação, e a tabela só pode oferecê-la na coluna Valor estimado.

**Pedido:** acrescentar a `ORDENACOES_DA_LISTAGEM` pelo menos:

```python
"criado_em": ("criado_em", "pk"),
"-criado_em": ("-criado_em", "-pk"),
"titulo": ("titulo", "pk"),
"-titulo": ("-titulo", "-pk"),
```

Status fica de fora: o código do status em ordem alfabética não segue o fluxo da demanda, e o filtro de status já atende a quem quer separar por ele.

*Estado atual no frontend:* `OrdenacaoDemandas` em `app/lib/demandas.ts` e o botão de ordenação da coluna Valor em `DemandasTabela.tsx`. Com as ordenações novas, as colunas Título e Criada em ganham o mesmo botão.
