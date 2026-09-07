import { expect, test, type Page } from "@playwright/test";
import {
  criarOrcamentoFixture,
  META_COM_ORCAMENTO,
  META_SEM_ORCAMENTO,
  removerOrcamentoFixture,
  RUBRICA_CRITICA,
  RUBRICA_TRANQUILA,
  type OrcamentoFixture,
} from "./helpers/orcamentoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Painel de Orçamento (§5.3.3) — matriz Meta × Rubrica.
 *
 * Os cinco valores e o semáforo são calculados pelo backend, em
 * `GET /api/v1/sgp/orcamento/painel/`; a tela apenas os apresenta. Estes testes
 * cobrem a apresentação, os filtros e o recorte por perfil — a regra de
 * classificação tem cobertura própria em
 * `backend/apps/sgp/tests/test_budget_painel.py`.
 *
 * ─── Por que os testes criam o orçamento ────────────────────────────────────
 *
 * O `seed_demo` não cria nenhuma `BudgetAllocation`. A fixture monta um cenário
 * determinístico — 85% comprometido em Diárias, 20% em Passagens — que não
 * depende da data em que a suíte roda, ao contrário do semáforo do PT físico.
 * Ver `helpers/orcamentoFixture.ts` para o porquê do ORM cru.
 */

let fixture: OrcamentoFixture;

test.beforeAll(() => {
  fixture = criarOrcamentoFixture();
});

test.afterAll(() => {
  removerOrcamentoFixture();
});

/** Abre a tela e espera a matriz (ou o estado vazio) substituir o skeleton. */
async function abrirPainel(page: Page, query = ""): Promise<void> {
  await page.goto(`/sgp/orcamento/${query}`);
  await expect(page.getByTestId("orcamento-page")).toBeVisible();
  await expect(page.getByTestId("orcamento-skeleton")).toHaveCount(0);
}

/** Linha da matriz para um par Meta × rubrica. */
function linha(page: Page, metaId: number | string, slug: string) {
  return page.getByTestId(`orcamento-linha-${metaId}-${slug}`);
}

/** Id da Meta N — a matriz usa o id, os testes raciocinam sobre o número. */
async function idDaMeta(page: Page, numero: number): Promise<string> {
  const grupo = page
    .locator('[data-testid^="orcamento-meta-"]')
    .filter({ hasText: `Meta ${numero}` })
    .first();
  await expect(grupo).toBeVisible();
  const testid = await grupo.getAttribute("data-testid");
  return testid!.replace("orcamento-meta-", "");
}

