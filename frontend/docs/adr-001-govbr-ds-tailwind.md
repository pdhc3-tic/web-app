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
   GOV.BR DS. No core 3.7.0, por exemplo, `.container`, `.hidden`, `.mt-4`,
   `.p-3` e `.text-center` existem nos dois. Sem prefixo, a ordem de
   carregamento decide quem vence e a convivência fica frágil.

O Tailwind v4 oferece duas alavancas que resolvem as duas questões: `prefix`
na diretiva `@import` e a importação separada de tema e utilidades, omitindo `preflight.css`.

## Decisão

1. **Prefixo `tw:` em todas as utilidades do Tailwind.** A issue fala em
   prefixo `tw-`, que é a forma do Tailwind v3. No v4 o prefixo se declara
   com `prefix(tw)` no `@import` e vira uma variante: as utilidades passam a
   se chamar `tw:flex`, `tw:gap-2`, `tw:text-sm` etc. O prefixo também muda
   as variáveis geradas pelo `@theme`: `--spacing` vira `--tw-spacing` e
   `--color-primary` vira `--tw-color-primary`. A forma final do import está
   no item 2.

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
   | 3 | SGP: `/sgp/ufpas`, `/sgp/atividades`, `/sgp/metas` (telas de leitura e busca primeiro) | 5 pts |
   | 4 | SGP: formulários de edição (UFPA, Atividade, Membros) | 5 pts |
   | 5 | SGD: `/sgd/demandas` (listagem + master-detail), `/sgd/execucao` | 5 pts |
   | 6 | SGD: montagem de demanda, configurações, Arlo | 5 pts |
   | 7 | SCA, administração, integrações | 3 pts |

   Total estimado: **28 pts**, distribuídos em cerca de 3 sprints. Esta
   issue entrega só a ADR e o spike; o lote 1 começa no PR seguinte, junto
   com o codemod.

## Validação (spike)

O spike fica em `frontend/app/styleguide/govbr-spike/page.tsx`, só em
desenvolvimento. A página monta um iframe com um documento próprio
(`documento.ts`), que carrega as folhas na ordem do guia do GOV.BR DS 3.x:
fonte Rawline, Font Awesome 5, `@govbr-ds/core@3.7.0` e, por último, o
Tailwind prefixado. A série 4 do GOV.BR DS ainda não tem versão estável
(só `4.0.0-next`), por isso a 3.7.0.

O arquivo `app/styleguide/govbr-spike/govbr-spike.css` importa só o tema e
as utilidades do Tailwind, com `prefix(tw)` e sem `preflight`, e lê as
classes do próprio `documento.ts` (`@source`). O comando
`npm run build:govbr-spike` compila esse CSS em `public/govbr-spike.css`,
que fica versionado. O teste `govbr-spike-css.test.ts` recompila e acusa
quando o arquivo publicado fica desatualizado. O build da aplicação não
depende desse passo.

- Componentes usam `br-button` (com ícone), `br-input` e `br-message`.
- O layout usa `tw:grid`, `tw:gap-4`, `tw:p-6` e `tw:sm:grid-cols-2`.

**O que o spike prova e o que ele não prova.** Ele prova a configuração de
destino: GOV.BR DS com o Tailwind só de tema e utilidades, prefixado e sem
`preflight`, sem colisão de classes. Como roda isolado no iframe, as demais
telas não mudam, e não há regressão nelas. Ele **não** exercita a transição
no app: tirar o `preflight` do `globals.css` e renomear os tokens afeta
todas as telas ao mesmo tempo. Essa validação é o critério de aceite do PR
do lote 1: comparar capturas de tela das rotas de referência (login,
dashboard, uma listagem e um formulário de cada sistema) antes e depois do
codemod.

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

**Como saber se um token é utilidade.** O Tailwind v4 não tem mais
`--content` nem uma listagem de utilidades no CLI, e o projeto usa só o
plugin do PostCSS (`@tailwindcss/postcss`). O codemod usa o mesmo motor: o
pacote `tailwindcss` compila o `app/globals.css` atual (com o `@theme` do
projeto) e, para cada token candidato, verifica se ele gera CSS. Token que
gera CSS é utilidade; o resto (classes do GOV.BR DS, classes próprias,
`data-*`) fica como está. Assim a decisão segue o tema real do projeto, e
não uma lista mantida à mão.

**Classes.** Para cada `.ts`/`.tsx` de `app/`, o codemod lê as strings de
`className`, inclusive template literals, ternários e os mapas de variantes
dos componentes de `app/components/ui/*`:

1. Partir pelo espaço o conteúdo de cada string literal.
2. Se o token for utilidade, trocar por `tw:<token>`. O prefixo vem antes
   das variantes (`sm:flex` → `tw:sm:flex`) e o `!important` fica no fim
   (`!bg-primary` → `tw:bg-primary!`). Valores arbitrários também entram
   (`h-[1100px]` → `tw:h-[1100px]`).
3. Se o token estiver na **lista de exceções**, não prefixar.

**Variáveis CSS.** Com o prefixo, os tokens do `@theme` passam a se chamar
`--tw-*`. Em 11/2026 havia 47 usos de `var(--color-…)`, `var(--spacing…)`,
`var(--radius…)` e afins fora do `globals.css`, em estilos inline e em CSS
próprio, além das redefinições do modo escuro no próprio `globals.css`.
O codemod troca `var(--<namespace>-…)` por `var(--tw-<namespace>-…)` nos
`.ts`, `.tsx` e `.css` do `app/`, para os namespaces do tema, e o modo
escuro passa a redefinir os nomes prefixados. Sem isso, cores e espaçamentos
dessas telas somem silenciosamente.

**Testes.** Testes de componente e E2E que procuram classes pelo nome
(`toHaveClass`, seletores `.flex` etc.) entram na mesma passada.

Um `--dry-run` imprime o diff proposto. A versão final roda `prettier` depois
para normalizar quebras de linha.

## Pontos abertos

1. A sintaxe foi conferida no compilador instalado (Tailwind 4.2.4) e o
   spike, no navegador. Falta a comparação visual das telas de referência,
   que é critério do PR do lote 1 (ver "Validação").
2. Lista completa de exceções (classes semânticas que parecem Tailwind mas
   não são). Primeira passada do codemod imprime uma lista "parece Tailwind,
   confirme" para revisão.
3. Se o `shadcn/ui` (ou similar) entrar no futuro, decidir se ele recebe o
   mesmo prefixo (é o que o shadcn espera, basta configurar).

## Referências

- Tailwind v4, prefixo: https://tailwindcss.com/docs/styling-with-utility-classes#using-the-prefix-option
- Tailwind v4, preflight: https://tailwindcss.com/docs/preflight
- GOV.BR DS: https://www.gov.br/ds/
- Arquitetura do projeto, §10.3 (camadas visuais)
