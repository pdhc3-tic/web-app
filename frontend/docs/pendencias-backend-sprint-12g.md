# Pendências de backend — sprint 12g

*Compilado em 23/11/2026, na branch `frontend/sprint-12g`.*

*Os documentos das sprints anteriores continuam valendo para o que está lá. O item 9 da 12b, o seletor de objeto de abrangência da #405, segue pendente.*

| Item | Issue do front | Depende de | Bloqueia critério de aceite? |
|---|---|---|---|
| 1 | #438 (dotação nacional) | #437 (entidade TED) | Não. A #438 fica aberta só por ele |

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