test.describe("Painel de Orçamento — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("exibe matriz meta x rubrica", async ({ page }) => {
    await abrirPainel(page);

    const matriz = page.getByTestId("orcamento-matriz");
    await expect(matriz).toBeVisible();

    // As 6 rubricas do §5.3.1, dentro do grupo da Meta que tem orçamento.
    const metaId = await idDaMeta(page, META_COM_ORCAMENTO);
    const grupo = page.getByTestId(`orcamento-meta-${metaId}`);
    await expect(
      grupo.locator('tr[data-testid^="orcamento-linha-"]'),
    ).toHaveCount(6);

    // As cinco colunas de §5.3.3, como cabeçalhos de coluna.
    for (const titulo of [
      "Aprovado",
      "Distribuído",
      "Comprometido",
      "Executado",
      "Disponível",
    ]) {
      await expect(
        matriz.getByRole("columnheader", { name: titulo, exact: true }),
      ).toBeVisible();
    }

    // BRL em pt-BR: 100000.00 → "R$ 100.000,00". O espaço do Intl é NBSP.
    const critica = linha(page, metaId, RUBRICA_CRITICA.slug);
    await expect(critica).toContainText(/R\$\s*100\.000,00/);
    await expect(critica).toContainText(/R\$\s*85\.000,00/);

    // Acessibilidade: <caption> nomeando a tabela e o nível exibido.
    await expect(matriz.locator("caption")).toContainText("Nacional");
  });

  test("semaforo reflete percentual", async ({ page }) => {
    await abrirPainel(page);
    const metaId = await idDaMeta(page, META_COM_ORCAMENTO);

    // 85.000 de 100.000 = 85% ≥ 80% → vermelho.
    const critica = linha(page, metaId, RUBRICA_CRITICA.slug);
    await expect(critica).toHaveAttribute("data-nivel", "vermelho");
    await expect(critica.getByTestId("semaforo-badge")).toHaveAttribute(
      "data-nivel",
      "vermelho",
    );

    // O semáforo não comunica só por cor: o badge carrega texto.
    await expect(critica.getByTestId("semaforo-badge")).toContainText("80%");

    // 10.000 de 50.000 = 20% → verde. Prova que a cor vem do dado.
    const tranquila = linha(page, metaId, RUBRICA_TRANQUILA.slug);
    await expect(tranquila).toHaveAttribute("data-nivel", "verde");
  });

  test("banner de alerta lista vermelhas", async ({ page }) => {
    await abrirPainel(page);
    const metaId = await idDaMeta(page, META_COM_ORCAMENTO);

    const alerta = page.getByTestId("orcamento-alerta");
    await expect(alerta).toBeVisible();
    await expect(alerta).toContainText("Alocações que exigem atenção");

    // A crítica está no banner; a tranquila, não.
    await expect(
      alerta.getByTestId(`orcamento-alerta-item-${metaId}-${RUBRICA_CRITICA.slug}`),
    ).toBeVisible();
    await expect(
      alerta.getByTestId(
        `orcamento-alerta-item-${metaId}-${RUBRICA_TRANQUILA.slug}`,
      ),
    ).toHaveCount(0);

    // Filtrando para a rubrica sem alerta, o banner some por inteiro — ele não
    // é uma caixa permanente que aprende a ser ignorada.
    await abrirPainel(page, `?rubrica=${RUBRICA_TRANQUILA.slug}`);
    await expect(page.getByTestId("orcamento-alerta")).toHaveCount(0);
  });

  test("filtros refletem na URL", async ({ page }) => {
    await abrirPainel(page);

    // O <Select> do design system é um combobox custom: abre com clique no
    // trigger e escolhe numa <li role="option">, como nas demais specs.
    await page.locator("#orcamento-filtro-rubrica").click();
    await page
      .locator('li[role="option"]')
      .filter({ hasText: new RegExp(`^${RUBRICA_CRITICA.nome}$`) })
      .click();

    await page.waitForURL(new RegExp(`rubrica=${RUBRICA_CRITICA.slug}`));

    const metaId = await idDaMeta(page, META_COM_ORCAMENTO);
    const grupo = page.getByTestId(`orcamento-meta-${metaId}`);
    await expect(
      grupo.locator('tr[data-testid^="orcamento-linha-"]'),
    ).toHaveCount(1);

    // Recarregar preserva o recorte: a URL é o estado, não uma cópia dele.
    await page.reload();
    await expect(page.getByTestId("orcamento-skeleton")).toHaveCount(0);
    await expect(page).toHaveURL(new RegExp(`rubrica=${RUBRICA_CRITICA.slug}`));
    await expect(
      page
        .getByTestId(`orcamento-meta-${metaId}`)
        .locator('tr[data-testid^="orcamento-linha-"]'),
    ).toHaveCount(1);

    // Limpar devolve as 6 rubricas e some com a query string.
    await page.getByTestId("orcamento-limpar-filtros").click();
    await expect(page).not.toHaveURL(/rubrica=/);
    await expect(
      page
        .getByTestId(`orcamento-meta-${metaId}`)
        .locator('tr[data-testid^="orcamento-linha-"]'),
    ).toHaveCount(6);
  });

  test("drill-down abre slideover", async ({ page }) => {
    await abrirPainel(page);
    const metaId = await idDaMeta(page, META_COM_ORCAMENTO);

    await page
      .getByTestId(`orcamento-detalhar-${metaId}-${RUBRICA_CRITICA.slug}`)
      .click();

    const detalhe = page.getByTestId("orcamento-detalhe");
    await expect(detalhe).toBeVisible();
    await expect(detalhe).toContainText("Detalhamento por nível");

    // A fixture criou uma alocação territorial nesta rubrica: o detalhamento
    // por nível tem de mostrá-la, com o nome do território.
    const niveis = page.getByTestId("orcamento-detalhe-niveis");
    await expect(niveis).toBeVisible();
    await expect(niveis).toContainText(fixture.territorioAdt);
    await expect(niveis).toContainText(/R\$\s*7\.000,00/);
  });

  test("estado vazio", async ({ page }) => {
    // A Meta 2 é deixada sem nenhuma alocação pela fixture. O backend devolve
    // 6 linhas ZERADAS (uma por rubrica ativa), nunca uma lista vazia — o
    // EmptyState é a tela reconhecendo esse caso, e é isto que se testa aqui.
    await abrirPainel(page);
    const idSemOrcamento = await idDaMeta(page, META_SEM_ORCAMENTO);

    await abrirPainel(page, `?meta=${idSemOrcamento}`);

    await expect(page.getByTestId("orcamento-matriz")).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "Nenhum orçamento para este recorte" }),
    ).toBeVisible();
    await expect(page.getByTestId("orcamento-vazio-limpar")).toBeVisible();
  });
});

test.describe("Painel de Orçamento — ADT/ACR", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("adt ve apenas seu territorio", async ({ page }) => {
    await abrirPainel(page);

    // O backend fixa este perfil no nível territorial (`resolver_nivel_painel`).
    await expect(page.getByTestId("orcamento-matriz")).toHaveAttribute(
      "data-nivel-escopo",
      "territorial",
    );
    await expect(page.getByTestId("orcamento-aviso-adt")).toBeVisible();

    // Sem controles de outros níveis — Meta e Rubrica continuam.
    await expect(page.locator("#orcamento-filtro-estado")).toHaveCount(0);
    await expect(page.locator("#orcamento-filtro-territorio")).toHaveCount(0);
    await expect(page.locator("#orcamento-filtro-meta")).toBeVisible();

    const metaId = await idDaMeta(page, META_COM_ORCAMENTO);
    const critica = linha(page, metaId, RUBRICA_CRITICA.slug);

    // Vê os valores do SEU território (7.000), não os nacionais (100.000).
    await expect(critica).toContainText(/R\$\s*7\.000,00/);
    await expect(critica).not.toContainText(/R\$\s*100\.000,00/);
    await expect(page.getByTestId("orcamento-matriz")).not.toContainText(
      /R\$\s*85\.000,00/,
    );

    // 1.400 de 7.000 = 20% → verde, e portanto sem banner de alerta.
    await expect(critica).toHaveAttribute("data-nivel", "verde");
    await expect(page.getByTestId("orcamento-alerta")).toHaveCount(0);

    // Uma URL colada de outro perfil não pode levá-lo a um 403: o filtro de
    // estado é descartado na leitura da query string.
    await abrirPainel(page, "?estado=PE");
    await expect(page.getByTestId("orcamento-matriz")).toHaveAttribute(
      "data-nivel-escopo",
      "territorial",
    );
  });
});
