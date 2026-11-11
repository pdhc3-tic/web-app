# ADR 001 — Convivência de GOV.BR DS e Tailwind, com Tailwind restrito a layout

**Status:** Proposta
**Data:** 2026-11-10
**Issue:** #397 (AJ-FE-01)
**Refs:** C4; Arquitetura §10.3

## Contexto

A aplicação evoluiu em Tailwind v4, com tokens em `@theme` no `app/globals.css`
e um estilo próprio de componentes em `app/components/ui/*` (Button, Input,
Select, Badge, etc.). A nova fase pede adoção do **GOV.BR Design System**
como camada de componentes oficial do governo federal, mantendo o Tailwind
para o que ele faz bem no projeto hoje: **layout, espaçamento e composição**.

Os dois sistemas entram em conflito por dois motivos:

1. O `preflight` do Tailwind reseta as regras base de todos os elementos
   (`button`, `input`, `h1`…). Isso quebra a aparência nativa dos componentes
   do GOV.BR DS, que depende dessas regras.
2. Vários nomes de classe do Tailwind colidem com classes utilitárias do
   GOV.BR DS (`.container`, `.row`, `.text-primary`, etc.). Sem prefixo, a
   ordem de carregamento decide quem vence e a convivência fica frágil.

O Tailwind v4 oferece duas alavancas que resolvem as duas questões: `prefix`
na diretiva `@import` e a importação separada de tema e utilidades, omitindo `preflight.css`.

## Decisão

1. **Prefixo `tw:` em todas as utilidades do Tailwind.** No topo do
   `app/globals.css`, trocar `@import "tailwindcss";` por:

   ```css
   @import "tailwindcss" prefix(tw);
   ```

   A partir daí, as utilidades passam a se chamar `tw:flex`, `tw:gap-2`,
   `tw:text-sm` etc. O prefixo também muda as variáveis geradas, por exemplo `--spacing` vira `--tw-spacing`.

2. **`preflight` desligado.** No Tailwind v4, `@import "tailwindcss" prefix(tw);`
   equivale a importar `theme.css`, `preflight.css` e `utilities.css`. Para
   desligar o reset base (`preflight`) mantendo o prefixo `tw:`, importa-se
   apenas o tema e as utilidades sem `preflight.css`:

   ```css
   @layer theme, base, components, utilities;
   @import "tailwindcss/theme.css" layer(theme) prefix(tw);
   @import "tailwindcss/utilities.css" layer(utilities) prefix(tw);
   ```

   Sem `preflight`, o GOV.BR DS mantém `button`, `input`, `h1…h6` com o
   estilo oficial.

3. **Divisão de responsabilidade por camada:**
   - **GOV.BR DS**: componentes (`.br-button`, `.br-input`, `.br-card`,
     `.br-table`, cabeçalho, rodapé, mensagens, selos, chips…). Qualquer
     coisa com semântica visual de "esse é o botão do governo" é GOV.BR DS.
   - **Tailwind (`tw:`)**: só **layout**: grid, flex, gap, padding externo,
     posicionamento, largura/altura, visibilidade responsiva. Nada que o
     GOV.BR DS já resolva no componente.
   - **CSS vars em `@theme`**: ponte entre os dois. As vars de paleta do
     projeto passam a ter o prefixo (`--tw-color-primary`, etc.) e servem as classes `tw:*`
     e também podem ser consumidas por overrides pontuais em componentes
     próprios. Nenhuma cor é hardcoded em componente.

   Exemplo:

   ```tsx
   <section className="tw:grid tw:gap-4 tw:p-6">
     <button className="br-button primary">Autorizar</button>
   </section>
   ```

4. **Códigos existentes migram por codemod.** Um script
   `frontend/scripts/codemod-tw-prefix.mjs` lê todos os `.tsx`/`.ts` do
   `app/`, identifica atributos `className`/`class` e insere `tw:` em cada
   token que for utilidade Tailwind conhecida. Classes que não são do
   Tailwind (ex.: `text-primary` quando usada como classe semântica de
   componente próprio) são ignoradas por uma lista de exceção explícita.

   O codemod roda **uma vez**, entregue num PR dedicado, com diff grande
   mas mecânico. A revisão foca na lista de exceções, não na massa de
   substituições.

