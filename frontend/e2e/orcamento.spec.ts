import { expect, test, type Page } from "@playwright/test";
import {
  criarOrcamentoFixture,
  ESTADO_DRILL,
  removerOrcamentoFixture,
  RUBRICA_CRITICA,
  RUBRICA_SEM_POOL,
  RUBRICA_TRANQUILA,
  type OrcamentoFixture,
} from "./helpers/orcamentoFixture";
import { storageStatePath } from "./helpers/users";

/**
 * Painel de Orçamento (§5.3.3) — matriz Rubrica × Nível do orçamento por pool
 * (#398), contra o backend real.
 *
 * Os valores e o semáforo vêm prontos de `GET /api/v1/sgp/orcamento/painel/`;
 * a tela os agrupa por rubrica, em árvore (Nacional → estado → território).
 * A fixture ajusta quatro pools com valores determinísticos e restaura o
 * orçamento no fim (ver `helpers/orcamentoFixture.ts`).
 */

let fx: OrcamentoFixture;

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fx = criarOrcamentoFixture();
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

const linha = (page: Page, poolId: number) => page.getByTestId(`orcamento-linha-${poolId}`);

test.describe("Painel de Orçamento — UGP", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("exibe a matriz rubrica x nivel em arvore", async ({ page }) => {
    await abrirPainel(page);
    const matriz = page.getByTestId("orcamento-matriz");
    await expect(matriz).toBeVisible();

    for (const titulo of ["Aprovado", "Distribuído", "Comprometido", "Executado", "Disponível"]) {
      await expect(matriz.getByRole("columnheader", { name: titulo, exact: true })).toBeVisible();
    }

    // Um bloco por rubrica: Diárias tem o nacional e o território do ADT.
    const diarias = page.getByTestId(`orcamento-rubrica-${RUBRICA_CRITICA.slug}`);
    await expect(diarias).toContainText(RUBRICA_CRITICA.nome);
    await expect(diarias.getByTestId(`orcamento-linha-${fx.pools.diariasNacional}`)).toHaveAttribute(
      "data-nivel-pool",
      "nacional",
    );
    await expect(linha(page, fx.pools.diariasNacional)).toContainText(/R\$\s*100\.000,00/);
    await expect(linha(page, fx.pools.diariasNacional)).toContainText(/R\$\s*95\.000,00/);
    await expect(linha(page, fx.pools.diariasTerritorio)).toContainText(fx.territorioAdt);

    // Passagens: o nacional acima do estado de PE, que vem antes dos territórios.
    const passagens = page.getByTestId(`orcamento-rubrica-${RUBRICA_TRANQUILA.slug}`);
    const ordem = await passagens
      .locator('tr[data-testid^="orcamento-linha-"]')
      .evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")));
    expect(ordem.indexOf(`orcamento-linha-${fx.pools.passagensNacional}`)).toBe(0);
    expect(ordem).toContain(`orcamento-linha-${fx.pools.passagensPE}`);
  });

  test("semaforo reflete o percentual com os limiares da API", async ({ page }) => {
    await abrirPainel(page);
    // 95.000 de 100.000 = 95% ≥ 90% → vermelho.
    const critica = linha(page, fx.pools.diariasNacional);
    await expect(critica).toHaveAttribute("data-nivel", "vermelho");
    await expect(critica.getByTestId("semaforo-badge")).toContainText("90%");
    // 10.000 de 50.000 = 20% → verde.
    await expect(linha(page, fx.pools.passagensNacional)).toHaveAttribute("data-nivel", "verde");
  });

  test("banner de alerta lista os pools vermelhos", async ({ page }) => {
    await abrirPainel(page);
    const alerta = page.getByTestId("orcamento-alerta");
    await expect(alerta).toContainText("Pools que exigem atenção");
    await expect(alerta.getByTestId(`orcamento-alerta-item-${fx.pools.diariasNacional}`)).toContainText("Nacional");
    await expect(alerta.getByTestId(`orcamento-alerta-item-${fx.pools.passagensNacional}`)).toHaveCount(0);

    // Filtrando para a rubrica sem alerta, o banner some por inteiro.
    await abrirPainel(page, `?rubrica=${RUBRICA_TRANQUILA.slug}`);
    await expect(page.getByTestId("orcamento-alerta")).toHaveCount(0);
  });

  test("filtro de rubrica fica na URL e sobrevive ao recarregar", async ({ page }) => {
    await abrirPainel(page);
    await page.locator("#orcamento-filtro-rubrica").click();
    await page
      .locator('li[role="option"]')
      .filter({ hasText: new RegExp(`^${RUBRICA_CRITICA.nome}$`) })
      .click();
    await page.waitForURL(new RegExp(`rubrica=${RUBRICA_CRITICA.slug}`));
    await expect(page.locator('tbody[data-testid^="orcamento-rubrica-"]')).toHaveCount(1);

    await page.reload();
    await expect(page.getByTestId("orcamento-skeleton")).toHaveCount(0);
    await expect(page.locator('tbody[data-testid^="orcamento-rubrica-"]')).toHaveCount(1);

    await page.getByTestId("orcamento-limpar-filtros").click();
    await expect(page).not.toHaveURL(/rubrica=/);
    await expect(page.getByTestId(`orcamento-rubrica-${RUBRICA_TRANQUILA.slug}`)).toBeVisible();
  });

  test("filtro de estado desce ao pool do estado e aos territorios dele", async ({ page }) => {
    await abrirPainel(page, `?estado=${ESTADO_DRILL.sigla}`);
    await expect(page.getByTestId("orcamento-aviso-nivel")).toBeVisible();
    await expect(linha(page, fx.pools.passagensPE)).toContainText(/R\$\s*12\.000,00/);
    // O nacional sai do recorte.
    await expect(linha(page, fx.pools.passagensNacional)).toHaveCount(0);
  });

  test("Meta e so relatorio: a coluna passa a ser o executado na Meta", async ({ page }) => {
    await abrirPainel(page, `?meta=${fx.metaId}`);
    await expect(page.getByTestId("orcamento-aviso-meta")).toBeVisible();
    const matriz = page.getByTestId("orcamento-matriz");
    await expect(matriz.getByRole("columnheader", { name: "Executado na Meta" })).toBeVisible();
    // O saldo continua o do pool: aprovado e comprometido não mudam com a Meta.
    await expect(linha(page, fx.pools.diariasNacional)).toContainText(/R\$\s*100\.000,00/);
    await expect(linha(page, fx.pools.diariasNacional)).toContainText(/R\$\s*95\.000,00/);
  });

  test("detalhar abre o pool com as movimentacoes", async ({ page }) => {
    await abrirPainel(page);
    await page.getByTestId(`orcamento-detalhar-${fx.pools.diariasTerritorio}`).click();
    const detalhe = page.getByTestId("orcamento-detalhe");
    await expect(detalhe).toBeVisible();
    await expect(detalhe).toContainText(/R\$\s*7\.000,00/);
    await expect(detalhe).toContainText("Movimentações");
  });

  test("estado vazio para um recorte sem pool", async ({ page }) => {
    await abrirPainel(page, `?rubrica=${RUBRICA_SEM_POOL.slug}`);
    await expect(page.getByTestId("orcamento-matriz")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Nenhum orçamento para este recorte" })).toBeVisible();
    await expect(page.getByTestId("orcamento-vazio-limpar")).toBeVisible();
  });
});