5. **Ordem de migração por tela.** Cada tela migra de forma independente,
   substituindo componentes próprios por GOV.BR DS **um por vez**, sem
   pressa. A ordem evita telas quentes do negócio no início:

   | Lote | Telas | Estimativa |
   |------|-------|------------|
   | 1 (piloto) | `/styleguide/govbr-spike`, `/esqueci-minha-senha`, `/redefinir-senha` | 2 pts |
   | 2 | `/login`, `/dashboard`, cabeçalho e menu | 3 pts |
   | 3 | SGP: `/sgp/upfs`, `/sgp/atividades`, `/sgp/metas` (telas de leitura e busca primeiro) | 5 pts |
   | 4 | SGP: formulários de edição (UPF, Atividade, Membros) | 5 pts |
   | 5 | SGD: `/sgd/demandas` (listagem + master-detail), `/sgd/execucao` | 5 pts |
   | 6 | SGD: montagem de demanda, configurações, Arlo | 5 pts |
   | 7 | SCA, administração, integrações | 3 pts |

   Total estimado: **28 pts**, idealmente spread em 3 sprints. O lote 1 é
   o alvo desta issue (ADR + spike).

## Validação (spike)

O spike entra em `frontend/app/styleguide/govbr-spike/page.tsx`. Objetivo:
provar que GOV.BR DS e Tailwind prefixado convivem na mesma página, **sem
modificar nada das outras telas**. A página demonstra os componentes e o layout em um iframe. O documento não herda o preflight nem os estilos da aplicação. O CSS do GOV.BR DS fica dentro do iframe.

O arquivo `app/styleguide/govbr-spike/govbr-spike.css` importa somente o tema e as utilidades do Tailwind com `prefix(tw)`. O comando `npm run build:govbr-spike`, também executado antes de `dev` e `build`, compila o CSS em `public/govbr-spike.css`.

- Componentes usam `br-button`, `br-input` e `br-message`.
- O layout usa `tw:grid`, `tw:gap-4`, `tw:p-6` e `tw:sm:grid-cols-2`.
- O CSS compilado pode ser regenerado com a versão instalada do Tailwind.

Após o merge desta ADR, o próximo PR ativa o prefixo no `globals.css` global,
roda o codemod e migra o lote 1 da tabela acima.

## Consequências

**Positivas**
- Alinhamento com a política de design do governo federal.
- Classes do Tailwind imediatamente reconhecíveis (`tw:`), facilitando code
  review e separando o que é "layout" do que é "componente".
- Base para auditoria de acessibilidade padrão GOV.BR DS.

**Negativas**
- Diff gigantesco no PR do codemod (toda ocorrência de `className`). Mitiga
  revisando pela lista de exceções e pela amostragem de 5-10 telas antes de
  mergear.
- Tempo de familiarização do time com nomes `br-*`.
- Dupla fonte de componentes em transição: `app/components/ui/*` continua
  servindo o que ainda não migrou. A lista de equivalências entra em outro
  ADR por lote.

## Codemod — especificação técnica

Entrada: lista de utilidades Tailwind geradas por `tailwindcss` (via
`--content ./app/**/*.{ts,tsx}` + `--list-utilities`, ou extraindo do CSS
compilado).

Para cada arquivo `.ts`/`.tsx`, para cada atributo `className`,
`class`, `clsx(...)`, `cn(...)`, template literal com `className`:

1. Partir pelo espaço o conteúdo de string literal.
2. Para cada token, se for utilidade Tailwind conhecida, substituir por
   `tw:<token>`. O prefixo vem antes das variantes (`sm:flex` → `tw:sm:flex`), e `!important` fica no fim (`!bg-primary` → `tw:bg-primary!`).
3. Se o token estiver na **lista de exceções** (classes semânticas próprias,
   ex.: `btn-perigo`, `text-link`), não prefixar.
4. Expressões condicionais do clsx preservam a estrutura (`clsx(ativo && "tw:text-primary")`).

Um `--dry-run` imprime o diff proposto. A versão final roda `prettier` depois
para normalizar quebras de linha.

## Pontos abertos

1. A sintaxe foi conferida no compilador instalado. Validar visualmente o spike e as telas de referência em navegador antes de migrar as demais telas.
2. Lista completa de exceções (classes semânticas que parecem Tailwind mas
   não são). Primeira passada do codemod imprime uma lista "parece Tailwind,
   confirme" para revisão.
3. Se o `shadcn/ui` (ou similar) entrar no futuro, decidir se ele recebe o
   mesmo prefixo (é o que o shadcn espera, basta configurar).

## Referências

- Tailwind v4: https://tailwindcss.com/docs/v4-beta
- GOV.BR DS: https://www.gov.br/ds/
- Arquitetura do projeto, §10.3 (camadas visuais)