test.describe("Painel de Orçamento — ADT/ACR", () => {
  test.use({ storageState: storageStatePath("semPermissao") });

  test("adt ve apenas o pool do seu territorio", async ({ page }) => {
    await abrirPainel(page);
    await expect(page.getByTestId("orcamento-aviso-adt")).toBeVisible();
    await expect(page.locator("#orcamento-filtro-estado")).toHaveCount(0);
    await expect(page.locator("#orcamento-filtro-territorio")).toHaveCount(0);

    const territorio = linha(page, fx.pools.diariasTerritorio);
    await expect(territorio).toContainText(/R\$\s*7\.000,00/);
    await expect(linha(page, fx.pools.diariasNacional)).toHaveCount(0);
    await expect(page.getByTestId("orcamento-matriz")).not.toContainText(/R\$\s*95\.000,00/);
    // 1.400 de 7.000 = 20% → verde, sem banner.
    await expect(territorio).toHaveAttribute("data-nivel", "verde");
    await expect(page.getByTestId("orcamento-alerta")).toHaveCount(0);

    // Uma URL colada de outro perfil não o leva a um 403: o estado é descartado na leitura.
    await abrirPainel(page, "?estado=PE");
    await expect(linha(page, fx.pools.diariasTerritorio)).toBeVisible();
  });
});
